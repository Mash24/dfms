from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.commands.base import CommandError, raise_command_error
from app.commands.record_milking import handle_record_milking
from app.commands.register_animal import handle_register_animal
from app.database import get_db
from app.models import Farm, OwnerUser, Worker
from app.schemas import CommandSuccess, RecordMilkingRequest, RegisterAnimalRequest
from app.services.auth import decode_token

router = APIRouter(prefix="/commands", tags=["commands"])


def get_current_claims(authorization: Annotated[str | None, Header()] = None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_owner(claims: dict = Depends(get_current_claims)) -> tuple[dict, UUID]:
    if claims.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return claims, UUID(claims["farm_id"])


def require_worker(claims: dict = Depends(get_current_claims)) -> tuple[dict, UUID]:
    if claims.get("role") != "worker":
        raise HTTPException(status_code=403, detail="Worker access required")
    return claims, UUID(claims["farm_id"])


@router.post("/register-animal", response_model=CommandSuccess)
def register_animal(
    payload: RegisterAnimalRequest,
    db: Session = Depends(get_db),
    auth: tuple[dict, UUID] = Depends(require_owner),
):
    claims, farm_id = auth
    farm = db.get(Farm, farm_id)
    owner = db.get(OwnerUser, UUID(claims["sub"]))
    if not farm or not owner:
        raise HTTPException(status_code=404, detail="Farm or owner not found")
    try:
        events = handle_register_animal(db, farm, owner, payload)
        db.commit()
    except CommandError as exc:
        db.rollback()
        raise_command_error(exc)
    return CommandSuccess(command="RegisterAnimal", events=events)


@router.post("/record-milking", response_model=CommandSuccess)
def record_milking(
    payload: RecordMilkingRequest,
    db: Session = Depends(get_db),
    auth: tuple[dict, UUID] = Depends(require_worker),
):
    claims, farm_id = auth
    farm = db.get(Farm, farm_id)
    worker = db.get(Worker, UUID(claims["sub"]))
    if not farm or not worker:
        raise HTTPException(status_code=404, detail="Farm or worker not found")
    try:
        events = handle_record_milking(db, farm, worker, payload)
        db.commit()
    except CommandError as exc:
        db.rollback()
        raise_command_error(exc)
    return CommandSuccess(command="RecordMilking", events=events)
