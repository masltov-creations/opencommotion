from __future__ import annotations

from re import findall


def transcribe_audio(audio: bytes, hint: str = "") -> dict:
    if hint.strip():
        return {
            "partial": "",
            "final": hint.strip(),
            "confidence": 0.95,
            "engine": "hint",
        }

    decoded = _decode_text_payload(audio)
    if decoded:
        return {
            "partial": "",
            "final": decoded,
            "confidence": 0.72,
            "engine": "text-fallback",
        }

    return {
        "partial": "",
        "final": "voice input received",
        "confidence": 0.4,
        "engine": "fallback",
    }


def _decode_text_payload(audio: bytes) -> str:
    try:
        decoded = audio.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""
    if not decoded:
        return ""
    tokens = findall(r"[A-Za-z0-9']+", decoded)
    if len(tokens) < 2:
        return ""
    if tokens[:2] == ["RIFF", "WAVEfmt"] or tokens[:1] == ["RIFF"]:
        return ""
    cleaned = " ".join(tokens).strip()
    if len(cleaned) > 160:
        return cleaned[:160].rstrip()
    return cleaned


__all__ = ["transcribe_audio"]
