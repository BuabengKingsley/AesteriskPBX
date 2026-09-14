from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_customer, current_elevated_customer
from app.database.session import get_db
from app.models import Account, Customer
from app.schemas.account import AccountSummary, BalanceResponse
from app.schemas.case import TemporaryRestrictionRequest, TemporaryRestrictionResponse
from app.services.audit_service import record_audit
from app.services.case_service import temporarily_restrict_account

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/me", response_model=list[AccountSummary])
def my_accounts(customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)]):
    accounts = db.scalars(select(Account).where(Account.customer_id == customer.id).order_by(Account.id)).all()
    return [AccountSummary(id=a.id, account=a.account_number_masked, account_type=a.account_type, currency=a.currency, status=a.status) for a in accounts]


@router.get("/{account_id}/balance", response_model=BalanceResponse)
def balance(account_id: int, customer: Annotated[Customer, Depends(current_customer)], db: Annotated[Session, Depends(get_db)]):
    account = db.scalar(select(Account).where(Account.id == account_id, Account.customer_id == customer.id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    record_audit(db, customer_id=customer.id, event_type="balance_requested", action="get_account_balance", result="success", metadata={"account_id": account.id})
    db.commit()
    return BalanceResponse(account=account.account_number_masked, currency=account.currency, available_balance=account.available_balance)


@router.post("/{account_id}/temporary-restriction", response_model=TemporaryRestrictionResponse, status_code=201)
def restrict_account(account_id: int, payload: TemporaryRestrictionRequest,
                     customer: Annotated[Customer, Depends(current_elevated_customer)], db: Annotated[Session, Depends(get_db)]):
    account = db.scalar(select(Account).where(Account.id == account_id, Account.customer_id == customer.id))
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    case = temporarily_restrict_account(db, customer=customer, account=account, reason=payload.reason)
    return TemporaryRestrictionResponse(account=account.account_number_masked, status=account.status, case_reference=case.case_reference)

