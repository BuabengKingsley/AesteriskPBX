from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intents import IntentType
from app.models import Account, CallSession, Customer, SupportCase, Transaction


@dataclass
class HandoffSummary:
    call_id: str
    authenticated: bool
    customer_reference: str | None
    masked_account: str | None
    intent: str | None
    transaction_reference: str | None
    amount: str | None
    currency: str | None
    case_reference: str | None
    escalation_reason: str


def prepare_human_handoff(db: Session, call: CallSession) -> HandoffSummary:
    customer = db.get(Customer, call.customer_id) if call.customer_id else None
    account = db.scalar(select(Account).where(Account.customer_id == customer.id)) if customer else None
    case = db.scalar(select(SupportCase).where(SupportCase.call_id == call.call_id).order_by(SupportCase.created_at.desc()))
    tx = db.get(Transaction, case.transaction_id) if case and case.transaction_id else None
    escalation_reason = "customer_requested" if call.current_intent == IntentType.TRANSFER_TO_HUMAN.value else "policy_or_auth_failure"
    return HandoffSummary(
        call_id=call.call_id,
        authenticated=call.authenticated,
        customer_reference=customer.customer_reference if customer else None,
        masked_account=account.account_number_masked if account else None,
        intent=call.current_intent,
        transaction_reference=tx.transaction_reference if tx else None,
        amount=str(tx.amount) if tx else None,
        currency=tx.currency if tx else None,
        case_reference=case.case_reference if case else None,
        escalation_reason=escalation_reason,
    )
