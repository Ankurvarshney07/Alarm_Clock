"""
scheduler.py — Timing logic: next ring time, due detection, snooze.

Kept pure (no I/O, no side effects) so every function is unit-testable
without mocking the filesystem.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .models import Alarm

# Day-name → weekday index (Monday=0)
_DAY_TO_WEEKDAY = {
    "MON": 0, "TUE": 1, "WED": 2, "THU": 3,
    "FRI": 4, "SAT": 5, "SUN": 6,
}


def next_ring(alarm: Alarm, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Calculate the next datetime at which *alarm* should ring.

    Returns None if the alarm is disabled or has no valid future time
    (e.g. a one-shot alarm that already fired).
    """
    if not alarm.enabled:
        return None

    now = now or datetime.now()

    # If snoozed, the next ring is the snooze expiry
    if alarm.snoozed_until:
        snooze_dt = datetime.fromisoformat(alarm.snoozed_until)
        if snooze_dt > now:
            return snooze_dt

    # Build today's candidate firing time
    candidate = now.replace(
        hour=alarm.hour,
        minute=alarm.minute,
        second=0,
        microsecond=0,
    )

    if alarm.repeat_days:
        # Find the nearest future day that matches one of the repeat days
        for delta in range(8):  # at most 7 days ahead to complete a cycle
            test_dt = (now + timedelta(days=delta)).replace(
                hour=alarm.hour, minute=alarm.minute, second=0, microsecond=0
            )
            day_abbr = test_dt.strftime("%a").upper()[:3]
            if day_abbr in alarm.repeat_days and test_dt > now:
                return test_dt
        return None  # should not happen with valid repeat_days

    # One-shot: ring today if not yet passed, otherwise tomorrow
    if candidate > now:
        return candidate
    return candidate + timedelta(days=1)


def is_due(alarm: Alarm, now: Optional[datetime] = None) -> bool:
    """
    Return True if the alarm should ring right now (within the current minute).

    We use a one-minute window because:
    - The scheduler polls every second.
    - We want to catch the alarm even if the process was briefly paused.
    - We track `last_fired` via the snoozed_until mechanism to avoid
      ringing twice in the same minute.
    """
    if not alarm.enabled:
        return False

    now = now or datetime.now()

    # If snoozed, check snooze expiry instead of scheduled time
    if alarm.snoozed_until:
        snooze_dt = datetime.fromisoformat(alarm.snoozed_until)
        return (
            snooze_dt.year == now.year
            and snooze_dt.month == now.month
            and snooze_dt.day == now.day
            and snooze_dt.hour == now.hour
            and snooze_dt.minute == now.minute
        )

    # Check if current time matches alarm time (hour + minute)
    if alarm.hour != now.hour or alarm.minute != now.minute:
        return False

    # For repeat alarms, check day-of-week
    if alarm.repeat_days:
        day_abbr = now.strftime("%a").upper()[:3]
        return day_abbr in alarm.repeat_days

    return True  # one-shot, time matched


def time_until(alarm: Alarm, now: Optional[datetime] = None) -> Optional[timedelta]:
    """Return timedelta until next ring, or None if alarm is disabled."""
    ring = next_ring(alarm, now)
    if ring is None:
        return None
    now = now or datetime.now()
    return ring - now


def format_countdown(td: timedelta) -> str:
    """Convert a timedelta to a human-readable countdown string."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "now"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes > 0:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def apply_snooze(alarm: Alarm, minutes: int = 5, now: Optional[datetime] = None) -> Alarm:
    """Return an updated Alarm with snoozed_until set *minutes* from now."""
    now = now or datetime.now()
    snooze_until = now + timedelta(minutes=minutes)
    alarm.snoozed_until = snooze_until.isoformat()
    return alarm


def clear_snooze(alarm: Alarm) -> Alarm:
    """Remove any active snooze from an alarm."""
    alarm.snoozed_until = None
    return alarm
