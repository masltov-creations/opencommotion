from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

LLM_PROVIDER_ENV = "OPENCOMMOTION_LLM_PROVIDER"
LLM_MODEL_ENV = "OPENCOMMOTION_LLM_MODEL"
LLM_SYSTEM_PROMPT_ENV = "OPENCOMMOTION_LLM_SYSTEM_PROMPT"
LLM_ALLOW_FALLBACK_ENV = "OPENCOMMOTION_LLM_ALLOW_FALLBACK"
LLM_TIMEOUT_ENV = "OPENCOMMOTION_LLM_TIMEOUT_S"

OLLAMA_URL_ENV = "OPENCOMMOTION_OLLAMA_URL"
OPENAI_BASE_URL_ENV = "OPENCOMMOTION_OPENAI_BASE_URL"
OPENAI_API_KEY_ENV = "OPENCOMMOTION_OPENAI_API_KEY"

VALID_PROVIDERS = {"heuristic", "ollama", "openai-compatible"}
TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass
class LLMEngineError(RuntimeError):
    provider: str
    message: str

    def __str__(self) -> str:
        return self.message


def generate_text_response(prompt: str) -> str:
    cleaned = prompt.strip()
    if not cleaned:
        return "OpenCommotion: I need a prompt to generate a synchronized text, voice, and visual response."

    provider = _selected_provider()
    try:
        if provider == "ollama":
            generated = _generate_with_ollama(cleaned)
        elif provider == "openai-compatible":
            generated = _generate_with_openai_compatible(cleaned)
        else:
            generated = _heuristic_text(cleaned)
    except LLMEngineError:
        if _allow_fallback():
            return _normalize_response(_heuristic_text(cleaned))
        raise

    text = (generated or "").strip()
    if not text:
        if _allow_fallback():
            text = _heuristic_text(cleaned)
        else:
            raise LLMEngineError(provider=provider, message=f"{provider} returned an empty text response")

    return _normalize_response(text)


def llm_capabilities(probe: bool = False) -> dict[str, Any]:
    selected = _selected_provider()
    allow_fallback = _allow_fallback()
    timeout_s = _timeout_s()
    model = _model_for_provider(selected)

    providers: dict[str, dict[str, Any]] = {
        "heuristic": {"ready": True, "note": "Always available built-in fallback"},
        "ollama": {
            "ready": bool(model),
            "base_url": _ollama_url(),
            "model": _model_for_provider("ollama"),
            "reachable": None,
            "model_available": None,
            "error": "",
        },
        "openai-compatible": {
            "ready": bool(model),
            "base_url": _openai_base_url(),
            "model": _model_for_provider("openai-compatible"),
            "api_key_set": bool(os.getenv(OPENAI_API_KEY_ENV, "").strip()),
            "reachable": None,
            "model_available": None,
            "error": "",
        },
    }

    if probe:
        providers["ollama"].update(_probe_ollama())
        providers["openai-compatible"].update(_probe_openai_compatible())

    selected_ready = bool(providers.get(selected, {}).get("ready"))
    effective_provider = selected if selected_ready else ("heuristic" if allow_fallback else selected)
    effective_ready = selected_ready or allow_fallback

    return {
        "selected_provider": selected,
        "effective_provider": effective_provider,
        "active_provider_ready": selected_ready,
        "effective_ready": effective_ready,
        "allow_fallback": allow_fallback,
        "timeout_s": timeout_s,
        "model": model,
        "providers": providers,
    }


def _selected_provider() -> str:
    selected = os.getenv(LLM_PROVIDER_ENV, "heuristic").strip().lower()
    if selected not in VALID_PROVIDERS:
        return "heuristic"
    return selected


def _allow_fallback() -> bool:
    value = os.getenv(LLM_ALLOW_FALLBACK_ENV, "true").strip().lower()
    return value in TRUE_VALUES


def _timeout_s() -> float:
    raw = os.getenv(LLM_TIMEOUT_ENV, "20").strip()
    try:
        value = float(raw)
    except ValueError:
        return 20.0
    return min(max(value, 0.5), 120.0)


def _model_for_provider(provider: str) -> str:
    configured = os.getenv(LLM_MODEL_ENV, "").strip()
    if configured:
        return configured
    if provider == "ollama":
        return "qwen2.5:7b-instruct"
    if provider == "openai-compatible":
        return "Qwen/Qwen2.5-7B-Instruct"
    return ""


def _system_prompt() -> str:
    configured = os.getenv(LLM_SYSTEM_PROMPT_ENV, "").strip()
    if configured:
        return configured
    return (
        "You are OpenCommotion's narration engine. "
        "Produce concise, clear narration suitable for synchronized voice and visual playback."
    )


def _ollama_url() -> str:
    return os.getenv(OLLAMA_URL_ENV, "http://127.0.0.1:11434").rstrip("/")


def _openai_base_url() -> str:
    return os.getenv(OPENAI_BASE_URL_ENV, "http://127.0.0.1:8002/v1").rstrip("/")


def _generate_with_ollama(prompt: str) -> str:
    model = _model_for_provider("ollama")
    if not model:
        raise LLMEngineError(provider="ollama", message=f"Missing {LLM_MODEL_ENV} for ollama provider")
    url = f"{_ollama_url()}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "system": _system_prompt(),
        "stream": False,
    }
    try:
        res = httpx.post(url, json=payload, timeout=_timeout_s())
        res.raise_for_status()
        data = res.json()
    except Exception as exc:
        raise LLMEngineError(provider="ollama", message=f"Ollama request failed: {exc}") from exc
    return str(data.get("response", "")).strip()


def _generate_with_openai_compatible(prompt: str) -> str:
    model = _model_for_provider("openai-compatible")
    if not model:
        raise LLMEngineError(
            provider="openai-compatible",
            message=f"Missing {LLM_MODEL_ENV} for openai-compatible provider",
        )

    headers: dict[str, str] = {"content-type": "application/json"}
    api_key = os.getenv(OPENAI_API_KEY_ENV, "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": prompt},
        ],
    }
    url = f"{_openai_base_url()}/chat/completions"

    try:
        res = httpx.post(url, json=payload, headers=headers, timeout=_timeout_s())
        res.raise_for_status()
        data = res.json()
    except Exception as exc:
        raise LLMEngineError(
            provider="openai-compatible",
            message=f"OpenAI-compatible request failed: {exc}",
        ) from exc

    return _extract_chat_content(data)


def _extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
        return " ".join(chunks).strip()
    return ""


def _probe_ollama() -> dict[str, Any]:
    url = f"{_ollama_url()}/api/tags"
    model = _model_for_provider("ollama")
    try:
        res = httpx.get(url, timeout=min(_timeout_s(), 5.0))
        res.raise_for_status()
        data = res.json()
        models = data.get("models", [])
        available = False
        if isinstance(models, list):
            for item in models:
                if not isinstance(item, dict):
                    continue
                if str(item.get("name", "")).strip() == model:
                    available = True
                    break
        return {
            "ready": available,
            "reachable": True,
            "model_available": available,
            "error": "" if available else f"model '{model}' not found in ollama list",
        }
    except Exception as exc:
        return {
            "ready": False,
            "reachable": False,
            "model_available": False,
            "error": str(exc),
        }


def _probe_openai_compatible() -> dict[str, Any]:
    model = _model_for_provider("openai-compatible")
    url = f"{_openai_base_url()}/models"
    headers: dict[str, str] = {}
    api_key = os.getenv(OPENAI_API_KEY_ENV, "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    try:
        res = httpx.get(url, headers=headers, timeout=min(_timeout_s(), 5.0))
        res.raise_for_status()
        data = res.json()
        model_data = data.get("data", [])
        available = False
        if isinstance(model_data, list):
            for item in model_data:
                if not isinstance(item, dict):
                    continue
                if str(item.get("id", "")).strip() == model:
                    available = True
                    break
        return {
            "ready": available,
            "reachable": True,
            "model_available": available,
            "error": "" if available else f"model '{model}' not found in /models list",
        }
    except Exception as exc:
        return {
            "ready": False,
            "reachable": False,
            "model_available": False,
            "error": str(exc),
        }


def _heuristic_text(prompt: str) -> str:
    return f"{prompt}. I will explain this with concise narration and synchronized visuals."


def _normalize_response(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "OpenCommotion: I need a prompt to generate a synchronized text, voice, and visual response."
    if cleaned.lower().startswith("opencommotion:"):
        return cleaned
    return f"OpenCommotion: {cleaned}"


__all__ = ["LLMEngineError", "generate_text_response", "llm_capabilities"]
