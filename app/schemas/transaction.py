from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    transaction_reference: str
    account: str
    transaction_type: str
    amount: Decimal
    currency: str
    recipient_or_merchant: str
    description: str
    transaction_date: datetime
    status: str
    fraud_flag: bool

