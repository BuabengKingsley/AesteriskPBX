import pytest

from app.ai.intents import IntentType, detect_intent


@pytest.mark.parametrize("text,expected", [
    ("I noticed a transfer I did not make", IntentType.REPORT_UNAUTHORISED_TRANSACTION),
    ("This looks like fraud on my account", IntentType.REPORT_UNAUTHORISED_TRANSACTION),
    ("Please block my account right now", IntentType.TEMPORARILY_RESTRICT_ACCOUNT),
    ("Can you verify transaction TXN-01-0002", IntentType.VERIFY_TRANSACTION),
    ("What are my recent transactions", IntentType.LIST_TRANSACTIONS),
    ("What is my account balance", IntentType.CHECK_BALANCE),
    ("I want to file a complaint", IntentType.CREATE_SUPPORT_CASE),
    ("I want to speak to a human", IntentType.TRANSFER_TO_HUMAN),
    ("What can you do", IntentType.GENERAL_HELP),
    ("asdf qwerty", IntentType.UNKNOWN),
    ("", IntentType.UNKNOWN),
])
def test_detect_intent(text, expected):
    assert detect_intent(text) == expected


def test_unauthorised_transaction_takes_priority_over_generic_transaction_keyword():
    assert detect_intent("I didn't make this transaction") == IntentType.REPORT_UNAUTHORISED_TRANSACTION
