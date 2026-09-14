from dataclasses import dataclass

from app.ai.intents import IntentType


@dataclass
class PolicyRule:
    requires_authentication: bool
    requires_step_up: bool = False
    requires_confirmation: bool = False


@dataclass
class PolicyDecision:
    allowed: bool
    requires_authentication: bool
    requires_step_up: bool
    requires_confirmation: bool
    reason: str | None = None


POLICY_TABLE: dict[IntentType, PolicyRule] = {
    IntentType.CHECK_BALANCE: PolicyRule(requires_authentication=True),
    IntentType.LIST_TRANSACTIONS: PolicyRule(requires_authentication=True),
    IntentType.VERIFY_TRANSACTION: PolicyRule(requires_authentication=True),
    IntentType.REPORT_UNAUTHORISED_TRANSACTION: PolicyRule(requires_authentication=True, requires_confirmation=True),
    IntentType.TEMPORARILY_RESTRICT_ACCOUNT: PolicyRule(requires_authentication=True, requires_step_up=True, requires_confirmation=True),
    IntentType.CREATE_SUPPORT_CASE: PolicyRule(requires_authentication=True, requires_confirmation=True),
    IntentType.TRANSFER_TO_HUMAN: PolicyRule(requires_authentication=False),
    IntentType.GENERAL_HELP: PolicyRule(requires_authentication=False),
    IntentType.UNKNOWN: PolicyRule(requires_authentication=False),
}


def evaluate_policy(intent: IntentType, authentication_level: str, confirmed: bool) -> PolicyDecision:
    rule = POLICY_TABLE.get(intent, PolicyRule(requires_authentication=True))
    if rule.requires_authentication and authentication_level == "none":
        return PolicyDecision(False, True, rule.requires_step_up, rule.requires_confirmation, "authentication_required")
    if rule.requires_step_up and authentication_level != "elevated":
        return PolicyDecision(False, True, True, rule.requires_confirmation, "step_up_required")
    if rule.requires_confirmation and not confirmed:
        return PolicyDecision(False, False, False, True, "confirmation_required")
    return PolicyDecision(True, False, False, False)
