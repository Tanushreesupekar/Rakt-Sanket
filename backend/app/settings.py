from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "staging", "production"}:
    raise RuntimeError("APP_ENV must be development, staging, or production")
IS_PRODUCTION = APP_ENV in {"staging", "production"}
DEMO_SEED = os.getenv("DEMO_SEED", "true" if not IS_PRODUCTION else "false").strip().lower() == "true"

# On Vercel the platform names the hostnames this deployment answers on, as
# system environment variables. A preview deployment gets a new URL on every
# push, so trusting exactly these keeps previews working without a wildcard;
# ALLOWED_HOSTS / FRONTEND_ORIGINS are then only needed for custom domains.
VERCEL_HOSTS: tuple[str, ...] = tuple(dict.fromkeys(
    host.strip()
    for host in (os.getenv("VERCEL_URL"), os.getenv("VERCEL_BRANCH_URL"), os.getenv("VERCEL_PROJECT_PRODUCTION_URL"))
    if host and host.strip()
)) if os.getenv("VERCEL") == "1" else ()

configured_origins = os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN"))
if configured_origins is None:
    configured_origins = "" if VERCEL_HOSTS else "http://localhost:5173"
FRONTEND_ORIGINS = tuple(dict.fromkeys((
    *(origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()),
    *(f"https://{host}" for host in VERCEL_HOSTS),
)))
if IS_PRODUCTION and (not FRONTEND_ORIGINS or any(not origin.startswith("https://") for origin in FRONTEND_ORIGINS)):
    raise RuntimeError("Production FRONTEND_ORIGINS must contain explicit deployed HTTPS origins")
ALLOWED_HOSTS = tuple(dict.fromkeys((
    *(host.strip() for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver" if not IS_PRODUCTION else "").split(",") if host.strip()),
    *VERCEL_HOSTS,
)))
if not IS_PRODUCTION and "testserver" not in ALLOWED_HOSTS:
    # Starlette TestClient sends host "testserver"; a local .env that
    # overrides ALLOWED_HOSTS must not break the test suite.
    ALLOWED_HOSTS = (*ALLOWED_HOSTS, "testserver")
if IS_PRODUCTION and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise RuntimeError("Production ALLOWED_HOSTS must be explicitly configured")

raw_database_url = os.getenv("DATABASE_URL")
if not raw_database_url:
    if IS_PRODUCTION:
        raise RuntimeError("DATABASE_URL must point to a managed PostgreSQL database in production")
    raw_database_url = "sqlite:///./rakt_sanket.db"

database_url = make_url(raw_database_url)
if database_url.drivername == "postgresql":
    database_url = database_url.set(drivername="postgresql+psycopg")
if IS_PRODUCTION:
    if not database_url.drivername.startswith("postgresql"):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL")
    query = dict(database_url.query)
    query["sslmode"] = "require"
    database_url = database_url.set(query=query)
DATABASE_URL = database_url.render_as_string(hide_password=False)

SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret-key")
if IS_PRODUCTION and (len(SECRET_KEY) < 32 or "replace-with" in SECRET_KEY or SECRET_KEY == "development-only-change-this-secret-key"):
    raise RuntimeError("SECRET_KEY must contain at least 32 characters in production")

ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
if ACCESS_TOKEN_MINUTES < 5 or ACCESS_TOKEN_MINUTES > 120:
    raise RuntimeError("ACCESS_TOKEN_MINUTES must be between 5 and 120")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# SMTP is optional. With no SMTP_HOST, outreach rounds stay simulated and the
# console shows that email delivery is not configured.
SMTP_ENABLED = _env_flag("SMTP_ENABLED", True)
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
if SMTP_PORT < 1 or SMTP_PORT > 65535:
    raise RuntimeError("SMTP_PORT must be between 1 and 65535")
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USERNAME
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "RaktSanket").strip() or "RaktSanket"
SMTP_USE_TLS = _env_flag("SMTP_USE_TLS", True)
SMTP_USE_SSL = _env_flag("SMTP_USE_SSL", False)
SMTP_TIMEOUT_SECONDS = int(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
if SMTP_USE_TLS and SMTP_USE_SSL:
    raise RuntimeError("Set either SMTP_USE_TLS or SMTP_USE_SSL, not both")
if SMTP_HOST and not SMTP_FROM:
    raise RuntimeError("SMTP_FROM (or SMTP_USERNAME) is required when SMTP_HOST is set")
if SMTP_TIMEOUT_SECONDS < 1 or SMTP_TIMEOUT_SECONDS > 120:
    raise RuntimeError("SMTP_TIMEOUT_SECONDS must be between 1 and 120")

API_DOCS_ENABLED = not IS_PRODUCTION or os.getenv("ENABLE_API_DOCS", "false").lower() == "true"