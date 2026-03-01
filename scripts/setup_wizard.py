#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE_PATH = ROOT / ".env.example"
ENV_PATH = ROOT / ".env"
DEFAULT_LOCAL_TRUSTED_IPS = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"


def parse_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(path: Path, payload: dict[str, str]) -> None:
    ordered_keys = []
    for raw_line in ENV_EXAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
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


def choose(
    prompt: str,
    options: list[tuple[str, str]],
    default: int = 0,
    default_value: str | None = None,
) -> str:
    if default_value is not None:
        for idx, (value, _label) in enumerate(options):
            if value == default_value:
                default = idx
                break

    print(f"\n{prompt}")
    for idx, (value, label) in enumerate(options, start=1):
        marker = " (default)" if (idx - 1) == default else ""
        print(f"  {idx}. {label}{marker}")
    raw = input(f"Select [1-{len(options)}] (default {default + 1}): ").strip()
    if not raw:
        return options[default][0]
    try:
        index = int(raw) - 1
    except ValueError:
        return options[default][0]
    if index < 0 or index >= len(options):
        return options[default][0]
    return options[index][0]


def ask(prompt: str, default: str = "") -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw if raw else default


def yes_no(prompt: str, default_yes: bool = True) -> bool:
    default = "Y/n" if default_yes else "y/N"
    raw = input(f"{prompt} ({default}): ").strip().lower()
    if not raw:
        return default_yes
    return raw in {"y", "yes"}


def as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def build_configuration(existing: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    config = dict(existing)
    tips: list[str] = []

    print("OpenCommotion setup wizard")
    print("This will configure LLM, STT, and TTS defaults in .env.")

    llm_choice = choose(
        "Choose LLM provider",
        [
            ("ollama", "Ollama local models (recommended open-source default)"),
            ("openai-compatible", "OpenAI-compatible server (llama.cpp/vLLM/LocalAI)"),
            ("codex-cli", "Codex CLI local worker"),
            ("openclaw-cli", "OpenClaw CLI local worker"),
            ("openclaw-openai", "OpenClaw OpenAI-compatible endpoint"),
            ("heuristic", "Built-in offline heuristic fallback only"),
        ],
        default=0,
        default_value=config.get("OPENCOMMOTION_LLM_PROVIDER"),
    )
    config["OPENCOMMOTION_LLM_PROVIDER"] = llm_choice
    config["OPENCOMMOTION_LLM_ALLOW_FALLBACK"] = "true"
    config["OPENCOMMOTION_LLM_TIMEOUT_S"] = ask(
        "LLM timeout seconds",
        config.get("OPENCOMMOTION_LLM_TIMEOUT_S", "20"),
    )

    if llm_choice == "ollama":
        model = ask(
            "Ollama model",
            config.get("OPENCOMMOTION_LLM_MODEL", "qwen2.5:7b-instruct"),
        )
        config["OPENCOMMOTION_LLM_MODEL"] = model
        config["OPENCOMMOTION_OLLAMA_URL"] = ask(
            "Ollama URL",
            config.get("OPENCOMMOTION_OLLAMA_URL", "http://127.0.0.1:11434"),
        )
        tips.append(f"ollama pull {model}")
    elif llm_choice == "openai-compatible":
        config["OPENCOMMOTION_LLM_MODEL"] = ask(
            "OpenAI-compatible model id",
            config.get("OPENCOMMOTION_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        )
        config["OPENCOMMOTION_OPENAI_BASE_URL"] = ask(
            "OpenAI-compatible base URL",
            config.get("OPENCOMMOTION_OPENAI_BASE_URL", "http://127.0.0.1:8002/v1"),
        )
        config["OPENCOMMOTION_OPENAI_API_KEY"] = ask(
            "API key (leave blank for local servers that do not require auth)",
            config.get("OPENCOMMOTION_OPENAI_API_KEY", ""),
        )
    elif llm_choice == "codex-cli":
        config["OPENCOMMOTION_CODEX_BIN"] = ask(
            "Codex binary name/path",
            config.get("OPENCOMMOTION_CODEX_BIN", "codex"),
        )
        config["OPENCOMMOTION_CODEX_MODEL"] = ask(
            "Codex model (optional)",
            config.get("OPENCOMMOTION_CODEX_MODEL", ""),
        )
        config["OPENCOMMOTION_CODEX_TIMEOUT_S"] = ask(
            "Codex timeout seconds",
            config.get("OPENCOMMOTION_CODEX_TIMEOUT_S", "60"),
        )
    elif llm_choice == "openclaw-cli":
        config["OPENCOMMOTION_OPENCLAW_BIN"] = ask(
            "OpenClaw binary name/path",
            config.get("OPENCOMMOTION_OPENCLAW_BIN", "openclaw"),
        )
        config["OPENCOMMOTION_OPENCLAW_TIMEOUT_S"] = ask(
            "OpenClaw timeout seconds",
            config.get("OPENCOMMOTION_OPENCLAW_TIMEOUT_S", "90"),
        )
        config["OPENCOMMOTION_OPENCLAW_SESSION_PREFIX"] = ask(
            "OpenClaw session prefix",
            config.get("OPENCOMMOTION_OPENCLAW_SESSION_PREFIX", "opencommotion"),
        )
    elif llm_choice == "openclaw-openai":
        config["OPENCOMMOTION_OPENCLAW_OPENAI_MODEL"] = ask(
            "OpenClaw OpenAI-compatible model id",
            config.get("OPENCOMMOTION_OPENCLAW_OPENAI_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        )
        config["OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL"] = ask(
            "OpenClaw OpenAI-compatible base URL",
            config.get("OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL", "http://127.0.0.1:8002/v1"),
        )
        config["OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY"] = ask(
            "OpenClaw OpenAI-compatible API key",
            config.get("OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY", ""),
        )
    else:
        config["OPENCOMMOTION_LLM_MODEL"] = ""

    stt_choice = choose(
        "Choose STT engine",
        [
            ("faster-whisper", "faster-whisper (recommended quality)"),
            ("vosk", "Vosk (lightweight offline)"),
            ("openai-compatible", "OpenAI-compatible cloud STT"),
            ("auto", "Auto (try faster-whisper, then vosk, then fallback)"),
            ("text-fallback", "Text fallback only (dev/testing)"),
        ],
        default=3,
        default_value=config.get("OPENCOMMOTION_STT_ENGINE"),
    )
    config["OPENCOMMOTION_STT_ENGINE"] = stt_choice
    if stt_choice == "faster-whisper":
        config["OPENCOMMOTION_STT_MODEL"] = ask(
            "faster-whisper model name",
            config.get("OPENCOMMOTION_STT_MODEL", "small.en"),
        )
        config["OPENCOMMOTION_STT_COMPUTE_TYPE"] = ask(
            "faster-whisper compute type",
            config.get("OPENCOMMOTION_STT_COMPUTE_TYPE", "int8"),
        )
        tips.append("pip install faster-whisper")
    elif stt_choice == "vosk":
        config["OPENCOMMOTION_VOSK_MODEL_PATH"] = ask(
            "Vosk model path",
            config.get("OPENCOMMOTION_VOSK_MODEL_PATH", "/opt/models/vosk-model-small-en-us-0.15"),
        )
        tips.append("pip install vosk")
    elif stt_choice == "openai-compatible":
        config["OPENCOMMOTION_VOICE_STT_MODEL"] = ask(
            "OpenAI-compatible STT model",
            config.get("OPENCOMMOTION_VOICE_STT_MODEL", "gpt-4o-mini-transcribe"),
        )

    tts_choice = choose(
        "Choose TTS engine",
        [
            ("piper", "Piper (recommended quality)"),
            ("espeak", "espeak/espeak-ng (quick local default)"),
            ("openai-compatible", "OpenAI-compatible cloud TTS"),
            ("auto", "Auto (try piper, then espeak, then tone fallback)"),
            ("tone-fallback", "Tone fallback only (dev/testing)"),
        ],
        default=0,
        default_value=config.get("OPENCOMMOTION_TTS_ENGINE"),
    )
    config["OPENCOMMOTION_TTS_ENGINE"] = tts_choice
    if tts_choice == "piper":
        config["OPENCOMMOTION_PIPER_BIN"] = ask(
            "Piper binary",
            config.get("OPENCOMMOTION_PIPER_BIN", "piper"),
        )
        config["OPENCOMMOTION_PIPER_MODEL"] = ask(
            "Piper model path",
            config.get("OPENCOMMOTION_PIPER_MODEL", "data/models/piper/en_US-lessac-high.onnx"),
        )
        tips.append("Install Piper binary and place a model at data/models/piper/*.onnx")
    elif tts_choice == "espeak":
        config["OPENCOMMOTION_ESPEAK_BIN"] = ask(
            "espeak binary name/path",
            config.get("OPENCOMMOTION_ESPEAK_BIN", "espeak"),
        )
        config["OPENCOMMOTION_ESPEAK_RATE"] = ask(
            "espeak rate",
            config.get("OPENCOMMOTION_ESPEAK_RATE", "170"),
        )
    elif tts_choice == "openai-compatible":
        config["OPENCOMMOTION_VOICE_TTS_MODEL"] = ask(
            "OpenAI-compatible TTS model",
            config.get("OPENCOMMOTION_VOICE_TTS_MODEL", "gpt-4o-mini-tts"),
        )

    if stt_choice == "openai-compatible" or tts_choice == "openai-compatible":
        config["OPENCOMMOTION_VOICE_OPENAI_BASE_URL"] = ask(
            "OpenAI-compatible voice base URL",
            config.get("OPENCOMMOTION_VOICE_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        config["OPENCOMMOTION_VOICE_OPENAI_API_KEY"] = ask(
            "OpenAI-compatible voice API key",
            config.get("OPENCOMMOTION_VOICE_OPENAI_API_KEY", ""),
        )
        config["OPENCOMMOTION_VOICE_OPENAI_TIMEOUT_S"] = ask(
            "OpenAI-compatible voice timeout seconds",
            config.get("OPENCOMMOTION_VOICE_OPENAI_TIMEOUT_S", "20"),
        )

    strict_real = yes_no(
        "Require real STT/TTS engines in runtime (recommended for production)?",
        default_yes=as_bool(config.get("OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES"), False),
    )
    config["OPENCOMMOTION_VOICE_REQUIRE_REAL_ENGINES"] = "true" if strict_real else "false"

    auth_mode = choose(
        "Choose gateway auth mode",
        [
            ("api-key", "API key mode (recommended)"),
            ("network-trust", "Allowlist network trust mode"),
        ],
        default=1,
        default_value=config.get("OPENCOMMOTION_AUTH_MODE"),
    )
    config["OPENCOMMOTION_AUTH_MODE"] = auth_mode
    if auth_mode == "api-key":
        config["OPENCOMMOTION_API_KEYS"] = ask(
            "Gateway API keys (comma-separated)",
            config.get("OPENCOMMOTION_API_KEYS", "dev-opencommotion-key"),
        )
    else:
        config["OPENCOMMOTION_ALLOWED_IPS"] = ask(
            "Allowed IP/CIDR list (comma-separated, default local + private LAN ranges)",
            config.get("OPENCOMMOTION_ALLOWED_IPS", DEFAULT_LOCAL_TRUSTED_IPS),
        )

    return config, tips


def main() -> int:
    if not ENV_EXAMPLE_PATH.exists():
        raise FileNotFoundError(f"Missing template: {ENV_EXAMPLE_PATH}")

    if not ENV_PATH.exists():
        shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)

    existing = parse_env(ENV_PATH)
    config, tips = build_configuration(existing)
    write_env(ENV_PATH, config)

    print(f"\nWrote configuration to {ENV_PATH}")
    print("\nNext steps:")
    for tip in tips:
        print(f"- {tip}")
    print("- opencommotion -preflight")
    print("- opencommotion -run")
    print("- open http://127.0.0.1:8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
