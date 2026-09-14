from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.handoff import prepare_human_handoff
from app.ai.orchestrator import handle_message, start_call
from app.ai.state_machine import CallState
from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models import CallSession
from app.schemas.conversation import (
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationStartRequest,
    ConversationStartResponse,
    HandoffSummaryResponse,
)

router = APIRouter(prefix="/conversation", tags=["conversation"])


def _require_agent_key(settings: Settings, x_agent_key: str | None) -> None:
    if not x_agent_key or x_agent_key != settings.agent_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing agent key")


@router.post("/start", response_model=ConversationStartResponse, status_code=201)
def start(payload: ConversationStartRequest, db: Annotated[Session, Depends(get_db)]):
    result = start_call(db, payload.caller_phone_number)
    return ConversationStartResponse(call_id=result.call_id, state=result.state, assistant_text=result.assistant_text)


@router.post("/{call_id}/message", response_model=ConversationMessageResponse)
def message(call_id: str, payload: ConversationMessageRequest, db: Annotated[Session, Depends(get_db)],
           settings: Annotated[Settings, Depends(get_settings)]):
    call = db.scalar(select(CallSession).where(CallSession.call_id == call_id))
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.current_state in (CallState.CALL_TERMINATED.value, CallState.HUMAN_HANDOFF.value):
        raise HTTPException(status_code=409, detail="Call is no longer active")
    result = handle_message(db, call, payload.text, settings)
    return ConversationMessageResponse(**asdict(result))


@router.get("/{call_id}/handoff-summary", response_model=HandoffSummaryResponse)
def handoff_summary(call_id: str, db: Annotated[Session, Depends(get_db)], settings: Annotated[Settings, Depends(get_settings)],
                    x_agent_key: Annotated[str | None, Header()] = None):
    _require_agent_key(settings, x_agent_key)
    call = db.scalar(select(CallSession).where(CallSession.call_id == call_id))
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return HandoffSummaryResponse(**asdict(prepare_human_handoff(db, call)))
