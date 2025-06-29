from typing import Optional


class RateLimitExceeded(Exception):
    """Rate limit exceeded"""

    def __init__(self, message: Optional[str] = "Rate limit exceeded"):
        self.message = message
        super().__init__(self.message)
