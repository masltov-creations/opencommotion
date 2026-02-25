#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from services.agents.voice.common import require_real_voice_engines
from services.agents.voice.stt.worker import stt_capabilities
from services.agents.voice.tts.worker import tts_capabilities


def main() -> int:
    stt = stt_capabilities()
    tts = tts_capabilities()
    strict = require_real_voice_engines()

    report = {
        "strict_real_engines": strict,
        "stt": stt,
        "tts": tts,
    }
    print(json.dumps(report, indent=2))

    if not strict:
        return 0

    stt_ready = bool(
        stt["faster_whisper"]["ready"]
        or stt["vosk"]["ready"]
        or stt.get("openai_compatible", {}).get("ready")
    )
    tts_ready = bool(
        tts["piper"]["ready"]
        or tts["espeak"]["ready"]
        or tts.get("openai_compatible", {}).get("ready")
        or tts.get("windows_sapi", {}).get("ready")
    )
    if stt_ready and tts_ready:
        return 0

    print(
        "voice_preflight failed: strict mode requires at least one real STT and one real TTS engine",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
