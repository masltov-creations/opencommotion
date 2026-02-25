from __future__ import annotations

import httpx
import pytest

from services.agents.text import worker


def test_generate_text_response_uses_heuristic_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENCOMMOTION_LLM_PROVIDER", raising=False)
    text = worker.generate_text_response("moonwalk adoption chart")
    assert text.startswith("OpenCommotion:")
    assert "moonwalk adoption chart" in text


def test_generate_text_response_falls_back_when_remote_provider_fails(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENCOMMOTION_LLM_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("OPENCOMMOTION_LLM_TIMEOUT_S", "0.5")

    def fail_request(*args, **kwargs):  # noqa: ANN002, ANN003
        req = httpx.Request("POST", "http://127.0.0.1:1/v1/chat/completions")
        raise httpx.ConnectError("connection failed", request=req)

    monkeypatch.setattr(worker.httpx, "post", fail_request)

    text = worker.generate_text_response("ufo landing")
    assert text.startswith("OpenCommotion:")
    assert "ufo landing" in text


def test_generate_text_response_raises_without_fallback(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENCOMMOTION_LLM_ALLOW_FALLBACK", "false")
    monkeypatch.setenv("OPENCOMMOTION_LLM_TIMEOUT_S", "0.5")

    def fail_request(*args, **kwargs):  # noqa: ANN002, ANN003
        req = httpx.Request("POST", "http://127.0.0.1:1/v1/chat/completions")
        raise httpx.ConnectError("connection failed", request=req)

    monkeypatch.setattr(worker.httpx, "post", fail_request)

    with pytest.raises(worker.LLMEngineError):
        worker.generate_text_response("ufo landing")


def test_llm_capabilities_reports_selected_provider(monkeypatch) -> None:
    monkeypatch.setenv("OPENCOMMOTION_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OPENCOMMOTION_LLM_MODEL", "qwen2.5:7b-instruct")
    caps = worker.llm_capabilities(probe=False)
    assert caps["selected_provider"] == "ollama"
    assert "providers" in caps
    assert "ollama" in caps["providers"]
