import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Sex(str, enum.Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"


class MilkingSession(str, enum.Enum):
    MORNING = "MORNING"
    MIDDAY = "MIDDAY"
    EVENING = "EVENING"


class AnimalGroupName(str, enum.Enum):
    LACTATING_COWS = "LACTATING_COWS"
    DRY_COWS = "DRY_COWS"
    HEIFERS = "HEIFERS"
    CALVES = "CALVES"


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Nairobi")
    three_session_threshold_litres: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=Decimal("15.0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    milking_windows: Mapped[list["MilkingWindow"]] = relationship(back_populates="farm")


class MilkingWindow(Base):
    __tablename__ = "milking_windows"
    __table_args__ = (UniqueConstraint("farm_id", "session", name="uq_farm_session_window"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    session: Mapped[MilkingSession] = mapped_column(Enum(MilkingSession), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    farm: Mapped[Farm] = relationship(back_populates="milking_windows")


class OwnerUser(Base):
    __tablename__ = "owner_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (UniqueConstraint("farm_id", "worker_code", name="uq_farm_worker_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    worker_code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class KioskDevice(Base):
    __tablename__ = "kiosk_devices"
    __table_args__ = (UniqueConstraint("farm_id", "device_id", name="uq_farm_device"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Animal(Base):
    __tablename__ = "animals"
    __table_args__ = (UniqueConstraint("farm_id", "animal_tag", name="uq_farm_animal_tag"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    animal_tag: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    sex: Mapped[Sex] = mapped_column(Enum(Sex), nullable=False)
    breed: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    is_lactating: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    died_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AnimalGroupMembership(Base):
    __tablename__ = "animal_group_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    animal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("animals.id"), nullable=False)
    group_name: Mapped[AnimalGroupName] = mapped_column(Enum(AnimalGroupName), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)


class MilkingSchedule(Base):
    __tablename__ = "milking_schedules"
    __table_args__ = (UniqueConstraint("animal_id", "schedule_date", name="uq_animal_schedule_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    animal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("animals.id"), nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    sessions: Mapped[list] = mapped_column(JSONB, nullable=False)
    basis_average: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    threshold_used: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)


class DomainEvent(Base):
    __tablename__ = "domain_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    issued_by: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(50))


class MilkingRecord(Base):
    __tablename__ = "milking_records"
    __table_args__ = (
        UniqueConstraint("animal_id", "session", "milking_date", name="uq_milking_animal_session_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    animal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("animals.id"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain_events.id"), nullable=False)
    session: Mapped[MilkingSession] = mapped_column(Enum(MilkingSession), nullable=False)
    volume_litres: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False)
    milking_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(50), nullable=False)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    outside_window: Mapped[bool] = mapped_column(Boolean, default=False)
    saleable: Mapped[bool] = mapped_column(Boolean, default=True)


class FlaggedRecord(Base):
    __tablename__ = "flagged_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), nullable=False)
    source_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("domain_events.id"), nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_range: Mapped[str | None] = mapped_column(String(100))
    actual_value: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
