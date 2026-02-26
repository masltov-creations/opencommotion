from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
ENV_PATH = PROJECT_ROOT / ".env"

SECRET_KEYS = {
    "OPENCOMMOTION_OPENAI_API_KEY",
    "OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY",
    "OPENCOMMOTION_VOICE_OPENAI_API_KEY",
    "OPENCOMMOTION_API_KEYS",
}

EDITABLE_KEYS = {
    "OPENCOMMOTION_LLM_PROVIDER",
    "OPENCOMMOTION_LLM_MODEL",
    "OPENCOMMOTION_LLM_ALLOW_FALLBACK",
    "OPENCOMMOTION_LLM_TIMEOUT_S",
    "OPENCOMMOTION_NARRATION_CONTEXT_ENABLED",
    "OPENCOMMOTION_OLLAMA_URL",
    "OPENCOMMOTION_OPENAI_BASE_URL",
    "OPENCOMMOTION_OPENAI_API_KEY",
    "OPENCOMMOTION_CODEX_BIN",
    "OPENCOMMOTION_CODEX_MODEL",
    "OPENCOMMOTION_CODEX_TIMEOUT_S",
    "OPENCOMMOTION_OPENCLAW_BIN",
    "OPENCOMMOTION_OPENCLAW_TIMEOUT_S",
    "OPENCOMMOTION_OPENCLAW_SESSION_PREFIX",
    "OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL",
    "OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY",
    "OPENCOMMOTION_OPENCLAW_OPENAI_MODEL",
    "OPENCOMMOTION_STT_ENGINE",
    "OPENCOMMOTION_STT_MODEL",
    "OPENCOMMOTION_STT_COMPUTE_TYPE",
    "OPENCOMMOTION_VOSK_MODEL_PATH",
    "OPENCOMMOTION_TTS_ENGINE",
    "OPENCOMMOTION_PIPER_BIN",
    "OPENCOMMOTION_PIPER_MODEL",
    "OPENCOMMOTION_PIPER_CONFIG",
    "OPENCOMMOTION_ESPEAK_BIN",
    "OPENCOMMOTION_ESPEAK_RATE",
    "OPENCOMMOTION_VOICE_OPENAI_BASE_URL",
    "OPENCOMMOTION_VOICE_OPENAI_API_KEY",
    "OPENCOMMOTION_VOICE_STT_MODEL",
    "OPENCOMMOTION_VOICE_TTS_MODEL",
    "OPENCOMMOTION_VOICE_OPENAI_TIMEOUT_S",
    "OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES",
    "OPENCOMMOTION_AUTH_MODE",
    "OPENCOMMOTION_API_KEYS",
    "OPENCOMMOTION_ALLOWED_IPS",
}

VALID_LLM_PROVIDERS = {
    "heuristic",
    "ollama",
    "openai-compatible",
    "codex-cli",
    "openclaw-cli",
    "openclaw-openai",
}
VALID_STT_ENGINES = {"auto", "hint", "faster-whisper", "vosk", "openai-compatible", "text-fallback"}
VALID_TTS_ENGINES = {"auto", "piper", "espeak", "openai-compatible", "tone-fallback"}
VALID_AUTH_MODES = {"api-key", "network-trust"}
LOCAL_VOICE_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "::1"}


def _voice_api_key_required(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    return host not in LOCAL_VOICE_HOSTS


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, payload: dict[str, str]) -> None:
    ordered_keys: list[str] = []
    if ENV_EXAMPLE_PATH.exists():
        for raw in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key not in ordered_keys:
                ordered_keys.append(key)

    for key in sorted(payload):
        if key not in ordered_keys:
            ordered_keys.append(key)

    lines = [f"{key}={payload.get(key, '')}" for key in ordered_keys]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def masked_state(values: dict[str, str]) -> dict[str, str]:
    masked: dict[str, str] = {}
    for key, value in values.items():
        if key in SECRET_KEYS and value:
            masked[key] = "********"
        else:
            masked[key] = value
    return masked


def normalized_editable(values: dict[str, Any]) -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in values.items():
        if key not in EDITABLE_KEYS:
            continue
        clean[key] = str(value).strip()
    return clean


def validate_setup(values: dict[str, str]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    provider = values.get("OPENCOMMOTION_LLM_PROVIDER", "").strip().lower() or "heuristic"
    if provider not in VALID_LLM_PROVIDERS:
        errors.append(f"Unsupported LLM provider: {provider}")

    if provider == "ollama":
        if not values.get("OPENCOMMOTION_OLLAMA_URL", "").strip():
            errors.append("OPENCOMMOTION_OLLAMA_URL is required for ollama provider")
    if provider == "openai-compatible":
        if not values.get("OPENCOMMOTION_OPENAI_BASE_URL", "").strip():
            errors.append("OPENCOMMOTION_OPENAI_BASE_URL is required for openai-compatible provider")
    if provider == "openclaw-openai":
        if not values.get("OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL", "").strip():
            errors.append("OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL is required for openclaw-openai provider")
    if provider == "codex-cli":
        bin_name = values.get("OPENCOMMOTION_CODEX_BIN", "codex").strip() or "codex"
        if shutil.which(bin_name) is None:
            warnings.append(f"{bin_name} is not currently on PATH")
    if provider == "openclaw-cli":
        bin_name = values.get("OPENCOMMOTION_OPENCLAW_BIN", "openclaw").strip() or "openclaw"
        if shutil.which(bin_name) is None:
            warnings.append(f"{bin_name} is not currently on PATH")

    stt = values.get("OPENCOMMOTION_STT_ENGINE", "").strip().lower() or "auto"
    if stt not in VALID_STT_ENGINES:
        errors.append(f"Unsupported STT engine: {stt}")
    if stt == "openai-compatible":
        stt_base_url = values.get("OPENCOMMOTION_VOICE_OPENAI_BASE_URL", "").strip()
        stt_api_key = values.get("OPENCOMMOTION_VOICE_OPENAI_API_KEY", "").strip()
        if not stt_base_url:
            errors.append("OPENCOMMOTION_VOICE_OPENAI_BASE_URL is required for openai-compatible STT")
        if not values.get("OPENCOMMOTION_VOICE_STT_MODEL", "").strip():
            errors.append("OPENCOMMOTION_VOICE_STT_MODEL is required for openai-compatible STT")
        if stt_base_url and _voice_api_key_required(stt_base_url) and not stt_api_key:
            errors.append("OPENCOMMOTION_VOICE_OPENAI_API_KEY is required for remote openai-compatible STT")

    tts = values.get("OPENCOMMOTION_TTS_ENGINE", "").strip().lower() or "auto"
    if tts not in VALID_TTS_ENGINES:
        errors.append(f"Unsupported TTS engine: {tts}")
    if tts == "openai-compatible":
        tts_base_url = values.get("OPENCOMMOTION_VOICE_OPENAI_BASE_URL", "").strip()
        tts_api_key = values.get("OPENCOMMOTION_VOICE_OPENAI_API_KEY", "").strip()
        if not tts_base_url:
            errors.append("OPENCOMMOTION_VOICE_OPENAI_BASE_URL is required for openai-compatible TTS")
        if not values.get("OPENCOMMOTION_VOICE_TTS_MODEL", "").strip():
            errors.append("OPENCOMMOTION_VOICE_TTS_MODEL is required for openai-compatible TTS")
        if tts_base_url and _voice_api_key_required(tts_base_url) and not tts_api_key:
            errors.append("OPENCOMMOTION_VOICE_OPENAI_API_KEY is required for remote openai-compatible TTS")

    auth_mode = values.get("OPENCOMMOTION_AUTH_MODE", "").strip().lower() or "api-key"
    if auth_mode not in VALID_AUTH_MODES:
        errors.append(f"Unsupported auth mode: {auth_mode}")
    if auth_mode == "api-key" and not values.get("OPENCOMMOTION_API_KEYS", "").strip():
        warnings.append("OPENCOMMOTION_API_KEYS is empty; requests will be unauthenticated")
    if auth_mode == "network-trust" and not values.get("OPENCOMMOTION_ALLOWED_IPS", "").strip():
        warnings.append(
            "OPENCOMMOTION_ALLOWED_IPS is empty; network-trust will allow all IPs. "
            "Use 127.0.0.1/32,::1/128 for local-machine-only access."
        )

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


__all__ = [
    "ENV_PATH",
    "EDITABLE_KEYS",
    "masked_state",
    "normalized_editable",
    "parse_env",
    "validate_setup",
    "write_env",
]
