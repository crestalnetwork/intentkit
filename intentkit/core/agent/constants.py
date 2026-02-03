import re

ENS_NAME_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:eth|base\.eth)$",
    re.IGNORECASE,
)
