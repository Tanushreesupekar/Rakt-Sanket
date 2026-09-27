from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
STOCK_FILE = DATA_DIR / "blood_stock_demand_full.csv"
DONOR_FILE = DATA_DIR / "donors_full.csv"
NOTIFICATION_FILE = DATA_DIR / "notifications_full.csv"
WORKBOOK_FILE = DATA_DIR / "raktsanket_full_dataset.xlsx"
BLOOD_GROUPS = ("A+", "B+", "O+", "O-", "AB+", "A-", "B-", "AB-")

STOCK_EXAMPLES = (
    ("01-09-2026", "A+", 42, 30, 18, 26),
    ("02-09-2026", "B+", 35, 28, 15, 22),
    ("03-09-2026", "O+", 27, 34, 12, 31),
    ("04-09-2026", "O-", 14, 18, 6, 17),
    ("05-09-2026", "AB+", 20, 15, 8, 12),
    ("06-09-2026", "A-", 16, 19, 7, 15),
    ("07-09-2026", "B-", 12, 17, 5, 14),
    ("08-09-2026", "O+", 21, 37, 10, 29),
    ("09-09-2026", "A+", 34, 25, 14, 20),
    ("10-09-2026", "B+", 29, 31, 13, 27),
    ("11-09-2026", "O-", 11, 20, 5, 18),
    ("12-09-2026", "AB+", 24, 18, 9, 15),
    ("13-09-2026", "A-", 18, 22, 8, 17),
    ("14-09-2026", "B-", 15, 21, 6, 19),
    ("15-09-2026", "O+", 17, 39, 9, 34),
    ("16-09-2026", "A+", 31, 27, 12, 23),
    ("17-09-2026", "B+", 25, 33, 11, 28),
    ("18-09-2026", "O-", 9, 22, 4, 20),
    ("19-09-2026", "AB+", 19, 16, 7, 13),
    ("20-09-2026", "O+", 13, 41, 8, 37),
)

DONOR_EXAMPLES = (
    ("A+", "10-07-2026", 6, 4, 3), ("B+", "22-06-2026", 4, 3, 2),
    ("O+", "15-08-2026", 7, 5, 4), ("O-", "01-07-2026", 3, 4, 2),
    ("AB+", "18-05-2026", 5, 2, 1), ("A-", "30-06-2026", 4, 3, 2),
    ("B-", "12-08-2026", 6, 4, 3), ("O+", "25-07-2026", 8, 6, 5),
    ("A+", "05-08-2026", 3, 2, 1), ("B+", "20-07-2026", 5, 5, 4),
    ("O-", "11-06-2026", 4, 3, 1), ("AB+", "28-07-2026", 6, 4, 3),
    ("A-", "16-08-2026", 3, 2, 2), ("B-", "09-07-2026", 5, 3, 2),
    ("O+", "02-08-2026", 7, 7, 5), ("A+", "14-06-2026", 4, 3, 2),
    ("B+", "29-07-2026", 6, 5, 4), ("O-", "06-08-2026", 2, 2, 1),
    ("AB+", "21-06-2026", 5, 4, 3), ("O+", "30-07-2026", 9, 6, 5),
)

NOTIFICATION_EXAMPLES = (
    ("D001", "12-09-2026", "Shortage", "Responded", "Yes"),
    ("D002", "12-09-2026", "Shortage", "Ignored", "No"),
    ("D003", "13-09-2026", "Urgent", "Responded", "Yes"),
    ("D004", "13-09-2026", "Shortage", "Responded", "Yes"),
    ("D005", "14-09-2026", "Shortage", "Ignored", "No"),
    ("D006", "14-09-2026", "Urgent", "Responded", "Yes"),
    ("D007", "15-09-2026", "Shortage", "Responded", "Yes"),
    ("D008", "15-09-2026", "Urgent", "Responded", "Yes"),
    ("D009", "16-09-2026", "Shortage", "Ignored", "No"),
    ("D010", "16-09-2026", "Shortage", "Responded", "Yes"),
    ("D011", "17-09-2026", "Urgent", "Ignored", "No"),
    ("D012", "17-09-2026", "Shortage", "Responded", "Yes"),
    ("D013", "18-09-2026", "Shortage", "Responded", "Yes"),
    ("D014", "18-09-2026", "Urgent", "Ignored", "No"),
    ("D015", "19-09-2026", "Urgent", "Responded", "Yes"),
    ("D016", "19-09-2026", "Shortage", "Ignored", "No"),
    ("D017", "20-09-2026", "Shortage", "Responded", "Yes"),
    ("D018", "20-09-2026", "Urgent", "Ignored", "No"),
    ("D019", "20-09-2026", "Shortage", "Responded", "Yes"),
    ("D020", "20-09-2026", "Urgent", "Responded", "Yes"),
)

DATA_DICTIONARY = [
    ("Stock ID", "Unique blood-stock observation identifier."),
    ("Date", "Date of stock/demand observation."),
    ("Blood Group", "ABO and Rh blood group for the stock record or donor."),
    ("Opening Stock (units)", "Units on hand at the start of the stock observation."),
    ("Demand/Requests", "Units requested during the stock observation."),
    ("Collected (units)", "Units collected during the stock observation."),
    ("Issued/Used (units)", "Units issued during the stock observation."),
    ("Donor ID", "Synthetic donor key shared by the donor and notification sheets."),
    ("Last Donation Date", "Most recent donation date recorded for the donor."),
    ("Previous Donations", "Count of donations before the current history summary."),
    ("Alerts Received", "Count of linked notification records for the donor."),
    ("Responses", "Count of linked notifications with Response = Responded."),
    ("Notification ID", "Unique donor-contact event identifier."),
    ("Alert Date", "Date of the donor notification."),
    ("Reason", "Shortage or Urgent, matching the example schema."),
    ("Response", "Responded or Ignored, matching the example schema."),
    ("Donation After Alert", "Yes for responded sample events; otherwise No."),
]


def _parse_example_date(value: str) -> date:
    return date.strptime(value, "%d-%m-%Y") if hasattr(date, "strptime") else pd.to_datetime(value, format="%d-%m-%Y").date()


def generate_stock_table(rows: int, random: np.random.Generator) -> pd.DataFrame:
    if rows < len(STOCK_EXAMPLES):
        raise ValueError(f"stock row count must be at least {len(STOCK_EXAMPLES)} to retain all PDF examples")

    records = []
    closing_stock: dict[str, int] = {}
    for index, (date_text, blood_group, opening, demand, collected, issued) in enumerate(STOCK_EXAMPLES, start=1):
        records.append({
            "Stock ID": f"BS{index:03d}", "Date": _parse_example_date(date_text), "Blood Group": blood_group,
            "Opening Stock (units)": opening, "Demand/Requests": demand, "Collected (units)": collected,
            "Issued/Used (units)": issued,
        })
        closing_stock[blood_group] = max(0, opening + collected - issued)

    remaining = rows - len(records)
    generated_start = date(2026, 9, 21)
    for offset in range(remaining):
        day_offset, group_index = divmod(offset, len(BLOOD_GROUPS))
        blood_group = BLOOD_GROUPS[group_index]
        opening = closing_stock.get(blood_group, int(random.integers(10, 36)))
        demand = int(random.integers(10, 43))
        collected = int(random.integers(3, 19))
        issued = min(demand, opening + collected)
        observation_date = generated_start + timedelta(days=day_offset)
        records.append({
            "Stock ID": f"BS{len(records) + 1:04d}", "Date": observation_date, "Blood Group": blood_group,
            "Opening Stock (units)": opening, "Demand/Requests": demand, "Collected (units)": collected,
            "Issued/Used (units)": issued,
        })
        closing_stock[blood_group] = opening + collected - issued
    return pd.DataFrame.from_records(records)


def generate_donor_table(rows: int, random: np.random.Generator) -> pd.DataFrame:
    if rows < len(DONOR_EXAMPLES):
        raise ValueError(f"donor row count must be at least {len(DONOR_EXAMPLES)} to retain all PDF examples")

    records = []
    for index, (blood_group, donation_text, previous, alerts, responses) in enumerate(DONOR_EXAMPLES, start=1):
        records.append({
            "Donor ID": f"D{index:03d}", "Blood Group": blood_group,
            "Last Donation Date": _parse_example_date(donation_text), "Previous Donations": previous,
            "Alerts Received": alerts, "Responses": responses,
        })

    for index in range(len(records), rows):
        alerts = int(random.integers(1, 8))
        response_rate = float(random.beta(2.5, 2.2))
        responses = min(alerts, int(random.binomial(alerts, response_rate)))
        last_donation = date(2025, 1, 1) + timedelta(days=int(random.integers(0, 570)))
        records.append({
            "Donor ID": f"D{index + 1:04d}", "Blood Group": BLOOD_GROUPS[int(random.integers(0, len(BLOOD_GROUPS)))],
            "Last Donation Date": last_donation, "Previous Donations": int(random.integers(1, 13)),
            "Alerts Received": alerts, "Responses": responses,
        })
    return pd.DataFrame.from_records(records)


def generate_notification_table(donors: pd.DataFrame, random: np.random.Generator) -> pd.DataFrame:
    first_twenty = []
    for index, (donor_id, date_text, reason, response, donation_after) in enumerate(NOTIFICATION_EXAMPLES, start=1):
        first_twenty.append({
            "Notification ID": f"N{index:03d}", "Donor ID": donor_id,
            "Alert Date": _parse_example_date(date_text), "Reason": reason,
            "Response": response, "Donation After Alert": donation_after,
        })

    records = list(first_twenty)
    for donor_id, _, _, _, target_alerts, target_responses in donors.iloc[:20].itertuples(index=False, name=None):
        target_alerts = int(target_alerts)
        target_responses = int(target_responses)
        donor_notifications = [record for record in first_twenty if record["Donor ID"] == donor_id]
        existing_responses = sum(record["Response"] == "Responded" for record in donor_notifications)
        missing_count = target_alerts - len(donor_notifications)
        missing_responses = target_responses - existing_responses
        if not 0 <= missing_responses <= missing_count:
            raise ValueError(f"PDF sample outcomes do not reconcile for donor {donor_id}")
        for _ in range(missing_count):
            responded = missing_responses > 0 and (missing_responses == missing_count or random.random() < missing_responses / missing_count)
            missing_count -= 1
            missing_responses -= int(responded)
            alert_date = date(2026, 9, 12) + timedelta(days=int(random.integers(0, 10)))
            records.append({
                "Notification ID": f"N{len(records) + 1:05d}", "Donor ID": donor_id,
                "Alert Date": alert_date, "Reason": "Urgent" if random.random() < 0.32 else "Shortage",
                "Response": "Responded" if responded else "Ignored",
                "Donation After Alert": "Yes" if responded else "No",
            })

    for donor_id, _, _, _, alert_count, response_count in donors.iloc[20:].itertuples(index=False, name=None):
        alert_count = int(alert_count)
        responses_left = int(response_count)
        for remaining in range(alert_count, 0, -1):
            responded = responses_left > 0 and (responses_left == remaining or random.random() < responses_left / remaining)
            responses_left -= int(responded)
            last_date = date(2025, 1, 1) + timedelta(days=int(random.integers(0, 630)))
            alert_date = last_date + timedelta(days=int(random.integers(90, 630)))
            alert_date = min(alert_date, date(2026, 9, 25))
            records.append({
                "Notification ID": f"N{len(records) + 1:05d}", "Donor ID": donor_id,
                "Alert Date": alert_date, "Reason": "Urgent" if random.random() < 0.32 else "Shortage",
                "Response": "Responded" if responded else "Ignored",
                "Donation After Alert": "Yes" if responded else "No",
            })

    return pd.DataFrame.from_records(records)


def export_workbook(tables: dict[str, pd.DataFrame], output: Path) -> None:
    dictionary = pd.DataFrame(DATA_DICTIONARY, columns=("Column", "Description"))
    notes = pd.DataFrame([
        ("Dataset", "RaktSanket full synthetic example-schema dataset"),
        ("Source reference", "RaktSanket_Example_Datasets_20_Rows (1).pdf"),
        ("Stock rows", len(tables["Blood Stock & Demand"])),
        ("Donor rows", len(tables["Donor"])),
        ("Notification rows", len(tables["Notification"])),
        ("Synthetic data", "All generated data is synthetic. The first 20 rows in each table preserve the values shown in the reference PDF."),
        ("Relationships", "Notification.Donor ID references Donor.Donor ID. Donor alert/response totals are reconciled against the notification table."),
        ("Limitations", "Synthetic demonstration data; not real blood-bank records, real donors, or evidence of model performance."),
    ], columns=("Property", "Value"))

    with pd.ExcelWriter(output, engine="openpyxl", date_format="dd-mm-yyyy") as writer:
        tables["Blood Stock & Demand"].to_excel(writer, sheet_name="Blood Stock", index=False)
        tables["Donor"].to_excel(writer, sheet_name="Donors", index=False)
        tables["Notification"].to_excel(writer, sheet_name="Notifications", index=False)
        dictionary.to_excel(writer, sheet_name="Data Dictionary", index=False)
        notes.to_excel(writer, sheet_name="Dataset Notes", index=False)

    workbook = load_workbook(output)
    header_fill = PatternFill("solid", fgColor="245E49")
    header_font = Font(name="Aptos", bold=True, color="FFFFFF")
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        sheet.row_dimensions[1].height = 25
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(vertical="center")
        for cells in sheet.columns:
            column = get_column_letter(cells[0].column)
            best_width = max(len(str(cell.value or "")) for cell in cells[: min(sheet.max_row, 80)])
            sheet.column_dimensions[column].width = min(max(best_width + 2, 14), 80)
    workbook.save(output)


def generate_full_dataset(rows: int = 1000, seed: int = 2026, output_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    if rows < 1000:
        raise ValueError("rows must be at least 1000 for each of the three tables")
    random = np.random.default_rng(seed)
    tables = {
        "Blood Stock & Demand": generate_stock_table(rows, random),
        "Donor": generate_donor_table(rows, random),
    }
    tables["Notification"] = generate_notification_table(tables["Donor"], random)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables["Blood Stock & Demand"].to_csv(output_dir / STOCK_FILE.name, index=False, date_format="%Y-%m-%d")
    tables["Donor"].to_csv(output_dir / DONOR_FILE.name, index=False, date_format="%Y-%m-%d")
    tables["Notification"].to_csv(output_dir / NOTIFICATION_FILE.name, index=False, date_format="%Y-%m-%d")
    export_workbook(tables, output_dir / WORKBOOK_FILE.name)
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate linked RaktSanket tables from the 20-row example PDF schema.")
    parser.add_argument("--rows", type=int, default=1000, help="Minimum rows in each primary table")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    arguments = parser.parse_args()
    tables = generate_full_dataset(arguments.rows, arguments.seed, arguments.output_dir)
    print(f"Created workbook: {arguments.output_dir / WORKBOOK_FILE.name}")
    for name, frame in tables.items():
        print(f"{name}: {len(frame):,} rows")


if __name__ == "__main__":
    main()