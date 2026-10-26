from collections.abc import Sequence
from datetime import date, datetime, timezone

import pandas as pd

from app.ml.donor_response import FEATURES, feature_row, predict_responses
from app.models import Donor
from app.services.scoring import donor_priority


def rank_donor(donor: Donor) -> dict:
    return rank_donors([donor])[0]


def rank_donors(donors: Sequence[Donor]) -> list[dict]:
    """Rank donors with a single batched model call (same results as ranking
    each donor on its own, in the same order as `donors`)."""
    if not donors:
        return []
    today = date.today()
    now = datetime.now(timezone.utc)
    timing = []
    rows = []
    for donor in donors:
        days_since_donation = (today - donor.last_donation_date).days if donor.last_donation_date else 365
        days_since_contact = None
        if donor.last_contact_at:
            contact = donor.last_contact_at
            if contact.tzinfo is None:
                contact = contact.replace(tzinfo=timezone.utc)
            days_since_contact = max(0, (now - contact).days)
        timing.append((days_since_donation, days_since_contact))
        rows.append(feature_row(
            age=donor.age,
            days_since_last_donation=days_since_donation,
            donations_count=donor.donations_count,
            response_rate=donor.response_rate,
            notifications_30d=donor.notifications_30d,
            days_since_last_contact=days_since_contact,
            reference_date=today,
        ))
    predictions = predict_responses(pd.DataFrame(rows, columns=FEATURES))
    return [
        _ranking(donor, days_since_donation, days_since_contact, None if predictions is None else predictions[index])
        for index, (donor, (days_since_donation, days_since_contact)) in enumerate(zip(donors, timing))
    ]


def _ranking(donor: Donor, days_since_donation: int, days_since_contact: int | None, model_prediction: tuple[float, str] | None) -> dict:
    eligible = donor.available and days_since_donation >= 90
    if model_prediction is None:
        recency_signal = min(1.0, max(0.0, days_since_donation / 180))
        frequency_signal = min(1.0, donor.donations_count / 8)
        response_probability = min(
            0.98,
            max(0.05, donor.response_rate * 0.65 + recency_signal * 0.2 + frequency_signal * 0.15),
        )
        model_explanation = None
    else:
        response_probability, model_explanation = model_prediction
    priority = donor_priority(response_probability, donor.notifications_30d, days_since_contact) if eligible else 0.0

    if not donor.available:
        explanation = "Marked unavailable; excluded from this activation round."
    elif days_since_donation < 90:
        explanation = f"Last donation was {days_since_donation} days ago; held out of the activation list."
    elif model_explanation:
        explanation = f"{model_explanation} Recent contact fatigue is applied separately to priority."
    elif donor.notifications_30d >= 3:
        explanation = "Strong historical response, but recent contact volume lowers priority to reduce fatigue."
    elif donor.response_rate >= 0.7:
        explanation = "High past response rate and eligible donation interval support a strong priority."
    else:
        explanation = "Eligible interval and response history contribute to this priority."

    return {
        "eligible": eligible,
        "response_probability": round(response_probability, 3),
        "priority_score": priority,
        "days_since_donation": days_since_donation,
        "days_since_contact": days_since_contact,
        "explanation": explanation,
    }
