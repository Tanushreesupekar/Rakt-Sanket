import isolated_env  # noqa: F401  (must precede app imports)
import smtplib
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, settings
from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import Donor, Inventory, Notification, User
from app.services import email as email_service


class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls.engine)

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
        auth.registration_throttle.reset()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def _register(self, email: str, **overrides) -> dict:
        payload = {
            "name": "Self Registered Donor",
            "email": email,
            "password": "donor-register-password-123",
            "district": "Amravati",
            "blood_group": "O+",
            "age": 29,
            "last_donation_date": (date.today() - timedelta(days=180)).isoformat(),
            "donations_count": 2,
            "consent": True,
        }
        payload.update(overrides)
        return payload

    def test_donor_can_register_sign_in_and_reach_only_own_record(self) -> None:
        response = self.client.post("/api/auth/register", json=self._register("self-donor@example.com"))
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["user"]["email"], "self-donor@example.com")
        self.assertEqual(body["user"]["role"], "donor")
        self.assertIsNotNone(body["user"]["donor_id"])
        donor_id = body["user"]["donor_id"]

        headers = {"Authorization": f"Bearer {body['access_token']}"}
        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["donor_id"], donor_id)
        self.assertEqual(self.client.get(f"/api/donors/{donor_id}/profile", headers=headers).status_code, 200)

        sign_in = self.client.post("/api/auth/login", json={
            "email": "SELF-DONOR@example.com",
            "password": "donor-register-password-123",
        })
        self.assertEqual(sign_in.status_code, 200)
        self.assertEqual(sign_in.json()["user"]["donor_id"], donor_id)

        other = self.client.post("/api/auth/register", json=self._register("self-donor-two@example.com"))
        self.assertEqual(other.status_code, 201, other.text)
        self.assertEqual(
            self.client.get(f"/api/donors/{other.json()['user']['donor_id']}/profile", headers=headers).status_code,
            403,
        )

    def test_duplicate_email_consent_and_password_rules_are_enforced(self) -> None:
        first = self.client.post("/api/auth/register", json=self._register("duplicate@example.com"))
        self.assertEqual(first.status_code, 201, first.text)
        duplicate = self.client.post("/api/auth/register", json=self._register("DUPLICATE@example.com"))
        self.assertEqual(duplicate.status_code, 409)

        no_consent = self.client.post("/api/auth/register", json=self._register("no-consent@example.com", consent=False))
        self.assertEqual(no_consent.status_code, 400)

        short_password = self.client.post("/api/auth/register", json=self._register("short@example.com", password="short"))
        self.assertEqual(short_password.status_code, 422)

    def test_registration_is_throttled_per_client(self) -> None:
        for index in range(auth.registration_throttle.max_per_client):
            response = self.client.post("/api/auth/register", json=self._register(f"throttle-{index}@example.com"))
            self.assertEqual(response.status_code, 201, response.text)
        blocked = self.client.post("/api/auth/register", json=self._register("throttle-blocked@example.com"))
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(int(blocked.headers["Retry-After"]), 0)


class FakeSMTP:
    sent: list = []
    fail = False
    logged_in = False

    def __init__(self, host: str, port: int, timeout: int | None = None) -> None:
        self.host = host
        self.port = port

    def ehlo(self) -> None:
        pass

    def starttls(self) -> None:
        pass

    def login(self, username: str, password: str) -> None:
        type(self).logged_in = True

    def send_message(self, message) -> None:
        if self.fail:
            raise smtplib.SMTPServerDisconnected("mailbox unavailable")
        self.sent.append(message)

    def quit(self) -> None:
        pass


class EmailOutreachTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        cls.session_factory = sessionmaker(bind=cls.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls.engine)
        with cls.session_factory.begin() as session:
            linked = Donor(
                name="Linked Donor", district="Amravati", blood_group="O+", age=30,
                last_donation_date=date.today() - timedelta(days=200), donations_count=3, response_rate=0.6,
            )
            unlinked = Donor(
                name="Unlinked Donor", district="Amravati", blood_group="O+", age=31,
                last_donation_date=date.today() - timedelta(days=200), donations_count=2, response_rate=0.5,
            )
            session.add_all([linked, unlinked])
            session.add(Inventory(
                district="Amravati", blood_group="O+", units_available=2,
                avg_daily_demand=3.0, safety_stock_units=30,
            ))
            session.flush()
            session.add_all([
                User(email="admin@example.com", password_hash=hash_password("admin-test-password-123"), role="admin"),
                User(email="linked@example.com", password_hash=hash_password("linked-test-password-123"), role="donor", donor_id=linked.id),
            ])
            cls.linked_id, cls.unlinked_id = linked.id, unlinked.id

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
        FakeSMTP.sent = []
        FakeSMTP.fail = False
        FakeSMTP.logged_in = False
        self.client = TestClient(app)
        self.client.__enter__()
        login = self.client.post("/api/auth/login", json={
            "email": "admin@example.com", "password": "admin-test-password-123",
        })
        self.assertEqual(login.status_code, 200, login.text)
        self.admin = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def _campaign(self) -> dict:
        response = self.client.post("/api/campaigns", headers=self.admin, json={
            "district": "Amravati", "blood_group": "O+", "stage": 1, "batch_size": 5,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_campaign_emails_only_donors_with_linked_logins(self) -> None:
        smtp_settings = dict(
            SMTP_ENABLED=True,
            SMTP_HOST="smtp.example.org",
            SMTP_PORT=587,
            SMTP_USERNAME="mailer@example.org",
            SMTP_PASSWORD="smtp-password",
            SMTP_FROM="bloodbank@example.org",
            SMTP_FROM_NAME="RaktSanket Test",
            SMTP_USE_TLS=True,
            SMTP_USE_SSL=False,
            SMTP_TIMEOUT_SECONDS=5,
        )
        with patch.multiple(settings, **smtp_settings), patch.object(email_service.smtplib, "SMTP", FakeSMTP):
            campaign = self._campaign()

        self.assertEqual(campaign["status"], "partially emailed")
        self.assertEqual(campaign["recipients_count"], 2)
        self.assertEqual(campaign["emailed_count"], 1)
        self.assertEqual(campaign["email_failed_count"], 0)
        self.assertTrue(campaign["email_configured"])
        self.assertEqual(len(FakeSMTP.sent), 1)
        self.assertEqual(FakeSMTP.sent[0]["To"], "linked@example.com")
        self.assertIn("O+", FakeSMTP.sent[0]["Subject"])
        self.assertTrue(FakeSMTP.logged_in)

        with self.session_factory() as session:
            statuses = {
                notification.donor_id: notification.status
                for notification in session.scalars(select(Notification).where(Notification.campaign_id == campaign["id"]))
            }
        self.assertEqual(statuses[self.linked_id], "emailed")
        self.assertEqual(statuses[self.unlinked_id], "no email account")

        donor_login = self.client.post("/api/auth/login", json={
            "email": "linked@example.com", "password": "linked-test-password-123",
        })
        donor_headers = {"Authorization": f"Bearer {donor_login.json()['access_token']}"}
        notifications = self.client.get(f"/api/donors/{self.linked_id}/notifications", headers=donor_headers).json()
        self.assertEqual(notifications[0]["status"], "emailed")
        self.assertIn("sent to your registered address", notifications[0]["message"])

    def test_smtp_failure_marks_the_campaign_and_notifications(self) -> None:
        smtp_settings = dict(
            SMTP_ENABLED=True,
            SMTP_HOST="smtp.example.org",
            SMTP_PORT=587,
            SMTP_USERNAME="",
            SMTP_PASSWORD="",
            SMTP_FROM="bloodbank@example.org",
            SMTP_FROM_NAME="RaktSanket Test",
            SMTP_USE_TLS=True,
            SMTP_USE_SSL=False,
            SMTP_TIMEOUT_SECONDS=5,
        )
        FakeSMTP.fail = True
        with patch.multiple(settings, **smtp_settings), patch.object(email_service.smtplib, "SMTP", FakeSMTP):
            campaign = self._campaign()

        self.assertEqual(campaign["status"], "email failed")
        self.assertEqual(campaign["emailed_count"], 0)
        self.assertEqual(campaign["email_failed_count"], 1)
        with self.session_factory() as session:
            statuses = {
                notification.donor_id: notification.status
                for notification in session.scalars(select(Notification).where(Notification.campaign_id == campaign["id"]))
            }
        self.assertEqual(statuses[self.linked_id], "email failed")

    def test_without_smtp_the_campaign_stays_simulated(self) -> None:
        self.assertFalse(email_service.email_configured())
        campaign = self._campaign()
        self.assertEqual(campaign["status"], "simulated")
        self.assertFalse(campaign["email_configured"])
        self.assertEqual(campaign["emailed_count"], 0)
        with self.session_factory() as session:
            statuses = {
                notification.donor_id: notification.status
                for notification in session.scalars(select(Notification).where(Notification.campaign_id == campaign["id"]))
            }
        self.assertEqual(statuses[self.linked_id], "simulated")

    def test_email_status_endpoint_requires_admin(self) -> None:
        self.assertEqual(self.client.get("/api/admin/email-status").status_code, 401)
        response = self.client.get("/api/admin/email-status", headers=self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])


if __name__ == "__main__":
    unittest.main()
