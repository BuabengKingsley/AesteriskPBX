import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Customer, SupportCase, Transaction
from app.services.audit_service import record_audit


def generate_case_reference() -> str:
    return f"CASE-{uuid.uuid4().hex[:10].upper()}"


def report_unauthorised_transaction(db: Session, *, customer: Customer, transaction: Transaction, call_id: str | None = None) -> SupportCase:
    if transaction.status == "disputed":
        raise HTTPException(status_code=409, detail="Transaction has already been reported")
    transaction.status = "disputed"
    risk_level = "high" if transaction.fraud_flag else "medium"
    case = SupportCase(case_reference=generate_case_reference(), customer_id=customer.id, transaction_id=transaction.id,
                       case_type="unauthorised_transaction", description="Customer reported this transaction as unauthorised.",
                       status="open", risk_level=risk_level, call_id=call_id)
    db.add(case)
    record_audit(db, customer_id=customer.id, event_type="transaction_disputed", action="report_unauthorised_transaction",
                 result="success", metadata={"transaction_reference": transaction.transaction_reference}, call_id=call_id)
    db.commit()
    db.refresh(case)
    return case


def temporarily_restrict_account(db: Session, *, customer: Customer, account: Account, reason: str | None, call_id: str | None = None) -> SupportCase:
    if account.status == "temporarily_restricted":
        raise HTTPException(status_code=409, detail="Account is already restricted")
    account.status = "temporarily_restricted"
    case = SupportCase(case_reference=generate_case_reference(), customer_id=customer.id, transaction_id=None,
                       case_type="account_restriction", description=reason or "Customer requested a temporary account restriction.",
                       status="open", risk_level="high", call_id=call_id)
    db.add(case)
    record_audit(db, customer_id=customer.id, event_type="account_restricted", action="temporarily_restrict_account",
                 result="success", metadata={"account_id": account.id}, call_id=call_id)
    db.commit()
    db.refresh(case)
    return case


def lift_account_restriction(db: Session, *, customer: Customer, account: Account, resolution_note: str | None, call_id: str | None = None) -> SupportCase | None:
    if account.status != "temporarily_restricted":
        raise HTTPException(status_code=409, detail="Account is not currently restricted")
    account.status = "active"
    case = db.scalar(select(SupportCase).where(SupportCase.customer_id == customer.id, SupportCase.case_type == "account_restriction",
                                               SupportCase.status == "open").order_by(SupportCase.created_at.desc()))
    if case:
        case.status = "resolved"
        if resolution_note:
            case.description = f"{case.description}\nResolution: {resolution_note}"
    record_audit(db, customer_id=customer.id, event_type="account_restriction_lifted", action="lift_account_restriction",
                result="success", metadata={"account_id": account.id}, call_id=call_id)
    db.commit()
    if case:
        db.refresh(case)
    return case
