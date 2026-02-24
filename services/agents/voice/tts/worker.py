from __future__ import annotations

import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_AUDIO_ROOT = PROJECT_ROOT / "data" / "audio"


def synthesize_segments(text: str, voice: str = "opencommotion-local") -> dict:
    safe_text = text.strip() or "No response provided."
    audio_root = Path(os.getenv("OPENCOMMOTION_AUDIO_ROOT", str(DEFAULT_AUDIO_ROOT)))
    audio_root.mkdir(parents=True, exist_ok=True)

    filename = f"voice-{uuid4()}.wav"
    output_path = audio_root / filename

    engine = _render_voice_wav(safe_text, output_path)
    duration_ms = _wav_duration_ms(output_path)

    return {
        "voice": voice,
        "engine": engine,
        "segments": [
            {
                "text": safe_text,
                "start_ms": 0,
                "duration_ms": duration_ms,
                "audio_uri": f"/v1/audio/{filename}",
            }
        ],
    }


def _render_voice_wav(text: str, output_path: Path) -> str:
    espeak_bin = shutil.which("espeak") or shutil.which("espeak-ng")
    if espeak_bin:
        completed = subprocess.run(
            [espeak_bin, "-w", str(output_path), text],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0 and output_path.exists():
            return "espeak"

    _write_tone_wav(
        output_path=output_path,
        duration_ms=min(max(len(text) * 65, 900), 7000),
        sample_rate=22050,
    )
    return "tone-fallback"


def _write_tone_wav(output_path: Path, duration_ms: int, sample_rate: int) -> None:
    frames = int(sample_rate * (duration_ms / 1000.0))
    sample_bytes = bytearray()
    for frame in range(frames):
        envelope = 0.25 if frame % 2 == 0 else 0.2
        angle = (frame % 220) / 220.0
        sample = int(32767 * envelope * (0.5 - abs(angle - 0.5)))
        sample_bytes.extend(struct.pack("<h", sample))

    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(sample_bytes)


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate() or 1
    return int((frames / rate) * 1000)


__all__ = ["synthesize_segments"]
