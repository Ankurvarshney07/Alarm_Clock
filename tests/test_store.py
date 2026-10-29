"""Tests for the store (persistence) layer using a temp directory."""

from __future__ import annotations

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from alarm_clock.models import Alarm
from alarm_clock import store as store_module


class TestStore(unittest.TestCase):

    def setUp(self):
        # Redirect all store I/O to a temp directory
        self._tmpdir = tempfile.mkdtemp()
        self._orig_data_dir = store_module.DATA_DIR
        self._orig_alarm_file = store_module.ALARM_FILE
        self._orig_lock_file = store_module.LOCK_FILE

        store_module.DATA_DIR = Path(self._tmpdir)
        store_module.ALARM_FILE = Path(self._tmpdir) / "alarms.json"
        store_module.LOCK_FILE = Path(self._tmpdir) / ".alarms.lock"

    def tearDown(self):
        store_module.DATA_DIR = self._orig_data_dir
        store_module.ALARM_FILE = self._orig_alarm_file
        store_module.LOCK_FILE = self._orig_lock_file

    def test_load_returns_empty_when_no_file(self):
        alarms = store_module.load_alarms()
        self.assertEqual(alarms, [])

    def test_add_and_load_roundtrip(self):
        alarm = store_module.add_alarm(hour=7, minute=30, label="Morning")
        loaded = store_module.load_alarms()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].hour, 7)
        self.assertEqual(loaded[0].label, "Morning")

    def test_ids_auto_increment(self):
        a1 = store_module.add_alarm(hour=7, minute=0)
        a2 = store_module.add_alarm(hour=8, minute=0)
        self.assertEqual(a2.id, a1.id + 1)

    def test_delete_existing(self):
        alarm = store_module.add_alarm(hour=7, minute=0)
        result = store_module.delete_alarm(alarm.id)
        self.assertTrue(result)
        self.assertEqual(store_module.load_alarms(), [])

    def test_delete_non_existing_returns_false(self):
        result = store_module.delete_alarm(999)
        self.assertFalse(result)

    def test_toggle_enables_disables(self):
        alarm = store_module.add_alarm(hour=7, minute=0)
        self.assertTrue(alarm.enabled)

        new_state = store_module.toggle_alarm(alarm.id)
        self.assertFalse(new_state)

        new_state = store_module.toggle_alarm(alarm.id)
        self.assertTrue(new_state)

    def test_toggle_missing_returns_none(self):
        result = store_module.toggle_alarm(999)
        self.assertIsNone(result)

    def test_update_alarm(self):
        alarm = store_module.add_alarm(hour=7, minute=0, label="Old")
        alarm.label = "New"
        ok = store_module.update_alarm(alarm)
        self.assertTrue(ok)
        loaded = store_module.load_alarms()
        self.assertEqual(loaded[0].label, "New")

    def test_multiple_alarms_persist(self):
        for h in range(5):
            store_module.add_alarm(hour=h, minute=0, label=f"Alarm {h}")
        loaded = store_module.load_alarms()
        self.assertEqual(len(loaded), 5)


if __name__ == "__main__":
    unittest.main()
