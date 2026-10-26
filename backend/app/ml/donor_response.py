from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from functools import lru_cache
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from xgboost import Booster, DMatrix

if TYPE_CHECKING:
    import pandas as pd

# The served API deliberately avoids pandas and scikit-learn: a Vercel Python
# function must stay under 500 MB installed, and both are needed only for
# training (requirements-dev.txt). Inference uses a NumPy matrix and the raw
# XGBoost Booster, which gives the same probabilities as XGBClassifier for
# this binary:logistic model saved without early stopping.


FEATURES = (
    "age",
    "days_since_last_donation",
    "donations_count",
    "response_rate",
    "notifications_30d",
    "days_since_last_contact",
    "month",
    "is_festival_season",
    "previous_requests",
    "previous_responses",
    "is_urgent",
)
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "donor_response_xgb.json"
METADATA_PATH = MODEL_DIR / "donor_response_metrics.json"


def build_features(**kwargs) -> pd.DataFrame:
    """One feature row as a DataFrame, for training code and tests."""
    import pandas as pd

    return pd.DataFrame([feature_row(**kwargs)], columns=FEATURES)


def feature_row(
    *,
    age: int,
    days_since_last_donation: int,
    donations_count: int,
    response_rate: float,
    notifications_30d: int,
    days_since_last_contact: int | None,
    reference_date: date | None = None,
    previous_requests: int | None = None,
    previous_responses: int | None = None,
    is_urgent: int = 0,
) -> dict:
    day = reference_date or date.today()
    contact_age = 365 if days_since_last_contact is None else days_since_last_contact
    # DRPS spec: previous request/response counts default to the 30-day
    # contact counters when per-request history is unavailable (live ranking
    # has no current request yet, so history == lifetime totals).
    if previous_requests is None:
        previous_requests = notifications_30d
    if previous_responses is None:
        previous_responses = min(int(previous_requests), int(round(response_rate * previous_requests)))
    return {
        "age": age,
        "days_since_last_donation": days_since_last_donation,
        "donations_count": donations_count,
        "response_rate": response_rate,
        "notifications_30d": notifications_30d,
        "days_since_last_contact": contact_age,
        "month": day.month,
        "is_festival_season": int(day.month in (1, 8, 10, 11)),
        "previous_requests": int(previous_requests),
        "previous_responses": int(previous_responses),
        "is_urgent": int(is_urgent),
    }


@lru_cache(maxsize=1)
def load_model() -> Booster | None:
    if not MODEL_PATH.exists():
        return None
    return Booster(model_file=str(MODEL_PATH))


Rows = Sequence[Mapping[str, Any]]


def _as_rows(features: Rows | pd.DataFrame) -> list[Mapping[str, Any]]:
    to_dict = getattr(features, "to_dict", None)
    return to_dict("records") if callable(to_dict) else list(features)


def predict_response(
    features: Rows | pd.DataFrame,
) -> tuple[float, str] | None:
    predictions = predict_responses(features)
    return None if predictions is None else predictions[0]


def predict_responses(
    features: Rows | pd.DataFrame,
) -> list[tuple[float, str]] | None:
    """Score every row of `features` with one model call and one TreeSHAP
    call. Per-row calls cost ~8 ms each, which made ranking a district with
    1,000 donors take seconds; batching keeps it to a few milliseconds."""
    booster = load_model()
    if booster is None:
        return None
    rows = _as_rows(features)
    if not rows:
        return []

    expected = list(booster.feature_names) if booster.feature_names else list(FEATURES)
    matrix = DMatrix(
        np.array([[float(row[name]) for name in expected] for row in rows], dtype=np.float32),
        feature_names=expected,
    )
    probabilities = booster.predict(matrix)
    contributions = booster.predict(matrix, pred_contribs=True)[:, :-1]
    names = expected[: contributions.shape[1]]
    results = []
    for row, probability in enumerate(probabilities):
        strongest = sorted(zip(names, contributions[row]), key=lambda pair: abs(float(pair[1])), reverse=True)[:2]
        reasons = [_feature_reason(name, float(value), rows[row][name]) for name, value in strongest]
        results.append((round(float(probability), 3), "Model factors: " + "; ".join(reasons) + "."))
    return results


def _feature_reason(name: str, contribution: float, value: object) -> str:
    direction = "increases" if contribution >= 0 else "reduces"
    descriptions = {
        "age": f"age ({int(value)} years) {direction} predicted response",
        "days_since_last_donation": f"donation recency ({int(value)} days) {direction} predicted response",
        "donations_count": f"prior donation count ({int(value)}) {direction} predicted response",
        "response_rate": f"past response rate ({float(value):.0%}) {direction} predicted response",
        "notifications_30d": f"recent contact count ({int(value)}) {direction} predicted response",
        "days_since_last_contact": f"contact recency ({int(value)} days) {direction} predicted response",
        "month": f"seasonal month ({int(value)}) {direction} predicted response",
        "is_festival_season": f"festival-season timing {direction} predicted response",
        "previous_requests": f"previous request count ({int(value)}) {direction} predicted response",
        "previous_responses": f"previous response count ({int(value)}) {direction} predicted response",
        "is_urgent": f"urgent request reason {direction} predicted response",
    }
    return descriptions[name]


def model_status() -> dict:
    if not MODEL_PATH.exists():
        return {"available": False, "kind": "rule-based-fallback", "metrics": None}
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8")) if METADATA_PATH.exists() else {}
    try:
        from app.services.scoring import load_calibrated_weights
        calibration = load_calibrated_weights()
        weights = (
            {"shortage": calibration.shortage, "response": calibration.response,
             "fatigue_adjusted_priority": calibration.fatigue_adjusted_priority}
            if calibration else None
        )
    except Exception:
        weights = None
    return {
        "available": True,
        "kind": "xgboost-classifier",
        "metrics": metadata,
        "features": list(metadata.get("features", list(FEATURES))),
        "cbsri_calibrated_weights": weights,
    }