import re
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intents import IntentType
from app.core.config import Settings
from app.models import Account, CallSession, Customer, SupportCase, Transaction
from app.services.audit_service import record_audit
from app.services.case_service import generate_case_reference, report_unauthorised_transaction, temporarily_restrict_account

TRANSACTION_REFERENCE_PATTERN = re.compile(r"TXN-\d{2,}-\d{4,}", re.IGNORECASE)


@dataclass
class ToolContext:
    db: Session
    call: CallSession
    customer: Customer
    settings: Settings


@dataclass
class ToolResult:
    tool_name: str
    assistant_text: str
    data: dict = field(default_factory=dict)


def _customer_account(ctx: ToolContext) -> Account | None:
    return ctx.db.scalar(select(Account).where(Account.customer_id == ctx.customer.id).order_by(Account.id))


def _find_transaction_by_reference(ctx: ToolContext, reference: str) -> Transaction | None:
    return ctx.db.scalar(select(Transaction).join(Account).where(Transaction.transaction_reference == reference,
                                                                  Account.customer_id == ctx.customer.id))


def _tool_check_balance(ctx: ToolContext, params: dict) -> ToolResult:
    account = _customer_account(ctx)
    if not account:
        return ToolResult("check_balance", "I could not find an account on this profile.")
    return ToolResult("check_balance", f"Your available balance is {account.available_balance} {account.currency}.",
                      data={"account": account.account_number_masked, "available_balance": str(account.available_balance), "currency": account.currency})


def _tool_list_transactions(ctx: ToolContext, params: dict) -> ToolResult:
    account = _customer_account(ctx)
    if not account:
        return ToolResult("list_transactions", "I could not find an account on this profile.")
    transactions = ctx.db.scalars(select(Transaction).where(Transaction.account_id == account.id)
                                  .order_by(Transaction.transaction_date.desc()).limit(5)).all()
    if not transactions:
        return ToolResult("list_transactions", "You have no recent transactions.")
    summary = "; ".join(f"{tx.amount} {tx.currency} to {tx.recipient_or_merchant} on {tx.transaction_date.date()}" for tx in transactions)
    return ToolResult("list_transactions", f"Here are your recent transactions: {summary}.",
                      data={"transaction_references": [tx.transaction_reference for tx in transactions]})


def _tool_verify_transaction(ctx: ToolContext, params: dict) -> ToolResult:
    reference = params.get("transaction_reference")
    if not reference:
        return ToolResult("verify_transaction", "Which transaction reference would you like me to check?")
    tx = _find_transaction_by_reference(ctx, reference)
    if not tx:
        return ToolResult("verify_transaction", f"I could not find a transaction matching {reference} on your account.")
    return ToolResult("verify_transaction", f"Transaction {tx.transaction_reference} is a {tx.amount} {tx.currency} "
                      f"{tx.transaction_type} to {tx.recipient_or_merchant} on {tx.transaction_date.date()}, status {tx.status}.",
                      data={"transaction_reference": tx.transaction_reference})


def _tool_report_unauthorised_transaction(ctx: ToolContext, params: dict) -> ToolResult:
    reference = params.get("transaction_reference")
    if not reference:
        return ToolResult("report_unauthorised_transaction", "Which transaction would you like to report as unauthorised?")
    tx = _find_transaction_by_reference(ctx, reference)
    if not tx:
        return ToolResult("report_unauthorised_transaction", f"I could not find a transaction matching {reference} on your account.")
    case = report_unauthorised_transaction(ctx.db, customer=ctx.customer, transaction=tx, call_id=ctx.call.call_id)
    return ToolResult("report_unauthorised_transaction",
                      f"I have reported transaction {tx.transaction_reference} as unauthorised and opened case {case.case_reference}.",
                      data={"case_reference": case.case_reference, "transaction_reference": tx.transaction_reference})


def _tool_temporarily_restrict_account(ctx: ToolContext, params: dict) -> ToolResult:
    account = _customer_account(ctx)
    if not account:
        return ToolResult("temporarily_restrict_account", "I could not find an account on this profile.")
    case = temporarily_restrict_account(ctx.db, customer=ctx.customer, account=account, reason=params.get("raw_text"), call_id=ctx.call.call_id)
    return ToolResult("temporarily_restrict_account",
                      f"Your account has been temporarily restricted. Reference case {case.case_reference}.",
                      data={"case_reference": case.case_reference, "account": account.account_number_masked})


def _tool_create_support_case(ctx: ToolContext, params: dict) -> ToolResult:
    reference = generate_case_reference()
    support_case = SupportCase(case_reference=reference, customer_id=ctx.customer.id, transaction_id=None,
                               call_id=ctx.call.call_id, case_type="general_support",
                               description=params.get("raw_text") or "Customer requested a support case.",
                               status="open", risk_level="medium")
    ctx.db.add(support_case)
    ctx.db.flush()
    return ToolResult("create_support_case", f"I have opened support case {reference} for you.", data={"case_reference": reference})


def _tool_transfer_to_human(ctx: ToolContext, params: dict) -> ToolResult:
    ctx.call.escalation_required = True
    return ToolResult("transfer_to_human", "I am transferring you to a human support agent now.")


TOOL_REGISTRY: dict[IntentType, Callable[[ToolContext, dict], ToolResult]] = {
    IntentType.CHECK_BALANCE: _tool_check_balance,
    IntentType.LIST_TRANSACTIONS: _tool_list_transactions,
    IntentType.VERIFY_TRANSACTION: _tool_verify_transaction,
    IntentType.REPORT_UNAUTHORISED_TRANSACTION: _tool_report_unauthorised_transaction,
    IntentType.TEMPORARILY_RESTRICT_ACCOUNT: _tool_temporarily_restrict_account,
    IntentType.CREATE_SUPPORT_CASE: _tool_create_support_case,
    IntentType.TRANSFER_TO_HUMAN: _tool_transfer_to_human,
}


def invoke_tool(db: Session, call: CallSession, intent: IntentType, settings: Settings, confirmed: bool, raw_text: str) -> ToolResult:
    handler = TOOL_REGISTRY[intent]
    customer = db.get(Customer, call.customer_id)
    ctx = ToolContext(db=db, call=call, customer=customer, settings=settings)
    reference_match = TRANSACTION_REFERENCE_PATTERN.search(raw_text)
    params = {"confirmed": confirmed, "raw_text": raw_text, "transaction_reference": reference_match.group(0).upper() if reference_match else None}
    result = handler(ctx, params)
    record_audit(db, customer_id=customer.id, event_type="tool_invoked", action=intent.value, result="success",
                metadata={"tool": result.tool_name}, call_id=call.call_id)
    db.commit()
    return result
