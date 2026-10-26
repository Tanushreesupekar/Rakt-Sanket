"""Build ML training frames from the linked RaktSanket reference tables.

The reference dataset (backend/data/blood_stock_demand_full.csv,
donors_full.csv, notifications_full.csv) preserves the 20-row example PDF
schema and expands it to 1000 donors / 1000 stock rows / ~3900 linked
notification events.

This module converts those tables into:
1. A leakage-free donor-response training frame (one row per notification,
   label = Responded/Ignored). Prior-only aggregates are used so the model
   never sees the current outcome in its inputs (DRPS spec: previous request
   count, previous response count, previous response history).
2. Per-blood-group shortage statistics for the SFS time-series forecaster
   (historical demand, issued, collected, trend, seasonal/festival factors).
3. Correlation-based CBSRI weight calibration on historical events.

All outputs are documented as derived from synthetic example-schema data,
not real blood-bank records.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
STOCK_FILE = DATA_DIR / "blood_stock_demand_full.csv"
DONOR_FILE = DATA_DIR / "donors_full.csv"
NOTIFICATION_FILE = DATA_DIR / "notifications_full.csv"
SHORTAGE_STATS_PATH = MODEL_DIR / "shortage_forecast.json"
CBSRI_WEIGHTS_PATH = MODEL_DIR / "cbsri_weights.json"

FESTIVAL_MONTHS = (1, 8, 10, 11)

# DRPS-aligned feature order. The first 8 match the legacy synthetic model so
# checkpoints remain comparable; the last 3 make previous request/response
# history and request urgency explicit per the DRPS spec.
REFERENCE_FEATURES = (
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
TARGET_COLUMN = "accepted_invitation"


def load_reference_tables(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stock = pd.read_csv(data_dir / STOCK_FILE.name, parse_dates=["Date"])
    donors = pd.read_csv(data_dir / DONOR_FILE.name, parse_dates=["Last Donation Date"])
    notifications = pd.read_csv(data_dir / NOTIFICATION_FILE.name, parse_dates=["Alert Date"])
    return stock, donors, notifications


def build_reference_donor_frame(
    donors: pd.DataFrame | None = None,
    notifications: pd.DataFrame | None = None,
    data_dir: Path = DATA_DIR,
) -> pd.DataFrame:
    """Return one leakage-free training row per notification event.

    For the k-th notification of a donor, response history features use only
    the k prior notifications (prior response rate defaults to 0.5 when there
    is no history). ``notifications_30d`` counts prior alerts in the 30 days
    before the current alert, matching the operational fatigue feature.
    """
    if donors is None or notifications is None:
        _, donors, notifications = load_reference_tables(data_dir)
    donors = donors.copy()
    notifications = notifications.copy()
    donors["Last Donation Date"] = pd.to_datetime(donors["Last Donation Date"])
    notifications["Alert Date"] = pd.to_datetime(notifications["Alert Date"])
    donor_lookup = donors.set_index("Donor ID")

    rows: list[dict] = []
    for donor_id, group in notifications.sort_values("Alert Date").groupby("Donor ID"):
        donor = donor_lookup.loc[donor_id]
        last_donation = donor["Last Donation Date"]
        previous_donations = int(donor["Previous Donations"])
        ordered = group.sort_values("Alert Date")
        alert_dates = ordered["Alert Date"].tolist()
        responded = (ordered["Response"] == "Responded").astype(int).tolist()
        reasons = ordered["Reason"].tolist()
        for position, (alert_date, label, reason) in enumerate(zip(alert_dates, responded, reasons)):
            prior_labels = responded[:position]
            prior_alerts = position
            prior_responses = int(sum(prior_labels))
            prior_rate = (prior_responses / prior_alerts) if prior_alerts else 0.5
            window_start = alert_date - pd.Timedelta(days=30)
            prior_dates = alert_dates[:position]
            notifications_30d = sum(1 for d in prior_dates if d > window_start)
            if prior_dates:
                days_since_contact = int((alert_date - prior_dates[-1]).days)
            else:
                days_since_contact = 365
            days_since_donation = int((alert_date - last_donation).days)
            month = int(alert_date.month)
            rows.append({
                "invitation_date": alert_date.date(),
                "age": 30,  # Example donor table has no age; fixed neutral value, documented.
                "days_since_last_donation": max(0, days_since_donation),
                "donations_count": previous_donations,
                "response_rate": round(float(prior_rate), 4),
                "notifications_30d": int(notifications_30d),
                "days_since_last_contact": int(days_since_contact),
                "month": month,
                "is_festival_season": int(month in FESTIVAL_MONTHS),
                "previous_requests": int(prior_alerts),
                "previous_responses": int(prior_responses),
                "is_urgent": int(reason == "Urgent"),
                TARGET_COLUMN: int(label),
            })
    frame = pd.DataFrame(rows)
    frame["invitation_date"] = pd.to_datetime(frame["invitation_date"])
    return frame.sort_values("invitation_date", kind="stable").reset_index(drop=True)


def build_shortage_stats(stock: pd.DataFrame | None = None, data_dir: Path = DATA_DIR) -> dict:
    """Compute per-blood-group demand/collection/trend statistics (SFS inputs)."""
    if stock is None:
        stock, _, _ = load_reference_tables(data_dir)
    stock = stock.copy()
    stock["Date"] = pd.to_datetime(stock["Date"])
    stock["closing_stock"] = stock["Opening Stock (units)"] + stock["Collected (units)"] - stock["Issued/Used (units)"]
    stock["unmet_demand"] = (stock["Demand/Requests"] - stock["Issued/Used (units)"]).clip(lower=0)
    stock["shortage_event"] = (stock["unmet_demand"] > 0).astype(int)
    stock["month"] = stock["Date"].dt.month

    overall_demand = float(stock["Demand/Requests"].mean())
    stats: dict = {"blood_groups": {}, "overall_avg_daily_demand": round(overall_demand, 3)}
    for group, table in stock.groupby("Blood Group"):
        table = table.sort_values("Date")
        x = np.arange(len(table), dtype=float)
        y = table["closing_stock"].to_numpy(dtype=float)
        slope = float(np.polyfit(x, y, 1)[0]) if len(table) >= 2 else 0.0
        monthly = table.groupby("month")["Demand/Requests"].mean()
        group_mean = float(table["Demand/Requests"].mean())
        seasonal = {int(m): round(float(v) / group_mean, 3) for m, v in monthly.items()} if group_mean else {}
        festival_mask = table["month"].isin(FESTIVAL_MONTHS)
        festival_uplift = None
        if festival_mask.any() and (~festival_mask).any():
            festival_uplift = round(float(table.loc[festival_mask, "Demand/Requests"].mean() / table.loc[~festival_mask, "Demand/Requests"].mean()), 3)
        stats["blood_groups"][str(group)] = {
            "observations": int(len(table)),
            "avg_daily_demand": round(float(table["Demand/Requests"].mean()), 3),
            "avg_issued": round(float(table["Issued/Used (units)"].mean()), 3),
            "avg_collected": round(float(table["Collected (units)"].mean()), 3),
            "unmet_rate": round(float(table["shortage_event"].mean()), 4),
            "closing_trend_per_day": round(slope, 4),
            "seasonal_demand_factor_by_month": seasonal,
            "festival_uplift_ratio": festival_uplift,
        }
    stats["warning"] = "Synthetic example-schema data; not real blood-bank records."
    return stats


def _point_biserial(x: pd.Series, y: pd.Series) -> float:
    if x.nunique() < 2 or y.nunique() < 2:
        return 0.0
    return abs(float(x.corr(y)) or 0.0)


def calibrate_cbsri_weights(
    donor_frame: pd.DataFrame | None = None,
    stock: pd.DataFrame | None = None,
    data_dir: Path = DATA_DIR,
) -> dict:
    """Calibrate CBSRI weights by correlation strength on historical events.

    - shortage weight: |corr(demand pressure, shortage event)| on stock rows,
      where demand pressure = (demand - collected) / max(demand, 1).
    - response weight: |corr(prior response rate, responded)| on notifications.
    - priority weight: |corr(fatigue-discounted prior rate, responded)|, where
      the fatigue discount mirrors services.scoring.fatigue_multiplier.
    Weights are normalized to sum to 1 (fallback: 0.45/0.30/0.25 on failure).
    """
    if donor_frame is None or stock is None:
        stock_loaded, _, _ = load_reference_tables(data_dir)
        if stock is None:
            stock = stock_loaded
        if donor_frame is None:
            donor_frame = build_reference_donor_frame(data_dir=data_dir)
    stock = stock.copy()
    pressure = (stock["Demand/Requests"] - stock["Collected (units)"]) / stock["Demand/Requests"].clip(lower=1)
    shortage_event = ((stock["Demand/Requests"] - stock["Issued/Used (units)"]) > 0).astype(int)
    w_shortage = _point_biserial(pressure, shortage_event)

    y = donor_frame[TARGET_COLUMN]
    w_response = _point_biserial(donor_frame["response_rate"], y)
    contact_load = (1.0 - 0.22 * donor_frame["notifications_30d"]).clip(lower=0.15)
    recency = (donor_frame["days_since_last_contact"] / 30).clip(lower=0.25, upper=1.0)
    fatigue_proxy = donor_frame["response_rate"] * contact_load * recency
    w_priority = _point_biserial(fatigue_proxy, y)

    total = w_shortage + w_response + w_priority
    if total <= 0:
        weights = {"shortage": 0.45, "response": 0.30, "fatigue_adjusted_priority": 0.25}
    else:
        weights = {
            "shortage": round(w_shortage / total, 4),
            "response": round(w_response / total, 4),
            "fatigue_adjusted_priority": round(w_priority / total, 4),
        }
    return {
        "weights": weights,
        "correlations": {
            "shortage_demand_pressure_vs_shortage_event": round(w_shortage, 4),
            "prior_response_rate_vs_responded": round(w_response, 4),
            "fatigue_discounted_rate_vs_responded": round(w_priority, 4),
        },
        "method": "Weights proportional to |correlation| with historical shortage/response events in the linked reference tables.",
        "warning": "Synthetic example-schema data; weights are pilot defaults, not clinical evidence.",
    }


def train_reference_donor_model(
    donor_frame: pd.DataFrame | None = None,
    data_dir: Path = DATA_DIR,
    seed: int = 2026,
) -> dict:
    """Train XGBoost DRPS model on the linked reference tables.

    Chronological 80/20 split by invitation date (no shuffling, so history
    never leaks into training). Same hyperparameters as the synthetic
    baseline for comparability. Saves model + metrics to models/.
    """
    from datetime import datetime, timezone

    from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
    from xgboost import XGBClassifier

    from app.ml.donor_response import METADATA_PATH, MODEL_DIR as _MODEL_DIR, MODEL_PATH as _MODEL_PATH

    if donor_frame is None:
        donor_frame = build_reference_donor_frame(data_dir=data_dir)
    frame = donor_frame.sort_values("invitation_date", kind="stable").reset_index(drop=True)
    unique_dates = frame["invitation_date"].drop_duplicates().sort_values().to_numpy()
    split_date = unique_dates[int(len(unique_dates) * 0.8)]
    train = frame.loc[frame["invitation_date"] < split_date]
    test = frame.loc[frame["invitation_date"] >= split_date]
    if train[TARGET_COLUMN].nunique() < 2 or test[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Both chronological partitions must contain both outcome classes")

    model = XGBClassifier(
        n_estimators=240,
        max_depth=4,
        learning_rate=0.045,
        subsample=0.85,
        colsample_bytree=0.9,
        min_child_weight=4,
        reg_lambda=2.0,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=seed,
        n_jobs=4,
    )
    model.fit(train.loc[:, list(REFERENCE_FEATURES)], train[TARGET_COLUMN])
    probabilities = model.predict_proba(test.loc[:, list(REFERENCE_FEATURES)])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "synthetic_data": True,
        "data_source": "linked reference tables (donors_full + notifications_full, example-schema synthetic)",
        "rows": int(len(frame)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_through": str(pd.to_datetime(train["invitation_date"].max()).date()),
        "test_from": str(pd.to_datetime(test["invitation_date"].min()).date()),
        "date_overlap": bool(train["invitation_date"].max() >= test["invitation_date"].min()),
        "acceptance_rate": round(float(frame[TARGET_COLUMN].mean()), 4),
        "accuracy": round(float(accuracy_score(test[TARGET_COLUMN], predictions)), 4),
        "roc_auc": round(float(roc_auc_score(test[TARGET_COLUMN], probabilities)), 4),
        "brier_score": round(float(brier_score_loss(test[TARGET_COLUMN], probabilities)), 4),
        "seed": seed,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "features": list(REFERENCE_FEATURES),
        "warning": "Metrics measure recovery of synthetic example-schema outcomes, not real donor behavior.",
    }
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(_MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    # Invalidate cached booster so predict_response picks up the new file.
    from app.ml import donor_response as _dr
    _dr.load_model.cache_clear()
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Build reference-table training frames and calibration artifacts.")
    parser.add_argument("--output-dir", type=Path, default=MODEL_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--preview-rows", type=int, default=5)
    args = parser.parse_args()

    stock, donors, notifications = load_reference_tables(args.data_dir)
    donor_frame = build_reference_donor_frame(donors, notifications)
    stats = build_shortage_stats(stock)
    calibration = calibrate_cbsri_weights(donor_frame, stock)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "shortage_forecast.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "cbsri_weights.json").write_text(json.dumps(calibration, indent=2) + "\n", encoding="utf-8")
    preview = donor_frame.head(args.preview_rows).to_string(index=False)
    print(f"donor_training_rows: {len(donor_frame)}")
    print(f"response_rate: {donor_frame[TARGET_COLUMN].mean():.1%}")
    print(f"stock_groups: {sorted(stats['blood_groups'])}")
    print(f"weights: {calibration['weights']}")
    print(preview)


if __name__ == "__main__":
    main()
