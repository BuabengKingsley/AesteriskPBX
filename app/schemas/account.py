from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountSummary(BaseModel):
    id: int
    account: str
    account_type: str
    currency: str
    status: str
    model_config = ConfigDict(from_attributes=True)


class BalanceResponse(BaseModel):
    account: str
    currency: str
    available_balance: Decimal

