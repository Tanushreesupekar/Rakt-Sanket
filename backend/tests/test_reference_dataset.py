import tempfile
import unittest
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.import_example_data import import_example_dataset
from app.models import Base, Donor, ExampleDonorRecord, ExampleNotificationRecord, ExampleStockObservation, Inventory
from app.ml.reference_dataset import DATA_DIR
from app.ml.reference_dataset import generate_full_dataset


class ReferenceDatasetTests(unittest.TestCase):
    def test_tables_meet_minimum_and_relationships_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tables = generate_full_dataset(rows=1000, seed=2026, output_dir=Path(directory))
            stock = tables["Blood Stock & Demand"]
            donors = tables["Donor"]
            notifications = tables["Notification"]

            self.assertGreaterEqual(len(stock), 1000)
            self.assertGreaterEqual(len(donors), 1000)
            self.assertGreaterEqual(len(notifications), 1000)
            self.assertEqual(stock.iloc[0]["Stock ID"], "BS001")
            self.assertEqual(donors.iloc[0]["Donor ID"], "D001")
            self.assertEqual(notifications.iloc[0]["Notification ID"], "N001")
            self.assertLessEqual(set(notifications["Donor ID"]), set(donors["Donor ID"]))

            totals = notifications.groupby("Donor ID").agg(
                alerts=("Notification ID", "count"),
                responses=("Response", lambda column: int((column == "Responded").sum())),
            )
            expected = donors.set_index("Donor ID")[["Alerts Received", "Responses"]]
            joined = expected.join(totals, how="left")
            self.assertTrue((joined["Alerts Received"] == joined["alerts"]).all())
            self.assertTrue((joined["Responses"] == joined["responses"]).all())

            workbook = pd.ExcelFile(Path(directory) / "raktsanket_full_dataset.xlsx")
            self.assertEqual(workbook.sheet_names, ["Blood Stock", "Donors", "Notifications", "Data Dictionary", "Dataset Notes"])
            workbook.close()

    def test_same_seed_produces_same_records(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = generate_full_dataset(rows=1000, seed=44, output_dir=Path(first_dir))
            second = generate_full_dataset(rows=1000, seed=44, output_dir=Path(second_dir))
            pd.testing.assert_frame_equal(first["Blood Stock & Demand"], second["Blood Stock & Demand"])
            pd.testing.assert_frame_equal(first["Donor"], second["Donor"])
            pd.testing.assert_frame_equal(first["Notification"], second["Notification"])

    def test_database_import_is_linked_and_idempotent(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)
        try:
            with session_factory.begin() as session:
                session.add(Donor(
                    name="Existing donor", district="amt", blood_group="O+", age=40,
                    donations_count=2, response_rate=0.5,
                ))

            with session_factory.begin() as session:
                first = import_example_dataset(session, "amt", DATA_DIR)
            with session_factory.begin() as session:
                second = import_example_dataset(session, "amt", DATA_DIR)

            self.assertEqual(first["stock_observations_added"], 1000)
            self.assertEqual(first["donors_added"], 1000)
            self.assertEqual(first["notifications_added"], 3905)
            self.assertEqual(first["inventory_summaries_added"], 8)
            self.assertEqual(second["stock_observations_added"], 0)
            self.assertEqual(second["donors_added"], 0)
            self.assertEqual(second["notifications_added"], 0)
            self.assertEqual(second["inventory_summaries_added"], 0)

            with session_factory() as session:
                self.assertEqual(session.scalar(select(func.count()).select_from(Donor)), 1001)
                self.assertEqual(session.scalar(select(func.count()).select_from(ExampleStockObservation)), 1000)
                self.assertEqual(session.scalar(select(func.count()).select_from(ExampleDonorRecord)), 1000)
                self.assertEqual(session.scalar(select(func.count()).select_from(ExampleNotificationRecord)), 3905)
                self.assertEqual(session.scalar(select(func.count()).select_from(Inventory)), 8)
                invalid_links = session.execute(
                    select(ExampleNotificationRecord.id)
                    .outerjoin(ExampleDonorRecord, ExampleNotificationRecord.donor_record_id == ExampleDonorRecord.id)
                    .where(ExampleDonorRecord.id.is_(None))
                ).all()
                self.assertEqual(invalid_links, [])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()