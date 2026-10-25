from __future__ import annotations

from datetime import date
from functools import lru_cache
import json
from pathlib import Path

import pandas as pd
from xgboost import DMatrix, XGBClassifier


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
def load_model() -> XGBClassifier | None:
    if not MODEL_PATH.exists():
        return None
    model = XGBClassifier()
    model.load_model(MODEL_PATH)
    return model


def predict_response(
    features: pd.DataFrame,
) -> tuple[float, str] | None:
    predictions = predict_responses(features)
    return None if predictions is None else predictions[0]


def predict_responses(
    features: pd.DataFrame,
) -> list[tuple[float, str]] | None:
    """Score every row of `features` with one model call and one TreeSHAP
    call. Per-row calls cost ~8 ms each, which made ranking a district with
    1,000 donors take seconds; batching keeps it to a few milliseconds."""
    model = load_model()
    if model is None:
        return None
    if features.empty:
        return []

    booster_names = model.get_booster().feature_names
    expected = list(booster_names) if booster_names else list(FEATURES)
    frame = features.loc[:, [c for c in expected if c in features.columns]]
    probabilities = model.predict_proba(frame)[:, 1]
    contributions = model.get_booster().predict(
        DMatrix(frame, feature_names=expected), pred_contribs=True
    )[:, :-1]
    names = expected[: contributions.shape[1]]
    rows = features.to_dict("records")
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