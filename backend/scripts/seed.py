"""Seed development farm, users, kiosk, and sample lactating cow."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Animal, AnimalGroupMembership, AnimalGroupName, Farm, KioskDevice, OwnerUser, Sex, Worker
from app.services.auth import hash_password
from app.services.milking_schedule import ensure_default_windows, upsert_schedule_for_animal


def seed() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(Farm).where(Farm.name == "Chiang Mai Farm"))
        if existing:
            print("Seed skipped: farm already exists")
            return

        farm = Farm(
            id=uuid4(),
            name="Chiang Mai Farm",
            timezone="Africa/Nairobi",
            three_session_threshold_litres=Decimal("15.0"),
            created_at=datetime.utcnow(),
        )
        db.add(farm)
        db.flush()

        ensure_default_windows(db, farm)

        owner = OwnerUser(
            id=uuid4(),
            farm_id=farm.id,
            email="owner@dfms.local",
            password_hash=hash_password("owner123"),
            name="Farm Owner",
        )
        db.add(owner)

        worker = Worker(
            id=uuid4(),
            farm_id=farm.id,
            worker_code="002",
            name="John",
            pin_hash=hash_password("1234"),
        )
        db.add(worker)

        db.add(
            KioskDevice(
                id=uuid4(),
                farm_id=farm.id,
                device_id="KIOSK-01",
                label="Milking Parlour",
            )
        )

        animal = Animal(
            id=uuid4(),
            farm_id=farm.id,
            animal_tag="101",
            name="Bella",
            sex=Sex.FEMALE,
            breed="Friesian",
            date_of_birth=date(2022, 3, 15),
            is_lactating=True,
            is_active=True,
            registered_at=datetime.utcnow(),
        )
        db.add(animal)
        db.flush()

        db.add(
            AnimalGroupMembership(
                farm_id=farm.id,
                animal_id=animal.id,
                group_name=AnimalGroupName.LACTATING_COWS,
                start_date=date.today(),
            )
        )

        upsert_schedule_for_animal(db, farm, animal, date.today())
        db.commit()
        print("Seed complete")
        print("Owner: owner@dfms.local / owner123")
        print("Worker: code 002 / PIN 1234")
        print("Sample cow: tag 101 (lactating)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
