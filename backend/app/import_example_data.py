from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.ml.reference_dataset import DATA_DIR, DONOR_FILE, NOTIFICATION_FILE, STOCK_FILE
from app.models import Donor, ExampleDonorRecord, ExampleNotificationRecord, ExampleStockObservation, Inventory
from app.settings import IS_PRODUCTION


def _parse_date(value: str) -> date:
    for date_format in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported example date: {value}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required example dataset not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def import_example_dataset(session: Session, district: str, data_dir: Path = DATA_DIR) -> dict[str, int | str]:
    district = district.strip()
    if len(district) < 2 or len(district) > 80:
        raise ValueError("district must contain 2 to 80 characters")

    stock_rows = _read_csv(data_dir / STOCK_FILE.name)
    donor_rows = _read_csv(data_dir / DONOR_FILE.name)
    notification_rows = _read_csv(data_dir / NOTIFICATION_FILE.name)

    source_donor_ids = {row["Donor ID"] for row in donor_rows}
    unknown_donors = sorted({row["Donor ID"] for row in notification_rows} - source_donor_ids)
    if unknown_donors:
        raise ValueError(f"Notifications reference missing donor IDs: {unknown_donors[:5]}")

    existing_stock_ids = set(session.scalars(select(ExampleStockObservation.source_id)).all())
    existing_donor_ids = set(session.scalars(select(ExampleDonorRecord.source_id)).all())
    existing_notification_ids = set(session.scalars(select(ExampleNotificationRecord.source_id)).all())

    stock_added = 0
    for row in stock_rows:
        source_id = row["Stock ID"]
        if source_id in existing_stock_ids:
            continue
        session.add(ExampleStockObservation(
            source_id=source_id,
            district=district,
            observed_on=_parse_date(row["Date"]),
            blood_group=row["Blood Group"],
            opening_stock_units=int(row["Opening Stock (units)"]),
            demand_requests=int(row["Demand/Requests"]),
            collected_units=int(row["Collected (units)"]),
            issued_units=int(row["Issued/Used (units)"]),
        ))
        existing_stock_ids.add(source_id)
        stock_added += 1

    donor_records = {
        record.source_id: record
        for record in session.scalars(select(ExampleDonorRecord)).all()
    }
    donors_added = 0
    for row in donor_rows:
        source_id = row["Donor ID"]
        if source_id in donor_records:
            continue
        alert_count = int(row["Alerts Received"])
        response_count = int(row["Responses"])
        donor = Donor(
            name=f"Example donor {source_id} (synthetic)",
            district=district,
            blood_group=row["Blood Group"],
            age=30,
            last_donation_date=_parse_date(row["Last Donation Date"]),
            donations_count=int(row["Previous Donations"]),
            response_rate=response_count / alert_count if alert_count else 0.0,
            notifications_30d=0,
            available=True,
        )
        session.add(donor)
        session.flush()
        reference = ExampleDonorRecord(
            source_id=source_id,
            donor_id=donor.id,
            blood_group=row["Blood Group"],
            last_donation_date=_parse_date(row["Last Donation Date"]),
            previous_donations=int(row["Previous Donations"]),
            alerts_received=alert_count,
            responses=response_count,
        )
        session.add(reference)
        session.flush()
        donor_records[source_id] = reference
        donors_added += 1

    notification_added = 0
    for row in notification_rows:
        source_id = row["Notification ID"]
        if source_id in existing_notification_ids:
            continue
        session.add(ExampleNotificationRecord(
            source_id=source_id,
            donor_record_id=donor_records[row["Donor ID"]].id,
            alert_date=_parse_date(row["Alert Date"]),
            reason=row["Reason"],
            response=row["Response"],
            donation_after_alert=row["Donation After Alert"],
        ))
        existing_notification_ids.add(source_id)
        notification_added += 1

    session.flush()
    observations = session.scalars(select(ExampleStockObservation).where(
        ExampleStockObservation.district == district,
    ).order_by(ExampleStockObservation.observed_on, ExampleStockObservation.id)).all()
    latest_by_group: dict[str, ExampleStockObservation] = {}
    demand_by_group: dict[str, list[int]] = {}
    for observation in observations:
        latest_by_group[observation.blood_group] = observation
        demand_by_group.setdefault(observation.blood_group, []).append(observation.demand_requests)

    inventory_added = 0
    for blood_group, latest in latest_by_group.items():
        exists = session.scalar(select(Inventory.id).where(
            Inventory.district == district,
            Inventory.blood_group == blood_group,
        ))
        if exists:
            continue
        closing_units = max(0, latest.opening_stock_units + latest.collected_units - latest.issued_units)
        average_demand = sum(demand_by_group[blood_group]) / len(demand_by_group[blood_group])
        session.add(Inventory(
            district=district,
            blood_group=blood_group,
            units_available=closing_units,
            avg_daily_demand=max(0.1, average_demand),
            safety_stock_units=max(1, round(average_demand * 7)),
        ))
        inventory_added += 1

    return {
        "district": district,
        "stock_observations_added": stock_added,
        "donors_added": donors_added,
        "notifications_added": notification_added,
        "inventory_summaries_added": inventory_added,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import the linked synthetic reference dataset into the configured database.")
    parser.add_argument("--district", required=True, help="District assigned to this sample dataset (for example: amt)")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--confirm-synthetic-data", action="store_true", help="Acknowledge that all records are synthetic sample data")
    arguments = parser.parse_args()
    if not arguments.confirm_synthetic_data:
        raise SystemExit("Refusing import: rerun with --confirm-synthetic-data to acknowledge synthetic records")
    if IS_PRODUCTION and not arguments.confirm_synthetic_data:
        raise SystemExit("Production import requires explicit synthetic-data confirmation")

    with SessionLocal.begin() as session:
        result = import_example_dataset(session, arguments.district, arguments.data_dir)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()