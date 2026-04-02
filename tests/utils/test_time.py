"""Tests for intentkit.utils.time."""

from datetime import datetime, timezone

from intentkit.utils.time import add_month


def test_add_month_normal():
    dt = datetime(2026, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 2, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_add_month_december_to_january():
    dt = datetime(2025, 12, 10, 8, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 1, 10, 8, 0, 0, tzinfo=timezone.utc)


def test_add_month_jan31_to_mar1():
    """Jan 31 → Feb 31 doesn't exist → March 1 00:00."""
    dt = datetime(2026, 1, 31, 14, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_mar31_to_may1():
    """Mar 31 → Apr 31 doesn't exist → May 1 00:00."""
    dt = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_feb28_normal():
    dt = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 3, 28, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_leap_year_jan29():
    """In a leap year, Jan 29 → Feb 29 should work."""
    dt = datetime(2028, 1, 29, 0, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2028, 2, 29, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_non_leap_year_jan29():
    """Non-leap year: Jan 29 → Feb 29 doesn't exist → Mar 1 00:00."""
    dt = datetime(2026, 1, 29, 0, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_oct31_to_dec1():
    """Oct 31 → Nov 31 doesn't exist → Dec 1 00:00."""
    dt = datetime(2026, 10, 31, 23, 59, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_add_month_nov30_to_dec30():
    """Nov 30 → Dec 30 works fine."""
    dt = datetime(2026, 11, 30, 5, 0, 0, tzinfo=timezone.utc)
    result = add_month(dt)
    assert result == datetime(2026, 12, 30, 5, 0, 0, tzinfo=timezone.utc)


def test_add_month_preserves_timezone():
    from datetime import timedelta

    tz = timezone(timedelta(hours=8))
    dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=tz)
    result = add_month(dt)
    assert result.tzinfo == tz
    assert result == datetime(2026, 7, 15, 12, 0, 0, tzinfo=tz)
