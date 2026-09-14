from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accounts: Mapped[list["Account"]] = relationship(back_populates="customer")


class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(32), unique=True)
    account_number_masked: Mapped[str] = mapped_column(String(32))
    account_type: Mapped[str] = mapped_column(String(30))
    currency: Mapped[str] = mapped_column(String(3))
    available_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(30), default="active")
    customer: Mapped[Customer] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    transaction_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    recipient_or_merchant: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(200))
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    account: Mapped[Account] = relationship(back_populates="transactions")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    otp_hash: Mapped[str] = mapped_column(String(64))
    otp_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    authentication_level: Mapped[str] = mapped_column(String(20), default="standard")
    session_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(String(30))
    event_metadata: Mapped[str] = mapped_column("metadata", Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CallSession(Base):
    __tablename__ = "call_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    caller_phone_number: Mapped[str | None] = mapped_column(String(24), nullable=True)
    current_state: Mapped[str] = mapped_column(String(40), default="CALL_STARTED")
    current_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_challenge_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_step_up: Mapped[bool] = mapped_column(Boolean, default=False)
    auth_session_id: Mapped[int | None] = mapped_column(ForeignKey("auth_sessions.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_required: Mapped[bool] = mapped_column(Boolean, default=False)


class SupportCase(Base):
    __tablename__ = "support_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    case_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open")
    risk_level: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
