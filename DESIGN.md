# Design Document — Alarm Clock CLI

*This document captures the requirements refinement, architecture decisions, and
implementation plan worked out before writing the first line of production code.*

---

## Step 1 — Problem Definition (AI-assisted refinement)

The brief said "build an alarm clock CLI." That's deliberately vague — which is the
actual test. I used AI to challenge the definition before touching code.

**Starting prompt to AI:** *"I need to build a CLI alarm clock in Python. Before
coding, help me define what problem I'm actually solving, who the user is, and
what 'done' looks like."*

**Refined problem statement:**

> A developer working at a terminal wants time-based reminders without breaking
> their flow. The tool must: (a) persist alarms across terminal sessions, (b) ring
> reliably, (c) be scriptable/composable with other CLI tools, and (d) be beautiful
> enough that a developer would actually use it.

This framing ruled out several directions immediately:
- ❌ No system tray / GUI — wrong medium
- ❌ No background daemon — too fragile, too much OS surface area
- ❌ No database — overkill for <100 alarms
- ✅ Foreground `alarm run` loop + JSON persistence

---

## Step 2 — Requirements (refined from vague to specific)

### Must-have (MVP)
| Feature | Reason |
|---|---|
| `alarm add HH:MM [--label] [--repeat]` | Core functionality |
| `alarm list` | Essential for visibility |
| `alarm delete <id>` | Essential for management |
| `alarm run` | How the clock actually runs |
| JSON persistence in `~/.alarm_clock/` | Survives reboots |
| Audio (with fallback) | It's an alarm — it must ring |
| Rich terminal UI | Differentiates from a bare print() script |

### Nice-to-have (time permitting)
| Feature | Reason |
|---|---|
| `alarm toggle <id>` | Disable without deleting |
| `alarm snooze <id>` | Core alarm UX behaviour |
| `alarm next` | Scriptability / shell prompt integration |
| Repeat alarms (daily/weekdays/specific days) | Real-world usefulness |
| Colour-coded urgency (green → yellow → red) | At-a-glance awareness |

### Out of scope
- Web UI, React, database, mobile, system notifications, daemon/service

---

## Step 3 — Architecture

I prompted AI: *"Given these requirements, propose a module structure. Justify each
boundary — where should the layers be and why?"*

```
alarm_clock/
├── models.py      ← Data shape only. No logic, no I/O.
├── store.py       ← All filesystem I/O. Nothing else.
├── scheduler.py   ← Pure timing logic. No I/O, fully testable.
├── audio.py       ← Audio playback in a background thread.
├── ui.py          ← Rich rendering only. No business logic.
└── cli.py         ← Argument parsing + thin command handlers.
```

**Why this matters:** The scheduler has zero I/O — every function accepts an
optional `now: datetime` parameter. This makes all timing logic unit-testable
without mocking, patching, or sleeping. I validated this by writing 25 tests
before wiring up the I/O layers.

---

## Step 4 — Key Design Decisions

### Decision 1: Foreground monitor, not a background daemon

**Option A:** `alarm run` starts a background daemon (PID file, signal handling)
**Option B:** `alarm run` is a foreground process the user keeps open

**Chose B.** Rationale:
- Daemons require PID file management, different approaches per OS (systemd / launchd / Windows services)
- A foreground process is observable — you see it running, you kill it deliberately
- Composes naturally with `tmux`, `screen`, `nohup &`
- Far less surface area for bugs

### Decision 2: JSON file store, not SQLite

**Option A:** SQLite via stdlib `sqlite3`
**Option B:** JSON file via stdlib `json`

**Chose B.** Rationale:
- Human-readable and hand-editable — developer friendly
- Zero schema migration story to maintain
- Atomic write via `os.replace()` gives corruption safety
- POSIX `flock()` gives concurrency safety
- For <100 alarms, performance is irrelevant

### Decision 3: Atomic writes + file locking

Even though alarms are rarely written concurrently, `alarm add` and `alarm run`
can overlap. The pattern:

```python
# 1. Write to .tmp
# 2. os.replace(.tmp, alarms.json)   ← atomic on POSIX
```

...means a killed process can never leave a half-written JSON file.
`flock(LOCK_EX)` on a `.lock` file prevents two writers racing.

### Decision 4: 3-tier audio fallback

```
pygame.mixer  →  playsound  →  \a terminal bell
```

Detection happens at runtime (`try: import pygame`), not at install time.
This means the tool is installable and functional in headless/CI environments
where audio is impossible — it just falls back gracefully.

### Decision 5: Rich's `Live` display, not curses

curses gives full terminal control but requires substantial boilerplate and
careful cleanup on exception. Rich's `Live` context manager gives smooth
live-updating display for ~5 lines of code, handles terminal resize, and
cleans up on `KeyboardInterrupt`.

### Decision 6: Integer IDs, not UUIDs

`alarm delete 3` beats `alarm delete a7f3b2c1-...`. The user types these.
Readability wins over global uniqueness for a local single-user tool.

---

## Step 5 — Timing Logic Analysis

Before implementing `is_due()`, I thought through the edge cases:

| Scenario | Behaviour |
|---|---|
| Alarm at 08:00, now is 07:59 | Not due |
| Alarm at 08:00, now is 08:00:30 | Due (same minute window) |
| Alarm at 08:00, now is 08:01 | Not due (window passed) |
| Alarm at 08:00, snoozed to 08:05, now is 08:05:15 | Due at snooze time |
| Repeat alarm MON, now is WED 08:00 | Not due |
| Process paused (e.g. laptop sleep) | May miss a minute — acceptable for a dev tool |

The "missed minute" case is a conscious acceptance. A true alarm system would
need a persistence layer that tracks "was this alarm fired today?" For a dev
reminder tool, if you close your laptop through an alarm time, you probably
don't need the alarm anymore.

**Double-firing protection:** A `handled_this_minute` dict in the run loop
maps `alarm_id → "YYYY-MM-DDTHH:MM"`. An alarm is only triggered once per
minute regardless of how many times the 1-second poll fires within that window.

---

## Step 6 — What I'd add with more time

1. **`alarm edit <id>`** — modify label/time without delete+re-add
2. **`alarm import/export`** — JSON file interchange
3. **Desktop notifications** via `plyer` (cross-platform)
4. **`alarm run --daemon`** — opt-in background mode with proper PID file
5. **Shell completions** — argcomplete integration
6. **Config file** — default snooze duration, custom sound path, time format
7. **Windows support** — replace `fcntl` with `msvcrt` file locking

---

## Implementation Order (followed exactly)

1. `generate_tone.py` → get a sound asset with zero deps
2. `models.py` → define the data shape
3. `store.py` → persistence layer (I/O only)
4. `scheduler.py` → pure timing logic
5. `tests/` → write tests *before* wiring up CLI (validated layer isolation)
6. `audio.py` → background thread playback
7. `ui.py` → Rich rendering
8. `cli.py` + `__main__.py` → wire everything up
9. `pyproject.toml` + `README.md` + `DESIGN.md`
