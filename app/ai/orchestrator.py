import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intents import IntentType, detect_intent
from app.ai.policy import evaluate_policy
from app.ai.state_machine import CallEvent, CallState, next_state
from app.ai.tools import invoke_tool
from app.core.config import Settings
from app.models import AuthSession, CallSession, Customer
from app.services.authentication_service import as_utc, start_authentication, utcnow, verify_otp

GREETING_TEXT = "Welcome. How can I help you today?"
CLARIFICATION_TEXT = "Sorry, I did not understand that. You can ask about your balance, your recent transactions, or say 'human' to speak with someone."
ASK_FOR_IDENTIFIER_TEXT = "For your security, please tell me your customer reference or registered phone number."
ASK_FOR_OTP_TEXT = "I've sent a one-time code. Please read it back to me."
INVALID_IDENTIFIER_TEXT = "I could not find an account matching that. Please try your customer reference again."
OTP_RETRY_TEXT = "That code was not correct. Please try again."
OTP_EXHAUSTED_TEXT = "That challenge has run out of attempts. Please start over."
GOODBYE_TEXT = "No problem, is there anything else I can help with?"

_CONFIRMATION_PROMPTS: dict[IntentType, str] = {
    IntentType.REPORT_UNAUTHORISED_TRANSACTION: "I can report this transaction as unauthorised and open a case. Should I proceed?",
    IntentType.TEMPORARILY_RESTRICT_ACCOUNT: "For your protection, I can temporarily restrict your account. Should I proceed?",
    IntentType.CREATE_SUPPORT_CASE: "I can open a support case for this. Should I proceed?",
}

_AFFIRMATIVE_WORDS = {"yes", "yeah", "yep", "confirm", "correct", "proceed", "sure", "please do"}
_NEGATIVE_WORDS = {"no", "nope", "cancel", "don't", "do not", "stop"}


@dataclass
class TurnResult:
    call_id: str
    state: str
    intent: str | None
    assistant_text: str
    requires_authentication: bool
    requires_confirmation: bool
    tool_executed: str | None


def start_call(db: Session, caller_phone_number: str | None) -> TurnResult:
    call = CallSession(call_id=str(uuid.uuid4()), caller_phone_number=caller_phone_number, current_state=CallState.CALL_STARTED.value)
    db.add(call)
    call.current_state = next_state(CallState.CALL_STARTED, CallEvent.START).value
    db.commit()
    return TurnResult(call_id=call.call_id, state=call.current_state, intent=None, assistant_text=GREETING_TEXT,
                      requires_authentication=False, requires_confirmation=False, tool_executed=None)


def _current_auth_level(db: Session, call: CallSession) -> str:
    if call.auth_session_id is None:
        return "none"
    session = db.get(AuthSession, call.auth_session_id)
    if not session or not session.session_expires_at or as_utc(session.session_expires_at) <= utcnow():
        call.authenticated = False
        call.auth_session_id = None
        return "none"
    return session.authentication_level


def _is_affirmative(text: str) -> bool:
    normalized = text.strip().lower()
    return any(word in normalized for word in _AFFIRMATIVE_WORDS)


def _is_negative(text: str) -> bool:
    normalized = text.strip().lower()
    return any(word in normalized for word in _NEGATIVE_WORDS)


def handle_message(db: Session, call: CallSession, text: str, settings: Settings) -> TurnResult:
    state = CallState(call.current_state)
    if state == CallState.AUTHENTICATING:
        result = _handle_otp_turn(db, call, text, settings)
    elif state == CallState.AUTHENTICATION_REQUIRED and call.customer_id is None:
        result = _handle_identifier_turn(db, call, text, settings)
    elif state == CallState.AWAITING_CONFIRMATION:
        result = _handle_confirmation_turn(db, call, text, settings)
    else:
        result = _handle_intent_turn(db, call, text, settings)
    db.commit()
    return result


def _handle_intent_turn(db: Session, call: CallSession, text: str, settings: Settings) -> TurnResult:
    if call.current_state in (CallState.GREETING.value, CallState.COMPLETED.value, CallState.AUTHENTICATION_FAILED.value):
        event = CallEvent.GREETED if call.current_state == CallState.GREETING.value else CallEvent.RESET_FOR_NEXT_TURN
        call.current_state = next_state(CallState(call.current_state), event).value

    intent = detect_intent(text)
    call.current_intent = intent.value

    if intent == IntentType.TRANSFER_TO_HUMAN:
        call.current_state = next_state(CallState(call.current_state), CallEvent.HANDOFF_REQUESTED).value
        call.escalation_required = True
        return TurnResult(call.call_id, call.current_state, intent.value, "I am transferring you to a human support agent now.",
                          False, False, None)

    if intent == IntentType.UNKNOWN:
        return TurnResult(call.call_id, call.current_state, intent.value, CLARIFICATION_TEXT, False, False, None)

    if intent == IntentType.GENERAL_HELP:
        return TurnResult(call.call_id, call.current_state, intent.value,
                          "I can check your balance, list recent transactions, help verify a transaction, report fraud, or restrict your account.",
                          False, False, None)

    return _process_intent(db, call, text, settings, confirmed=False)


def _process_intent(db: Session, call: CallSession, text: str, settings: Settings, confirmed: bool) -> TurnResult:
    intent = IntentType(call.current_intent)
    level = _current_auth_level(db, call)
    decision = evaluate_policy(intent, level, confirmed)

    if decision.requires_authentication and level == "none":
        call.current_state = next_state(CallState(call.current_state), CallEvent.INTENT_NEEDS_AUTH).value
        return TurnResult(call.call_id, call.current_state, intent.value, ASK_FOR_IDENTIFIER_TEXT, True, False, None)

    if decision.requires_step_up and level != "elevated":
        challenge_id = start_authentication(db, _customer_reference(db, call), settings)
        call.pending_challenge_id = challenge_id
        call.pending_step_up = True
        call.current_state = next_state(CallState.AUTHENTICATION_REQUIRED, CallEvent.OTP_REQUESTED).value
        return TurnResult(call.call_id, call.current_state, intent.value, ASK_FOR_OTP_TEXT, True, False, None)

    if decision.requires_confirmation and not confirmed:
        call.current_state = next_state(CallState.PROCESSING_REQUEST, CallEvent.ACTION_REQUIRES_CONFIRMATION).value
        prompt = _CONFIRMATION_PROMPTS.get(intent, "Should I proceed?")
        return TurnResult(call.call_id, call.current_state, intent.value, prompt, False, True, None)

    result = invoke_tool(db, call, intent, settings, confirmed, text)
    call.current_state = next_state(CallState.PROCESSING_REQUEST, CallEvent.ACTION_DONE).value
    return TurnResult(call.call_id, call.current_state, intent.value, result.assistant_text, False, False, result.tool_name)


def _customer_reference(db: Session, call: CallSession) -> str:
    customer = db.get(Customer, call.customer_id)
    return customer.customer_reference


def _handle_identifier_turn(db: Session, call: CallSession, text: str, settings: Settings) -> TurnResult:
    identifier = text.strip()
    try:
        challenge_id = start_authentication(db, identifier, settings)
    except HTTPException:
        return TurnResult(call.call_id, call.current_state, call.current_intent, INVALID_IDENTIFIER_TEXT, True, False, None)

    challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == challenge_id))
    call.customer_id = challenge.customer_id
    call.pending_challenge_id = challenge_id
    call.current_state = next_state(CallState.AUTHENTICATION_REQUIRED, CallEvent.OTP_REQUESTED).value
    return TurnResult(call.call_id, call.current_state, call.current_intent, ASK_FOR_OTP_TEXT, True, False, None)


def _handle_otp_turn(db: Session, call: CallSession, text: str, settings: Settings) -> TurnResult:
    otp = text.strip()
    level = "elevated" if call.pending_step_up else "standard"
    try:
        verify_otp(db, call.pending_challenge_id, otp, settings, authentication_level=level)
    except HTTPException:
        challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == call.pending_challenge_id))
        if not challenge or challenge.failed_attempts >= settings.otp_max_attempts:
            call.current_state = next_state(CallState.AUTHENTICATING, CallEvent.OTP_EXHAUSTED).value
            call.pending_challenge_id = None
            call.pending_step_up = False
            return TurnResult(call.call_id, call.current_state, call.current_intent, OTP_EXHAUSTED_TEXT, True, False, None)
        call.current_state = next_state(CallState.AUTHENTICATING, CallEvent.OTP_FAILED).value
        return TurnResult(call.call_id, call.current_state, call.current_intent, OTP_RETRY_TEXT, True, False, None)

    challenge = db.scalar(select(AuthSession).where(AuthSession.session_id == call.pending_challenge_id))
    call.authenticated = True
    call.auth_session_id = challenge.id
    call.pending_challenge_id = None
    call.pending_step_up = False
    call.current_state = next_state(CallState.AUTHENTICATING, CallEvent.OTP_VERIFIED).value

    if call.current_intent:
        return _process_intent(db, call, "", settings, confirmed=False)
    return TurnResult(call.call_id, call.current_state, call.current_intent, "You're verified. How can I help?", False, False, None)


def _handle_confirmation_turn(db: Session, call: CallSession, text: str, settings: Settings) -> TurnResult:
    if _is_affirmative(text):
        return _process_intent(db, call, text, settings, confirmed=True)
    if _is_negative(text):
        call.current_state = next_state(CallState.AWAITING_CONFIRMATION, CallEvent.DECLINED).value
        return TurnResult(call.call_id, call.current_state, call.current_intent, GOODBYE_TEXT, False, False, None)
    return TurnResult(call.call_id, call.current_state, call.current_intent,
                      "Sorry, should I proceed? Please say yes or no.", False, True, None)
