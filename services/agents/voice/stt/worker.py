from __future__ import annotations


def transcribe_audio(_: bytes) -> dict:
    return {
        "partial": "",
        "final": "stt placeholder",
        "confidence": 0.5,
        "engine": "placeholder",
    }
