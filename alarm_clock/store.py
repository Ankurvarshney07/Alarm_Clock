"""
store.py — JSON-backed persistence layer for alarms.

Design choices:
- Stores alarms in ~/.alarm_clock/alarms.json (user home, not cwd)
- Uses an atomic write (write to .tmp then os.replace) to avoid corruption
  if the process is killed mid-write.
- File-level locking via a .lock file prevents concurrent writer races when
  the user runs `alarm add` and `alarm run` simultaneously.
- No external dependencies.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import List, Optional

from .models import Alarm

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".alarm_clock"
ALARM_FILE = DATA_DIR / "alarms.json"
LOCK_FILE = DATA_DIR / ".alarms.lock"


# ── Internal helpers ──────────────────────────────────────────────────────────


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


class _FileLock:
    """Simple advisory file lock using fcntl (POSIX)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: Optional[int] = None

    def __enter__(self) -> "_FileLock":
        _ensure_dir()
        self._fd = os.open(str(self._path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


# ── Public API ────────────────────────────────────────────────────────────────


def load_alarms() -> List[Alarm]:
    """Return all persisted alarms (empty list if file doesn't exist)."""
    _ensure_dir()
    if not ALARM_FILE.exists():
        return []
    try:
        with ALARM_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return [Alarm.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError):
        # Corrupted file — return empty and let the user know via caller
        return []


def save_alarms(alarms: List[Alarm]) -> None:
    """Atomically persist the alarm list to disk."""
    _ensure_dir()
    tmp_path = ALARM_FILE.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump([a.to_dict() for a in alarms], fh, indent=2)
    os.replace(tmp_path, ALARM_FILE)


def _next_id(alarms: List[Alarm]) -> int:
    return max((a.id for a in alarms), default=0) + 1


def add_alarm(
    hour: int,
    minute: int,
    label: str = "Alarm",
    repeat_days: Optional[List[str]] = None,
) -> Alarm:
    """Create, persist, and return a new Alarm."""
    with _FileLock(LOCK_FILE):
        alarms = load_alarms()
        alarm = Alarm(
            id=_next_id(alarms),
            hour=hour,
            minute=minute,
            label=label,
            repeat_days=repeat_days or [],
        )
        alarms.append(alarm)
        save_alarms(alarms)
    return alarm


def delete_alarm(alarm_id: int) -> bool:
    """Remove alarm by ID. Returns True if found and deleted."""
    with _FileLock(LOCK_FILE):
        alarms = load_alarms()
        before = len(alarms)
        alarms = [a for a in alarms if a.id != alarm_id]
        if len(alarms) == before:
            return False
        save_alarms(alarms)
    return True


def toggle_alarm(alarm_id: int) -> Optional[bool]:
    """Toggle enabled state. Returns new state, or None if not found."""
    with _FileLock(LOCK_FILE):
        alarms = load_alarms()
        for alarm in alarms:
            if alarm.id == alarm_id:
                alarm.enabled = not alarm.enabled
                save_alarms(alarms)
                return alarm.enabled
    return None


def update_alarm(updated: Alarm) -> bool:
    """Replace an alarm in-place by ID. Returns True if found."""
    with _FileLock(LOCK_FILE):
        alarms = load_alarms()
        for i, a in enumerate(alarms):
            if a.id == updated.id:
                alarms[i] = updated
                save_alarms(alarms)
                return True
    return False
