"""
ui.py — Rich terminal UI for the alarm clock.

Provides:
- display_alarm_table()   → pretty table of all alarms
- render_alarm_ring()     → full-screen ring panel
- make_live_display()     → Rich renderable for the `run` monitor loop
- prompt_ring_action()    → interactive prompt (snooze / dismiss / quit)
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .models import Alarm
from .scheduler import next_ring, time_until, format_countdown

console = Console()


# ── Alarm table ───────────────────────────────────────────────────────────────


def display_alarm_table(alarms: List[Alarm]) -> None:
    """Render a Rich table of all alarms to stdout."""
    if not alarms:
        console.print(
            Panel(
                "[dim]No alarms scheduled. Use [bold]alarm add HH:MM[/bold] to create one.[/dim]",
                title="⏰ Alarms",
                border_style="dim",
            )
        )
        return

    now = datetime.now()
    table = Table(
        title="⏰  Scheduled Alarms",
        box=box.ROUNDED,
        border_style="bright_cyan",
        header_style="bold bright_cyan",
        show_lines=True,
    )

    table.add_column("ID", justify="right", style="dim", width=4)
    table.add_column("Time", justify="center", style="bold white", width=7)
    table.add_column("Label", style="white", min_width=16)
    table.add_column("Repeat", justify="center", style="cyan", width=10)
    table.add_column("Status", justify="left", min_width=14)
    table.add_column("Next Ring", justify="right", min_width=14)

    for alarm in alarms:
        # Status column
        if not alarm.enabled:
            status = Text("○ disabled", style="dim")
        elif alarm.snoozed_until:
            status = Text("💤 snoozed", style="yellow")
        else:
            status = Text("● active", style="bright_green")

        # Countdown column
        td = time_until(alarm, now)
        if td is None or not alarm.enabled:
            countdown = Text("—", style="dim")
        else:
            countdown_str = format_countdown(td)
            if td.total_seconds() < 300:        # < 5 min  → red
                countdown = Text(countdown_str, style="bold red")
            elif td.total_seconds() < 3600:     # < 1 hr  → yellow
                countdown = Text(countdown_str, style="yellow")
            else:
                countdown = Text(countdown_str, style="green")

        table.add_row(
            str(alarm.id),
            alarm.time_str,
            alarm.label,
            alarm.repeat_str,
            status,
            countdown,
        )

    console.print()
    console.print(table)
    console.print()


# ── Run-loop live panel ────────────────────────────────────────────────────────


def make_monitor_panel(alarms: List[Alarm]) -> Panel:
    """
    Build the Rich renderable for the live `alarm run` display.

    Called ~every second by the Live context.
    """
    now = datetime.now()
    clock_str = now.strftime("%H:%M:%S")
    date_str = now.strftime("%A, %B %-d %Y")

    # Header
    header = Text(justify="center")
    header.append(f"  {clock_str}  ", style="bold bright_white on grey15")
    header.append(f"\n  {date_str}  ", style="dim white")

    # Next alarm section
    active = [a for a in alarms if a.enabled]
    if not active:
        next_info = Text("\n  [No alarms scheduled]  ", style="dim")
    else:
        # Find the alarm ringing soonest
        upcoming = sorted(
            [(a, time_until(a, now)) for a in active if time_until(a, now) is not None],
            key=lambda x: x[1],  # type: ignore[arg-type]
        )
        if upcoming:
            next_alarm, td = upcoming[0]
            countdown_str = format_countdown(td)
            next_info = Text(justify="center")
            next_info.append("\n")
            if td.total_seconds() < 60:
                next_info.append(f'  🚨 "{next_alarm.label}" in {countdown_str}  ', style="bold red blink")
            elif td.total_seconds() < 300:
                next_info.append(f'  ⚡ "{next_alarm.label}" in {countdown_str}  ', style="bold yellow")
            else:
                next_info.append(f'  Next: "{next_alarm.label}" at {next_alarm.time_str} (in {countdown_str})  ', style="bright_cyan")
        else:
            next_info = Text("\n  [All alarms disabled]  ", style="dim")

    body = Text(justify="center")
    body.append_text(header)
    body.append_text(next_info)
    body.append("\n\n  [dim]Ctrl+C to stop monitor[/dim]  ")

    return Panel(
        body,
        title="[bold bright_cyan]⏰  Alarm Clock[/bold bright_cyan]",
        border_style="bright_cyan",
        padding=(1, 4),
    )


# ── Alarm ring screen ─────────────────────────────────────────────────────────


def render_alarm_ring(alarm: Alarm) -> None:
    """Print a dramatic ring notification panel."""
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"\n[bold blink bright_red]🚨  ALARM RINGING!  🚨[/]\n\n"
                f"[bold white]{alarm.label}[/]\n"
                f"[dim]{alarm.time_str}[/]\n",
                justify="center",
            ),
            title="[bold red]── WAKE UP ──[/bold red]",
            border_style="bold red",
            padding=(1, 6),
        )
    )


def prompt_ring_action(alarm: Alarm, default_snooze: int = 5) -> str:
    """
    Prompt the user to snooze, dismiss, or quit.

    Returns one of: 'snooze', 'dismiss', 'quit'
    """
    console.print(
        f"  [[bold yellow]s[/bold yellow]] Snooze {default_snooze} min  "
        f"[[bold green]d[/bold green]] Dismiss  "
        f"[[bold red]q[/bold red]] Quit monitor"
    )
    try:
        response = input("  → ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return "quit"

    if response.startswith("s"):
        return "snooze"
    if response.startswith("d"):
        return "dismiss"
    if response.startswith("q"):
        return "quit"
    return "snooze"  # default
