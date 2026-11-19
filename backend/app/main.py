from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.auth import authorize_donor_access, create_access_token, get_current_user, hash_password, login_throttle, registration_throttle, require_admin, verify_login
from app.database import SessionLocal, engine, get_db
from app.ml.donor_response import model_status
from app.models import BloodRequest, Campaign, Donor, Inventory, Notification, User
from app.schemas import AdminBloodRequestOut, AdvisoryOut, AuthUserOut, BloodRequestCreate, BloodRequestOut, BloodRequestReview, DonorAccountOut, CampaignCreate, CampaignOut, DonorAccountCreate, DonorCreate, DonorOut, DonorProfileUpdate, DonorRegister, DonationHistoryOut, EmailStatusOut, ForecastOut, InventoryOut, InventoryUpdate, LoginOut, LoginRequest
from app.seed import seed_demo_data
from app.settings import ACCESS_TOKEN_MINUTES, ALLOWED_HOSTS, API_DOCS_ENABLED, APP_ENV, DEMO_SEED, FRONTEND_ORIGINS, IS_PRODUCTION
from app.services.email import build_campaign_email, email_configured, send_emails, sender_address, send_test_email
from app.services.forecasting import build_forecast, shortage_score
from app.services.ranking import rank_donors
from app.services.scoring import active_weights, compute_cbsri, risk_label


@asynccontextmanager
async def lifespan(_: FastAPI):
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    if DEMO_SEED:
        if IS_PRODUCTION:
            raise RuntimeError("DEMO_SEED must be disabled in production")
        from app.models import Base

        Base.metadata.create_all(bind=engine)
    else:
        # Auto-run alembic migrations on every startup so Vercel deployments
        # stay in sync with the latest schema without a manual migration step.
        try:
            from alembic.config import Config
            from alembic import command as alembic_command
            import os
            alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
            alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
            alembic_command.upgrade(alembic_cfg, "head")
        except Exception as _migration_err:
            # Non-fatal: migrations may have already been applied or alembic not available.
            pass
        with engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
        required_tables = {"users", "donors", "inventory", "campaigns", "notifications", "blood_requests", "alembic_version"}
        if not required_tables.issubset(table_names):
            raise RuntimeError("Database schema is missing; run `alembic upgrade head` before starting the API")
    with SessionLocal() as session:
        if DEMO_SEED:
            seed_demo_data(session)
    yield


app = FastAPI(
    title="RaktSanket API",
    version="0.1.0",
    description="Pilot API for explainable blood shortage forecasting and donor activation.",
    docs_url="/docs" if API_DOCS_ENABLED else None,
    redoc_url="/redoc" if API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if API_DOCS_ENABLED else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not IS_PRODUCTION else list(FRONTEND_ORIGINS),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
if IS_PRODUCTION:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS))
else:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if IS_PRODUCTION and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "raktsanket-api", "mode": APP_ENV, "donor_response_model": model_status()}


@app.get("/api/ready")
def readiness(session: Session = Depends(get_db)):
    session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected", "environment": APP_ENV}


@app.get("/api/model-status")
def model_health(_: User | None = Depends(require_admin)):
    return model_status()


@app.post("/api/auth/login", response_model=LoginOut)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_db)):
    email = payload.email.strip().casefold()
    client = request.client.host if request.client else "unknown"
    wait = login_throttle.retry_after(email, client)
    if wait:
        raise HTTPException(status_code=429, detail="Too many failed sign-in attempts. Try again later.", headers={"Retry-After": str(wait)})
    user = session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if not verify_login(user, payload.password):
        login_throttle.record_failure(email, client)
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    login_throttle.record_success(email)
    return _session_payload(user)


def _session_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "user": {"id": user.id, "email": user.email, "role": user.role, "donor_id": user.donor_id},
    }


@app.post("/api/auth/register", response_model=LoginOut, status_code=201)
def register_donor(payload: DonorRegister, request: Request, session: Session = Depends(get_db)):
    """Public donor self-registration.

    Creates a donor record and its login together, then signs the donor in.
    Existing donor records provisioned by a blood bank are linked through the
    admin console, not claimed through this endpoint."""
    client = request.client.host if request.client else "unknown"
    wait = registration_throttle.retry_after(client)
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many account registrations from this network. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    registration_throttle.record(client)
    if not payload.consent:
        raise HTTPException(status_code=400, detail="Consent to be contacted about blood donation is required")
    normalized_email = payload.email.strip().casefold()
    if session.scalar(select(User.id).where(User.email == normalized_email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists. Sign in instead.")
    donor = Donor(
        name=payload.name.strip(),
        district=payload.district.strip(),
        blood_group=payload.blood_group,
        age=payload.age,
        last_donation_date=payload.last_donation_date,
        donations_count=payload.donations_count,
        response_rate=0.5,
        notifications_30d=0,
        available=True,
    )
    session.add(donor)
    session.flush()
    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role="donor",
        donor_id=donor.id,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _session_payload(user)


@app.get("/api/auth/me", response_model=AuthUserOut)
def current_account(user: User | None = Depends(get_current_user)):
    if user is None:
        return {"id": 0, "email": "demo@localhost", "role": "admin", "donor_id": None}
    return user


@app.post("/api/auth/switch-role", response_model=LoginOut)
def switch_role(target_role: str = Query(..., pattern="^(admin|donor)$"), user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    if IS_PRODUCTION:
        raise HTTPException(status_code=403, detail="Role switching is disabled in production")
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user.role = target_role
    session.commit()
    session.refresh(user)
    return _session_payload(user)


@app.get("/api/admin/donor-accounts", response_model=list[DonorAccountOut])
def donor_accounts(_: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    """Donor logins, so the console can show which donor records have one."""
    return session.scalars(select(User).where(User.role == "donor").order_by(User.created_at)).all()


@app.post("/api/admin/donor-accounts", response_model=AuthUserOut, status_code=201)
def create_donor_account(
    payload: DonorAccountCreate,
    _: User | None = Depends(require_admin),
    session: Session = Depends(get_db),
):
    donor = session.get(Donor, payload.donor_id)
    if donor is None:
        raise HTTPException(status_code=404, detail="Donor record not found")
    normalized_email = payload.email.strip().casefold()
    if session.scalar(select(User.id).where(User.email == normalized_email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    if session.scalar(select(User.id).where(User.donor_id == payload.donor_id)):
        raise HTTPException(status_code=409, detail="This donor already has a login account")
    user = User(email=normalized_email, password_hash=hash_password(payload.password), role="donor", donor_id=donor.id)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.get("/api/admin/email-status", response_model=EmailStatusOut)
def admin_email_status(_: User | None = Depends(require_admin)):
    """Lets the outreach screen show whether campaigns will send email."""
    return {"configured": email_configured(), "from_address": sender_address()}


@app.post("/api/admin/test-email")
def admin_test_email(payload: dict | None = None, user: User | None = Depends(require_admin)):
    """Sends a diagnostic test email to verify SMTP credentials."""
    from app import settings
    target = None
    if payload and isinstance(payload, dict):
        target = payload.get("to_email")
    if not target and user:
        target = user.email
    if not target:
        target = settings.SMTP_FROM
    if not target:
        raise HTTPException(status_code=400, detail="No destination email provided and no sender email configured.")
    success, msg = send_test_email(target.strip())
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}


# Donor rankings run the XGBoost model, so endpoints rank each donor once per
# request (rank_donors batches the model call) and pass the results down.
GroupRankings = dict[tuple[str, str], list[dict]]


def rank_by_id(donors) -> dict[int, dict]:
    return {donor.id: ranking for donor, ranking in zip(donors, rank_donors(donors))}


def rankings_by_group(donors, ranked: dict[int, dict]) -> GroupRankings:
    groups: GroupRankings = {}
    for donor in donors:
        groups.setdefault((donor.district, donor.blood_group), []).append(ranked[donor.id])
    return groups


def group_rankings_for(session: Session, items) -> GroupRankings:
    """Rank every donor relevant to `items` with one batched model call."""
    districts = {item.district for item in items}
    if not districts:
        return {}
    donors = session.scalars(select(Donor).where(Donor.district.in_(districts))).all()
    groups = rankings_by_group(donors, rank_by_id(donors))
    for item in items:
        groups.setdefault((item.district, item.blood_group), [])
    return groups


def calculate_group_scores(session: Session, inventory: Inventory, horizon_days: int = 14, rankings: GroupRankings | None = None) -> dict:
    key = (inventory.district, inventory.blood_group)
    if rankings is not None and key in rankings:
        ranked = rankings[key]
    else:
        donors = session.scalars(select(Donor).where(
            Donor.district == inventory.district,
            Donor.blood_group == inventory.blood_group,
        )).all()
        ranked = rank_donors(donors)
    eligible = [entry for entry in ranked if entry["eligible"]]
    strongest = sorted(eligible, key=lambda entry: entry["priority_score"], reverse=True)[:5]
    response_score = round(sum(entry["response_probability"] for entry in strongest) / len(strongest) * 100, 1) if strongest else 0.0
    priority_score = round(sum(entry["priority_score"] for entry in strongest) / len(strongest), 1) if strongest else 0.0
    forecast_score = shortage_score(inventory, horizon_days)
    cbsri = compute_cbsri(forecast_score, response_score, priority_score, active_weights())
    return {
        "shortage_score": forecast_score,
        "response_score": response_score,
        "fatigue_adjusted_priority_score": priority_score,
        "cbsri": cbsri,
        "risk_level": risk_label(cbsri),
        "eligible_donor_count": len(eligible),
    }


def inventory_out(session: Session, item: Inventory, scores: dict | None = None) -> dict:
    scores = scores or calculate_group_scores(session, item)
    return {
        "id": item.id,
        "district": item.district,
        "blood_group": item.blood_group,
        "units_available": item.units_available,
        "avg_daily_demand": item.avg_daily_demand,
        "safety_stock_units": item.safety_stock_units,
        "days_of_supply": round(item.units_available / item.avg_daily_demand, 1),
        "shortage_score": scores["shortage_score"],
        "risk_level": scores["risk_level"],
        "cbsri": scores["cbsri"],
        "response_score": scores["response_score"],
        "eligible_donor_count": scores["eligible_donor_count"],
    }


def donor_out(donor: Donor, ranking: dict | None = None) -> dict:
    ranking = ranking or rank_donors([donor])[0]
    return {
        "id": donor.id,
        "name": donor.name,
        "district": donor.district,
        "blood_group": donor.blood_group,
        "age": donor.age,
        "last_donation_date": donor.last_donation_date,
        "donations_count": donor.donations_count,
        "response_rate": donor.response_rate,
        "notifications_30d": donor.notifications_30d,
        "last_contact_at": donor.last_contact_at,
        "available": donor.available,
        "eligible": ranking["eligible"],
        "priority_score": ranking["priority_score"],
        "response_probability": ranking["response_probability"],
        "explanation": ranking["explanation"],
    }


def build_forecast_out(session: Session, item: Inventory, days: int, scores: dict | None = None) -> dict:
    scores = scores or calculate_group_scores(session, item, days)
    points = build_forecast(item, days)
    final_units = points[-1]["projected_units"]
    explanation = (
        f"{item.units_available} units are available against {item.avg_daily_demand:.1f} units of average daily demand. "
        f"The {days}-day projection ends at {final_units:.1f} units; "
        f"{scores['eligible_donor_count']} eligible donors are available in this group."
    )
    return {
        "district": item.district,
        "blood_group": item.blood_group,
        "horizon_days": days,
        "current_units": item.units_available,
        "avg_daily_demand": item.avg_daily_demand,
        "safety_stock_units": item.safety_stock_units,
        "cbsri": scores["cbsri"],
        "response_score": scores["response_score"],
        "fatigue_adjusted_priority_score": scores["fatigue_adjusted_priority_score"],
        "explanation": explanation,
        "points": points,
    }


@app.get("/api/dashboard")
def dashboard(district: str | None = None, _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    districts = sorted({
        *session.scalars(select(Inventory.district).distinct()).all(),
        *session.scalars(select(Donor.district).distinct()).all(),
        *session.scalars(select(BloodRequest.district).distinct()).all(),
    }, key=str.casefold)
    inventory_districts = session.scalars(select(Inventory.district).distinct().order_by(Inventory.district)).all()
    default_district = inventory_districts[0] if inventory_districts else (districts[0] if districts else None)
    selected_district = district.strip() if district and district.strip() else default_district
    query = select(Inventory).where(Inventory.district == selected_district) if selected_district else select(Inventory)
    items = session.scalars(query.order_by(Inventory.blood_group)).all()
    donor_query = select(Donor).where(Donor.district == selected_district) if selected_district else select(Donor)
    donors = session.scalars(donor_query).all()
    ranked = rank_by_id(donors)
    groups = rankings_by_group(donors, ranked)
    # inventory cards and forecasts share the 14-day horizon, so score once
    scores = {item.id: calculate_group_scores(session, item, 14, groups) for item in items}
    stocks = [inventory_out(session, item, scores[item.id]) for item in items]
    donor_cards = sorted((donor_out(donor, ranked[donor.id]) for donor in donors), key=lambda entry: entry["priority_score"], reverse=True)
    campaigns = session.scalars(select(Campaign).order_by(Campaign.created_at.desc()).limit(5)).all()
    return {
        "generated_at": datetime.now(timezone.utc),
        "districts": districts,
        "selected_district": selected_district,
        "totals": {
            "inventory_units": sum(item["units_available"] for item in stocks),
            "donor_count": len(donors),
            "eligible_donors": sum(1 for donor in donor_cards if donor["eligible"]),
            "at_risk_groups": sum(1 for item in stocks if item["risk_level"] != "stable"),
            "critical_groups": sum(1 for item in stocks if item["risk_level"] == "critical"),
        },
        "inventory": stocks,
        "forecasts": [build_forecast_out(session, item, 14, scores[item.id]) for item in items],
        "top_donors": [donor for donor in donor_cards if donor["eligible"]][:8],
        "recent_campaigns": [campaign_out(session, item) for item in campaigns],
    }


@app.get("/api/forecasts", response_model=list[ForecastOut])
def forecasts(
    district: str | None = None,
    blood_group: str | None = None,
    days: int = Query(default=14, ge=7, le=14),
    _: User | None = Depends(require_admin),
    session: Session = Depends(get_db),
):
    query = select(Inventory)
    if district:
        query = query.where(Inventory.district == district)
    if blood_group:
        query = query.where(Inventory.blood_group == blood_group)
    items = session.scalars(query.order_by(Inventory.district, Inventory.blood_group)).all()
    if not items:
        raise HTTPException(status_code=404, detail="No inventory found for the selected district and blood group")
    groups = group_rankings_for(session, items)
    return [build_forecast_out(session, item, days, calculate_group_scores(session, item, days, groups)) for item in items]


@app.get("/api/inventory", response_model=list[InventoryOut])
def inventory(district: str | None = None, _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    query = select(Inventory)
    if district:
        query = query.where(Inventory.district == district)
    items = session.scalars(query.order_by(Inventory.district, Inventory.blood_group)).all()
    groups = group_rankings_for(session, items)
    return [inventory_out(session, item, calculate_group_scores(session, item, rankings=groups)) for item in items]


@app.patch("/api/inventory/{inventory_id}")
def update_inventory(inventory_id: int, payload: InventoryUpdate, _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    item = session.get(Inventory, inventory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    item.units_available = payload.units_available
    item.avg_daily_demand = payload.avg_daily_demand
    item.safety_stock_units = payload.safety_stock_units
    item.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(item)
    return inventory_out(session, item)


@app.get("/api/donors", response_model=list[DonorOut])
def donors(
    district: str | None = None,
    blood_group: str | None = None,
    eligible_only: bool = False,
    _: User | None = Depends(require_admin),
    session: Session = Depends(get_db),
):
    query = select(Donor)
    if district:
        query = query.where(Donor.district == district)
    if blood_group:
        query = query.where(Donor.blood_group == blood_group)
    found = session.scalars(query.order_by(Donor.id)).all()
    entries = [donor_out(donor, ranking) for donor, ranking in zip(found, rank_donors(found))]
    if eligible_only:
        entries = [entry for entry in entries if entry["eligible"]]
    entries.sort(key=lambda entry: entry["priority_score"], reverse=True)
    return entries


@app.post("/api/donors", response_model=DonorOut, status_code=201)
def create_donor(payload: DonorCreate, _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    donor = Donor(**payload.model_dump())
    session.add(donor)
    session.commit()
    session.refresh(donor)
    return donor_out(donor)


@app.get("/api/donors/{donor_id}/profile")
def donor_profile(donor_id: int, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(donor_id, user)
    donor = session.get(Donor, donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    return donor_out(donor)


@app.patch("/api/donors/{donor_id}/profile")
def update_donor_profile(donor_id: int, payload: DonorProfileUpdate, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(donor_id, user)
    donor = session.get(Donor, donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    donor.name = payload.name
    donor.age = payload.age
    donor.available = payload.available
    session.commit()
    session.refresh(donor)
    return donor_out(donor)


@app.get("/api/donors/{donor_id}/notifications")
def donor_notifications(donor_id: int, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(donor_id, user)
    donor = session.get(Donor, donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    entries = session.execute(
        select(Notification, Campaign)
        .join(Campaign, Notification.campaign_id == Campaign.id)
        .where(Notification.donor_id == donor_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [{
        "id": notification.id,
        "created_at": notification.created_at,
        "blood_group": campaign.blood_group,
        "district": campaign.district,
        "stage": campaign.stage,
        "cbsri": campaign.cbsri,
        "status": notification.status,
        "message": (
            f"An email about this {campaign.blood_group} donor activation in {campaign.district} "
            "was sent to your registered address."
            if notification.status == "emailed"
            else f"Email delivery failed for this {campaign.blood_group} donor activation in "
                 f"{campaign.district}. The request is still recorded in your portal."
            if notification.status == "email failed"
            else f"A {campaign.blood_group} donor activation was recorded for {campaign.district}. "
                 "No email was sent for this notification."
        ),
    } for notification, campaign in entries]


@app.get("/api/donors/{donor_id}/history", response_model=DonationHistoryOut)
def donor_history(donor_id: int, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(donor_id, user)
    donor = session.get(Donor, donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    notification_count = session.scalar(
        select(func.count()).select_from(Notification).where(Notification.donor_id == donor_id)
    ) or 0
    interval_days = None
    if donor.last_donation_date:
        interval_days = max(0, (date.today() - donor.last_donation_date).days)
    return {
        "donations_count": donor.donations_count,
        "last_donation_date": donor.last_donation_date,
        "donation_interval_days": interval_days,
        "notifications_received": notification_count,
    }


@app.get("/api/blood-requests", response_model=list[BloodRequestOut])
def blood_requests(donor_id: int, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(donor_id, user)
    if not session.get(Donor, donor_id):
        raise HTTPException(status_code=404, detail="Donor profile not found")
    requests = session.scalars(
        select(BloodRequest).where(BloodRequest.donor_id == donor_id).order_by(BloodRequest.created_at.desc())
    ).all()
    return requests


@app.post("/api/blood-requests", response_model=BloodRequestOut, status_code=201)
def create_blood_request(payload: BloodRequestCreate, user: User | None = Depends(get_current_user), session: Session = Depends(get_db)):
    authorize_donor_access(payload.donor_id, user)
    donor = session.get(Donor, payload.donor_id)
    if not donor:
        raise HTTPException(status_code=404, detail="Donor profile not found")
    request = BloodRequest(**payload.model_dump())
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


# Which review decisions each request status allows. Fulfilled and rejected
# are final, so a closed request cannot be reopened by accident.
REVIEW_TRANSITIONS = {
    "pending review": {"approved", "rejected"},
    "approved": {"fulfilled", "rejected"},
}


def admin_request_out(request: BloodRequest, donor_name: str) -> dict:
    return {**BloodRequestOut.model_validate(request, from_attributes=True).model_dump(), "donor_name": donor_name}


@app.get("/api/admin/blood-requests", response_model=list[AdminBloodRequestOut])
def admin_blood_requests(
    district: str | None = None,
    status: str | None = None,
    _: User | None = Depends(require_admin),
    session: Session = Depends(get_db),
):
    query = select(BloodRequest, Donor.name).join(Donor, BloodRequest.donor_id == Donor.id)
    if district and district.strip():
        # donors type the district themselves, so match it case-insensitively
        query = query.where(func.lower(BloodRequest.district) == district.strip().lower())
    if status:
        query = query.where(BloodRequest.status == status)
    rows = session.execute(query.order_by(BloodRequest.created_at.desc()).limit(500)).all()
    return [admin_request_out(request, name) for request, name in rows]


@app.patch("/api/admin/blood-requests/{request_id}", response_model=AdminBloodRequestOut)
def review_blood_request(
    request_id: int,
    payload: BloodRequestReview,
    _: User | None = Depends(require_admin),
    session: Session = Depends(get_db),
):
    request = session.get(BloodRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Blood request not found")
    if payload.status not in REVIEW_TRANSITIONS.get(request.status, set()):
        raise HTTPException(status_code=409, detail=f"A request that is {request.status} cannot be marked {payload.status}")
    request.status = payload.status
    request.reviewed_at = datetime.now(timezone.utc)
    if payload.note is not None and payload.note.strip():
        request.admin_note = payload.note.strip()
    session.commit()
    session.refresh(request)
    donor = session.get(Donor, request.donor_id)
    return admin_request_out(request, donor.name if donor else "Unknown donor")


def campaign_out(session: Session, campaign: Campaign) -> dict:
    names = session.scalars(select(Donor.name).join(Notification).where(Notification.campaign_id == campaign.id)).all()
    status_counts = dict(session.execute(
        select(Notification.status, func.count())
        .where(Notification.campaign_id == campaign.id)
        .group_by(Notification.status)
    ).all())
    return {
        "id": campaign.id,
        "district": campaign.district,
        "blood_group": campaign.blood_group,
        "stage": campaign.stage,
        "recipients_count": campaign.recipients_count,
        "cbsri": campaign.cbsri,
        "status": campaign.status,
        "created_at": campaign.created_at,
        "donor_names": names,
        "emailed_count": status_counts.get("emailed", 0),
        "email_failed_count": status_counts.get("email failed", 0),
        "email_configured": email_configured(),
    }


@app.get("/api/campaigns", response_model=list[CampaignOut])
def campaigns(_: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    items = session.scalars(select(Campaign).order_by(Campaign.created_at.desc()).limit(30)).all()
    return [campaign_out(session, item) for item in items]


@app.post("/api/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    inventory_item = session.scalar(select(Inventory).where(
        func.lower(Inventory.district) == payload.district.lower(),
        Inventory.blood_group == payload.blood_group,
    ))
    if not inventory_item:
        raise HTTPException(status_code=404, detail="No inventory found for that district and blood group")

    candidates = session.scalars(select(Donor).where(
        func.lower(Donor.district) == payload.district.lower(),
        Donor.blood_group == payload.blood_group,
    )).all()
    if not candidates and payload.blood_group != "ALL":
        candidates = session.scalars(select(Donor).where(Donor.blood_group == payload.blood_group)).all()
    if not candidates:
        candidates = session.scalars(select(Donor)).all()

    ranked = rank_by_id(candidates)
    eligible = [donor for donor in candidates if ranked[donor.id]["eligible"]]
    # If all candidates are filtered out by interval, include all candidates so outreach still works simply
    selected = eligible if eligible else candidates
    if payload.batch_size and payload.batch_size < len(selected):
        selected = selected[:payload.batch_size]

    # Include all active registered donor accounts so every donor with an email gets notified
    donor_users = session.scalars(select(User).where(User.role == "donor", User.is_active.is_(True))).all()
    donor_user_map = {u.donor_id: u.email for u in donor_users if u.donor_id is not None}
    for u in donor_users:
        if u.donor_id:
            d = session.get(Donor, u.donor_id)
            if d and d not in selected:
                selected.append(d)

    scores = calculate_group_scores(session, inventory_item, rankings=rankings_by_group(candidates, ranked)) if candidates else {"cbsri": 70.0}

    accounts = session.scalars(select(User).where(
        User.donor_id.in_([donor.id for donor in selected]),
        User.is_active.is_(True),
    )).all() if selected else []
    linked_emails = {account.donor_id: account.email for account in accounts if account.donor_id is not None}
    linked_emails.update(donor_user_map)
    smtp_ready = email_configured()

    if not selected:
        initial_status = "no recipients"
    elif not smtp_ready:
        initial_status = "simulated"
    elif linked_emails:
        initial_status = "queued"
    else:
        initial_status = "no linked emails"

    campaign = Campaign(
        district=payload.district,
        blood_group=payload.blood_group,
        stage=payload.stage,
        recipients_count=len(selected),
        cbsri=scores["cbsri"],
        status=initial_status,
    )
    session.add(campaign)
    session.flush()
    now = datetime.now(timezone.utc)
    for donor in selected:
        donor.notifications_30d += 1
        donor.last_contact_at = now
        if not smtp_ready:
            notification_status = "simulated"
        elif donor.id in linked_emails:
            notification_status = "queued"
        else:
            notification_status = "no email account"
        session.add(Notification(campaign_id=campaign.id, donor_id=donor.id, status=notification_status))
    session.commit()
    session.refresh(campaign)

    if smtp_ready and linked_emails:
        outbound = [
            build_campaign_email(
                to=linked_emails[donor.id],
                donor_name=donor.name,
                blood_group=campaign.blood_group,
                district=campaign.district,
                stage=campaign.stage,
                cbsri=campaign.cbsri,
            )
            for donor in selected
            if donor.id in linked_emails
        ]
        result = send_emails(outbound)
        sent_recipients = set(result.sent_recipients)
        failed_recipients = set(result.failed_recipients)
        notifications = session.scalars(
            select(Notification).where(Notification.campaign_id == campaign.id)
        ).all()
        for notification in notifications:
            email = linked_emails.get(notification.donor_id)
            if email in sent_recipients:
                notification.status = "emailed"
            elif email in failed_recipients:
                notification.status = "email failed"
        if result.sent == len(selected):
            campaign.status = "email sent"
        elif result.sent:
            campaign.status = "partially emailed"
        else:
            campaign.status = "email failed"
        session.commit()
        session.refresh(campaign)

    return campaign_out(session, campaign)


ADVISORIES = {
    "en": {
        "critical": ("Urgent stock gap ahead", "Forecasted demand is likely to take stock below the safety level within 14 days.", "Review the forecast and begin the first donor activation tier."),
        "elevated": ("Plan donor outreach", "One or more blood groups are trending toward their safety stock threshold.", "Review donor priority and prepare a staged outreach round."),
        "stable": ("Stock outlook is steady", "Current stock is projected to remain near or above the safety level.", "Continue daily monitoring and keep donor records current."),
    },
    "hi": {
        "critical": ("आने वाली रक्त-कमी पर ध्यान दें", "पूर्वानुमान के अनुसार 14 दिनों में भंडार सुरक्षा स्तर से नीचे जा सकता है।", "पूर्वानुमान देखें और पहले चरण के दाता संपर्क की तैयारी करें।"),
        "elevated": ("दाता संपर्क की योजना बनाएं", "कुछ रक्त समूहों का भंडार सुरक्षा सीमा की ओर घट रहा है।", "दाता प्राथमिकता देखें और चरणबद्ध संपर्क तैयार करें।"),
        "stable": ("भंडार की स्थिति स्थिर है", "वर्तमान भंडार सुरक्षा स्तर के आसपास या ऊपर रहने का अनुमान है।", "दैनिक निगरानी जारी रखें और दाता रिकॉर्ड अपडेट रखें।"),
    },
    "mr": {
        "critical": ("पुढील रक्तटंचाईकडे लक्ष द्या", "अंदाजानुसार १४ दिवसांत साठा सुरक्षित पातळीखाली जाऊ शकतो.", "अंदाज तपासा आणि पहिल्या दाता संपर्क टप्प्याची तयारी करा."),
        "elevated": ("दाता संपर्काचे नियोजन करा", "काही रक्तगटांचा साठा सुरक्षित मर्यादेकडे कमी होत आहे.", "दाता प्राधान्य तपासा आणि टप्प्याटप्प्याने संपर्काची तयारी करा."),
        "stable": ("साठ्याचा अंदाज स्थिर आहे", "सध्याचा साठा सुरक्षित पातळीच्या जवळ किंवा वर राहण्याची शक्यता आहे.", "दररोज निरीक्षण सुरू ठेवा आणि दात्यांची नोंद अद्ययावत ठेवा."),
    },
}


@app.get("/api/advisories", response_model=AdvisoryOut)
def advisory(district: str | None = None, language: str = "en", _: User | None = Depends(require_admin), session: Session = Depends(get_db)):
    language = language if language in ADVISORIES else "en"
    query = select(Inventory)
    if district:
        query = query.where(Inventory.district == district)
    items = session.scalars(query).all()
    if not items:
        raise HTTPException(status_code=404, detail="No inventory found for the selected district")
    groups = group_rankings_for(session, items)
    highest = max((inventory_out(session, item, calculate_group_scores(session, item, rankings=groups)) for item in items), key=lambda item: item["cbsri"])
    title, message, action = ADVISORIES[language][highest["risk_level"]]
    return {"language": language, "title": title, "message": message, "action": action, "cbsri": highest["cbsri"]}
