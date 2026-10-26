from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path


CALIBRATED_WEIGHTS_PATH = Path(__file__).resolve().parents[2] / "models" / "cbsri_weights.json"


@dataclass(frozen=True)
class CBSRIWeights:
    shortage: float = 0.45
    response: float = 0.30
    fatigue_adjusted_priority: float = 0.25

    def __post_init__(self) -> None:
        values = (self.shortage, self.response, self.fatigue_adjusted_priority)
        if any(value < 0 for value in values) or sum(values) <= 0:
            raise ValueError("CBSRI weights must be non-negative with a positive total")

    def normalized(self) -> tuple[float, float, float]:
        total = self.shortage + self.response + self.fatigue_adjusted_priority
        return (self.shortage / total, self.response / total, self.fatigue_adjusted_priority / total)


def fatigue_multiplier(notifications_30d: int, days_since_contact: int | None) -> float:
    """Return a transparent contact-fatigue discount between 0.15 and 1.0."""
    if notifications_30d < 0:
        raise ValueError("notifications_30d cannot be negative")
    contact_load = max(0.15, 1.0 - 0.22 * notifications_30d)
    recency = 1.0 if days_since_contact is None else min(1.0, max(0.25, days_since_contact / 30))
    return round(contact_load * recency, 4)


def donor_priority(response_probability: float, notifications_30d: int, days_since_contact: int | None) -> float:
    if not 0 <= response_probability <= 1:
        raise ValueError("response_probability must be between 0 and 1")
    return round(response_probability * fatigue_multiplier(notifications_30d, days_since_contact) * 100, 2)


def compute_cbsri(
    shortage_score: float,
    donor_response_score: float,
    fatigue_adjusted_priority_score: float,
    weights: CBSRIWeights = CBSRIWeights(),
) -> float:
    scores = (shortage_score, donor_response_score, fatigue_adjusted_priority_score)
    if any(not 0 <= score <= 100 for score in scores):
        raise ValueError("CBSRI component scores must be between 0 and 100")
    shortage_weight, response_weight, priority_weight = weights.normalized()
    return round(
        shortage_score * shortage_weight
        + donor_response_score * response_weight
        + fatigue_adjusted_priority_score * priority_weight,
        2,
    )


def risk_label(score: float) -> str:
    if score >= 70:
        return "critical"
    if score >= 45:
        return "elevated"
    return "stable"


@lru_cache(maxsize=1)
def load_calibrated_weights() -> CBSRIWeights | None:
    """Return correlation-calibrated CBSRI weights, or None when unavailable.

    Calibration artifact: models/cbsri_weights.json, produced by
    app.ml.reference_training.calibrate_cbsri_weights from the linked
    reference tables. Weights are proportional to |correlation| of each
    component with historical shortage/response events. Pilot defaults
    (0.45/0.30/0.25) apply when the file is missing or invalid.
    """
    if not CALIBRATED_WEIGHTS_PATH.exists():
        return None
    try:
        payload = json.loads(CALIBRATED_WEIGHTS_PATH.read_text(encoding="utf-8"))
        weights = payload.get("weights", {})
        return CBSRIWeights(
            shortage=float(weights["shortage"]),
            response=float(weights["response"]),
            fatigue_adjusted_priority=float(weights["fatigue_adjusted_priority"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def active_weights() -> CBSRIWeights:
    """Calibrated weights when present, else transparent pilot defaults."""
    return load_calibrated_weights() or CBSRIWeights()
