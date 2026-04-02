"""Time utility functions."""

import calendar
from datetime import datetime, timezone


def add_month(dt: datetime) -> datetime:
    """Return the same day/time one month later.

    If the target day doesn't exist in the next month (e.g. Jan 31 → Feb 31),
    return the 1st of the month after next at 00:00 in the same timezone.
    """
    year = dt.year + (dt.month // 12)
    month = dt.month % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    if dt.day <= max_day:
        return dt.replace(year=year, month=month)
    # Day doesn't exist in next month — go to 1st of month after next
    year2 = year + (month // 12)
    month2 = month % 12 + 1
    tz = dt.tzinfo or timezone.utc
    return datetime(year2, month2, 1, 0, 0, 0, tzinfo=tz)
