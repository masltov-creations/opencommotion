"""Coherence assessment agent for OpenCommotion.

Evaluates whether generated text narration and visual strokes are
consistent with each other and the original prompt.  Uses the existing
LLM adapter infrastructure.  Gracefully degrades (returns ``ok``) when
no LLM provider is configured.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("opencommotion.coherence")

_COHERENCE_PROVIDER_ENV = "OPENCOMMOTION_LLM_PROVIDER"
_COHERENCE_TIMEOUT_ENV = "OPENCOMMOTION_LLM_TIMEOUT_S"
_VALID_PROVIDERS = {"ollama", "openai-compatible", "codex-cli", "openclaw-cli", "openclaw-openai"}


def _coherence_system_prompt() -> str:
    return (
        "You are a coherence quality gate for a multimodal live interface.\n"
        "You receive a user prompt, the narration text produced by the text agent, "
        "and a summary of the visual strokes produced by the visual agent.\n"
        "\n"
        "Your task is to assess whether the text and visuals are coherent — "
        "i.e. they describe the same scene, match the user intent, and would "
        "make sense when played together.\n"
        "\n"
        "Return ONLY a JSON object with this schema:\n"
        '{"ok": <bool>, "reason": "<short explanation>", "adjustments": [<optional list of short suggestions>]}\n'
        "\n"
        "Rules:\n"
        '1. If text and visuals are coherent, return {"ok": true, "reason": "coherent"}.\n'
        "2. If they are incoherent, set ok=false, explain why in reason, and suggest adjustments.\n"
        "3. Keep reason under 80 characters.\n"
        "4. Keep adjustments to at most 3 items, each under 60 characters.\n"
        "5. Return ONLY the JSON. No markdown fences, no prose.\n"
    )


def _summarize_strokes(strokes: list[dict]) -> str:
    """Build a concise summary of visual strokes for the coherence prompt."""
    kinds: list[str] = []
    entities: list[str] = []
    for stroke in strokes:
        kind = stroke.get("kind", "")
        if kind and kind not in kinds:
            kinds.append(kind)
        params = stroke.get("params", {})
        actor_type = params.get("actor_type")
        if actor_type:
            entities.append(str(actor_type))
        program = params.get("program", {})
        commands = program.get("commands", [])
        for cmd in commands[:10]:
            op = cmd.get("op", "")
            cmd_id = cmd.get("id", "")
            if op:
                entities.append(f"{op}:{cmd_id}" if cmd_id else op)
    summary = f"Stroke kinds: {', '.join(kinds[:8])}"
    if entities:
        summary += f"\nScene elements: {', '.join(entities[:12])}"
    return summary


def _parse_coherence_response(raw: str) -> dict:
    """Parse the LLM coherence response into a dict."""
    clean = raw.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        inner = [ln for ln in lines[1:] if not ln.startswith("```")]
        clean = "\n".join(inner).strip()
    brace_start = clean.find("{")
    if brace_start == -1:
        return {"ok": True, "reason": "unparseable response", "skipped": True}
    clean = clean[brace_start:]
    depth = 0
    end = 0
    for i, ch in enumerate(clean):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == 0:
        return {"ok": True, "reason": "unparseable response", "skipped": True}
    try:
        payload = json.loads(clean[:end])
    except json.JSONDecodeError:
        return {"ok": True, "reason": "unparseable response", "skipped": True}
    if not isinstance(payload, dict):
        return {"ok": True, "reason": "unparseable response", "skipped": True}
    return {
        "ok": bool(payload.get("ok", True)),
        "reason": str(payload.get("reason", ""))[:120],
        "adjustments": [str(a)[:80] for a in payload.get("adjustments", [])[:5]],
    }


def _timeout_s() -> float:
    raw = os.getenv(_COHERENCE_TIMEOUT_ENV, "10").strip()
    try:
        return min(max(float(raw), 0.5), 30.0)
    except ValueError:
        return 10.0


def assess_coherence(
    prompt: str,
    text: str,
    visual_strokes: list[dict],
) -> dict[str, Any]:
    """Assess coherence between generated text and visual strokes.

    Returns a dict with:
    - ``ok`` (bool): whether text and visuals are coherent
    - ``reason`` (str): short explanation
    - ``adjustments`` (list[str]): suggested fixes (if incoherent)
    - ``skipped`` (bool): set to True if coherence was not checked
    """
    provider = os.getenv(_COHERENCE_PROVIDER_ENV, "heuristic").strip().lower()
    if provider not in _VALID_PROVIDERS:
        return {"ok": True, "skipped": True, "reason": "coherence check not available in heuristic mode"}

    try:
        from services.agents.text.adapters import AdapterError, build_adapters  # noqa: PLC0415

        adapters_map = build_adapters(timeout_s=_timeout_s())
        adapter = adapters_map.get(provider)
        if adapter is None:
            logger.warning("Coherence: adapter '%s' not available", provider)
            return {"ok": True, "skipped": True, "reason": f"adapter {provider} unavailable"}

        stroke_summary = _summarize_strokes(visual_strokes)
        user_message = (
            f"User prompt: {prompt[:300]}\n\n"
            f"Text narration:\n{text[:500]}\n\n"
            f"Visual scene:\n{stroke_summary}\n"
        )

        system_prompt = _coherence_system_prompt()
        raw = (adapter.generate(user_message, system_prompt_override=system_prompt) or "").strip()
        if not raw:
            logger.info("Coherence: LLM returned empty response, assuming coherent")
            return {"ok": True, "skipped": True, "reason": "empty coherence response"}

        result = _parse_coherence_response(raw)
        if not result.get("ok"):
            logger.info(
                "Coherence: incoherent — %s (adjustments: %s)",
                result.get("reason"),
                result.get("adjustments"),
            )
        return result

    except AdapterError as exc:
        logger.warning("Coherence: adapter error: %s", exc)
        return {"ok": True, "skipped": True, "reason": f"adapter error: {exc}"}
    except Exception:  # noqa: BLE001
        logger.warning("Coherence: unexpected error, skipping check", exc_info=True)
        return {"ok": True, "skipped": True, "reason": "unexpected error"}


__all__ = ["assess_coherence"]
