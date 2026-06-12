import pytest
from langchain_core.tools.base import ToolException

from intentkit.skills.xmtp.transfer import _parse_token_amount


def test_parse_token_amount_preserves_large_integer_precision():
    assert (
        _parse_token_amount("123456789123456789.123456789123456789", 18)
        == 123456789123456789123456789123456789
    )


@pytest.mark.parametrize("amount", ["1e309", "Infinity", "NaN", "0", "-1"])
def test_parse_token_amount_rejects_non_positive_or_non_finite_values(amount):
    with pytest.raises(ToolException):
        _parse_token_amount(amount, 18)


def test_parse_token_amount_rejects_more_precision_than_token_supports():
    with pytest.raises(ToolException):
        _parse_token_amount("1.0000001", 6)
