import isolated_env  # noqa: F401  (must precede app imports)
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Donor, User


class AdminDonorManagementTests(unittest.TestCase):
    """The admin side of the donor flow, with sign-in enforced as in
    production: creating donor logins, and reviewing blood requests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls.engine)
        with cls.session_factory.begin() as session:
            linked = Donor(name="Linked Donor", district="Amravati", blood_group="O+", age=30, donations_count=3, response_rate=0.6)
            unlinked = Donor(name="New Donor", district="Amravati", blood_group="A-", age=26, donations_count=1, response_rate=0.5)
            elsewhere = Donor(name="Akola Donor", district="Akola", blood_group="B+", age=41, donations_count=6, response_rate=0.7)
            session.add_all([linked, unlinked, elsewhere])
            session.flush()
            session.add_all([
                User(email="admin@example.com", password_hash=hash_password("admin-test-password-123"), role="admin"),
                User(email="linked@example.com", password_hash=hash_password("linked-test-password-123"), role="donor", donor_id=linked.id),
            ])
            cls.linked_id, cls.unlinked_id, cls.elsewhere_id = linked.id, unlinked.id, elsewhere.id

        def override_get_db():
            session = cls.session_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.original_production_flag = auth.IS_PRODUCTION
        auth.IS_PRODUCTION = True

    @classmethod
    def tearDownClass(cls) -> None:
        auth.IS_PRODUCTION = cls.original_production_flag
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self) -> None:
        auth.login_throttle.reset()
        self.client = TestClient(app)
        self.client.__enter__()
        self.admin = self._headers("admin@example.com", "admin-test-password-123")
        self.donor = self._headers("linked@example.com", "linked-test-password-123")

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def _headers(self, email: str, password: str) -> dict[str, str]:
        response = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def _submit_request(self, district: str = "Amravati") -> dict:
        response = self.client.post("/api/blood-requests", headers=self.donor, json={
            "donor_id": self.linked_id, "blood_group": "O+", "units_requested": 2,
            "hospital_name": "District Hospital", "district": district,
            "needed_by": (date.today() + timedelta(days=3)).isoformat(),
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    # ------------------------------------------------------------ logins
    def test_admin_lists_donor_logins_and_creates_one(self) -> None:
        listed = self.client.get("/api/admin/donor-accounts", headers=self.admin)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([(a["email"], a["donor_id"], a["is_active"]) for a in listed.json()],
                         [("linked@example.com", self.linked_id, True)])

        created = self.client.post("/api/admin/donor-accounts", headers=self.admin, json={
            "donor_id": self.unlinked_id, "email": "new-donor@example.com", "password": "new-donor-password-123",
        })
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual({a["donor_id"] for a in self.client.get("/api/admin/donor-accounts", headers=self.admin).json()},
                         {self.linked_id, self.unlinked_id})
        # the new donor can sign in and reach their own record only
        new_donor = self._headers("new-donor@example.com", "new-donor-password-123")
        self.assertEqual(self.client.get(f"/api/donors/{self.unlinked_id}/profile", headers=new_donor).status_code, 200)
        self.assertEqual(self.client.get(f"/api/donors/{self.linked_id}/profile", headers=new_donor).status_code, 403)

    def test_donor_cannot_list_or_create_logins(self) -> None:
        self.assertEqual(self.client.get("/api/admin/donor-accounts", headers=self.donor).status_code, 403)
        self.assertEqual(self.client.post("/api/admin/donor-accounts", headers=self.donor, json={
            "donor_id": self.elsewhere_id, "email": "sneaky@example.com", "password": "sneaky-password-123",
        }).status_code, 403)

    # ---------------------------------------------------------- requests
    def test_admin_sees_donor_requests_with_donor_name(self) -> None:
        submitted = self._submit_request()
        listed = self.client.get("/api/admin/blood-requests", headers=self.admin, params={"district": "amravati"})
        self.assertEqual(listed.status_code, 200)
        entry = next(item for item in listed.json() if item["id"] == submitted["id"])
        self.assertEqual(entry["donor_name"], "Linked Donor")
        self.assertEqual(entry["status"], "pending review")
        self.assertIsNone(entry["reviewed_at"])
        # district filter is case-insensitive and excludes other districts
        other = self._submit_request(district="Akola")
        ids = {item["id"] for item in self.client.get("/api/admin/blood-requests", headers=self.admin, params={"district": "Amravati"}).json()}
        self.assertIn(submitted["id"], ids)
        self.assertNotIn(other["id"], ids)
        pending = self.client.get("/api/admin/blood-requests", headers=self.admin, params={"status": "pending review"}).json()
        self.assertTrue(all(item["status"] == "pending review" for item in pending))

    def test_review_moves_through_statuses_and_donor_sees_the_note(self) -> None:
        submitted = self._submit_request()
        path = f"/api/admin/blood-requests/{submitted['id']}"
        approved = self.client.patch(path, headers=self.admin, json={"status": "approved", "note": "Two units reserved at the district bank."})
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "approved")
        self.assertIsNotNone(approved.json()["reviewed_at"])

        fulfilled = self.client.patch(path, headers=self.admin, json={"status": "fulfilled"})
        self.assertEqual(fulfilled.status_code, 200)
        # a final status cannot be changed again
        self.assertEqual(self.client.patch(path, headers=self.admin, json={"status": "rejected"}).status_code, 409)

        mine = self.client.get("/api/blood-requests", headers=self.donor, params={"donor_id": self.linked_id}).json()
        entry = next(item for item in mine if item["id"] == submitted["id"])
        self.assertEqual(entry["status"], "fulfilled")
        self.assertEqual(entry["admin_note"], "Two units reserved at the district bank.")

    def test_invalid_reviews_are_refused(self) -> None:
        submitted = self._submit_request()
        path = f"/api/admin/blood-requests/{submitted['id']}"
        # pending requests cannot jump straight to fulfilled, and unknown statuses fail validation
        self.assertEqual(self.client.patch(path, headers=self.admin, json={"status": "fulfilled"}).status_code, 409)
        self.assertEqual(self.client.patch(path, headers=self.admin, json={"status": "lost"}).status_code, 422)
        self.assertEqual(self.client.patch("/api/admin/blood-requests/999999", headers=self.admin, json={"status": "approved"}).status_code, 404)
        # donors cannot review, or list everyone's requests
        self.assertEqual(self.client.patch(path, headers=self.donor, json={"status": "approved"}).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/blood-requests", headers=self.donor).status_code, 403)
        rejected = self.client.patch(path, headers=self.admin, json={"status": "rejected", "note": "Request a hospital transfer instead."})
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["admin_note"], "Request a hospital transfer instead.")


if __name__ == "__main__":
    unittest.main()
