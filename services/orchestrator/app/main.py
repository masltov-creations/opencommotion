from __future__ import annotations

import os
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from services.agents.text.worker import LLMEngineError, generate_text_response, llm_capabilities
from services.agents.voice.errors import VoiceEngineError
from services.agents.visual.worker import generate_visual_strokes
from services.agents.voice.tts.worker import synthesize_segments
from services.protocol import ProtocolValidationError, ProtocolValidator

protocol_validator = ProtocolValidator()
BRUSH_STROKE_SCHEMA = "types/brush_stroke_v1.schema.json"

REQUEST_COUNTER = Counter(
    "opencommotion_orchestrator_http_requests_total",
    "Total orchestrator HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "opencommotion_orchestrator_http_latency_seconds",
    "Orchestrator request latency",
    ["method", "path"],
    buckets=(0.01, 0.03, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
ORCHESTRATE_LATENCY = Histogram(
    "opencommotion_orchestrator_turn_latency_seconds",
    "Orchestrator turn latency",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0),
)

class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


class RuntimeConfigApplyRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


app = FastAPI(title="OpenCommotion Orchestrator", version="0.5.0")


@app.middleware("http")
async def metrics_middleware(request, call_next):  # type: ignore[override]
    started = perf_counter()
    response = await call_next(request)
    duration_s = perf_counter() - started
    REQUEST_COUNTER.labels(method=request.method, path=request.url.path, status=str(response.status_code)).inc()
    REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(duration_s)
    return response


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "orchestrator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/llm/capabilities")
def llm_runtime_capabilities() -> dict:
    return llm_capabilities(probe=True)


@app.post("/v1/runtime/config/apply")
def runtime_config_apply(req: RuntimeConfigApplyRequest) -> dict:
    applied: list[str] = []
    for key, value in req.values.items():
        clean_key = str(key).strip()
        if not clean_key.startswith("OPENCOMMOTION_"):
            continue
        os.environ[clean_key] = str(value).strip()
        applied.append(clean_key)
    return {"ok": True, "applied_keys": sorted(set(applied))}


@app.post("/v1/orchestrate")
def orchestrate(req: OrchestrateRequest) -> dict:
    if len(req.prompt) > 4000:
        raise HTTPException(status_code=422, detail={"error": "prompt_too_long", "max_chars": 4000})
    started = perf_counter()

    try:
        text = generate_text_response(req.prompt)
    except LLMEngineError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_engine_unavailable",
                "provider": exc.provider,
                "message": str(exc),
            },
        ) from exc
    strokes = generate_visual_strokes(req.prompt)
    try:
        voice = synthesize_segments(text)
    except VoiceEngineError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "tts_engine_unavailable",
                "engine": exc.engine,
                "message": str(exc),
            },
        ) from exc

    for idx, stroke in enumerate(strokes):
        try:
            protocol_validator.validate(BRUSH_STROKE_SCHEMA, stroke)
        except ProtocolValidationError as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "invalid_generated_stroke",
                    "index": idx,
                    "issues": exc.issues,
                },
            ) from exc

    duration_ms = max(
        [0]
        + [
            int(stroke.get("timing", {}).get("start_ms", 0))
            + int(stroke.get("timing", {}).get("duration_ms", 0))
            for stroke in strokes
        ]
        + [
            int(segment.get("start_ms", 0)) + int(segment.get("duration_ms", 0))
            for segment in voice.get("segments", [])
        ]
    )

    payload = {
        "session_id": req.session_id,
        "turn_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "visual_strokes": strokes,
        "voice": voice,
        "timeline": {"duration_ms": duration_ms},
    }
    ORCHESTRATE_LATENCY.observe(perf_counter() - started)
    return payload
