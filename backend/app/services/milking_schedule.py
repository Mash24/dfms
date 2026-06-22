from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Animal,
    Farm,
    MilkingRecord,
    MilkingSchedule,
    MilkingSession,
    MilkingWindow,
)


DEFAULT_WINDOWS: dict[MilkingSession, tuple[time, time]] = {
    MilkingSession.MORNING: (time(5, 0), time(9, 0)),
    MilkingSession.MIDDAY: (time(11, 0), time(14, 0)),
    MilkingSession.EVENING: (time(16, 0), time(20, 0)),
}


def farm_now(farm: Farm) -> datetime:
    return datetime.now(ZoneInfo(farm.timezone))


def farm_today(farm: Farm) -> date:
    return farm_now(farm).date()


def sessions_for_average(avg: Decimal | None, threshold: Decimal) -> list[str]:
    if avg is not None and avg > threshold:
        return [MilkingSession.MORNING.value, MilkingSession.MIDDAY.value, MilkingSession.EVENING.value]
    return [MilkingSession.MORNING.value, MilkingSession.EVENING.value]


def ensure_default_windows(db: Session, farm: Farm) -> None:
    existing = db.scalars(select(MilkingWindow).where(MilkingWindow.farm_id == farm.id)).all()
    if existing:
        return
    for session, (start, end) in DEFAULT_WINDOWS.items():
        db.add(MilkingWindow(farm_id=farm.id, session=session, start_time=start, end_time=end))


def seven_day_average(db: Session, animal_id, as_of: date) -> Decimal | None:
    start = as_of - timedelta(days=6)
    rows = db.execute(
        select(MilkingRecord.milking_date, func.sum(MilkingRecord.volume_litres))
        .where(
            MilkingRecord.animal_id == animal_id,
            MilkingRecord.milking_date >= start,
            MilkingRecord.milking_date <= as_of,
        )
        .group_by(MilkingRecord.milking_date)
    ).all()
    if len(rows) < 3:
        return None
    daily_totals = [Decimal(str(total)) for _, total in rows]
    return sum(daily_totals) / Decimal(len(daily_totals))


def upsert_schedule_for_animal(db: Session, farm: Farm, animal: Animal, schedule_date: date) -> MilkingSchedule:
    avg = seven_day_average(db, animal.id, schedule_date)
    threshold = Decimal(str(farm.three_session_threshold_litres))
    sessions = sessions_for_average(avg, threshold)

    schedule = db.scalar(
        select(MilkingSchedule).where(
            MilkingSchedule.animal_id == animal.id,
            MilkingSchedule.schedule_date == schedule_date,
        )
    )
    if schedule:
        schedule.sessions = sessions
        schedule.basis_average = avg
        schedule.threshold_used = threshold
        return schedule

    schedule = MilkingSchedule(
        farm_id=farm.id,
        animal_id=animal.id,
        schedule_date=schedule_date,
        sessions=sessions,
        basis_average=avg,
        threshold_used=threshold,
    )
    db.add(schedule)
    return schedule


def recalculate_schedules_for_farm(db: Session, farm: Farm, schedule_date: date) -> int:
    animals = db.scalars(
        select(Animal).where(
            Animal.farm_id == farm.id,
            Animal.is_active.is_(True),
            Animal.is_lactating.is_(True),
        )
    ).all()
    for animal in animals:
        upsert_schedule_for_animal(db, farm, animal, schedule_date)
    return len(animals)


def is_outside_window(db: Session, farm: Farm, session: MilkingSession, recorded_at: datetime) -> bool:
    local_dt = recorded_at.astimezone(ZoneInfo(farm.timezone))
    window = db.scalar(
        select(MilkingWindow).where(MilkingWindow.farm_id == farm.id, MilkingWindow.session == session)
    )
    if not window:
        start, end = DEFAULT_WINDOWS[session]
    else:
        start, end = window.start_time, window.end_time
    current = local_dt.time()
    return not (start <= current <= end)


def session_average(db: Session, animal_id: str, session: MilkingSession, limit: int = 3) -> Decimal | None:
    rows = db.scalars(
        select(MilkingRecord.volume_litres)
        .where(MilkingRecord.animal_id == animal_id, MilkingRecord.session == session)
        .order_by(MilkingRecord.milking_date.desc())
        .limit(limit)
    ).all()
    if not rows:
        return None
    return sum(Decimal(str(v)) for v in rows) / Decimal(len(rows))
