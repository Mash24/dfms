from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Farm, KioskDevice, OwnerUser, Worker
from app.schemas import OwnerLoginRequest, TokenResponse, WorkerLoginRequest
from app.services.auth import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/owner/login", response_model=TokenResponse)
def owner_login(payload: OwnerLoginRequest, db: Session = Depends(get_db)):
    owner = db.scalar(select(OwnerUser).where(OwnerUser.email == payload.email, OwnerUser.is_active.is_(True)))
    if not owner or not verify_password(payload.password, owner.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(
        subject=str(owner.id),
        claims={"role": "owner", "farm_id": str(owner.farm_id), "email": owner.email},
    )
    return TokenResponse(access_token=token, role="owner", farm_id=owner.farm_id, subject=owner.email)


@router.post("/worker/login", response_model=TokenResponse)
def worker_login(payload: WorkerLoginRequest, db: Session = Depends(get_db)):
    worker = db.scalar(
        select(Worker).where(Worker.worker_code == payload.worker_code, Worker.is_active.is_(True))
    )
    if not worker or not verify_password(payload.pin, worker.pin_hash):
        raise HTTPException(status_code=401, detail="Invalid worker credentials")

    device = db.scalar(
        select(KioskDevice).where(
            KioskDevice.farm_id == worker.farm_id,
            KioskDevice.device_id == payload.device_id,
            KioskDevice.is_active.is_(True),
        )
    )
    if not device:
        raise HTTPException(status_code=401, detail="Unknown kiosk device")

    token = create_access_token(
        subject=str(worker.id),
        claims={
            "role": "worker",
            "farm_id": str(worker.farm_id),
            "worker_code": worker.worker_code,
            "device_id": payload.device_id,
        },
        expires_minutes=15,
    )
    return TokenResponse(
        access_token=token,
        role="worker",
        farm_id=worker.farm_id,
        subject=f"W-{worker.worker_code}",
    )
