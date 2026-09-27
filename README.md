# RaktSanket

A pilot dashboard for district-level blood availability, donor response prioritisation, explainable shortage advisories, and staged donor activation.

## What is included

- React, TypeScript, and Vite dashboard with separate admin and donor workspaces. Admin views cover inventory, demand forecasts, donor management, CBSRI ranking, notifications, and analytics; donor views cover profile, blood requests, notifications, and donation history.
- FastAPI service for district inventory, 7–14 day projections, donor eligibility and fatigue-adjusted priority, advisory translations, and campaign simulation.
- SQLAlchemy persistence with SQLite for local demos and PostgreSQL for staging/production; Alembic owns deployed schema changes.
- Argon2 password hashing, short-lived signed bearer tokens, admin/donor role enforcement, donor-record ownership checks, and interactive first-admin provisioning.
- Synthetic demo records for Amravati, Akola, Wardha, and Yavatmal. Demo names are marked and do not represent real donors.
- A reproducible synthetic donor-response dataset and trained XGBoost model with TreeSHAP feature attributions.
- API, scoring, dataset-generation, and model-inference tests.

The Admin/Donor selector is available only in development demo mode. Production builds enable the sign-in flow and server-side role enforcement. Donor accounts are provisioned against donor records by an administrator. Identity verification, account recovery, consent evidence, SMS/email delivery, and clinical eligibility integrations still require deployment-specific implementation.

## Run locally on Windows

Use two PowerShell terminals from the repository root.

Backend terminal:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Set-Location backend
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The API is at `http://localhost:8000`; interactive API documentation is at `http://localhost:8000/docs`. The database file is created in `backend\rakt_sanket.db` on first startup.

Frontend terminal:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`.

On macOS or Linux, create and activate a virtual environment with `python3 -m venv .venv` and `source .venv/bin/activate`. Replace the PowerShell `Copy-Item` commands with `cp`.

## Configuration

The backend reads `backend/.env`. Local demo mode uses SQLite. Staging/production requires PostgreSQL, an explicit `SECRET_KEY`, `FRONTEND_ORIGINS`, and `ALLOWED_HOSTS`; use [backend/.env.production.example](backend/.env.production.example) as a variable checklist, not as a deployable file.

```dotenv
APP_ENV=production
DEMO_SEED=false
DATABASE_URL=postgresql+psycopg://user:password@managed-postgres-host:5432/raktsanket?sslmode=require
SECRET_KEY=<generate-and-store-a-random-secret-of-at-least-32-characters>
FRONTEND_ORIGINS=https://your-frontend-domain.example
ALLOWED_HOSTS=your-api-domain.example
```

The frontend reads the root `.env`; `VITE_API_URL=/api` uses the Vite development proxy. Production builds use [/.env.production.example](.env.production.example): set the deployed API origin and `VITE_AUTH_REQUIRED=true`, then build with `npm run build`.

## Staging and production

1. Provision a managed PostgreSQL database and deploy the API behind HTTPS. Store the actual `DATABASE_URL`, randomly generated `SECRET_KEY`, API host, and frontend origin in the hosting provider's secret/environment settings. Never commit populated `.env` files or real database credentials.
2. Set `APP_ENV=production`, `DEMO_SEED=false`, `FRONTEND_ORIGINS` to the exact HTTPS frontend origin, and `ALLOWED_HOSTS` to the API hostname. Startup refuses SQLite, missing signing keys, demo seeding, and wildcard/missing production hosts/origins.
3. Install backend dependencies, then run `python -m alembic upgrade head` as a release migration step before starting the service. Startup checks PostgreSQL connectivity and required migrated tables; it does not create or seed production tables.
4. Create the first administrator interactively with `python -m app.create_admin`; no default administrator credentials are shipped. Administrators can create donor login accounts through `POST /api/admin/donor-accounts`, linking each account to an existing donor record.
5. Set frontend `VITE_API_URL` and `VITE_AUTH_REQUIRED=true` at build time, deploy the static `dist/` output, and configure the API CORS allowlist to that exact origin. Route `/api` to FastAPI if using a same-origin deployment, or use the absolute API URL in the frontend setting.

To load the PDF-derived synthetic records into a database after migration, run `python -m app.import_example_data --district <district> --confirm-synthetic-data` from `backend`. This is an explicit, idempotent import; it preserves existing records and adds marked synthetic profiles, stock history, notification outcomes, and inventory summaries. Do not run it with real data unless you intentionally want synthetic records in that database.

`GET /api/health` is a liveness check; `GET /api/ready` checks database connectivity. Point the platform readiness probe at `/api/ready`. A real provider connection is not established in this workspace because the database URL, account secret, and deployment host are not available here.

## API surface

- `GET /api/health` — service status.
- `GET /api/dashboard?district=Amravati` — district totals, inventory, forecasts, prioritized donors, and recent campaigns.
- `GET /api/forecasts?district=Amravati&blood_group=O-&days=14` — forecast for 7–14 days.
- `GET /api/inventory?district=Amravati` and `PATCH /api/inventory/{id}` — read and update stock inputs.
- `GET /api/donors?district=Amravati&eligible_only=true` and `POST /api/donors` — donor records and ranking.
- `GET /api/campaigns` and `POST /api/campaigns` — staged contact-list simulation; no message is sent.
- `GET /api/advisories?district=Amravati&language=mr` — English (`en`), Hindi (`hi`), or Marathi (`mr`) advisory.
- `GET/PATCH /api/donors/{id}/profile`, `GET /api/donors/{id}/notifications`, and `GET /api/donors/{id}/history` — donor portal records.
- `GET /api/blood-requests?donor_id={id}` and `POST /api/blood-requests` — blood request submission and history, pending operator review.
- `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/admin/donor-accounts` — production sign-in, session identity, and donor-account provisioning.

## Validation

```powershell
Set-Location backend
python -m unittest discover -s tests -v
Set-Location ..
npm run build
```

## Donor response AI

The generated training data is at `backend/data/donor_response_synthetic.csv` (8,000 rows, fixed seed `2026`); the Excel workbook version is `backend/data/donor_response_synthetic.xlsx` and includes a data dictionary and dataset notes. Each row represents an invitation and contains non-identifying historical features plus `accepted_invitation`, a simulated outcome. It is generated with a known, documented-in-code probability process and must not be treated as observed donor behavior.

The trained artifact and holdout metrics are at `backend/models/donor_response_xgb.json` and `backend/models/donor_response_metrics.json`. To regenerate the dataset and retrain from the backend directory:

```powershell
python -m app.ml.train --regenerate --rows 8000 --seed 2026
```

The trainer sorts by invitation date and reserves later dates for the test partition. Current synthetic holdout metrics are ROC AUC `0.6755`, accuracy `0.7298`, and Brier score `0.1838`; the metadata records the exact date boundary. These describe recovery of the synthetic label process only and are not estimates of real-world donor response. The API uses the trained model when the artifact is present, applies contact-fatigue adjustment separately, and returns the top model factors using XGBoost TreeSHAP contributions. If the model file is absent, donor ranking falls back to the documented heuristic.

## Full example-schema dataset

The reference-PDF-based dataset is in `backend/data/raktsanket_full_dataset.xlsx`, with separate CSV exports: `blood_stock_demand_full.csv`, `donors_full.csv`, and `notifications_full.csv`. The workbook has one sheet per source table, a data dictionary, and dataset notes. It retains the 20 example records from the PDF at the beginning of each table; generated notification records link to donor IDs, and alert/response totals reconcile with each donor row. The default generator creates 1,000 stock rows, 1,000 donors, and more than 1,000 notification events.

Regenerate from the backend directory:

```powershell
python -m app.ml.reference_dataset --rows 1000 --seed 2026
```

All added rows are synthetic demonstrations, not verified bank, donor, or contact data. This relational example dataset is separate from the donor-response model training CSV above.

## Model and data boundaries

This repository is a production-configurable pilot foundation, not a clinically validated system. It includes a trained XGBoost donor-response classifier, but its training labels are synthetic. The active shortage forecast is still a transparent weekday-adjusted demand projection because no historical stock series was supplied. CBSRI uses explicit, configurable default weights (0.45 shortage, 0.30 response, 0.25 fatigue-adjusted priority), normalized at runtime; these weights are not statistically derived.

Before medical operations, replace synthetic donor training labels and demo seed records with approved, de-identified observations; calibrate and back-test forecasts against documented shortage periods and a moving-average baseline; retrain and evaluate the donor model on a date-separated real dataset; and derive CBSRI weights from the historical event set. Authentication and database role checks are implemented, but this workspace has not been connected to an organization-hosted PostgreSQL instance. SMS delivery, donor account recovery, consent evidence, and clinical eligibility remain unconfigured. Human review remains mandatory for every contact decision.
#   R a k t - S a n k e t  
 