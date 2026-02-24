from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel

from services.agents.text.worker import generate_text_response
from services.agents.visual.worker import generate_visual_strokes
from services.agents.voice.tts.worker import synthesize_segments


class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


app = FastAPI(title="OpenCommotion Orchestrator", version="0.2.0")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "orchestrator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/v1/orchestrate")
def orchestrate(req: OrchestrateRequest) -> dict:
    text = generate_text_response(req.prompt)
    strokes = generate_visual_strokes(req.prompt)
    voice = synthesize_segments(text)

    return {
        "session_id": req.session_id,
        "turn_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "visual_strokes": strokes,
        "voice": voice,
    }
