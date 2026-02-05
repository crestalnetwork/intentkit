from decimal import Decimal
from enum import Enum

# Precision constant for 4 decimal places
FOURPLACES = Decimal("0.0001")


class CreditType(str, Enum):
    """Credit type is used in db column names, do not change it."""

    FREE = "free_credits"
    REWARD = "reward_credits"
    PERMANENT = "credits"


class OwnerType(str, Enum):
    """Type of credit account owner."""

    USER = "user"
    AGENT = "agent"
    TEAM = "team"
    PLATFORM = "platform"


# Platform virtual account ids/owner ids, they are used for transaction balance tracing
# The owner id and account id are the same
DEFAULT_PLATFORM_ACCOUNT_RECHARGE = "platform_recharge"
DEFAULT_PLATFORM_ACCOUNT_REFILL = "platform_refill"
DEFAULT_PLATFORM_ACCOUNT_ADJUSTMENT = "platform_adjustment"
DEFAULT_PLATFORM_ACCOUNT_REWARD = "platform_reward"
DEFAULT_PLATFORM_ACCOUNT_REFUND = "platform_refund"
DEFAULT_PLATFORM_ACCOUNT_MESSAGE = "platform_message"
DEFAULT_PLATFORM_ACCOUNT_SKILL = "platform_skill"
DEFAULT_PLATFORM_ACCOUNT_MEMORY = "platform_memory"
DEFAULT_PLATFORM_ACCOUNT_VOICE = "platform_voice"
DEFAULT_PLATFORM_ACCOUNT_KNOWLEDGE = "platform_knowledge"
DEFAULT_PLATFORM_ACCOUNT_FEE = "platform_fee"
DEFAULT_PLATFORM_ACCOUNT_DEV = "platform_dev"
DEFAULT_PLATFORM_ACCOUNT_WITHDRAW = "platform_withdraw"
