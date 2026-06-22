from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.base import CommandError
from app.models import (
    Animal,
    DomainEvent,
    Farm,
    FlaggedRecord,
    MilkingRecord,
    MilkingSchedule,
    MilkingSession,
    Worker,
)
from app.schemas import RecordMilkingRequest
from app.services.milking_schedule import (
    farm_now,
    farm_today,
    is_outside_window,
    seven_day_average,
    upsert_schedule_for_animal,
)


def handle_record_milking(
    db: Session,
    farm: Farm,
    worker: Worker,
    payload: RecordMilkingRequest,
) -> list[dict]:
    try:
        session = MilkingSession(payload.session)
    except ValueError as exc:
        raise CommandError("INVALID_SESSION", "Invalid milking session", field="session") from exc

    animal = db.scalar(
        select(Animal).where(Animal.farm_id == farm.id, Animal.animal_tag == payload.animal_tag)
    )
    if not animal or not animal.is_active:
        raise CommandError("ANIMAL_NOT_FOUND", f"Animal {payload.animal_tag} not found", field="animal_tag")

    if not animal.is_lactating:
        raise CommandError("ANIMAL_NOT_LACTATING", f"Cow {payload.animal_tag} is not lactating", field="animal_tag")

    volume = Decimal(str(payload.volume_litres)).quantize(Decimal("0.1"))
    if volume < 0:
        raise CommandError("INVALID_VOLUME", "Volume must be zero or positive", field="volume_litres")
    if volume > Decimal("60"):
        raise CommandError("VOLUME_IMPLAUSIBLE", "Volume exceeds maximum plausible yield for a single session", field="volume_litres")

    recorded_at = payload.recorded_at or farm_now(farm)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=farm_now(farm).tzinfo)

    now = farm_now(farm)
    if recorded_at > now:
        raise CommandError("FUTURE_DATE", "Recorded time cannot be in the future", field="recorded_at")
    if recorded_at < now - timedelta(hours=24):
        raise CommandError("BACKDATE_LIMIT_EXCEEDED", "Cannot backdate more than 24 hours", field="recorded_at")

    milking_date = recorded_at.astimezone(now.tzinfo).date()
    schedule = db.scalar(
        select(MilkingSchedule).where(
            MilkingSchedule.animal_id == animal.id,
            MilkingSchedule.schedule_date == milking_date,
        )
    )
    if not schedule:
        schedule = upsert_schedule_for_animal(db, farm, animal, milking_date)

    if session.value not in schedule.sessions:
        raise CommandError(
            "SESSION_NOT_SCHEDULED",
            f"Cow {payload.animal_tag} is not scheduled for {session.value} on {milking_date}",
            field="session",
        )

    existing = db.scalar(
        select(MilkingRecord).where(
            MilkingRecord.animal_id == animal.id,
            MilkingRecord.session == session,
            MilkingRecord.milking_date == milking_date,
        )
    )
    if existing:
        if existing.volume_litres == volume:
            return [
                {
                    "event_type": "MilkingRecorded",
                    "event_id": str(existing.event_id),
                    "animal_tag": animal.animal_tag,
                    "session": session.value,
                    "volume_litres": float(existing.volume_litres),
                    "idempotent": True,
                }
            ]
        existing.volume_litres = volume
        existing.recorded_at = recorded_at
        db.flush()
        return [
            {
                "event_type": "MilkingRecorded",
                "event_id": str(existing.event_id),
                "animal_tag": animal.animal_tag,
                "session": session.value,
                "volume_litres": float(volume),
                "updated": True,
            }
        ]

    avg = seven_day_average(db, animal.id, milking_date)
    flagged = avg is not None and volume > (avg * 2)
    outside_window = is_outside_window(db, farm, session, recorded_at)

    event_id = uuid4()
    worker_ref = f"W-{worker.worker_code}"

    event = DomainEvent(
        id=event_id,
        farm_id=farm.id,
        event_type="MilkingRecorded",
        issued_by=worker_ref,
        device_id=payload.device_id,
        payload={
            "event_type": "MilkingRecorded",
            "event_id": str(event_id),
            "animal_id": str(animal.id),
            "animal_tag": animal.animal_tag,
            "farm_id": str(farm.id),
            "session": session.value,
            "volume_litres": float(volume),
            "recorded_at": recorded_at.isoformat(),
            "milking_date": milking_date.isoformat(),
            "worker_id": worker_ref,
            "device_id": payload.device_id,
            "flagged": flagged,
            "outside_window": outside_window,
            "saleable": True,
        },
    )
    db.add(event)

    record = MilkingRecord(
        id=uuid4(),
        farm_id=farm.id,
        animal_id=animal.id,
        event_id=event_id,
        session=session,
        volume_litres=volume,
        milking_date=milking_date,
        recorded_at=recorded_at,
        worker_id=worker_ref,
        device_id=payload.device_id,
        flagged=flagged,
        outside_window=outside_window,
        saleable=True,
    )
    db.add(record)

    events = [event.payload]

    if flagged:
        flag_id = uuid4()
        flag_event = DomainEvent(
            id=flag_id,
            farm_id=farm.id,
            event_type="FlaggedRecordCreated",
            issued_by="system",
            payload={
                "event_type": "FlaggedRecordCreated",
                "flagged_record_id": str(flag_id),
                "source_event_id": str(event_id),
                "source_event_type": "MilkingRecorded",
                "reason": "VOLUME_ABOVE_2X_AVERAGE",
                "expected_range": f"0 - {float((avg or Decimal('0')) * 2):.1f}",
                "actual_value": str(float(volume)),
                "farm_id": str(farm.id),
            },
        )
        db.add(flag_event)
        db.add(
            FlaggedRecord(
                id=flag_id,
                farm_id=farm.id,
                source_event_id=event_id,
                source_event_type="MilkingRecorded",
                reason="VOLUME_ABOVE_2X_AVERAGE",
                expected_range=flag_event.payload["expected_range"],
                actual_value=str(float(volume)),
            )
        )
        events.append(flag_event.payload)

    if outside_window:
        flag_id = uuid4()
        window_flag = DomainEvent(
            id=flag_id,
            farm_id=farm.id,
            event_type="FlaggedRecordCreated",
            issued_by="system",
            payload={
                "event_type": "FlaggedRecordCreated",
                "flagged_record_id": str(flag_id),
                "source_event_id": str(event_id),
                "source_event_type": "MilkingRecorded",
                "reason": "OUTSIDE_MILKING_WINDOW",
                "actual_value": recorded_at.astimezone(now.tzinfo).strftime("%H:%M"),
                "farm_id": str(farm.id),
            },
        )
        db.add(window_flag)
        db.add(
            FlaggedRecord(
                id=flag_id,
                farm_id=farm.id,
                source_event_id=event_id,
                source_event_type="MilkingRecorded",
                reason="OUTSIDE_MILKING_WINDOW",
                actual_value=window_flag.payload["actual_value"],
            )
        )
        events.append(window_flag.payload)

    db.flush()
    return events
