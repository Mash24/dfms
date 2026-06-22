from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.base import CommandError
from app.models import (
    Animal,
    AnimalGroupMembership,
    AnimalGroupName,
    DomainEvent,
    Farm,
    OwnerUser,
    Sex,
)
from app.schemas import RegisterAnimalRequest
from app.services.milking_schedule import farm_today, upsert_schedule_for_animal


def handle_register_animal(
    db: Session,
    farm: Farm,
    owner: OwnerUser,
    payload: RegisterAnimalRequest,
) -> list[dict]:
    existing = db.scalar(
        select(Animal).where(Animal.farm_id == farm.id, Animal.animal_tag == payload.animal_tag)
    )
    if existing:
        raise CommandError("DUPLICATE_TAG", "Animal tag already exists", field="animal_tag")

    if payload.date_of_birth.date() > farm_today(farm):
        raise CommandError("INVALID_DOB", "Date of birth cannot be in the future", field="date_of_birth")

    if payload.purchase_date.date() > farm_today(farm):
        raise CommandError(
            "INVALID_PURCHASE_DATE",
            "Purchase date cannot be in the future",
            field="purchase_date",
        )

    try:
        sex = Sex(payload.sex)
        group = AnimalGroupName(payload.initial_group)
    except ValueError as exc:
        raise CommandError("INVALID_ENUM", str(exc)) from exc

    animal_id = uuid4()
    registered_at = datetime.utcnow()

    animal = Animal(
        id=animal_id,
        farm_id=farm.id,
        animal_tag=payload.animal_tag,
        name=payload.name,
        sex=sex,
        breed=payload.breed,
        date_of_birth=payload.date_of_birth.date(),
        is_lactating=group == AnimalGroupName.LACTATING_COWS,
        is_active=True,
        registered_at=registered_at,
    )
    db.add(animal)

    membership = AnimalGroupMembership(
        farm_id=farm.id,
        animal_id=animal_id,
        group_name=group,
        start_date=payload.purchase_date.date(),
    )
    db.add(membership)

    registered_event = DomainEvent(
        id=uuid4(),
        farm_id=farm.id,
        event_type="AnimalRegistered",
        issued_by=str(owner.id),
        payload={
            "event_type": "AnimalRegistered",
            "animal_id": str(animal_id),
            "animal_tag": payload.animal_tag,
            "farm_id": str(farm.id),
            "sex": sex.value,
            "breed": payload.breed,
            "date_of_birth": payload.date_of_birth.date().isoformat(),
            "registered_at": registered_at.isoformat(),
            "registered_by": str(owner.id),
        },
    )
    db.add(registered_event)

    purchased_event = DomainEvent(
        id=uuid4(),
        farm_id=farm.id,
        event_type="AnimalPurchased",
        issued_by=str(owner.id),
        payload={
            "event_type": "AnimalPurchased",
            "animal_id": str(animal_id),
            "farm_id": str(farm.id),
            "purchase_date": payload.purchase_date.date().isoformat(),
            "purchase_price": float(payload.purchase_price) if payload.purchase_price is not None else None,
            "purchased_at": registered_at.isoformat(),
            "recorded_by": str(owner.id),
        },
    )
    db.add(purchased_event)

    group_event = DomainEvent(
        id=uuid4(),
        farm_id=farm.id,
        event_type="AnimalGroupChanged",
        issued_by=str(owner.id),
        payload={
            "event_type": "AnimalGroupChanged",
            "animal_id": str(animal_id),
            "farm_id": str(farm.id),
            "group": group.value,
            "previous_group": None,
            "effective_at": payload.purchase_date.date().isoformat(),
            "recorded_at": registered_at.isoformat(),
            "recorded_by": str(owner.id),
        },
    )
    db.add(group_event)

    if animal.is_lactating:
        upsert_schedule_for_animal(db, farm, animal, farm_today(farm))

    db.flush()
    return [registered_event.payload, purchased_event.payload, group_event.payload]
