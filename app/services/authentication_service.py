import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import generate_otp, generate_token, hash_secret, verify_secret
from app.models import AuthSession, Customer
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def start_authentication(db: Session, identifier: str, settings: Settings) -> str:
    customer = db.scalar(select(Customer).where(or_(Customer.customer_reference == identifier, Customer.phone_number == identifier)))
    if not customer or customer.status != "active":
        raise HTTPException(status_code=404, detail="Eligible customer not found")
    challenge_id = str(uuid.uuid4())
    otp = generate_otp()
    db.add(AuthSession(session_id=challenge_id, customer_id=customer.id,
                       otp_hash=hash_secret(otp, settings.secret_key),
                       otp_expires_at=utcnow() + timedelta(seconds=settings.otp_ttl_seconds)))
    record_audit(db, customer_id=customer.id, event_type="authentication_started", action="start_authentication", result="success")
    db.commit()
    if settings.app_env == "development":
        logger.info("Development OTP for challenge %s: %s", challenge_id, otp)
    return challenge_id


def verify_otp(db: Session, challenge_id: str, otp: str, settings: Settings, authentication_level: str = "standard") -> str:
    challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == challenge_id))
    if not challenge or challenge.verified or challenge.failed_attempts >= settings.otp_max_attempts:
        raise HTTPException(status_code=401, detail="Invalid or exhausted challenge")
    if as_utc(challenge.otp_expires_at) <= utcnow():
        record_audit(db, customer_id=challenge.customer_id, event_type="authentication_failed", action="verify_otp", result="expired")
        db.commit()
        raise HTTPException(status_code=401, detail="Challenge expired")
    if not verify_secret(otp, challenge.otp_hash, settings.secret_key):
        challenge.failed_attempts += 1
        record_audit(db, customer_id=challenge.customer_id, event_type="authentication_failed", action="verify_otp", result="invalid")
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid OTP")
    token = generate_token()
    challenge.verified = True
    challenge.otp_hash = hash_secret(generate_token(), settings.secret_key)
    challenge.session_token_hash = hash_secret(token, settings.secret_key)
    challenge.session_expires_at = utcnow() + timedelta(seconds=settings.session_ttl_seconds)
    challenge.authentication_level = authentication_level
    record_audit(db, customer_id=challenge.customer_id, event_type="authentication_succeeded", action="verify_otp", result="success")
    db.commit()
    return token


def authenticate_session(db: Session, token: str, settings: Settings) -> AuthSession:
    digest = hash_secret(token, settings.secret_key)
    session = db.scalar(select(AuthSession).where(AuthSession.session_token_hash == digest, AuthSession.verified.is_(True)))
    if not session or not session.session_expires_at or as_utc(session.session_expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session", headers={"WWW-Authenticate": "Bearer"})
    return session


def authenticate_token(db: Session, token: str, settings: Settings) -> Customer:
    session = authenticate_session(db, token, settings)
    customer = db.get(Customer, session.customer_id)
    if not customer or customer.status != "active":
        raise HTTPException(status_code=401, detail="Invalid session")
    return customer

