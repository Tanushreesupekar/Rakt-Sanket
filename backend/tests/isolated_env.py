"""Pin the test environment before `app.settings` reads backend/.env.

Every test module imports this first. Without it, a developer's local .env
(for example APP_ENV=production with a hosted PostgreSQL URL) leaks into the
suite: the trusted-host check rejects the test client and the app's startup
probe connects to the real database. Values set here win because
python-dotenv never overrides variables that are already set.
"""
import os

os.environ.update({
    "APP_ENV": "development",
    "DEMO_SEED": "true",
    "DATABASE_URL": "sqlite://",
    "ALLOWED_HOSTS": "localhost,127.0.0.1,testserver",
    "FRONTEND_ORIGINS": "http://localhost:5173",
    "SECRET_KEY": "unit-test-only-secret-key-not-for-deployment",
    "ACCESS_TOKEN_MINUTES": "30",
})
