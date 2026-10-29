# ⏰ Alarm Clock CLI

A developer-friendly terminal alarm clock — persistent, scriptable, and beautiful.

```
alarm add 07:30 --label "Morning standup" --repeat weekdays
alarm list
alarm run
```

![alarm list screenshot](https://raw.githubusercontent.com/placeholder/alarm-clock-cli/main/docs/screenshot.png)

---

## Design Thinking

Before writing code I ran an AI-assisted requirements refinement session (see [design doc](./DESIGN.md)) to answer three questions:

1. **What problem am I actually solving?** — A developer at a terminal who wants timed reminders without leaving their workflow. Not a general-purpose alarm app.

2. **What's the right architecture?** — Six modules with strict layer separation: `models → store → scheduler → audio → ui → cli`. Each layer has one job. The scheduler has zero I/O so all its logic is unit-testable with injected `datetime`.

3. **What should I cut?** — No daemon, no database, no web UI. A foreground `alarm run` loop is honest: you see it, you own it. JSON persistence is human-readable and zero-dependency.

Key decisions:
- **Foreground monitor over background daemon** — simpler, observable, composable with `tmux`/`screen`/`nohup`
- **Atomic writes (`os.replace`)** — prevent corrupted JSON if killed mid-write
- **3-tier audio fallback** — pygame → playsound → terminal bell, detected at runtime so the tool works in headless environments
- **Rich's `Live` display** — smooth live clock without curses complexity
- **Colour-coded countdowns** — green (>1h), yellow (<1h), red/blink (<5min)

---

## Installation

**Requires Python 3.8+**

```bash
git clone https://github.com/your-username/alarm-clock-cli.git
cd alarm-clock-cli

# Core (no audio)
pip install -e .

# With audio support (recommended)
pip install -e ".[audio]"
```

The `alarm` command will be available system-wide after install.

---

## Usage

### Add an alarm

```bash
alarm add HH:MM [--label "text"] [--repeat DAYS]
```

```bash
alarm add 07:30                                   # one-shot, default label
alarm add 09:00 --label "Morning coffee"
alarm add 14:30 --label "Team standup" --repeat weekdays
alarm add 08:00 --label "Weekend run"   --repeat "SAT,SUN"
alarm add 06:30 --label "Daily yoga"    --repeat daily
```

**Repeat values:** `daily` · `weekdays` · `weekend` · `MON,TUE,WED,THU,FRI,SAT,SUN` (comma-separated)

---

### List alarms

```bash
alarm list
```

Shows ID, time, label, repeat schedule, status (active / disabled / snoozed), and live countdown to next ring.

---

### Start the monitor

```bash
alarm run              # shows live clock, rings alarms
alarm run --no-sound   # visual only
alarm run --sound /path/to/custom.wav
```

When an alarm fires you get an interactive prompt:

```
🚨 ALARM RINGING!
Team standup — 14:30

  [s] Snooze 5 min  [d] Dismiss  [q] Quit monitor
  →
```

---

### Other commands

```bash
alarm delete 2             # remove alarm #2
alarm toggle 1             # enable / disable alarm #1
alarm snooze 3             # snooze alarm #3 for 5 minutes (default)
alarm snooze 3 --minutes 10
alarm next                 # print next alarm (useful in scripts / status bars)
alarm --version
alarm --help
```

---

## Project Structure

```
alarm_clock/
├── __init__.py       version
├── __main__.py       entry point
├── models.py         Alarm dataclass + serialisation
├── store.py          JSON persistence (atomic writes, file locking)
├── scheduler.py      Pure timing logic: next_ring, is_due, snooze
├── audio.py          pygame → playsound → bell fallback chain
└── ui.py             Rich tables, live panel, ring screen

tests/
├── test_scheduler.py  25 unit tests (all hermetic, no I/O)
└── test_store.py       9 integration tests (temp dir isolation)

scripts/
└── generate_tone.py  Generate bundled alarm.wav (stdlib only)

assets/
└── alarm.wav         Bundled 2-tone alarm sound
```

---

## Running Tests

```bash
python -m pytest tests/ -v
# 34 passed in 0.17s
```

---

## How It Works

### Data storage
Alarms live in `~/.alarm_clock/alarms.json`. Each write is atomic:

```
write → alarms.tmp → os.replace(alarms.tmp, alarms.json)
```

A POSIX `flock` advisory lock prevents concurrent write races when `alarm run` and `alarm add` execute simultaneously.

### Timing
The monitor loop wakes every second. `is_due()` checks if `alarm.hour == now.hour and alarm.minute == now.minute` (and day-of-week for repeating alarms). A `handled_this_minute` dict prevents double-firing within the same 60-second window.

### Audio
`AlarmPlayer` tries each backend in a daemon thread:
1. `pygame.mixer` — best quality, looping
2. `playsound` — simple, WAV/MP3
3. `\a` terminal bell — always available

---

## Scripting / Composability

`alarm next` exits 0 and prints structured output, making it composable:

```bash
# Add to your shell prompt
PS1='$(alarm next 2>/dev/null) $ '

# Create a desktop notification when the alarm is imminent
alarm next | grep -q "in [0-9]s" && notify-send "Alarm imminent"
```

---

## License

MIT
