from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_secret
from app.database.session import SessionLocal
from app.models import AuthSession, Customer
from app.services.authentication_service import verify_otp


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_auth_start_does_not_return_otp(client):
    response = client.post("/auth/start", json={"customer_reference": "CUS-1001"})
    assert response.status_code == 201
    assert set(response.json()) == {"challenge_id", "expires_in_seconds"}


def test_valid_and_invalid_otp():
    settings = get_settings()
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_reference == "CUS-1001"))
        session = AuthSession(session_id="challenge-valid", customer_id=customer.id,
            otp_hash=hash_secret("654321", settings.secret_key), otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2))
        db.add(session); db.commit()
        try:
            verify_otp(db, session.session_id, "000000", settings)
            assert False
        except Exception as exc:
            assert exc.status_code == 401
        assert verify_otp(db, session.session_id, "654321", settings)


def test_expired_otp_rejected():
    settings = get_settings()
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_reference == "CUS-1001"))
        session = AuthSession(session_id="challenge-expired", customer_id=customer.id,
            otp_hash=hash_secret("654321", settings.secret_key), otp_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        db.add(session); db.commit()
        try:
            verify_otp(db, session.session_id, "654321", settings)
            assert False
        except Exception as exc:
            assert exc.status_code == 401


def test_otp_retry_limit_exhausts_challenge():
    settings = get_settings()
    with SessionLocal() as db:
        customer = db.scalar(select(Customer).where(Customer.customer_reference == "CUS-1001"))
        session = AuthSession(session_id="challenge-retries", customer_id=customer.id,
            otp_hash=hash_secret("654321", settings.secret_key), otp_expires_at=datetime.now(timezone.utc) + timedelta(minutes=2))
        db.add(session); db.commit()
        for _ in range(settings.otp_max_attempts):
            try:
                verify_otp(db, session.session_id, "000000", settings)
            except Exception:
                pass
        try:
            verify_otp(db, session.session_id, "654321", settings)
            assert False
        except Exception as exc:
            assert exc.status_code == 401


def test_accounts_require_authentication(client):
    assert client.get("/accounts/me").status_code in {401, 403}


def test_balance_and_transactions(client, auth):
    balance = client.get(f"/accounts/{auth['account_id']}/balance", headers=auth["headers"])
    assert balance.status_code == 200
    assert balance.json()["available_balance"] == "4350.75"
    txs = client.get(f"/accounts/{auth['account_id']}/transactions?limit=3", headers=auth["headers"])
    assert txs.status_code == 200
    assert len(txs.json()) == 3
    detail = client.get(f"/transactions/{txs.json()[0]['transaction_reference']}", headers=auth["headers"])
    assert detail.status_code == 200


def test_ownership_is_enforced(client, auth):
    assert client.get("/accounts/2/balance", headers=auth["headers"]).status_code == 404
    assert client.get("/transactions/TXN-02-0001", headers=auth["headers"]).status_code == 404
