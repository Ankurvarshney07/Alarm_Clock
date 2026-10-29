"""
cli.py — argparse command definitions and handlers.

Sub-commands:
  add     Schedule a new alarm
  list    Show all alarms
  delete  Remove an alarm by ID
  toggle  Enable/disable an alarm
  next    Show time until next alarm (scriptable)
  run     Start the foreground monitor loop
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from . import __version__
from .models import Alarm
from .store import add_alarm, delete_alarm, load_alarms, toggle_alarm, update_alarm
from .scheduler import apply_snooze, clear_snooze, format_countdown, time_until
from .ui import console, display_alarm_table, render_alarm_ring, prompt_ring_action, make_monitor_panel

# ── Time validator ─────────────────────────────────────────────────────────────


def _parse_time(value: str) -> str:
    """Validate and normalise HH:MM input."""
    for fmt in ("%H:%M", "%I:%M%p", "%I:%M %p"):
        try:
            dt = datetime.strptime(value.upper(), fmt.upper())
            return f"{dt.hour:02d}:{dt.minute:02d}"
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid time '{value}'. Use 24-hour HH:MM (e.g. 07:30 or 14:00)."
    )


def _parse_repeat(value: str) -> List[str]:
    """Parse and validate a repeat specification."""
    shortcuts = {
        "DAILY": ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"],
        "WEEKDAYS": ["MON", "TUE", "WED", "THU", "FRI"],
        "WEEKEND": ["SAT", "SUN"],
    }
    upper = value.upper()
    if upper in shortcuts:
        return shortcuts[upper]

    valid = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
    days = [d.strip().upper()[:3] for d in value.split(",")]
    bad = [d for d in days if d not in valid]
    if bad:
        raise argparse.ArgumentTypeError(
            f"Unknown day(s): {bad}. Use MON,TUE,... or daily/weekdays/weekend."
        )
    return days


# ── Parser ─────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarm",
        description="⏰  A terminal alarm clock. Set it, run it, wake up.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  alarm add 07:30
  alarm add 14:00 --label "Team standup" --repeat weekdays
  alarm list
  alarm delete 2
  alarm toggle 1
  alarm next
  alarm run
""",
    )
    parser.add_argument("--version", action="version", version=f"alarm-clock {__version__}")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ── add ────────────────────────────────────────────────────────────────────
    p_add = sub.add_parser("add", help="Schedule a new alarm")
    p_add.add_argument("time", type=_parse_time, help="Alarm time in HH:MM (24-hour)")
    p_add.add_argument("-l", "--label", default="Alarm", help='Label shown when ringing (default: "Alarm")')
    p_add.add_argument(
        "-r", "--repeat",
        type=_parse_repeat,
        metavar="DAYS",
        help="Repeat days: MON,TUE,... or daily/weekdays/weekend",
    )

    # ── list ───────────────────────────────────────────────────────────────────
    sub.add_parser("list", help="List all scheduled alarms")

    # ── delete ─────────────────────────────────────────────────────────────────
    p_del = sub.add_parser("delete", aliases=["del", "rm"], help="Delete an alarm by ID")
    p_del.add_argument("id", type=int, help="Alarm ID (from `alarm list`)")

    # ── toggle ─────────────────────────────────────────────────────────────────
    p_tog = sub.add_parser("toggle", help="Enable or disable an alarm")
    p_tog.add_argument("id", type=int, help="Alarm ID")

    # ── snooze ─────────────────────────────────────────────────────────────────
    p_snz = sub.add_parser("snooze", help="Snooze an alarm")
    p_snz.add_argument("id", type=int, help="Alarm ID")
    p_snz.add_argument("-m", "--minutes", type=int, default=5, help="Snooze duration in minutes (default: 5)")

    # ── next ───────────────────────────────────────────────────────────────────
    sub.add_parser("next", help="Show time until the next alarm (useful for scripts)")

    # ── run ────────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Start the foreground alarm monitor")
    p_run.add_argument(
        "--no-sound", action="store_true", help="Disable audio (visual alert only)"
    )
    p_run.add_argument(
        "--sound", metavar="FILE", help="Path to a custom WAV file"
    )

    return parser


# ── Handlers ───────────────────────────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> int:
    hour, minute = map(int, args.time.split(":"))
    alarm = add_alarm(
        hour=hour,
        minute=minute,
        label=args.label,
        repeat_days=args.repeat or [],
    )
    td = time_until(alarm)
    countdown = f"  (in {format_countdown(td)})" if td else ""

    console.print(
        f"\n  [bold green]✔[/bold green]  Alarm [bold]#{alarm.id}[/bold] set for "
        f"[bold bright_white]{alarm.time_str}[/bold bright_white] — "
        f"[cyan]{alarm.label}[/cyan]{countdown}\n"
    )
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    display_alarm_table(alarms)
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    if delete_alarm(args.id):
        console.print(f"\n  [bold red]✖[/bold red]  Alarm [bold]#{args.id}[/bold] deleted.\n")
        return 0
    console.print(f"\n  [yellow]⚠[/yellow]  No alarm with ID [bold]{args.id}[/bold] found.\n")
    return 1


def cmd_toggle(args: argparse.Namespace) -> int:
    new_state = toggle_alarm(args.id)
    if new_state is None:
        console.print(f"\n  [yellow]⚠[/yellow]  No alarm with ID [bold]{args.id}[/bold] found.\n")
        return 1
    state_str = "[bold green]enabled[/bold green]" if new_state else "[dim]disabled[/dim]"
    console.print(f"\n  [bold]#{args.id}[/bold] is now {state_str}.\n")
    return 0


def cmd_snooze(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    target = next((a for a in alarms if a.id == args.id), None)
    if target is None:
        console.print(f"\n  [yellow]⚠[/yellow]  No alarm with ID [bold]{args.id}[/bold].\n")
        return 1
    updated = apply_snooze(target, minutes=args.minutes)
    update_alarm(updated)
    console.print(
        f"\n  [yellow]💤[/yellow]  Alarm [bold]#{args.id}[/bold] snoozed for "
        f"[bold]{args.minutes}[/bold] minutes.\n"
    )
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    alarms = load_alarms()
    active = [(a, time_until(a)) for a in alarms if a.enabled and time_until(a) is not None]
    if not active:
        console.print("\n  [dim]No upcoming alarms.[/dim]\n")
        return 0
    active.sort(key=lambda x: x[1])  # type: ignore[arg-type]
    alarm, td = active[0]
    console.print(
        f"\n  Next: [bold bright_white]{alarm.time_str}[/bold bright_white]"
        f" — [cyan]{alarm.label}[/cyan]"
        f" in [bold]{format_countdown(td)}[/bold]\n"   # type: ignore[arg-type]
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Foreground monitor loop — checks every second, triggers on match."""
    import time
    from datetime import datetime
    from rich.live import Live

    from .audio import AlarmPlayer
    from .scheduler import is_due
    from pathlib import Path

    # Track which alarms have already been handled this minute to avoid
    # ringing multiple times within the same 60-second window.
    handled_this_minute: dict[int, str] = {}  # alarm_id → "YYYY-MM-DDTHH:MM"

    sound_path = Path(args.sound) if getattr(args, "sound", None) else None
    no_sound = getattr(args, "no_sound", False)

    console.print(
        "\n  [bold bright_cyan]Alarm monitor started.[/bold bright_cyan]"
        "  [dim]Press Ctrl+C to stop.[/dim]\n"
    )

    try:
        with Live(
            make_monitor_panel(load_alarms()),
            refresh_per_second=2,
            console=console,
            transient=False,
        ) as live:
            while True:
                now = datetime.now()
                minute_key = now.strftime("%Y-%m-%dT%H:%M")
                alarms = load_alarms()

                # Clean up handled_this_minute for past minutes
                handled_this_minute = {
                    k: v for k, v in handled_this_minute.items() if v == minute_key
                }

                for alarm in alarms:
                    if not alarm.enabled:
                        continue
                    already_handled = handled_this_minute.get(alarm.id) == minute_key
                    if is_due(alarm, now) and not already_handled:
                        handled_this_minute[alarm.id] = minute_key

                        # Pause the live display during interactive ring prompt
                        live.stop()
                        render_alarm_ring(alarm)

                        # Start audio
                        player = None if no_sound else AlarmPlayer(sound_path)
                        if player:
                            player.start()

                        action = prompt_ring_action(alarm)

                        if player:
                            player.stop()

                        if action == "snooze":
                            updated = apply_snooze(alarm)
                            update_alarm(updated)
                            console.print(f"  [yellow]💤 Snoozed for 5 minutes.[/yellow]\n")
                        elif action == "dismiss":
                            if not alarm.repeat_days:
                                alarm.enabled = False
                                update_alarm(alarm)
                            else:
                                updated = clear_snooze(alarm)
                                update_alarm(updated)
                            console.print(f"  [green]✔ Alarm dismissed.[/green]\n")
                        elif action == "quit":
                            console.print("  [dim]Monitor stopped.[/dim]\n")
                            return 0

                        live.start()

                # Refresh the display with latest alarm data
                live.update(make_monitor_panel(alarms))
                time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n\n  [dim]Monitor stopped.[/dim]\n")

    return 0
