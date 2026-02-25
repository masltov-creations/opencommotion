from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.agents.voice.errors import VoiceEngineError
from services.agents.voice.stt.worker import stt_capabilities, transcribe_audio
from services.agents.voice.tts.worker import synthesize_segments, tts_capabilities
from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.brush_engine.opencommotion_brush.compiler import compile_brush_batch
from services.protocol import ProtocolValidationError, ProtocolValidator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8001")
VOICE_AUDIO_ROOT = Path(
    os.getenv("OPENCOMMOTION_AUDIO_ROOT", str(PROJECT_ROOT / "data" / "audio"))
)
VOICE_AUDIO_ROOT.mkdir(parents=True, exist_ok=True)

protocol_validator = ProtocolValidator()
BRUSH_STROKE_SCHEMA = "types/brush_stroke_v1.schema.json"
SCENE_PATCH_SCHEMA = "types/scene_patch_v1.schema.json"
BASE_EVENT_SCHEMA = "events/base_event.schema.json"
ARTIFACT_BUNDLE_SCHEMA = "types/artifact_bundle_v1.schema.json"


class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


class BrushCompileRequest(BaseModel):
    strokes: list[dict] = Field(default_factory=list)


class ArtifactSaveRequest(BaseModel):
    artifact_id: str | None = None
    title: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    scene_entrypoint: str = "scene/entry.scene.json"
    assets: list[dict] = Field(default_factory=list)
    saved_by: str = "user"


class ArtifactToggleRequest(BaseModel):
    value: bool = True


class VoiceSynthesizeRequest(BaseModel):
    text: str
    voice: str = "opencommotion-local"


class WsManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        if not self.connections:
            return
        wrapped = _wrap_base_event(event)
        _validate_or_422(wrapped, BASE_EVENT_SCHEMA, context="ws.gateway.event")
        await asyncio.gather(*(ws.send_json(wrapped) for ws in self.connections), return_exceptions=True)


def _wrap_base_event(payload: dict) -> dict:
    return {
        "event_type": "gateway.event",
        "session_id": payload.get("session_id", "unknown-session"),
        "turn_id": payload.get("turn_id", str(uuid4())),
        "actor": "gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def _validate_or_422(payload: object, schema_path: str, context: str) -> None:
    try:
        protocol_validator.validate(schema_path=schema_path, payload=payload)
    except ProtocolValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "schema_validation_failed",
                "schema": schema_path,
                "context": context,
                "issues": exc.issues,
            },
        ) from exc


def _validate_many(payloads: list[dict], schema_path: str, context_prefix: str) -> None:
    for idx, payload in enumerate(payloads):
        _validate_or_422(payload, schema_path=schema_path, context=f"{context_prefix}[{idx}]")


def _timeline_duration_ms(visual_strokes: list[dict], voice: dict) -> int:
    visual_end = 0
    for stroke in visual_strokes:
        timing = stroke.get("timing", {})
        start_ms = int(timing.get("start_ms", 0))
        duration_ms = int(timing.get("duration_ms", 0))
        visual_end = max(visual_end, start_ms + duration_ms)

    voice_end = 0
    for segment in voice.get("segments", []):
        start_ms = int(segment.get("start_ms", 0))
        duration_ms = int(segment.get("duration_ms", 0))
        voice_end = max(voice_end, start_ms + duration_ms)

    return max(visual_end, voice_end, 0)


def _validate_orchestrator_payload(result: dict) -> None:
    required = {"session_id", "turn_id", "text", "visual_strokes", "voice"}
    missing = sorted(required - set(result))
    if missing:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "orchestrator_contract_error",
                "missing_fields": missing,
            },
        )

    visual_strokes = result.get("visual_strokes", [])
    if not isinstance(visual_strokes, list):
        raise HTTPException(
            status_code=502,
            detail={"error": "orchestrator_contract_error", "message": "visual_strokes must be a list"},
        )
    _validate_many(visual_strokes, BRUSH_STROKE_SCHEMA, context_prefix="orchestrator.visual_strokes")


app = FastAPI(title="OpenCommotion Gateway", version="0.5.0")
app.mount("/v1/audio", StaticFiles(directory=str(VOICE_AUDIO_ROOT)), name="opencommotion-audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = ArtifactRegistry()
ws_manager = WsManager()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.websocket("/v1/events/ws")
async def events_ws(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.post("/v1/brush/compile")
def compile_brush(req: BrushCompileRequest) -> dict:
    _validate_many(req.strokes, BRUSH_STROKE_SCHEMA, context_prefix="compile.strokes")
    patches = compile_brush_batch(req.strokes)
    _validate_many(patches, SCENE_PATCH_SCHEMA, context_prefix="compile.patches")
    return {"count": len(patches), "patches": patches}


@app.post("/v1/voice/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    hint: str = Form(default=""),
) -> dict:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail={"error": "empty_audio_payload"})

    try:
        transcript = transcribe_audio(audio_bytes, hint=hint)
    except VoiceEngineError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "stt_engine_unavailable",
                "engine": exc.engine,
                "message": str(exc),
            },
        ) from exc
    return {"ok": True, "transcript": transcript}


@app.post("/v1/voice/synthesize")
def synthesize_voice(req: VoiceSynthesizeRequest) -> dict:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail={"error": "text_required"})
    try:
        voice = synthesize_segments(req.text, voice=req.voice)
    except VoiceEngineError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "tts_engine_unavailable",
                "engine": exc.engine,
                "message": str(exc),
            },
        ) from exc
    return {"ok": True, "voice": voice}


@app.get("/v1/voice/capabilities")
def voice_capabilities() -> dict:
    return {
        "stt": stt_capabilities(),
        "tts": tts_capabilities(),
    }


@app.get("/v1/runtime/capabilities")
async def runtime_capabilities() -> dict:
    llm_payload: dict = {
        "selected_provider": "unknown",
        "effective_ready": False,
        "error": "orchestrator_unreachable",
    }
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/v1/llm/capabilities")
        response.raise_for_status()
        llm_payload = response.json()
    except httpx.HTTPError as exc:
        llm_payload["message"] = str(exc)

    return {
        "llm": llm_payload,
        "voice": {
            "stt": stt_capabilities(),
            "tts": tts_capabilities(),
        },
    }


@app.post("/v1/artifacts/save")
async def save_artifact(req: ArtifactSaveRequest) -> dict:
    artifact_id = req.artifact_id or str(uuid4())
    bundle = {
        "artifact_id": artifact_id,
        "title": req.title,
        "summary": req.summary,
        "tags": req.tags,
        "scene_entrypoint": req.scene_entrypoint,
        "assets": req.assets,
        "version": "1.0.0",
    }
    _validate_or_422(bundle, ARTIFACT_BUNDLE_SCHEMA, context="artifact.save.bundle")

    artifact = registry.save_artifact(bundle, saved_by=req.saved_by)

    event = {
        "session_id": "artifact-memory",
        "turn_id": artifact["artifact_id"],
        "artifact": artifact,
    }
    await ws_manager.broadcast(event)

    return {"ok": True, "artifact": artifact}


@app.get("/v1/artifacts/search")
def search_artifacts(q: str = "", mode: str = "lexical", limit: int = 30) -> dict:
    capped_limit = max(1, min(limit, 100))
    return {"results": registry.search(query=q, mode=mode, limit=capped_limit)}


@app.post("/v1/artifacts/recall/{artifact_id}")
def recall_artifact(artifact_id: str) -> dict:
    artifact = registry.get(artifact_id)
    return {"ok": artifact is not None, "artifact": artifact}


@app.post("/v1/artifacts/pin/{artifact_id}")
def pin_artifact(artifact_id: str, req: ArtifactToggleRequest) -> dict:
    ok = registry.pin(artifact_id=artifact_id, value=req.value)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "artifact_not_found"})
    return {"ok": True, "artifact_id": artifact_id, "pinned": req.value}


@app.post("/v1/artifacts/archive/{artifact_id}")
def archive_artifact(artifact_id: str, req: ArtifactToggleRequest) -> dict:
    ok = registry.archive(artifact_id=artifact_id, value=req.value)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "artifact_not_found"})
    return {"ok": True, "artifact_id": artifact_id, "archived": req.value}


@app.post("/v1/orchestrate")
async def orchestrate(req: OrchestrateRequest) -> dict:
    if len(req.prompt) > 4000:
        raise HTTPException(status_code=422, detail={"error": "prompt_too_long", "max_chars": 4000})

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/v1/orchestrate",
                json={"session_id": req.session_id, "prompt": req.prompt},
            )
        resp.raise_for_status()
        result = resp.json()
    except httpx.HTTPStatusError as exc:
        details: dict | str
        try:
            payload = exc.response.json()
            details = payload.get("detail", payload)
        except ValueError:
            details = {
                "error": "orchestrator_http_error",
                "status_code": exc.response.status_code,
                "message": exc.response.text,
            }
        raise HTTPException(status_code=exc.response.status_code, detail=details) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "orchestrator_unreachable", "message": str(exc)},
        ) from exc

    _validate_orchestrator_payload(result)

    visual_strokes = result.get("visual_strokes", [])
    patches = compile_brush_batch(visual_strokes)
    _validate_many(patches, SCENE_PATCH_SCHEMA, context_prefix="orchestrate.visual_patches")

    voice = result.get("voice", {})
    event = {
        "session_id": result["session_id"],
        "turn_id": result["turn_id"],
        "timestamp": result.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "text": result["text"],
        "voice": voice,
        "visual_strokes": visual_strokes,
        "visual_patches": patches,
        "timeline": {
            "duration_ms": _timeline_duration_ms(visual_strokes=visual_strokes, voice=voice),
        },
    }
    await ws_manager.broadcast(event)
    return event
