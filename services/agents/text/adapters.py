from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import httpx

LLM_MODEL_ENV = "OPENCOMMOTION_LLM_MODEL"
LLM_SYSTEM_PROMPT_ENV = "OPENCOMMOTION_LLM_SYSTEM_PROMPT"
OLLAMA_URL_ENV = "OPENCOMMOTION_OLLAMA_URL"
OPENAI_BASE_URL_ENV = "OPENCOMMOTION_OPENAI_BASE_URL"
OPENAI_API_KEY_ENV = "OPENCOMMOTION_OPENAI_API_KEY"

CODEX_BIN_ENV = "OPENCOMMOTION_CODEX_BIN"
CODEX_MODEL_ENV = "OPENCOMMOTION_CODEX_MODEL"
CODEX_TIMEOUT_ENV = "OPENCOMMOTION_CODEX_TIMEOUT_S"

OPENCLAW_BIN_ENV = "OPENCOMMOTION_OPENCLAW_BIN"
OPENCLAW_TIMEOUT_ENV = "OPENCOMMOTION_OPENCLAW_TIMEOUT_S"
OPENCLAW_SESSION_PREFIX_ENV = "OPENCOMMOTION_OPENCLAW_SESSION_PREFIX"

OPENCLAW_OPENAI_BASE_URL_ENV = "OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL"
OPENCLAW_OPENAI_API_KEY_ENV = "OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY"
OPENCLAW_OPENAI_MODEL_ENV = "OPENCOMMOTION_OPENCLAW_OPENAI_MODEL"

CLI_RETRIES_ENV = "OPENCOMMOTION_LLM_CLI_RETRIES"


@dataclass
class AdapterError(RuntimeError):
    provider: str
    message: str

    def __str__(self) -> str:
        return self.message


class TextProviderAdapter(Protocol):
    name: str

    def generate(self, prompt: str) -> str:
        ...

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        ...


def extract_codex_agent_message(stream: str) -> str:
    best = ""
    for raw in stream.splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            best = text.strip()
    return best


def extract_openclaw_text(payload: str) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    rows = data.get("payloads")
    if not isinstance(rows, list):
        return ""
    parts: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts).strip()


def _timeout_s(value: str, default: float) -> float:
    raw = os.getenv(value, str(default)).strip()
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return min(max(parsed, 0.5), 180.0)


def _cli_retries() -> int:
    raw = os.getenv(CLI_RETRIES_ENV, "1").strip()
    try:
        parsed = int(raw)
    except ValueError:
        return 1
    return min(max(parsed, 1), 5)


def _run_cli(command: list[str], timeout_s: float, retries: int, provider: str) -> subprocess.CompletedProcess[str]:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(
                provider=provider,
                message=f"{provider} timed out after {timeout_s:.1f}s",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= retries:
                break
            time.sleep(min(0.6 * attempt, 1.5))
            continue
        if completed.returncode == 0:
            return completed
        if attempt >= retries:
            stderr = (completed.stderr or "").strip()
            raise AdapterError(
                provider=provider,
                message=f"{provider} command failed with code {completed.returncode}: {stderr or 'no stderr'}",
            )
        time.sleep(min(0.6 * attempt, 1.5))

    if last_exc is None:
        raise AdapterError(provider=provider, message=f"{provider} command failed")
    raise AdapterError(provider=provider, message=f"{provider} command error: {last_exc}")


def _system_prompt() -> str:
    configured = os.getenv(LLM_SYSTEM_PROMPT_ENV, "").strip()
    if configured:
        return configured
    return (
        "You are OpenCommotion's narration engine for a live visual interface. "
        "Assume the runtime has drawing and motion primitives available (shapes, paths, actors, timing, animation). "
        "Always proceed with a direct narrated response; do not ask clarification questions unless the user explicitly asks for options. "
        "Keep output concise, concrete, and suitable for synchronized voice and visual playback."
    )


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
        parts: list[str] = []
        for row in content:
            if not isinstance(row, dict):
                continue
            text = row.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return " ".join(parts).strip()
    return ""


def _model(default: str = "") -> str:
    configured = os.getenv(LLM_MODEL_ENV, "").strip()
    return configured or default


def _provider_probe_version(command: list[str], timeout_s: float) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    out = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode == 0:
        return True, out
    return False, out or f"exit={completed.returncode}"


@dataclass
class HeuristicAdapter:
    name: str = "heuristic"

    def generate(self, prompt: str) -> str:
        return f"{prompt}. I will explain this with concise narration and synchronized visuals."

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        return {"ready": True, "note": "Always available built-in fallback"}


@dataclass
class OllamaAdapter:
    timeout_s: float
    name: str = "ollama"

    def _url(self) -> str:
        return os.getenv(OLLAMA_URL_ENV, "http://127.0.0.1:11434").rstrip("/")

    def _model(self) -> str:
        return _model("qwen2.5:7b-instruct")

    def generate(self, prompt: str) -> str:
        model = self._model()
        if not model:
            raise AdapterError(provider=self.name, message=f"Missing {LLM_MODEL_ENV} for ollama provider")
        payload = {
            "model": model,
            "prompt": prompt,
            "system": _system_prompt(),
            "stream": False,
        }
        try:
            res = httpx.post(f"{self._url()}/api/generate", json=payload, timeout=self.timeout_s)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(provider=self.name, message=f"Ollama request failed: {exc}") from exc
        return str(data.get("response", "")).strip()

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        model = self._model()
        state = {
            "ready": bool(model),
            "base_url": self._url(),
            "model": model,
            "reachable": None,
            "model_available": None,
            "error": "",
        }
        if not probe:
            return state
        try:
            res = httpx.get(f"{self._url()}/api/tags", timeout=min(self.timeout_s, 5.0))
            res.raise_for_status()
            payload = res.json()
            available = False
            rows = payload.get("models", [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and str(row.get("name", "")).strip() == model:
                        available = True
                        break
            state["reachable"] = True
            state["model_available"] = available
            state["ready"] = bool(model) and available
            state["error"] = "" if available else f"model '{model}' not found in ollama list"
        except Exception as exc:  # noqa: BLE001
            state["ready"] = False
            state["reachable"] = False
            state["model_available"] = False
            state["error"] = str(exc)
        return state


@dataclass
class OpenAICompatibleAdapter:
    timeout_s: float
    name: str = "openai-compatible"

    def _base_url(self) -> str:
        return os.getenv(OPENAI_BASE_URL_ENV, "http://127.0.0.1:8002/v1").rstrip("/")

    def _api_key(self) -> str:
        return os.getenv(OPENAI_API_KEY_ENV, "").strip()

    def _model(self) -> str:
        return _model("Qwen/Qwen2.5-7B-Instruct")

    def generate(self, prompt: str) -> str:
        model = self._model()
        if not model:
            raise AdapterError(provider=self.name, message=f"Missing {LLM_MODEL_ENV} for {self.name} provider")
        headers: dict[str, str] = {"content-type": "application/json"}
        api_key = self._api_key()
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
        try:
            res = httpx.post(f"{self._base_url()}/chat/completions", json=payload, headers=headers, timeout=self.timeout_s)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(provider=self.name, message=f"OpenAI-compatible request failed: {exc}") from exc
        return _extract_chat_content(data)

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        model = self._model()
        state = {
            "ready": bool(model),
            "base_url": self._base_url(),
            "model": model,
            "api_key_set": bool(self._api_key()),
            "reachable": None,
            "model_available": None,
            "error": "",
        }
        if not probe:
            return state
        headers: dict[str, str] = {}
        api_key = self._api_key()
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        try:
            res = httpx.get(f"{self._base_url()}/models", headers=headers, timeout=min(self.timeout_s, 5.0))
            res.raise_for_status()
            payload = res.json()
            available = False
            rows = payload.get("data", [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and str(row.get("id", "")).strip() == model:
                        available = True
                        break
            state["ready"] = bool(model) and available
            state["reachable"] = True
            state["model_available"] = available
            state["error"] = "" if available else f"model '{model}' not found in /models list"
        except Exception as exc:  # noqa: BLE001
            state["ready"] = False
            state["reachable"] = False
            state["model_available"] = False
            state["error"] = str(exc)
        return state


@dataclass
class CodexCliAdapter:
    timeout_s: float
    name: str = "codex-cli"

    def _bin(self) -> str:
        return os.getenv(CODEX_BIN_ENV, "codex").strip() or "codex"

    def _resolved_bin(self) -> str | None:
        configured = self._bin()
        return shutil.which(configured) or configured if configured.startswith("/") else shutil.which(configured)

    def _model(self) -> str:
        return os.getenv(CODEX_MODEL_ENV, "").strip()

    def _timeout(self) -> float:
        return _timeout_s(CODEX_TIMEOUT_ENV, self.timeout_s)

    def generate(self, prompt: str) -> str:
        binary = self._resolved_bin()
        if not binary:
            raise AdapterError(provider=self.name, message=f"{self._bin()} is not installed or not in PATH")
        command = [binary, "exec", "--ephemeral", "--json"]
        model = self._model()
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        completed = _run_cli(
            command=command,
            timeout_s=self._timeout(),
            retries=_cli_retries(),
            provider=self.name,
        )
        text = extract_codex_agent_message(completed.stdout or "")
        if text:
            return text
        raise AdapterError(provider=self.name, message="codex-cli returned no agent_message content")

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        binary = self._resolved_bin()
        state = {
            "ready": binary is not None,
            "binary": self._bin(),
            "resolved_binary": binary,
            "model": self._model(),
            "version": "",
            "error": "" if binary else "binary_not_found",
        }
        if probe and binary:
            ok, detail = _provider_probe_version([binary, "--version"], timeout_s=min(self._timeout(), 5.0))
            if ok:
                state["version"] = detail
            else:
                state["ready"] = False
                state["error"] = detail
        return state


@dataclass
class OpenClawCliAdapter:
    timeout_s: float
    name: str = "openclaw-cli"

    def _bin(self) -> str:
        return os.getenv(OPENCLAW_BIN_ENV, "openclaw").strip() or "openclaw"

    def _resolved_bin(self) -> str | None:
        configured = self._bin()
        return shutil.which(configured) or configured if configured.startswith("/") else shutil.which(configured)

    def _session_prefix(self) -> str:
        return os.getenv(OPENCLAW_SESSION_PREFIX_ENV, "opencommotion-turn").strip() or "opencommotion-turn"

    def _timeout(self) -> float:
        return _timeout_s(OPENCLAW_TIMEOUT_ENV, self.timeout_s)

    def generate(self, prompt: str) -> str:
        binary = self._resolved_bin()
        if not binary:
            raise AdapterError(provider=self.name, message=f"{self._bin()} is not installed or not in PATH")
        session_id = f"{self._session_prefix()}-{uuid4()}"
        command = [
            binary,
            "agent",
            "--local",
            "--json",
            "--session-id",
            session_id,
            "--message",
            prompt,
        ]
        completed = _run_cli(
            command=command,
            timeout_s=self._timeout(),
            retries=_cli_retries(),
            provider=self.name,
        )
        text = extract_openclaw_text(completed.stdout or "")
        if text:
            return text
        raise AdapterError(provider=self.name, message="openclaw-cli returned no payload text")

    def capabilities(self, probe: bool = False) -> dict[str, Any]:
        binary = self._resolved_bin()
        state = {
            "ready": binary is not None,
            "binary": self._bin(),
            "resolved_binary": binary,
            "version": "",
            "session_prefix": self._session_prefix(),
            "error": "" if binary else "binary_not_found",
        }
        if probe and binary:
            ok, detail = _provider_probe_version([binary, "--version"], timeout_s=min(self._timeout(), 5.0))
            if ok:
                state["version"] = detail
            else:
                state["ready"] = False
                state["error"] = detail
        return state


@dataclass
class OpenClawOpenAIAdapter(OpenAICompatibleAdapter):
    name: str = "openclaw-openai"

    def _base_url(self) -> str:
        return os.getenv(OPENCLAW_OPENAI_BASE_URL_ENV, os.getenv(OPENAI_BASE_URL_ENV, "http://127.0.0.1:8002/v1")).rstrip("/")

    def _api_key(self) -> str:
        return os.getenv(OPENCLAW_OPENAI_API_KEY_ENV, os.getenv(OPENAI_API_KEY_ENV, "")).strip()

    def _model(self) -> str:
        configured = os.getenv(OPENCLAW_OPENAI_MODEL_ENV, "").strip()
        if configured:
            return configured
        return _model("Qwen/Qwen2.5-7B-Instruct")


def build_adapters(timeout_s: float) -> dict[str, TextProviderAdapter]:
    return {
        "heuristic": HeuristicAdapter(),
        "ollama": OllamaAdapter(timeout_s=timeout_s),
        "openai-compatible": OpenAICompatibleAdapter(timeout_s=timeout_s),
        "codex-cli": CodexCliAdapter(timeout_s=timeout_s),
        "openclaw-cli": OpenClawCliAdapter(timeout_s=timeout_s),
        "openclaw-openai": OpenClawOpenAIAdapter(timeout_s=timeout_s),
    }


__all__ = [
    "AdapterError",
    "TextProviderAdapter",
    "build_adapters",
    "extract_codex_agent_message",
    "extract_openclaw_text",
]
