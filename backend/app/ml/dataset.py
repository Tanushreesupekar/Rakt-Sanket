from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


FEATURE_COLUMNS = (
    "age",
    "days_since_last_donation",
    "donations_count",
    "response_rate",
    "notifications_30d",
    "days_since_last_contact",
    "month",
    "is_festival_season",
)
TARGET_COLUMN = "accepted_invitation"
DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "donor_response_synthetic.csv"


def generate_dataset(rows: int = 8000, seed: int = 2026) -> pd.DataFrame:
    if rows < 100:
        raise ValueError("rows must be at least 100")

    random = np.random.default_rng(seed)
    start = np.datetime64("2021-01-01")
    event_dates = start + random.integers(0, 2050, size=rows).astype("timedelta64[D]")
    months = pd.DatetimeIndex(event_dates).month.to_numpy()
    age = random.integers(18, 66, size=rows)
    donation_recency = random.integers(90, 1501, size=rows)
    donation_count = random.poisson(4.2, size=rows).clip(0, 30)
    response_rate = random.beta(2.2, 2.0, size=rows)
    contacts = random.integers(0, 6, size=rows)
    contact_recency = random.integers(0, 181, size=rows)
    no_contact = random.random(size=rows) < 0.17
    contact_recency[no_contact] = 365
    festival_season = np.isin(months, (1, 8, 10, 11)).astype(int)

    log_odds = (
        -1.05
        + 2.25 * (response_rate - 0.5)
        + 0.22 * np.log1p(donation_count)
        + 0.18 * np.clip((donation_recency - 180) / 365, -1, 2)
        - 0.20 * contacts
        - 0.55 * np.exp(-contact_recency / 12)
        - 0.012 * np.abs(age - 35)
        + 0.12 * festival_season
    )
    probability = 1 / (1 + np.exp(-log_odds))
    accepted = random.binomial(1, probability)

    frame = pd.DataFrame({
        "invitation_date": pd.to_datetime(event_dates).date,
        "age": age,
        "days_since_last_donation": donation_recency,
        "donations_count": donation_count,
        "response_rate": response_rate.round(4),
        "notifications_30d": contacts,
        "days_since_last_contact": contact_recency,
        "month": months,
        "is_festival_season": festival_season,
        TARGET_COLUMN: accepted,
    })
    return frame.sort_values("invitation_date", kind="stable").reset_index(drop=True)


def save_dataset(path: Path = DATASET_PATH, rows: int = 8000, seed: int = 2026) -> pd.DataFrame:
    frame = generate_dataset(rows=rows, seed=seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a reproducible synthetic donor response dataset.")
    parser.add_argument("--rows", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, default=DATASET_PATH)
    arguments = parser.parse_args()
    frame = save_dataset(arguments.output, arguments.rows, arguments.seed)
    rate = frame[TARGET_COLUMN].mean()
    print(f"Saved {len(frame):,} synthetic invitation rows to {arguments.output}")
    print(f"Simulated acceptance rate: {rate:.1%}; seed: {arguments.seed}")


if __name__ == "__main__":
    main()