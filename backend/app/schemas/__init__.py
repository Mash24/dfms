from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    field: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CommandSuccess(BaseModel):
    success: bool = True
    command: str
    events: list[dict[str, Any]]


class OwnerLoginRequest(BaseModel):
    email: str
    password: str


class WorkerLoginRequest(BaseModel):
    worker_code: str
    pin: str
    device_id: str = "KIOSK-01"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    farm_id: UUID
    subject: str


class RegisterAnimalRequest(BaseModel):
    animal_tag: str
    name: str | None = None
    sex: str
    breed: str
    date_of_birth: datetime
    purchase_date: datetime
    purchase_price: Decimal | None = None
    initial_group: str
    dam_tag: str | None = None
    sire_tag: str | None = None
    notes: str | None = None


class RecordMilkingRequest(BaseModel):
    animal_tag: str
    session: str
    volume_litres: Decimal
    recorded_at: datetime | None = None
    device_id: str = "KIOSK-01"
