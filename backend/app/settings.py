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
FRONTEND_ORIGINS = tuple(
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")).split(",")
    if origin.strip()
)
if IS_PRODUCTION and (not FRONTEND_ORIGINS or any(not origin.startswith("https://") for origin in FRONTEND_ORIGINS)):
    raise RuntimeError("Production FRONTEND_ORIGINS must contain explicit deployed HTTPS origins")
ALLOWED_HOSTS = tuple(
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver" if not IS_PRODUCTION else "").split(",")
    if host.strip()
)
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

API_DOCS_ENABLED = not IS_PRODUCTION or os.getenv("ENABLE_API_DOCS", "false").lower() == "true"