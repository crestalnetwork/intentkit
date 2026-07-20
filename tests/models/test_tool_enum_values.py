"""Pin the persisted enum string VALUES that the skill->tool rename flipped.

These strings are written to the DB / sent on the wire, so a missed literal
compiles fine but corrupts data. The skill->tool DB rename is captured in the
Alembic baseline; these asserts are the canaries.
"""

from intentkit.models.app_setting import DEFAULT_SYSTEM_MESSAGES, SystemMessageType
from intentkit.models.chat import AuthorType
from intentkit.models.credit.base import DEFAULT_PLATFORM_ACCOUNT_TOOL
from intentkit.models.credit.event import EventType
from intentkit.models.credit.price import PriceEntity
from intentkit.models.credit.transaction import TransactionType


def test_persisted_enum_values_flipped_to_tool():
    assert AuthorType.TOOL.value == "tool"
    assert EventType.TOOL_CALL.value == "tool_call"
    assert PriceEntity.TOOL_CALL.value == "tool_call"
    assert TransactionType.RECEIVE_BASE_TOOL.value == "receive_base_tool"
    assert DEFAULT_PLATFORM_ACCOUNT_TOOL == "platform_tool"
    assert SystemMessageType.TOOL_INTERRUPTED.value == "tool_interrupted"
    assert "tool_interrupted" in DEFAULT_SYSTEM_MESSAGES


def test_no_skill_enum_remnants():
    assert not hasattr(AuthorType, "SKILL")
    assert not hasattr(EventType, "SKILL_CALL")
    assert not hasattr(PriceEntity, "SKILL_CALL")
    assert not hasattr(TransactionType, "RECEIVE_BASE_SKILL")
    assert not hasattr(SystemMessageType, "SKILL_INTERRUPTED")
    assert "skill_interrupted" not in DEFAULT_SYSTEM_MESSAGES
