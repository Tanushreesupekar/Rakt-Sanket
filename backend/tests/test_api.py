import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Donor
from app.seed import seed_demo_data


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls.engine)
        with cls.session_factory() as session:
            seed_demo_data(session)

        def override_get_db():
            session = cls.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls) -> None:
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def test_dashboard_contains_seeded_forecasts_and_rankings(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/dashboard", params={"district": "Amravati"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_district"], "Amravati")
        self.assertEqual(len(payload["inventory"]), 8)
        self.assertEqual(len(payload["forecasts"][0]["points"]), 14)
        self.assertIn("cbsri", payload["forecasts"][0])

    def test_dashboard_district_filter_includes_donor_only_districts(self) -> None:
        with TestClient(app) as client:
            created = client.post("/api/donors", json={
                "name": "District Filter Donor",
                "district": "Nagpur",
                "blood_group": "A+",
                "age": 30,
                "donations_count": 1,
                "response_rate": 0.5,
            })
            self.assertEqual(created.status_code, 201)
            dashboard = client.get("/api/dashboard", params={"district": "Nagpur"})

        self.assertEqual(dashboard.status_code, 200)
        payload = dashboard.json()
        self.assertEqual(payload["selected_district"], "Nagpur")
        self.assertIn("Nagpur", payload["districts"])
        self.assertEqual(payload["totals"]["donor_count"], 1)
        self.assertEqual(payload["inventory"], [])

    def test_dashboard_defaults_to_district_with_inventory(self) -> None:
        with self.session_factory.begin() as session:
            session.add(Donor(
                name="No Stock District Donor",
                district="AAA Donor Only",
                blood_group="A+",
                age=30,
                donations_count=1,
                response_rate=0.5,
            ))
        with TestClient(app) as client:
            response = client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["selected_district"], "Akola")

    def test_campaign_is_simulated_and_fatigue_is_recorded(self) -> None:
        with TestClient(app) as client:
            eligible = client.get("/api/donors", params={"district": "Amravati", "eligible_only": "true"}).json()
            self.assertTrue(eligible)
            donor = eligible[0]
            response = client.post("/api/campaigns", json={
                "district": donor["district"],
                "blood_group": donor["blood_group"],
                "stage": 1,
                "batch_size": 1,
            })
            self.assertEqual(response.status_code, 201)
            campaign = response.json()
            self.assertEqual(campaign["status"], "simulated")
            self.assertEqual(campaign["recipients_count"], 1)
            self.assertEqual(campaign["donor_names"], [donor["name"]])

    def test_advisory_supports_marathi(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/advisories", params={"district": "Amravati", "language": "mr"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["language"], "mr")
        self.assertTrue(response.json()["message"])

    def test_demo_donors_cover_every_blood_group_in_each_district(self) -> None:
        with TestClient(app) as client:
            for district in ("Amravati", "Akola", "Wardha", "Yavatmal"):
                records = client.get("/api/donors", params={"district": district}).json()
                groups = {record["blood_group"] for record in records}
                self.assertEqual(groups, {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"})

    def test_stock_update_donor_create_and_short_forecast(self) -> None:
        with TestClient(app) as client:
            inventory = client.get("/api/inventory", params={"district": "Amravati"}).json()[0]
            update = client.patch(f"/api/inventory/{inventory['id']}", json={
                "units_available": 41,
                "avg_daily_demand": 3.5,
                "safety_stock_units": 24,
            })
            self.assertEqual(update.status_code, 200)
            self.assertEqual(update.json()["units_available"], 41)

            donor = client.post("/api/donors", json={
                "name": "Test Donor",
                "district": "Amravati",
                "blood_group": "A+",
                "age": 29,
                "last_donation_date": "2024-01-01",
                "donations_count": 3,
                "response_rate": 0.7,
            })
            self.assertEqual(donor.status_code, 201)
            self.assertIn("response_probability", donor.json())

            forecast = client.get("/api/forecasts", params={
                "district": "Amravati",
                "blood_group": "O-",
                "days": 7,
            })
            self.assertEqual(forecast.status_code, 200)
            self.assertEqual(len(forecast.json()[0]["points"]), 7)

    def test_health_reports_active_donor_model(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["donor_response_model"]["available"])

    def test_readiness_checks_database_connection(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "connected")

    def test_donor_portal_profile_requests_notifications_and_history(self) -> None:
        with TestClient(app) as client:
            donors = client.get("/api/donors", params={"district": "Amravati"}).json()
            donor = donors[0]
            donor_id = donor["id"]

            profile_update = client.patch(f"/api/donors/{donor_id}/profile", json={
                "name": "Portal Test Donor",
                "age": donor["age"],
                "available": False,
            })
            self.assertEqual(profile_update.status_code, 200)
            self.assertEqual(profile_update.json()["name"], "Portal Test Donor")
            self.assertFalse(profile_update.json()["available"])

            request = client.post("/api/blood-requests", json={
                "donor_id": donor_id,
                "blood_group": donor["blood_group"],
                "units_requested": 2,
                "hospital_name": "Amravati General Hospital",
                "district": "Amravati",
                "needed_by": "2026-10-01",
                "notes": "Urgent surgery requirement",
            })
            self.assertEqual(request.status_code, 201)
            requests = client.get("/api/blood-requests", params={"donor_id": donor_id})
            self.assertEqual(requests.status_code, 200)
            self.assertEqual(requests.json()[0]["status"], "pending review")

            history = client.get(f"/api/donors/{donor_id}/history")
            notifications = client.get(f"/api/donors/{donor_id}/notifications")
            self.assertEqual(history.status_code, 200)
            self.assertIn("donations_count", history.json())
            self.assertEqual(notifications.status_code, 200)
            self.assertIsInstance(notifications.json(), list)


if __name__ == "__main__":
    unittest.main()
