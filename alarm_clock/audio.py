"""
audio.py — Cross-platform alarm sound playback.

Strategy (graceful degradation):
  1. Try pygame.mixer — best quality, supports looping.
  2. Fall back to playsound — simpler, good cross-platform support.
  3. Fall back to terminal ASCII bell (\a) — zero dependencies.

The fallback chain is evaluated at runtime so the tool works even in
headless / CI environments where no audio hardware is present.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Optional

# Locate the bundled alarm.wav relative to this file
_ASSET_DIR = Path(__file__).parent.parent / "assets"
DEFAULT_SOUND = _ASSET_DIR / "alarm.wav"


class AlarmPlayer:
    """
    Manages alarm audio playback in a background thread.

    Usage:
        player = AlarmPlayer()
        player.start()          # begin looping playback
        ...
        player.stop()           # stop cleanly
    """

    def __init__(self, sound_path: Optional[Path] = None) -> None:
        self._sound_path = sound_path or DEFAULT_SOUND
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backend: str = "none"

    # ── Public interface ───────────────────────────────────────────────────

    def start(self) -> None:
        """Begin audio playback in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the playback thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    @property
    def backend(self) -> str:
        return self._backend

    # ── Internal ───────────────────────────────────────────────────────────

    def _play_loop(self) -> None:
        if self._try_pygame():
            return
        if self._try_playsound():
            return
        self._bell_fallback()

    def _try_pygame(self) -> bool:
        """Attempt playback via pygame.mixer. Returns True if successful."""
        try:
            import pygame  # type: ignore

            pygame.mixer.init()
            if not self._sound_path.exists():
                return False
            pygame.mixer.music.load(str(self._sound_path))
            pygame.mixer.music.play(loops=-1)  # loop indefinitely
            self._backend = "pygame"

            while not self._stop_event.is_set():
                time.sleep(0.1)

            pygame.mixer.music.stop()
            pygame.mixer.quit()
            return True
        except Exception:
            return False

    def _try_playsound(self) -> bool:
        """Attempt playback via playsound. Returns True if successful."""
        try:
            from playsound import playsound  # type: ignore

            if not self._sound_path.exists():
                return False
            self._backend = "playsound"
            while not self._stop_event.is_set():
                playsound(str(self._sound_path), block=True)
            return True
        except Exception:
            return False

    def _bell_fallback(self) -> None:
        """Ring terminal bell character repeatedly as last resort."""
        self._backend = "bell"
        while not self._stop_event.is_set():
            sys.stdout.write("\a")
            sys.stdout.flush()
            time.sleep(0.8)
