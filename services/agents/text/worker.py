from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from services.agents.text.adapters import AdapterError, build_adapters

LLM_PROVIDER_ENV = "OPENCOMMOTION_LLM_PROVIDER"
LLM_MODEL_ENV = "OPENCOMMOTION_LLM_MODEL"
LLM_ALLOW_FALLBACK_ENV = "OPENCOMMOTION_LLM_ALLOW_FALLBACK"
LLM_TIMEOUT_ENV = "OPENCOMMOTION_LLM_TIMEOUT_S"
PROMPT_REWRITE_ENABLED_ENV = "OPENCOMMOTION_PROMPT_REWRITE_ENABLED"
PROMPT_REWRITE_MAX_CHARS_ENV = "OPENCOMMOTION_PROMPT_REWRITE_MAX_CHARS"
NARRATION_CONTEXT_ENABLED_ENV = "OPENCOMMOTION_NARRATION_CONTEXT_ENABLED"

VALID_PROVIDERS = {
    "heuristic",
    "ollama",
    "openai-compatible",
    "codex-cli",
    "openclaw-cli",
    "openclaw-openai",
}
TRUE_VALUES = {"1", "true", "yes", "on"}
CLARIFICATION_PREFIXES = (
    "do you want",
    "would you like",
    "can you clarify",
    "which do you want",
    "should i",
    "single image",
)
NON_ACTIONABLE_HINTS = (
    "i can't",
    "i cannot",
    "can't do",
    "cannot do",
    "i'm unable",
    "unable to",
    "need more context",
    "need more detail",
    "need more details",
    "insufficient information",
)


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
    adapters = build_adapters(timeout_s=_timeout_s())
    heuristic = adapters["heuristic"]
    selected = adapters.get(provider, heuristic)
    invocation_context = _default_invocation_context()
    request_prompt = cleaned
    if _narration_context_enabled() and provider != "heuristic":
        request_prompt = _build_narration_request(cleaned, invocation_context)

    try:
        generated = selected.generate(request_prompt)
    except AdapterError as exc:
        if _allow_fallback():
            return _normalize_response(heuristic.generate(cleaned))
        raise LLMEngineError(provider=provider, message=str(exc)) from exc

    text = (generated or "").strip()
    if not text:
        if _allow_fallback():
            text = heuristic.generate(cleaned)
        else:
            raise LLMEngineError(provider=provider, message=f"{provider} returned an empty text response")
    elif _looks_like_clarification_request(text):
        if _allow_fallback():
            text = heuristic.generate(cleaned)
        else:
            text = f"{cleaned}. I will proceed with synchronized narration and visuals."
    elif _looks_non_actionable(text):
        if _allow_fallback():
            text = heuristic.generate(cleaned)
        else:
            text = f"{cleaned}. I will proceed with synchronized narration and visuals."

    return _normalize_response(text)


def rewrite_visual_prompt(prompt: str, *, context: str, first_turn: bool) -> tuple[str, dict[str, Any]]:
    cleaned = prompt.strip()
    provider = _selected_provider()
    metadata: dict[str, Any] = {
        "provider": provider,
        "scene_request": False,
        "warnings": [],
    }
    if not cleaned:
        return "", metadata
    if not _rewrite_enabled():
        metadata["warnings"] = ["prompt_rewrite_disabled"]
        return cleaned, metadata

    adapters = build_adapters(timeout_s=_timeout_s())
    selected = adapters.get(provider, adapters["heuristic"])
    request = _build_rewrite_request(prompt=cleaned, context=context, first_turn=first_turn)

    try:
        raw = (selected.generate(request) or "").strip()
    except AdapterError as exc:
        if _allow_fallback():
            metadata["warnings"] = [f"prompt_rewrite_provider_error:{provider}"]
            return cleaned, metadata
        raise LLMEngineError(provider=provider, message=str(exc)) from exc

    rewritten, scene_request = _parse_rewrite_response(raw=raw, fallback=cleaned)
    metadata["scene_request"] = scene_request
    if scene_request:
        metadata["warnings"] = [f"prompt_rewrite_scene_request:{provider}"]
    elif rewritten != cleaned:
        metadata["warnings"] = [f"prompt_rewrite_provider_applied:{provider}"]
    return rewritten, metadata


def llm_capabilities(probe: bool = False) -> dict[str, Any]:
    selected = _selected_provider()
    allow_fallback = _allow_fallback()
    timeout_s = _timeout_s()
    adapters = build_adapters(timeout_s=timeout_s)

    providers: dict[str, dict[str, Any]] = {}
    for provider in [
        "heuristic",
        "ollama",
        "openai-compatible",
        "codex-cli",
        "openclaw-cli",
        "openclaw-openai",
    ]:
        adapter = adapters[provider]
        try:
            capabilities = adapter.capabilities(probe=probe)
        except Exception as exc:  # noqa: BLE001
            capabilities = {"ready": False, "error": str(exc)}
        providers[provider] = capabilities

    selected_ready = bool(providers.get(selected, {}).get("ready"))
    effective_provider = selected if selected_ready else ("heuristic" if allow_fallback else selected)
    effective_ready = selected_ready or allow_fallback

    selected_model = str(providers.get(selected, {}).get("model", "")).strip()
    model = selected_model or os.getenv(LLM_MODEL_ENV, "").strip()

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
    raw = os.getenv(LLM_ALLOW_FALLBACK_ENV)
    if raw is None or not raw.strip():
        return True
    value = raw.strip().lower()
    return value in TRUE_VALUES


def _timeout_s() -> float:
    raw = os.getenv(LLM_TIMEOUT_ENV, "20").strip()
    try:
        value = float(raw)
    except ValueError:
        return 20.0
    return min(max(value, 0.5), 120.0)


def _normalize_response(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "OpenCommotion: I need a prompt to generate a synchronized text, voice, and visual response."
    if cleaned.lower().startswith("opencommotion:"):
        return cleaned
    return f"OpenCommotion: {cleaned}"


def _looks_like_clarification_request(text: str) -> bool:
    clean = text.strip().lower()
    if not clean:
        return False
    if "?" not in clean:
        return False
    return any(clean.startswith(prefix) or f" {prefix}" in clean for prefix in CLARIFICATION_PREFIXES)


def _looks_non_actionable(text: str) -> bool:
    clean = text.strip().lower()
    if not clean:
        return True
    return any(hint in clean for hint in NON_ACTIONABLE_HINTS)


def _narration_context_enabled() -> bool:
    raw = os.getenv(NARRATION_CONTEXT_ENABLED_ENV)
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() in TRUE_VALUES


def _default_invocation_context() -> str:
    return (
        "OpenCommotion orchestrator turn. "
        "The agent is already connected to a live visual runtime and must proceed without clarification loops. "
        "Return concise narration aligned to active visual rendering."
    )


def _build_narration_request(prompt: str, context: str) -> str:
    return (
        "You are OpenCommotion narration agent.\n"
        "Invocation context:\n"
        f"{context}\n\n"
        "Rules:\n"
        "- Do not ask clarifying questions.\n"
        "- Assume rendering tools are active.\n"
        "- Respond in 1-3 concise sentences.\n"
        "- Describe what is being shown and how it will animate.\n\n"
        "User prompt:\n"
        f"{prompt}"
    )


def _rewrite_enabled() -> bool:
    raw = os.getenv(PROMPT_REWRITE_ENABLED_ENV)
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() in TRUE_VALUES


def _rewrite_max_chars() -> int:
    raw = os.getenv(PROMPT_REWRITE_MAX_CHARS_ENV, "320").strip()
    try:
        value = int(raw)
    except ValueError:
        return 320
    return max(80, min(1200, value))


def _build_rewrite_request(prompt: str, context: str, first_turn: bool) -> str:
    example_block = (
        "Examples:\n"
        "- User: show 2 bouncing balls\n"
        "  VISUAL_PROMPT: draw two colored circles and animate both with bounce motion\n"
        "  SCENE_REQUEST: no\n"
        "- User: make the fish blooop\n"
        "  VISUAL_PROMPT: update fish behavior to bloop while keeping existing bowl and scene entities intact\n"
        "  SCENE_REQUEST: no\n"
    )
    mode_note = (
        "Turn mode: first turn. Build a complete initial scene with explicit actors and motion."
        if first_turn
        else "Turn mode: follow-up. Prefer small deterministic updates over full rebuilds."
    )
    return (
        "You are OpenCommotion prompt-planner. Rewrite user input into a concrete render/update prompt.\n"
        "Runtime contract:\n"
        "- The output will be executed by a visual scene compiler.\n"
        "- Use reusable primitives: actors, motion, fx, materials, camera, environment.\n"
        "- Keep nouns explicit (fish, bowl, ball, chart) and include counts when present.\n"
        "- For follow-ups, preserve continuity and mutate existing scene where possible.\n"
        "- Never ask questions; always provide executable visual intent.\n"
        f"{mode_note}\n\n"
        f"Scene context snapshot:\n{context}\n\n"
        f"{example_block}\n"
        f"User prompt:\n{prompt}\n\n"
        "Return EXACTLY two lines:\n"
        "VISUAL_PROMPT: <one line imperative prompt starting with draw/update/show>\n"
        "SCENE_REQUEST: <yes|no>\n"
    )


def _parse_rewrite_response(raw: str, fallback: str) -> tuple[str, bool]:
    clean = raw.strip().replace("\r", "")
    scene_request = False
    prompt_line = ""

    for line in clean.split("\n"):
        row = line.strip()
        if not row:
            continue
        lower = row.lower()
        if lower.startswith("scene_request:"):
            scene_request = "yes" in lower
            continue
        if lower.startswith("visual_prompt:"):
            prompt_line = row.split(":", 1)[1].strip()
            continue
        if not prompt_line:
            prompt_line = row

    candidate = (prompt_line or clean).strip()
    if candidate.lower().startswith("opencommotion:"):
        candidate = candidate.split(":", 1)[1].strip()
    candidate = candidate.strip("`\"' ")
    candidate = " ".join(candidate.split())
    if not candidate or _looks_like_clarification_request(candidate):
        return fallback, scene_request
    limit = _rewrite_max_chars()
    if len(candidate) > limit:
        candidate = candidate[:limit].rstrip()
    return candidate, scene_request


__all__ = ["LLMEngineError", "generate_text_response", "llm_capabilities", "rewrite_visual_prompt"]
