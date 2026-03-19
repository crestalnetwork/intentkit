from enum import Enum


class Kind(Enum):
    AiRelayer = 1
    TeamChannel = "team_channel"


def is_valid_kind(kind: int):
    try:
        _ = Kind(kind)
        return True
    except ValueError:
        return False
