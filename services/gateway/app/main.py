from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.brush_engine.opencommotion_brush.compiler import compile_brush_batch


class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


class BrushCompileRequest(BaseModel):
    strokes: list[dict] = Field(default_factory=list)


class ArtifactSaveRequest(BaseModel):
    title: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    scene_entrypoint: str = "scene/entry.scene.json"
    assets: list[dict] = Field(default_factory=list)
    saved_by: str = "user"


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
        wrapped = {
            "event_type": "gateway.event",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": event,
        }
        await asyncio.gather(*(ws.send_json(wrapped) for ws in self.connections), return_exceptions=True)


app = FastAPI(title="OpenCommotion Gateway", version="0.2.0")
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
    patches = compile_brush_batch(req.strokes)
    return {"count": len(patches), "patches": patches}


@app.post("/v1/artifacts/save")
def save_artifact(req: ArtifactSaveRequest) -> dict:
    artifact = registry.save_artifact(
        {
            "title": req.title,
            "summary": req.summary,
            "tags": req.tags,
            "scene_entrypoint": req.scene_entrypoint,
            "assets": req.assets,
            "version": "1.0.0",
        },
        saved_by=req.saved_by,
    )
    return {"ok": True, "artifact": artifact}


@app.get("/v1/artifacts/search")
def search_artifacts(q: str = "") -> dict:
    return {"results": registry.search(q)}


@app.post("/v1/artifacts/recall/{artifact_id}")
def recall_artifact(artifact_id: str) -> dict:
    artifact = registry.get(artifact_id)
    return {"ok": artifact is not None, "artifact": artifact}


@app.post("/v1/orchestrate")
async def orchestrate(req: OrchestrateRequest) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "http://127.0.0.1:8001/v1/orchestrate",
            json={"session_id": req.session_id, "prompt": req.prompt},
        )
        resp.raise_for_status()
        result = resp.json()

    patches = compile_brush_batch(result.get("visual_strokes", []))
    event = {
        "session_id": result["session_id"],
        "turn_id": result["turn_id"],
        "text": result["text"],
        "voice": result["voice"],
        "visual_strokes": result["visual_strokes"],
        "visual_patches": patches,
    }
    await ws_manager.broadcast(event)
    return event
