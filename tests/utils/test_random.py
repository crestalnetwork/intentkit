import string

from intentkit.utils.random import generate_tx_confirm_string


def test_generate_tx_confirm_string_prefix_and_length():
    token = generate_tx_confirm_string(8)

    assert token.startswith("tx-")
    assert len(token) == len("tx-") + 8
    assert all(char in string.ascii_letters + string.digits for char in token[3:])


def test_generate_tx_confirm_string_uniqueness(monkeypatch):
    """Test deterministic output by patching secrets.choice."""
    call_count = 0
    chars = list(string.ascii_letters + string.digits)

    def fake_choice(seq):
        nonlocal call_count
        result = seq[call_count % len(seq)]
        call_count += 1
        return result

    monkeypatch.setattr("intentkit.utils.random.secrets.choice", fake_choice)

    token = generate_tx_confirm_string(4)

    expected = "tx-" + "".join(chars[i] for i in range(4))
    assert token == expected
