from pydantic import BaseModel, Field


class ConversationStartRequest(BaseModel):
    caller_phone_number: str | None = Field(None, min_length=7, max_length=24)


class ConversationStartResponse(BaseModel):
    call_id: str
    state: str
    assistant_text: str


class ConversationMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ConversationMessageResponse(BaseModel):
    call_id: str
    state: str
    intent: str | None
    assistant_text: str
    requires_authentication: bool
    requires_confirmation: bool
    tool_executed: str | None


class HandoffSummaryResponse(BaseModel):
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
