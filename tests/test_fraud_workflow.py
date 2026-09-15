from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Account, SupportCase, Transaction


def _first_transaction_reference(auth) -> str:
    with SessionLocal() as db:
        tx = db.scalar(select(Transaction).where(Transaction.account_id == auth["account_id"]).order_by(Transaction.id))
        return tx.transaction_reference


def test_report_missing_confirm_rejected(client, auth):
    ref = _first_transaction_reference(auth)
    response = client.post(f"/transactions/{ref}/report", json={}, headers=auth["headers"])
    assert response.status_code == 422


def test_report_confirm_false_rejected(client, auth):
    ref = _first_transaction_reference(auth)
    response = client.post(f"/transactions/{ref}/report", json={"confirm": False}, headers=auth["headers"])
    assert response.status_code == 422


def test_report_success(client, auth):
    ref = _first_transaction_reference(auth)
    response = client.post(f"/transactions/{ref}/report", json={"confirm": True}, headers=auth["headers"])
    assert response.status_code == 201
    body = response.json()
    assert body["transaction_reference"] == ref
    assert body["status"] == "disputed"
    assert body["case_reference"].startswith("CASE-")
    with SessionLocal() as db:
        tx = db.scalar(select(Transaction).where(Transaction.transaction_reference == ref))
        assert tx.status == "disputed"


def test_report_already_disputed_conflict(client, auth):
    ref = _first_transaction_reference(auth)
    client.post(f"/transactions/{ref}/report", json={"confirm": True}, headers=auth["headers"])
    second = client.post(f"/transactions/{ref}/report", json={"confirm": True}, headers=auth["headers"])
    assert second.status_code == 409


def test_report_ownership_is_enforced(client, auth):
    response = client.post("/transactions/TXN-02-0001/report", json={"confirm": True}, headers=auth["headers"])
    assert response.status_code == 404


def test_restrict_requires_elevated_auth(client, auth):
    response = client.post(f"/accounts/{auth['account_id']}/temporary-restriction", json={"confirm": True}, headers=auth["headers"])
    assert response.status_code == 403


def test_restrict_succeeds_with_elevated_auth(client, elevated_auth):
    account_id = elevated_auth["account_id"]
    response = client.post(f"/accounts/{account_id}/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "temporarily_restricted"
    assert body["case_reference"].startswith("CASE-")
    with SessionLocal() as db:
        account = db.get(Account, account_id)
        assert account.status == "temporarily_restricted"


def test_restrict_already_restricted_conflict(client, elevated_auth):
    account_id = elevated_auth["account_id"]
    client.post(f"/accounts/{account_id}/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    second = client.post(f"/accounts/{account_id}/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    assert second.status_code == 409


def test_restrict_ownership_is_enforced(client, elevated_auth):
    response = client.post("/accounts/2/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    assert response.status_code == 404


def test_step_up_start_requires_auth(client):
    response = client.post("/auth/step-up/start")
    assert response.status_code in {401, 403}


def test_step_up_start_returns_challenge_without_leaking_otp(client, auth):
    response = client.post("/auth/step-up/start", headers=auth["headers"])
    assert response.status_code == 201
    assert set(response.json()) == {"challenge_id", "expires_in_seconds"}


def test_lift_restriction_requires_elevated_auth(client, auth):
    response = client.post(f"/accounts/{auth['account_id']}/lift-restriction", json={"confirm": True}, headers=auth["headers"])
    assert response.status_code == 403


def test_lift_restriction_when_not_restricted_conflict(client, elevated_auth):
    account_id = elevated_auth["account_id"]
    response = client.post(f"/accounts/{account_id}/lift-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    assert response.status_code == 409


def test_lift_restriction_succeeds_and_resolves_case(client, elevated_auth):
    account_id = elevated_auth["account_id"]
    restrict = client.post(f"/accounts/{account_id}/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    case_reference = restrict.json()["case_reference"]

    response = client.post(f"/accounts/{account_id}/lift-restriction", json={"confirm": True, "resolution_note": "Confirmed with customer"},
                           headers=elevated_auth["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["case_reference"] == case_reference

    with SessionLocal() as db:
        account = db.get(Account, account_id)
        assert account.status == "active"
        case = db.scalar(select(SupportCase).where(SupportCase.case_reference == case_reference))
        assert case.status == "resolved"
        assert "Confirmed with customer" in case.description


def test_lift_restriction_missing_confirm_rejected(client, elevated_auth):
    account_id = elevated_auth["account_id"]
    client.post(f"/accounts/{account_id}/temporary-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    response = client.post(f"/accounts/{account_id}/lift-restriction", json={}, headers=elevated_auth["headers"])
    assert response.status_code == 422


def test_lift_restriction_ownership_is_enforced(client, elevated_auth):
    response = client.post("/accounts/2/lift-restriction", json={"confirm": True}, headers=elevated_auth["headers"])
    assert response.status_code == 404
