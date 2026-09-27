from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DonorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=80)
    blood_group: str = Field(pattern=r"^(A|B|AB|O)[+-]$")
    age: int = Field(ge=18, le=65)
    last_donation_date: date | None = None
    donations_count: int = Field(default=0, ge=0)
    response_rate: float = Field(default=0.5, ge=0, le=1)


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)


class DonorAccountCreate(BaseModel):
    donor_id: int = Field(gt=0)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)


class AuthUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    donor_id: int | None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthUserOut


class DonorProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=18, le=65)
    available: bool


class BloodRequestCreate(BaseModel):
    donor_id: int = Field(gt=0)
    blood_group: str = Field(pattern=r"^(A|B|AB|O)[+-]$")
    units_requested: int = Field(ge=1, le=20)
    hospital_name: str = Field(min_length=2, max_length=160)
    district: str = Field(min_length=2, max_length=80)
    needed_by: date
    notes: str | None = Field(default=None, max_length=1000)


class BloodRequestOut(BaseModel):
    id: int
    donor_id: int
    blood_group: str
    units_requested: int
    hospital_name: str
    district: str
    needed_by: date
    notes: str | None
    status: str
    created_at: datetime


class DonationHistoryOut(BaseModel):
    donations_count: int
    last_donation_date: date | None
    donation_interval_days: int | None
    notifications_received: int


class DonorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    district: str
    blood_group: str
    age: int
    last_donation_date: date | None
    donations_count: int
    response_rate: float
    response_probability: float
    notifications_30d: int
    last_contact_at: datetime | None
    available: bool
    eligible: bool
    priority_score: float
    explanation: str


class InventoryUpdate(BaseModel):
    units_available: int = Field(ge=0, le=100000)
    avg_daily_demand: float = Field(gt=0, le=10000)
    safety_stock_units: int = Field(ge=0, le=100000)


class InventoryOut(BaseModel):
    id: int
    district: str
    blood_group: str
    units_available: int
    avg_daily_demand: float
    safety_stock_units: int
    days_of_supply: float
    shortage_score: float
    risk_level: str


class CampaignCreate(BaseModel):
    district: str = Field(min_length=2, max_length=80)
    blood_group: str = Field(pattern=r"^(A|B|AB|O)[+-]$")
    stage: int = Field(default=1, ge=1, le=3)
    batch_size: int = Field(default=10, ge=1, le=100)


class CampaignOut(BaseModel):
    id: int
    district: str
    blood_group: str
    stage: int
    recipients_count: int
    cbsri: float
    status: str
    created_at: datetime
    donor_names: list[str] = []


class ForecastPoint(BaseModel):
    date: date
    projected_units: float
    demand_units: float
    shortage_score: float
    risk_level: str
    explanation: str


class ForecastOut(BaseModel):
    district: str
    blood_group: str
    horizon_days: int
    current_units: int
    avg_daily_demand: float
    safety_stock_units: int
    cbsri: float
    response_score: float
    fatigue_adjusted_priority_score: float
    explanation: str
    points: list[ForecastPoint]


class AdvisoryOut(BaseModel):
    language: str
    title: str
    message: str
    action: str
    cbsri: float
