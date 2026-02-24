from __future__ import annotations


def synthesize_segments(text: str) -> dict:
    return {
        "voice": "opencommotion-local",
        "segments": [
            {
                "text": text,
                "start_ms": 0,
                "duration_ms": 1800,
                "audio_uri": "memory://voice/segment-0",
            }
        ],
    }
