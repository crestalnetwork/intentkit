import string

from intentkit.utils.random import generate_tx_confirm_string


def test_generate_tx_confirm_string_prefix_and_length():
    token = generate_tx_confirm_string(8)

    assert token.startswith("tx-")
    assert len(token) == len("tx-") + 8
    assert all(char in string.ascii_letters + string.digits for char in token[3:])


def test_generate_tx_confirm_string_uniqueness(monkeypatch):
    class DummyRandom:
        def __init__(self):
            self.calls = -1
            self.values = list(string.ascii_letters + string.digits)

        def choice(self, seq):
            self.calls += 1
            return seq[self.calls % len(seq)]

    dummy = DummyRandom()
    monkeypatch.setattr("intentkit.utils.random.random", dummy)

    token = generate_tx_confirm_string(4)

    expected = "tx-" + "".join(dummy.values[i] for i in range(4))
    assert token == expected
