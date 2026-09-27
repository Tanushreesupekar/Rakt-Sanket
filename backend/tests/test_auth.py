import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Donor, User


class ProductionAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls.engine)
        with cls.session_factory.begin() as session:
            donor = Donor(
                name="Auth Test Donor", district="Amravati", blood_group="A+", age=30,
                donations_count=2, response_rate=0.5,
            )
            other_donor = Donor(
                name="Other Test Donor", district="Amravati", blood_group="B+", age=31,
                donations_count=1, response_rate=0.5,
            )
            session.add_all([donor, other_donor])
            session.flush()
            session.add_all([
                User(email="admin@example.com", password_hash=hash_password("admin-test-password-123"), role="admin"),
                User(email="donor@example.com", password_hash=hash_password("donor-test-password-123"), role="donor", donor_id=donor.id),
            ])
            cls.donor_id = donor.id
            cls.other_donor_id = other_donor.id

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

    def test_protected_admin_route_requires_authentication(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_role_and_donor_ownership_are_enforced(self) -> None:
        with TestClient(app) as client:
            admin_login = client.post("/api/auth/login", json={"email": "ADMIN@example.com", "password": "admin-test-password-123"})
            donor_login = client.post("/api/auth/login", json={"email": "donor@example.com", "password": "donor-test-password-123"})
            self.assertEqual(admin_login.status_code, 200)
            self.assertEqual(donor_login.status_code, 200)
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
            donor_headers = {"Authorization": f"Bearer {donor_login.json()['access_token']}"}

            self.assertEqual(client.get("/api/dashboard", headers=admin_headers).status_code, 200)
            self.assertEqual(client.get("/api/dashboard", headers=donor_headers).status_code, 403)
            self.assertEqual(client.get(f"/api/donors/{self.donor_id}/profile", headers=donor_headers).status_code, 200)
            self.assertEqual(client.get(f"/api/donors/{self.other_donor_id}/profile", headers=donor_headers).status_code, 403)

            provisioned = client.post("/api/admin/donor-accounts", headers=admin_headers, json={
                "donor_id": self.other_donor_id,
                "email": "new-donor@example.com",
                "password": "new-donor-password-123",
            })
            self.assertEqual(provisioned.status_code, 201)
            self.assertEqual(provisioned.json()["role"], "donor")
            new_login = client.post("/api/auth/login", json={
                "email": "new-donor@example.com",
                "password": "new-donor-password-123",
            })
            self.assertEqual(new_login.status_code, 200)

    def test_login_does_not_disclose_which_credential_failed(self) -> None:
        with TestClient(app) as client:
            response = client.post("/api/auth/login", json={"email": "missing@example.com", "password": "not-a-real-password-123"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Email or password is incorrect")


if __name__ == "__main__":
    unittest.main()
