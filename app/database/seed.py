from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Customer, Transaction

CUSTOMERS = [
    ("CUS-1001", "Kwame Mensah", "+233200000001", "4350.75"),
    ("CUS-1002", "Ama Owusu", "+233200000002", "8275.20"),
    ("CUS-1003", "Kojo Asare", "+233200000003", "1220.00"),
    ("CUS-1004", "Abena Boateng", "+233200000004", "19640.50"),
    ("CUS-1005", "Kofi Antwi", "+233200000005", "675.35"),
]
KINDS = [
    ("card_purchase", "Melcom", "Card purchase"), ("bank_transfer", "ABC Ventures", "Bank transfer"),
    ("atm_withdrawal", "Airport ATM", "ATM withdrawal"), ("mobile_money_transfer", "Mobile wallet", "Mobile money transfer"),
    ("online_payment", "Online Store", "Online payment"), ("utility_payment", "ECG", "Utility payment"),
    ("card_purchase", "Pharmacy", "Card purchase"), ("mobile_money_transfer", "Airtime", "Airtime purchase"),
]


def seed_database(db: Session) -> None:
    if db.scalar(select(func.count(Customer.id))):
        return
    now = datetime.now(timezone.utc)
    for customer_index, (reference, name, phone, balance) in enumerate(CUSTOMERS, start=1):
        customer = Customer(customer_reference=reference, full_name=name, phone_number=phone)
        db.add(customer)
        db.flush()
        account = Account(customer_id=customer.id, account_number=f"01000000{customer_index:04d}",
                          account_number_masked=f"****{customer_index:04d}", account_type="savings",
                          currency="GHS", available_balance=Decimal(balance))
        db.add(account)
        db.flush()
        for tx_index, (kind, party, description) in enumerate(KINDS, start=1):
            suspicious = (customer_index, tx_index) in {(1, 2), (4, 5)}
            db.add(Transaction(transaction_reference=f"TXN-{customer_index:02d}-{tx_index:04d}", account_id=account.id,
                               transaction_type=kind, amount=Decimal(25 * tx_index + customer_index * 10), currency="GHS",
                               recipient_or_merchant=party, description=description,
                               transaction_date=now - timedelta(days=tx_index + customer_index), fraud_flag=suspicious))
    db.commit()
