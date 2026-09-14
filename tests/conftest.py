import os

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_voice_support.db"
os.environ["SECRET_KEY"] = "test-secret-key"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_secret
from app.database.base import Base
from app.database.seed import seed_database
from app.database.session import SessionLocal, engine
from app.main import app
from app.models import AuthSession, Customer
from app.services.authentication_service import verify_otp


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_database(db)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth():
    otp = "123456"
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_reference == "CUS-1001"))
        challenge = AuthSession(session_id="test-challenge-id", customer_id=customer.id,
                                otp_hash=hash_secret(otp, get_settings().secret_key),
                                otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        db.add(challenge)
        db.commit()
        token = verify_otp(db, challenge.session_id, otp, get_settings())
        account_id = customer.accounts[0].id
    return {"headers": {"Authorization": f"Bearer {token}"}, "account_id": account_id}


@pytest.fixture
def elevated_auth():
    otp = "654321"
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_reference == "CUS-1001"))
        challenge = AuthSession(session_id="test-elevated-challenge-id", customer_id=customer.id,
                                otp_hash=hash_secret(otp, get_settings().secret_key),
                                otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
        db.add(challenge)
        db.commit()
        token = verify_otp(db, challenge.session_id, otp, get_settings(), authentication_level="elevated")
        account_id = customer.accounts[0].id
    return {"headers": {"Authorization": f"Bearer {token}"}, "account_id": account_id}

