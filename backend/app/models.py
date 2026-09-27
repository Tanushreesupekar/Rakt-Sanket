from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Donor(Base):
    __tablename__ = "donors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), index=True, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    last_donation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    donations_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    response_rate: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    notifications_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    notifications: Mapped[list["Notification"]] = relationship(back_populates="donor")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    donor_id: Mapped[int | None] = mapped_column(ForeignKey("donors.id"), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    district: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), index=True, nullable=False)
    units_available: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_daily_demand: Mapped[float] = mapped_column(Float, nullable=False)
    safety_stock_units: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    district: Mapped[str] = mapped_column(String(80), nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)
    recipients_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cbsri: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="simulated", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    notifications: Mapped[list["Notification"]] = relationship(back_populates="campaign")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    campaign: Mapped[Campaign] = relationship(back_populates="notifications")
    donor: Mapped[Donor] = relationship(back_populates="notifications")


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), index=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    units_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    hospital_name: Mapped[str] = mapped_column(String(160), nullable=False)
    district: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    needed_by: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending review", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ExampleStockObservation(Base):
    __tablename__ = "example_stock_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    district: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    observed_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), index=True, nullable=False)
    opening_stock_units: Mapped[int] = mapped_column(Integer, nullable=False)
    demand_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_units: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_units: Mapped[int] = mapped_column(Integer, nullable=False)


class ExampleDonorRecord(Base):
    __tablename__ = "example_donor_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    donor_id: Mapped[int] = mapped_column(ForeignKey("donors.id"), unique=True, nullable=False)
    blood_group: Mapped[str] = mapped_column(String(3), nullable=False)
    last_donation_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_donations: Mapped[int] = mapped_column(Integer, nullable=False)
    alerts_received: Mapped[int] = mapped_column(Integer, nullable=False)
    responses: Mapped[int] = mapped_column(Integer, nullable=False)


class ExampleNotificationRecord(Base):
    __tablename__ = "example_notification_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    donor_record_id: Mapped[int] = mapped_column(ForeignKey("example_donor_records.id"), index=True, nullable=False)
    alert_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    response: Mapped[str] = mapped_column(String(16), nullable=False)
    donation_after_alert: Mapped[str] = mapped_column(String(8), nullable=False)
