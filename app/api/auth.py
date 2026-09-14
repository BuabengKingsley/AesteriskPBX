from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_customer
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models import AuthSession, Customer
from app.schemas.auth import AuthStartRequest, AuthStartResponse, AuthVerifyRequest, AuthVerifyResponse
from app.services.authentication_service import start_authentication, verify_otp

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/start", response_model=AuthStartResponse, status_code=201)
def start(payload: AuthStartRequest, db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]):
    challenge_id = start_authentication(db, payload.customer_reference or payload.phone_number or "", settings)
    return AuthStartResponse(challenge_id=challenge_id, expires_in_seconds=settings.otp_ttl_seconds)


@router.post("/verify", response_model=AuthVerifyResponse)
def verify(payload: AuthVerifyRequest, db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]):
    token = verify_otp(db, payload.challenge_id, payload.otp, settings)
    return AuthVerifyResponse(session_token=token, expires_in_seconds=settings.session_ttl_seconds)


@router.post("/step-up/start", response_model=AuthStartResponse, status_code=201)
def start_step_up(customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)],
                  settings: Annotated[Settings, Depends(get_settings)]):
    challenge_id = start_authentication(db, customer.customer_reference, settings)
    return AuthStartResponse(challenge_id=challenge_id, expires_in_seconds=settings.otp_ttl_seconds)


@router.post("/step-up/verify", response_model=AuthVerifyResponse)
def verify_step_up(payload: AuthVerifyRequest, customer: Annotated[Customer, Depends(current_customer)],
                   db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)]):
    challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == payload.challenge_id))
    if not challenge or challenge.customer_id != customer.id:
        raise HTTPException(status_code=403, detail="Challenge does not belong to the authenticated customer")
    token = verify_otp(db, payload.challenge_id, payload.otp, settings, authentication_level="elevated")
    return AuthVerifyResponse(session_token=token, expires_in_seconds=settings.session_ttl_seconds)

