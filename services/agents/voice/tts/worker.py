from __future__ import annotations

import os
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from uuid import uuid4

import httpx

from services.agents.voice.common import (
    normalized_env,
    require_real_voice_engines,
    voice_openai_api_key_required,
    voice_openai_ready,
)
from services.agents.voice.errors import VoiceEngineError

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_AUDIO_ROOT = PROJECT_ROOT / "data" / "audio"

TTS_ENGINE_ENV = "OPENCOMMOTION_TTS_ENGINE"
PIPER_BIN_ENV = "OPENCOMMOTION_PIPER_BIN"
PIPER_MODEL_ENV = "OPENCOMMOTION_PIPER_MODEL"
PIPER_CONFIG_ENV = "OPENCOMMOTION_PIPER_CONFIG"
ESPEAK_BIN_ENV = "OPENCOMMOTION_ESPEAK_BIN"
ESPEAK_RATE_ENV = "OPENCOMMOTION_ESPEAK_RATE"
VOICE_OPENAI_BASE_URL_ENV = "OPENCOMMOTION_VOICE_OPENAI_BASE_URL"
VOICE_OPENAI_API_KEY_ENV = "OPENCOMMOTION_VOICE_OPENAI_API_KEY"
VOICE_OPENAI_TTS_MODEL_ENV = "OPENCOMMOTION_VOICE_TTS_MODEL"
VOICE_OPENAI_TIMEOUT_ENV = "OPENCOMMOTION_VOICE_OPENAI_TIMEOUT_S"

VALID_TTS_ENGINES = {"auto", "piper", "espeak", "openai-compatible", "tone-fallback"}
REAL_TTS_ENGINES = {"piper", "espeak", "openai-compatible", "windows-sapi"}


def synthesize_segments(text: str, voice: str = "opencommotion-local") -> dict:
    safe_text = text.strip() or "No response provided."
    audio_root = Path(os.getenv("OPENCOMMOTION_AUDIO_ROOT", str(DEFAULT_AUDIO_ROOT)))
    audio_root.mkdir(parents=True, exist_ok=True)

    filename = f"voice-{uuid4()}.wav"
    output_path = audio_root / filename

    engine = _render_voice_wav(safe_text, output_path)
    if require_real_voice_engines() and engine not in REAL_TTS_ENGINES:
        output_path.unlink(missing_ok=True)
        capabilities = tts_capabilities()
        raise VoiceEngineError(
            engine="tts",
            message=(
                "No real TTS engine is configured or available. "
                f"selected={capabilities['selected_engine']}, "
                f"piper_ready={capabilities['piper']['ready']}, "
                f"espeak_ready={capabilities['espeak']['ready']}, "
                f"openai_ready={capabilities['openai_compatible']['ready']}, "
                f"openai_api_key_set={capabilities['openai_compatible']['api_key_set']}, "
                f"openai_api_key_required={capabilities['openai_compatible']['api_key_required']}"
            ),
        )

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


def tts_capabilities() -> dict:
    selected_engine = _selected_engine()

    piper_bin = _piper_binary()
    piper_model = os.getenv(PIPER_MODEL_ENV, "").strip()
    piper_ready = bool(piper_bin) and bool(piper_model) and Path(piper_model).is_file()

    espeak_bin = _espeak_binary()
    espeak_ready = espeak_bin is not None

    openai_base_url = os.getenv(VOICE_OPENAI_BASE_URL_ENV, "").strip()
    openai_model = os.getenv(VOICE_OPENAI_TTS_MODEL_ENV, "").strip()
    openai_api_key = os.getenv(VOICE_OPENAI_API_KEY_ENV, "").strip()
    openai_key_required = voice_openai_api_key_required(openai_base_url)
    openai_ready = voice_openai_ready(openai_base_url, openai_model, openai_api_key)
    windows_sapi_ready = _powershell_binary() is not None

    return {
        "selected_engine": selected_engine,
        "strict_real_engines": require_real_voice_engines(),
        "real_engines": sorted(REAL_TTS_ENGINES),
        "piper": {
            "binary": piper_bin,
            "model": piper_model,
            "ready": piper_ready,
        },
        "espeak": {
            "binary": espeak_bin,
            "ready": espeak_ready,
        },
        "openai_compatible": {
            "base_url": openai_base_url,
            "model": openai_model,
            "api_key_set": bool(openai_api_key),
            "api_key_required": openai_key_required,
            "ready": openai_ready,
        },
        "windows_sapi": {
            "ready": windows_sapi_ready,
        },
    }


def _selected_engine() -> str:
    selected = normalized_env(TTS_ENGINE_ENV, default="auto")
    if selected not in VALID_TTS_ENGINES:
        return "auto"
    return selected


def _render_voice_wav(text: str, output_path: Path) -> str:
    selected_engine = _selected_engine()

    if selected_engine == "piper":
        return _render_with_piper(text, output_path, required=True)

    if selected_engine == "espeak":
        return _render_with_espeak(text, output_path, required=True)

    if selected_engine == "openai-compatible":
        return _render_with_openai_compatible(text, output_path, required=True)

    if selected_engine == "tone-fallback":
        _write_tone_wav(
            output_path=output_path,
            duration_ms=min(max(len(text) * 65, 900), 7000),
            sample_rate=22050,
        )
        return "tone-fallback"

    piper_engine = _render_with_piper(text, output_path, required=False)
    if piper_engine:
        return piper_engine

    espeak_engine = _render_with_espeak(text, output_path, required=False)
    if espeak_engine:
        return espeak_engine

    openai_engine = _render_with_openai_compatible(text, output_path, required=False)
    if openai_engine:
        return openai_engine

    windows_engine = _render_with_windows_sapi(text, output_path, required=False)
    if windows_engine:
        return windows_engine

    _write_tone_wav(
        output_path=output_path,
        duration_ms=min(max(len(text) * 65, 900), 7000),
        sample_rate=22050,
    )
    return "tone-fallback"


def _render_with_piper(text: str, output_path: Path, required: bool) -> str | None:
    piper_bin = _piper_binary()
    piper_model = os.getenv(PIPER_MODEL_ENV, "").strip()
    piper_config = os.getenv(PIPER_CONFIG_ENV, "").strip()

    if not piper_bin:
        if required:
            raise VoiceEngineError(engine="piper", message="piper binary is not available")
        return None
    if not piper_model:
        if required:
            raise VoiceEngineError(engine="piper", message=f"Missing {PIPER_MODEL_ENV}")
        return None
    if not Path(piper_model).is_file():
        if required:
            raise VoiceEngineError(engine="piper", message=f"Piper model not found: {piper_model}")
        return None

    command = [piper_bin, "--model", piper_model, "--output_file", str(output_path)]
    if piper_config:
        command.extend(["--config", piper_config])

    try:
        completed = subprocess.run(command, input=text, capture_output=True, text=True, check=False)
    except OSError as exc:
        if required:
            raise VoiceEngineError(engine="piper", message=f"piper synthesis failed: {exc}") from exc
        return None
    if completed.returncode == 0 and output_path.exists():
        return "piper"

    if required:
        stderr = completed.stderr.strip() if completed.stderr else "unknown error"
        raise VoiceEngineError(engine="piper", message=f"piper synthesis failed: {stderr}")
    return None


def _render_with_espeak(text: str, output_path: Path, required: bool) -> str | None:
    espeak_bin = _espeak_binary()
    if not espeak_bin:
        if required:
            raise VoiceEngineError(engine="espeak", message="espeak/espeak-ng binary is not available")
        return None

    command = [espeak_bin, "-w", str(output_path)]
    rate = os.getenv(ESPEAK_RATE_ENV, "").strip()
    if rate.isdigit():
        command.extend(["-s", rate])
    command.append(text)

    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        if required:
            raise VoiceEngineError(engine="espeak", message=f"espeak synthesis failed: {exc}") from exc
        return None
    if completed.returncode == 0 and output_path.exists():
        return "espeak"

    if required:
        stderr = completed.stderr.strip() if completed.stderr else "unknown error"
        raise VoiceEngineError(engine="espeak", message=f"espeak synthesis failed: {stderr}")
    return None


def _openai_timeout_s() -> float:
    raw = os.getenv(VOICE_OPENAI_TIMEOUT_ENV, "20").strip()
    try:
        value = float(raw)
    except ValueError:
        return 20.0
    return min(max(value, 0.5), 120.0)


def _openai_headers() -> dict[str, str]:
    api_key = os.getenv(VOICE_OPENAI_API_KEY_ENV, "").strip()
    if not api_key:
        return {"content-type": "application/json"}
    return {
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    }


def _render_with_openai_compatible(text: str, output_path: Path, required: bool) -> str | None:
    base_url = os.getenv(VOICE_OPENAI_BASE_URL_ENV, "").rstrip("/")
    model = os.getenv(VOICE_OPENAI_TTS_MODEL_ENV, "").strip()
    api_key = os.getenv(VOICE_OPENAI_API_KEY_ENV, "").strip()
    if not base_url or not model:
        if required:
            missing = []
            if not base_url:
                missing.append(VOICE_OPENAI_BASE_URL_ENV)
            if not model:
                missing.append(VOICE_OPENAI_TTS_MODEL_ENV)
            raise VoiceEngineError(
                engine="openai-compatible",
                message=f"Missing required OpenAI-compatible TTS config: {', '.join(missing)}",
            )
        return None
    if voice_openai_api_key_required(base_url) and not api_key:
        if required:
            raise VoiceEngineError(
                engine="openai-compatible",
                message=f"Missing required OpenAI-compatible TTS config: {VOICE_OPENAI_API_KEY_ENV}",
            )
        return None

    payload = {
        "model": model,
        "input": text,
        "voice": "alloy",
        "format": "wav",
    }
    try:
        response = httpx.post(
            f"{base_url}/audio/speech",
            json=payload,
            headers=_openai_headers(),
            timeout=_openai_timeout_s(),
        )
        response.raise_for_status()
        content = response.content
    except Exception as exc:  # noqa: BLE001
        if required:
            raise VoiceEngineError(
                engine="openai-compatible",
                message=f"openai-compatible synthesis failed: {exc}",
            ) from exc
        return None

    if not content:
        if required:
            raise VoiceEngineError(engine="openai-compatible", message="openai-compatible returned empty audio payload")
        return None
    output_path.write_bytes(content)
    try:
        _wav_duration_ms(output_path)
    except Exception as exc:  # noqa: BLE001
        output_path.unlink(missing_ok=True)
        if required:
            raise VoiceEngineError(
                engine="openai-compatible",
                message=f"openai-compatible did not return valid wav audio: {exc}",
            ) from exc
        return None
    return "openai-compatible"


def _render_with_windows_sapi(text: str, output_path: Path, required: bool) -> str | None:
    powershell_bin = _powershell_binary()
    if not powershell_bin:
        if required:
            raise VoiceEngineError(engine="windows-sapi", message="powershell is not available")
        return None

    windows_output_path = _to_windows_path(output_path)
    if not windows_output_path:
        if required:
            raise VoiceEngineError(engine="windows-sapi", message="could not map output path for powershell")
        return None

    escaped_path = windows_output_path.replace("'", "''")
    escaped_text = text.replace("\r", " ").replace("\n", " ").replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$synth.SetOutputToWaveFile('{escaped_path}'); "
        f"$synth.Speak('{escaped_text}'); "
        "$synth.Dispose();"
    )
    command = [powershell_bin, "-NoProfile", "-Command", script]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        if required:
            raise VoiceEngineError(engine="windows-sapi", message=f"windows sapi synthesis failed: {exc}") from exc
        return None

    if completed.returncode == 0 and output_path.exists():
        return "windows-sapi"

    if required:
        stderr = completed.stderr.strip() if completed.stderr else "unknown error"
        raise VoiceEngineError(engine="windows-sapi", message=f"windows sapi synthesis failed: {stderr}")
    return None


def _piper_binary() -> str | None:
    configured = os.getenv(PIPER_BIN_ENV, "").strip()
    if configured:
        return shutil.which(configured) or configured
    return shutil.which("piper")


def _espeak_binary() -> str | None:
    configured = os.getenv(ESPEAK_BIN_ENV, "").strip()
    if configured:
        return shutil.which(configured) or configured
    return shutil.which("espeak") or shutil.which("espeak-ng")


def _powershell_binary() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


def _to_windows_path(path: Path) -> str | None:
    raw = str(path)
    if os.name == "nt":
        return raw
    wslpath_bin = shutil.which("wslpath")
    if not wslpath_bin:
        return None
    try:
        completed = subprocess.run([wslpath_bin, "-w", raw], capture_output=True, text=True, check=False)
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    mapped = completed.stdout.strip()
    return mapped or None


def _write_tone_wav(output_path: Path, duration_ms: int, sample_rate: int) -> None:
    frames = int(sample_rate * (duration_ms / 1000.0))
    sample_bytes = bytearray()
    for frame in range(frames):
        envelope = 0.25 if frame % 2 == 0 else 0.2
        angle = (frame % 220) / 220.0
        sample = int(32767 * envelope * (0.5 - abs(angle - 0.5)))
        sample_bytes.extend(struct.pack("<h", sample))

    with wave.open(str(output_path), "wb") as wav_writer:
        wav_writer.setnchannels(1)
        wav_writer.setsampwidth(2)
        wav_writer.setframerate(sample_rate)
        wav_writer.writeframes(sample_bytes)


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_reader:
        frames = wav_reader.getnframes()
        rate = wav_reader.getframerate() or 1
    return int((frames / rate) * 1000)


__all__ = ["synthesize_segments", "tts_capabilities"]
