from datetime import date, datetime, timezone

from app.ml.donor_response import build_features, predict_response
from app.models import Donor
from app.services.scoring import donor_priority


def rank_donor(donor: Donor) -> dict:
    today = date.today()
    days_since_donation = (today - donor.last_donation_date).days if donor.last_donation_date else 365
    days_since_contact = None
    if donor.last_contact_at:
        contact = donor.last_contact_at
        if contact.tzinfo is None:
            contact = contact.replace(tzinfo=timezone.utc)
        days_since_contact = max(0, (datetime.now(timezone.utc) - contact).days)

    eligible = donor.available and days_since_donation >= 90
    features = build_features(
        age=donor.age,
        days_since_last_donation=days_since_donation,
        donations_count=donor.donations_count,
        response_rate=donor.response_rate,
        notifications_30d=donor.notifications_30d,
        days_since_last_contact=days_since_contact,
        reference_date=today,
    )
    model_prediction = predict_response(features)
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
