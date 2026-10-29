"""
tests/test_scheduler.py — Unit tests for scheduler.py

All tests use explicit `now` injection so they're hermetic and fast.
No filesystem access, no audio, no I/O of any kind.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from alarm_clock.models import Alarm
from alarm_clock.scheduler import (
    apply_snooze,
    clear_snooze,
    format_countdown,
    is_due,
    next_ring,
    time_until,
)


def make_alarm(**kwargs) -> Alarm:
    """Factory with sensible defaults."""
    defaults = dict(id=1, hour=8, minute=0, label="Test", enabled=True, repeat_days=[])
    defaults.update(kwargs)
    return Alarm(**defaults)


# ── next_ring ─────────────────────────────────────────────────────────────────


class TestNextRing(unittest.TestCase):

    def test_same_day_future(self):
        """Alarm time is later today → ring today."""
        now = datetime(2024, 3, 14, 7, 45)   # 07:45
        alarm = make_alarm(hour=8, minute=0)
        ring = next_ring(alarm, now)
        self.assertIsNotNone(ring)
        self.assertEqual(ring.date(), now.date())
        self.assertEqual(ring.hour, 8)
        self.assertEqual(ring.minute, 0)

    def test_same_day_past_wraps_to_tomorrow(self):
        """Alarm time already passed today → ring tomorrow."""
        now = datetime(2024, 3, 14, 9, 0)    # 09:00
        alarm = make_alarm(hour=8, minute=0)
        ring = next_ring(alarm, now)
        self.assertIsNotNone(ring)
        self.assertEqual(ring.date(), (now + timedelta(days=1)).date())

    def test_exact_minute_wraps_to_tomorrow(self):
        """If now == alarm time, we have already fired this minute → tomorrow."""
        now = datetime(2024, 3, 14, 8, 0)
        alarm = make_alarm(hour=8, minute=0)
        ring = next_ring(alarm, now)
        self.assertIsNotNone(ring)
        self.assertEqual(ring.date(), (now + timedelta(days=1)).date())

    def test_disabled_alarm_returns_none(self):
        now = datetime(2024, 3, 14, 7, 0)
        alarm = make_alarm(hour=8, minute=0, enabled=False)
        self.assertIsNone(next_ring(alarm, now))

    def test_repeat_same_day(self):
        """Repeat alarm should fire today if the day matches and time is future."""
        # 2024-03-14 is a Thursday
        now = datetime(2024, 3, 14, 7, 45)
        alarm = make_alarm(hour=8, minute=0, repeat_days=["THU"])
        ring = next_ring(alarm, now)
        self.assertIsNotNone(ring)
        self.assertEqual(ring.date(), now.date())

    def test_repeat_next_occurrence(self):
        """Repeat alarm should skip to next matching weekday when today doesn't match."""
        # 2024-03-14 is Thursday → next MON is 2024-03-18
        now = datetime(2024, 3, 14, 10, 0)
        alarm = make_alarm(hour=8, minute=0, repeat_days=["MON"])
        ring = next_ring(alarm, now)
        self.assertIsNotNone(ring)
        self.assertEqual(ring.strftime("%a").upper()[:3], "MON")
        self.assertGreater(ring, now)

    def test_snoozed_alarm_rings_at_snooze_time(self):
        now = datetime(2024, 3, 14, 8, 1)
        snooze_time = datetime(2024, 3, 14, 8, 6)
        alarm = make_alarm(hour=8, minute=0, snoozed_until=snooze_time.isoformat())
        ring = next_ring(alarm, now)
        self.assertEqual(ring, snooze_time)


# ── is_due ────────────────────────────────────────────────────────────────────


class TestIsDue(unittest.TestCase):

    def test_not_due_wrong_hour(self):
        now = datetime(2024, 3, 14, 7, 59)
        alarm = make_alarm(hour=8, minute=0)
        self.assertFalse(is_due(alarm, now))

    def test_due_at_correct_time(self):
        now = datetime(2024, 3, 14, 8, 0, 30)   # 08:00:30
        alarm = make_alarm(hour=8, minute=0)
        self.assertTrue(is_due(alarm, now))

    def test_not_due_disabled(self):
        now = datetime(2024, 3, 14, 8, 0)
        alarm = make_alarm(hour=8, minute=0, enabled=False)
        self.assertFalse(is_due(alarm, now))

    def test_repeat_due_on_matching_day(self):
        # 2024-03-14 is Thursday
        now = datetime(2024, 3, 14, 8, 0)
        alarm = make_alarm(hour=8, minute=0, repeat_days=["THU"])
        self.assertTrue(is_due(alarm, now))

    def test_repeat_not_due_on_non_matching_day(self):
        # 2024-03-14 is Thursday
        now = datetime(2024, 3, 14, 8, 0)
        alarm = make_alarm(hour=8, minute=0, repeat_days=["MON"])
        self.assertFalse(is_due(alarm, now))

    def test_snoozed_alarm_due_at_snooze_expiry(self):
        snooze_time = datetime(2024, 3, 14, 8, 6)
        now = datetime(2024, 3, 14, 8, 6, 15)    # same minute as snooze expiry
        alarm = make_alarm(hour=8, minute=0, snoozed_until=snooze_time.isoformat())
        self.assertTrue(is_due(alarm, now))


# ── format_countdown ──────────────────────────────────────────────────────────


class TestFormatCountdown(unittest.TestCase):

    def test_seconds_only(self):
        self.assertEqual(format_countdown(timedelta(seconds=45)), "45s")

    def test_minutes_and_seconds(self):
        self.assertEqual(format_countdown(timedelta(minutes=3, seconds=7)), "3m 07s")

    def test_hours_minutes_seconds(self):
        self.assertEqual(format_countdown(timedelta(hours=2, minutes=5, seconds=9)), "2h 05m 09s")

    def test_negative_returns_now(self):
        self.assertEqual(format_countdown(timedelta(seconds=-1)), "now")


# ── snooze ────────────────────────────────────────────────────────────────────


class TestSnooze(unittest.TestCase):

    def test_apply_snooze_sets_field(self):
        now = datetime(2024, 3, 14, 8, 0)
        alarm = make_alarm()
        updated = apply_snooze(alarm, minutes=10, now=now)
        self.assertIsNotNone(updated.snoozed_until)
        snooze_dt = datetime.fromisoformat(updated.snoozed_until)
        self.assertEqual(snooze_dt.minute, 10)

    def test_clear_snooze_removes_field(self):
        alarm = make_alarm(snoozed_until="2024-03-14T08:06:00")
        updated = clear_snooze(alarm)
        self.assertIsNone(updated.snoozed_until)


# ── Alarm model ───────────────────────────────────────────────────────────────


class TestAlarmModel(unittest.TestCase):

    def test_time_str(self):
        alarm = make_alarm(hour=7, minute=5)
        self.assertEqual(alarm.time_str, "07:05")

    def test_repeat_str_weekdays(self):
        alarm = make_alarm(repeat_days=["MON", "TUE", "WED", "THU", "FRI"])
        self.assertEqual(alarm.repeat_str, "Weekdays")

    def test_repeat_str_weekend(self):
        alarm = make_alarm(repeat_days=["SAT", "SUN"])
        self.assertEqual(alarm.repeat_str, "Weekend")

    def test_repeat_str_daily(self):
        alarm = make_alarm(repeat_days=["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"])
        self.assertEqual(alarm.repeat_str, "Every day")

    def test_repeat_str_once(self):
        alarm = make_alarm(repeat_days=[])
        self.assertEqual(alarm.repeat_str, "Once")

    def test_serialisation_roundtrip(self):
        alarm = make_alarm(hour=14, minute=30, label="Lunch", repeat_days=["MON", "FRI"])
        restored = Alarm.from_dict(alarm.to_dict())
        self.assertEqual(restored.id, alarm.id)
        self.assertEqual(restored.hour, alarm.hour)
        self.assertEqual(restored.minute, alarm.minute)
        self.assertEqual(restored.label, alarm.label)
        self.assertEqual(restored.repeat_days, alarm.repeat_days)
        self.assertEqual(restored.enabled, alarm.enabled)


if __name__ == "__main__":
    unittest.main()
