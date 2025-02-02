import random
import string


def generate_tx_confirm_string(length) -> str:
    """
    Generates a random string of the specified length for the transaction reference.

    Args:
      length: The desired length of the random string.

    Returns:
      A random string of the specified length.
    """
    letters_and_digits = string.ascii_letters + string.digits
    return "tx-" + "".join(random.choice(letters_and_digits) for _ in range(length))
