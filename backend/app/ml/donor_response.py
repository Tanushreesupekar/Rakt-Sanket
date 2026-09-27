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
)
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "donor_response_xgb.json"
METADATA_PATH = MODEL_DIR / "donor_response_metrics.json"


def build_features(
    *,
    age: int,
    days_since_last_donation: int,
    donations_count: int,
    response_rate: float,
    notifications_30d: int,
    days_since_last_contact: int | None,
    reference_date: date | None = None,
) -> pd.DataFrame:
    day = reference_date or date.today()
    contact_age = 365 if days_since_last_contact is None else days_since_last_contact
    return pd.DataFrame([{
        "age": age,
        "days_since_last_donation": days_since_last_donation,
        "donations_count": donations_count,
        "response_rate": response_rate,
        "notifications_30d": notifications_30d,
        "days_since_last_contact": contact_age,
        "month": day.month,
        "is_festival_season": int(day.month in (1, 8, 10, 11)),
    }], columns=FEATURES)


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
    model = load_model()
    if model is None:
        return None

    probability = float(model.predict_proba(features.loc[:, FEATURES])[0, 1])
    contributions = model.get_booster().predict(
        DMatrix(features.loc[:, FEATURES], feature_names=list(FEATURES)), pred_contribs=True
    )[0][:-1]
    strongest = sorted(zip(FEATURES, contributions), key=lambda pair: abs(float(pair[1])), reverse=True)[:2]
    reasons = [_feature_reason(name, float(value), features.iloc[0][name]) for name, value in strongest]
    return round(probability, 3), "Model factors: " + "; ".join(reasons) + "."


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
    }
    return descriptions[name]


def model_status() -> dict:
    if not MODEL_PATH.exists():
        return {"available": False, "kind": "rule-based-fallback", "metrics": None}
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8")) if METADATA_PATH.exists() else {}
    return {"available": True, "kind": "xgboost-classifier", "metrics": metadata}