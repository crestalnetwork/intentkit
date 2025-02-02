from enum import Enum


class Kind(Enum):
    AiRelayer = 1


def is_valid_kind(kind: int):
    try:
        Kind(kind)
        return True
    except ValueError:
        return False
