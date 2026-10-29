"""
models.py — Alarm dataclass definition.

A single Alarm is intentionally kept as a plain dataclass so it can be
trivially serialised to/from JSON without any ORM or schema library.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Alarm:
    """Represents a single scheduled alarm."""

    # Unique numeric ID for friendly CLI references (e.g. `alarm delete 3`)
    id: int

    # Wall-clock time components
    hour: int
    minute: int

    # Human-readable label shown in UI and when the alarm rings
    label: str = "Alarm"

    # Enabled/disabled without deletion
    enabled: bool = True

    # Repeat days: list of 3-char uppercase day names, e.g. ["MON", "WED", "FRI"]
    # Empty list → one-shot alarm (auto-disabled after firing)
    repeat_days: List[str] = field(default_factory=list)

    # When the alarm is snoozed, this holds the snooze expiry as ISO-format string
    # None means not snoozed.
    snoozed_until: Optional[str] = None

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hour": self.hour,
            "minute": self.minute,
            "label": self.label,
            "enabled": self.enabled,
            "repeat_days": self.repeat_days,
            "snoozed_until": self.snoozed_until,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        return cls(
            id=data["id"],
            hour=data["hour"],
            minute=data["minute"],
            label=data.get("label", "Alarm"),
            enabled=data.get("enabled", True),
            repeat_days=data.get("repeat_days", []),
            snoozed_until=data.get("snoozed_until"),
        )

    # ── Convenience ───────────────────────────────────────────────────────────

    @property
    def time_str(self) -> str:
        """HH:MM 24-hour representation."""
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def repeat_str(self) -> str:
        """Human-readable repeat description."""
        if not self.repeat_days:
            return "Once"
        day_order = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        weekdays = {"MON", "TUE", "WED", "THU", "FRI"}
        weekend = {"SAT", "SUN"}
        days_set = set(self.repeat_days)
        if days_set == weekdays:
            return "Weekdays"
        if days_set == weekend:
            return "Weekend"
        if days_set == set(day_order):
            return "Every day"
        return ",".join(d.capitalize() for d in sorted(self.repeat_days, key=day_order.index))
