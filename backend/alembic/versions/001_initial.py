"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "farms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("three_session_threshold_litres", sa.Numeric(5, 1), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "milking_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("session", sa.Enum("MORNING", "MIDDAY", "EVENING", name="milkingsession"), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.UniqueConstraint("farm_id", "session", name="uq_farm_session_window"),
    )
    op.create_table(
        "owner_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("worker_code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("farm_id", "worker_code", name="uq_farm_worker_code"),
    )
    op.create_table(
        "kiosk_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("device_id", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("farm_id", "device_id", name="uq_farm_device"),
    )
    op.create_table(
        "animals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("animal_tag", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("sex", sa.Enum("FEMALE", "MALE", name="sex"), nullable=False),
        sa.Column("breed", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("is_lactating", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True)),
        sa.Column("died_at", sa.DateTime(timezone=True)),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("farm_id", "animal_tag", name="uq_farm_animal_tag"),
    )
    op.create_table(
        "animal_group_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("animals.id"), nullable=False),
        sa.Column("group_name", sa.Enum("LACTATING_COWS", "DRY_COWS", "HEIFERS", "CALVES", name="animalgroupname"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
    )
    op.create_table(
        "milking_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("animals.id"), nullable=False),
        sa.Column("schedule_date", sa.Date(), nullable=False),
        sa.Column("sessions", postgresql.JSONB(), nullable=False),
        sa.Column("basis_average", sa.Numeric(6, 1)),
        sa.Column("threshold_used", sa.Numeric(5, 1), nullable=False),
        sa.UniqueConstraint("animal_id", "schedule_date", name="uq_animal_schedule_date"),
    )
    op.create_table(
        "domain_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", sa.String(100), nullable=False),
        sa.Column("device_id", sa.String(50)),
    )
    op.create_table(
        "milking_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("animal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("animals.id"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domain_events.id"), nullable=False),
        sa.Column("session", sa.Enum("MORNING", "MIDDAY", "EVENING", name="milkingsession", create_type=False), nullable=False),
        sa.Column("volume_litres", sa.Numeric(6, 1), nullable=False),
        sa.Column("milking_date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("worker_id", sa.String(50), nullable=False),
        sa.Column("device_id", sa.String(50), nullable=False),
        sa.Column("flagged", sa.Boolean(), nullable=False),
        sa.Column("outside_window", sa.Boolean(), nullable=False),
        sa.Column("saleable", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("animal_id", "session", "milking_date", name="uq_milking_animal_session_date"),
    )
    op.create_table(
        "flagged_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id"), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("domain_events.id"), nullable=False),
        sa.Column("source_event_type", sa.String(100), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("expected_range", sa.String(100)),
        sa.Column("actual_value", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("flagged_records")
    op.drop_table("milking_records")
    op.drop_table("domain_events")
    op.drop_table("milking_schedules")
    op.drop_table("animal_group_memberships")
    op.drop_table("animals")
    op.drop_table("kiosk_devices")
    op.drop_table("workers")
    op.drop_table("owner_users")
    op.drop_table("milking_windows")
    op.drop_table("farms")
    op.execute("DROP TYPE IF EXISTS milkingsession")
    op.execute("DROP TYPE IF EXISTS sex")
    op.execute("DROP TYPE IF EXISTS animalgroupname")
