from datetime import date, datetime, time, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_customer
from app.database.session import get_db
from app.models import Account, Customer, Transaction
from app.schemas.case import ReportUnauthorisedTransactionRequest, ReportUnauthorisedTransactionResponse
from app.schemas.transaction import TransactionResponse
from app.services.audit_service import record_audit
from app.services.case_service import report_unauthorised_transaction

router = APIRouter(tags=["transactions"])


def response(tx: Transaction) -> TransactionResponse:
    return TransactionResponse(transaction_reference=tx.transaction_reference, account=tx.account.account_number_masked,
        transaction_type=tx.transaction_type, amount=tx.amount, currency=tx.currency,
        recipient_or_merchant=tx.recipient_or_merchant, description=tx.description,
        transaction_date=tx.transaction_date, status=tx.status, fraud_flag=tx.fraud_flag)


@router.get("/accounts/{account_id}/transactions", response_model=list[TransactionResponse])
def list_transactions(account_id: int, customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)],
                      limit: int = Query(10, ge=1, le=100), start_date: date | None = None, end_date: date | None = None):
    account = db.scalar(select(Account).where(Account.id == account_id, Account.customer_id == customer.id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    stmt = select(Transaction).where(Transaction.account_id == account.id)
    if start_date:
        stmt = stmt.where(Transaction.transaction_date >= datetime.combine(start_date, time.min, timezone.utc))
    if end_date:
        stmt = stmt.where(Transaction.transaction_date <= datetime.combine(end_date, time.max, timezone.utc))
    transactions = db.scalars(stmt.order_by(Transaction.transaction_date.desc()).limit(limit)).all()
    record_audit(db, customer_id=customer.id, event_type="transactions_requested", action="list_transactions", result="success", metadata={"account_id": account.id})
    db.commit()
    return [response(tx) for tx in transactions]


@router.get("/transactions/{transaction_reference}", response_model=TransactionResponse)
def transaction_detail(transaction_reference: str, customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)]):
    tx = db.scalar(select(Transaction).join(Account).where(Transaction.transaction_reference == transaction_reference, Account.customer_id == customer.id))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    record_audit(db, customer_id=customer.id, event_type="transaction_requested", action="get_transaction", result="success", metadata={"transaction_reference": tx.transaction_reference})
    db.commit()
    return response(tx)


@router.post("/transactions/{transaction_reference}/report", response_model=ReportUnauthorisedTransactionResponse, status_code=201)
def report_unauthorised(transaction_reference: str, payload: ReportUnauthorisedTransactionRequest,
                        customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)]):
    tx = db.scalar(select(Transaction).join(Account).where(Transaction.transaction_reference == transaction_reference, Account.customer_id == customer.id))
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    case = report_unauthorised_transaction(db, customer=customer, transaction=tx)
    return ReportUnauthorisedTransactionResponse(case_reference=case.case_reference, transaction_reference=tx.transaction_reference,
                                                 status=tx.status, risk_level=case.risk_level, created_at=case.created_at)

