from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.agents.text.worker import LLMEngineError, generate_text_response, llm_capabilities
from services.agents.voice.errors import VoiceEngineError
from services.agents.visual.worker import generate_visual_strokes
from services.agents.voice.tts.worker import synthesize_segments
from services.protocol import ProtocolValidationError, ProtocolValidator

protocol_validator = ProtocolValidator()
BRUSH_STROKE_SCHEMA = "types/brush_stroke_v1.schema.json"

class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


app = FastAPI(title="OpenCommotion Orchestrator", version="0.5.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "orchestrator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/v1/llm/capabilities")
def llm_runtime_capabilities() -> dict:
    return llm_capabilities(probe=True)


@app.post("/v1/orchestrate")
def orchestrate(req: OrchestrateRequest) -> dict:
    if len(req.prompt) > 4000:
        raise HTTPException(status_code=422, detail={"error": "prompt_too_long", "max_chars": 4000})

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

    return {
        "session_id": req.session_id,
        "turn_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "visual_strokes": strokes,
        "voice": voice,
        "timeline": {"duration_ms": duration_ms},
    }
