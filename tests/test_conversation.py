from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_secret
from app.database.session import SessionLocal
from app.models import Account, AuthSession, CallSession


def _inject_known_otp(call_id: str, otp: str) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        call = db.scalar(select(CallSession).where(CallSession.call_id == call_id))
        challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == call.pending_challenge_id))
        challenge.otp_hash = hash_secret(otp, settings.secret_key)
        db.commit()


def test_start_returns_greeting(client):
    response = client.post("/conversation/start", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "GREETING"
    assert body["call_id"]


def test_unknown_intent_asks_for_clarification(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]
    response = client.post(f"/conversation/{call_id}/message", json={"text": "asdf qwerty"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "UNKNOWN"
    assert body["state"] == "INTENT_DETECTION"


def test_transfer_to_human_bypasses_auth(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]
    response = client.post(f"/conversation/{call_id}/message", json={"text": "I want to speak to a human"})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "HUMAN_HANDOFF"
    assert body["requires_authentication"] is False


def test_message_after_handoff_rejected(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]
    client.post(f"/conversation/{call_id}/message", json={"text": "human please"})
    response = client.post(f"/conversation/{call_id}/message", json={"text": "hello?"})
    assert response.status_code == 409


def test_message_for_unknown_call_returns_404(client):
    response = client.post("/conversation/does-not-exist/message", json={"text": "hi"})
    assert response.status_code == 404


def test_check_balance_full_flow_with_manual_otp_injection(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]

    step1 = client.post(f"/conversation/{call_id}/message", json={"text": "what's my balance"}).json()
    assert step1["state"] == "AUTHENTICATION_REQUIRED"
    assert step1["requires_authentication"] is True

    step2 = client.post(f"/conversation/{call_id}/message", json={"text": "CUS-1001"}).json()
    assert step2["state"] == "AUTHENTICATING"

    _inject_known_otp(call_id, "111111")

    step3 = client.post(f"/conversation/{call_id}/message", json={"text": "111111"}).json()
    assert step3["state"] == "COMPLETED"
    assert step3["tool_executed"] == "check_balance"
    assert "4350.75" in step3["assistant_text"]


def test_restrict_account_flow_requires_step_up_and_confirmation(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]

    step1 = client.post(f"/conversation/{call_id}/message", json={"text": "please restrict my account"}).json()
    assert step1["state"] == "AUTHENTICATION_REQUIRED"

    step2 = client.post(f"/conversation/{call_id}/message", json={"text": "CUS-1001"}).json()
    assert step2["state"] == "AUTHENTICATING"

    _inject_known_otp(call_id, "222222")
    step3 = client.post(f"/conversation/{call_id}/message", json={"text": "222222"}).json()
    # Standard auth succeeded, but the account restriction requires step-up, so
    # the orchestrator immediately starts a second OTP round trip.
    assert step3["state"] == "AUTHENTICATING"
    assert step3["requires_authentication"] is True

    _inject_known_otp(call_id, "333333")
    step4 = client.post(f"/conversation/{call_id}/message", json={"text": "333333"}).json()
    assert step4["state"] == "AWAITING_CONFIRMATION"
    assert step4["requires_confirmation"] is True

    step5 = client.post(f"/conversation/{call_id}/message", json={"text": "yes"}).json()
    assert step5["state"] == "COMPLETED"
    assert step5["tool_executed"] == "temporarily_restrict_account"

    with SessionLocal() as db:
        call = db.scalar(select(CallSession).where(CallSession.call_id == call_id))
        account = db.scalar(select(Account).where(Account.customer_id == call.customer_id))
        assert account.status == "temporarily_restricted"


def test_handoff_summary_requires_agent_key(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]
    client.post(f"/conversation/{call_id}/message", json={"text": "human please"})
    response = client.get(f"/conversation/{call_id}/handoff-summary")
    assert response.status_code == 401


def test_handoff_summary_masks_account_and_returns_case(client):
    call_id = client.post("/conversation/start", json={}).json()["call_id"]
    client.post(f"/conversation/{call_id}/message", json={"text": "what's my balance"})
    client.post(f"/conversation/{call_id}/message", json={"text": "CUS-1001"})
    _inject_known_otp(call_id, "444444")
    client.post(f"/conversation/{call_id}/message", json={"text": "444444"})
    client.post(f"/conversation/{call_id}/message", json={"text": "human please"})

    response = client.get(f"/conversation/{call_id}/handoff-summary", headers={"X-Agent-Key": get_settings().agent_api_key})
    assert response.status_code == 200
    body = response.json()
    assert body["customer_reference"] == "CUS-1001"
    assert body["masked_account"].startswith("****")
    assert set(body) == {"call_id", "authenticated", "customer_reference", "masked_account", "intent",
                         "transaction_reference", "amount", "currency", "case_reference", "escalation_reason"}
