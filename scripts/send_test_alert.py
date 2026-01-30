#!/usr/bin/env python3
"""
Send a test alert message using the configured alert system.

Usage:
    python intentkit/scripts/send_test_alert.py "Your message here"

If no message is provided, a default message is used.
"""

import logging
import sys

from intentkit.config.config import config
from intentkit.utils.alert import cleanup_alert, send_alert


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    message = "Test alert message from send_test_alert.py"
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:]).strip() or message

    logging.info("Sending test alert message...")
    send_alert(message)
    logging.info("Test alert message sent (or logged if no alert service configured).")


if __name__ == "__main__":
    _ = config
    try:
        main()
    finally:
        cleanup_alert()
