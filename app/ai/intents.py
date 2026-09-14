from enum import Enum


class IntentType(str, Enum):
    CHECK_BALANCE = "CHECK_BALANCE"
    LIST_TRANSACTIONS = "LIST_TRANSACTIONS"
    VERIFY_TRANSACTION = "VERIFY_TRANSACTION"
    REPORT_UNAUTHORISED_TRANSACTION = "REPORT_UNAUTHORISED_TRANSACTION"
    TEMPORARILY_RESTRICT_ACCOUNT = "TEMPORARILY_RESTRICT_ACCOUNT"
    CREATE_SUPPORT_CASE = "CREATE_SUPPORT_CASE"
    TRANSFER_TO_HUMAN = "TRANSFER_TO_HUMAN"
    GENERAL_HELP = "GENERAL_HELP"
    UNKNOWN = "UNKNOWN"


# Ordered list, first-match-wins. Specific/high-risk intents are checked before
# generic ones so e.g. "I didn't make this transaction" hits
# REPORT_UNAUTHORISED_TRANSACTION rather than LIST_TRANSACTIONS's generic
# "transaction" keyword.
_KEYWORDS: list[tuple[IntentType, tuple[str, ...]]] = [
    (IntentType.REPORT_UNAUTHORISED_TRANSACTION, ("unauthorised", "unauthorized", "didn't make", "did not make", "not mine", "fraud")),
    (IntentType.TEMPORARILY_RESTRICT_ACCOUNT, ("block my account", "restrict my account", "freeze my account", "lock my account", "block my card")),
    (IntentType.VERIFY_TRANSACTION, ("is this transaction", "verify transaction", "confirm transaction", "check transaction")),
    (IntentType.LIST_TRANSACTIONS, ("transactions", "transaction history", "recent transactions", "statement")),
    (IntentType.CHECK_BALANCE, ("balance", "how much do i have", "account balance")),
    (IntentType.CREATE_SUPPORT_CASE, ("open a case", "file a complaint", "complaint", "support case")),
    (IntentType.TRANSFER_TO_HUMAN, ("human", "agent", "representative", "speak to someone", "talk to a person")),
    (IntentType.GENERAL_HELP, ("help", "what can you do", "options")),
]


def detect_intent(text: str) -> IntentType:
    normalized = text.strip().lower()
    if not normalized:
        return IntentType.UNKNOWN
    for intent, keywords in _KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return intent
    return IntentType.UNKNOWN
