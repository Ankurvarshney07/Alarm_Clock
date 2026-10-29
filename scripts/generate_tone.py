"""
generate_tone.py — Zero-dependency alarm sound generator.

Produces assets/alarm.wav using only Python stdlib `wave` + `struct`.
Run once: python scripts/generate_tone.py
"""
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44100   # Hz
CHANNELS = 1
SAMPLE_WIDTH = 2      # 16-bit


def sine_wave(freq: float, duration: float, amplitude: float = 0.5) -> bytes:
    """Return raw PCM bytes for a sine wave at the given frequency."""
    n_samples = int(SAMPLE_RATE * duration)
    frames = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        # Apply a short fade-in / fade-out envelope to avoid clicks
        env = 1.0
        fade = int(SAMPLE_RATE * 0.01)  # 10ms
        if i < fade:
            env = i / fade
        elif i > n_samples - fade:
            env = (n_samples - i) / fade
        sample = amplitude * env * math.sin(2 * math.pi * freq * t)
        frames.append(struct.pack("<h", int(sample * 32767)))
    return b"".join(frames)


def generate_alarm_wav(output_path: Path) -> None:
    """
    Generate a two-tone alarm pattern: high beep + rest, repeated.

    Pattern: 880Hz for 0.2s, silence 0.1s — 4 times, then 0.3s pause.
    Total clip ~2.4s, designed to loop.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    segments: list[bytes] = []
    silence_short = b"\x00\x00" * int(SAMPLE_RATE * 0.10)   # 100ms
    silence_long  = b"\x00\x00" * int(SAMPLE_RATE * 0.35)   # 350ms

    for _ in range(4):
        segments.append(sine_wave(880, 0.18))   # beep
        segments.append(silence_short)

    segments.append(sine_wave(660, 0.25))        # lower closing tone
    segments.append(silence_long)

    raw_audio = b"".join(segments)

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(raw_audio)

    print(f"✔ Generated {output_path}  ({len(raw_audio) // 1024} KB)")


if __name__ == "__main__":
    dest = Path(__file__).parent.parent / "assets" / "alarm.wav"
    generate_alarm_wav(dest)
