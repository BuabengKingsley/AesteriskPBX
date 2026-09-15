from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ReportUnauthorisedTransactionRequest(BaseModel):
    confirm: bool = Field(...)

    @model_validator(mode="after")
    def must_confirm(self):
        if not self.confirm:
            raise ValueError("Explicit confirmation is required (confirm=true)")
        return self


class ReportUnauthorisedTransactionResponse(BaseModel):
    case_reference: str
    transaction_reference: str
    status: str
    risk_level: str
    created_at: datetime


class TemporaryRestrictionRequest(BaseModel):
    confirm: bool = Field(...)
    reason: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def must_confirm(self):
        if not self.confirm:
            raise ValueError("Explicit confirmation is required (confirm=true)")
        return self


class TemporaryRestrictionResponse(BaseModel):
    account: str
    status: str
    case_reference: str


class LiftRestrictionRequest(BaseModel):
    confirm: bool = Field(...)
    resolution_note: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def must_confirm(self):
        if not self.confirm:
            raise ValueError("Explicit confirmation is required (confirm=true)")
        return self


class LiftRestrictionResponse(BaseModel):
    account: str
    status: str
    case_reference: str | None
