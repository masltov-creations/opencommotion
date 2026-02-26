from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.agent_runtime.manager import AgentRunManager
from services.agents.visual.quality import evaluate_market_growth_scene
from services.agents.voice.errors import VoiceEngineError
from services.agents.voice.stt.worker import stt_capabilities, transcribe_audio
from services.agents.voice.tts.worker import synthesize_segments, tts_capabilities
from services.artifact_registry.opencommotion_artifacts.registry import ArtifactRegistry
from services.brush_engine.opencommotion_brush.compiler import compile_brush_batch
from services.config.runtime_config import (
    EDITABLE_KEYS,
    ENV_PATH,
    masked_state,
    normalized_editable,
    parse_env,
    validate_setup,
    write_env,
)
from services.gateway.app.metrics import (
    metrics_response,
    record_http,
    record_orchestrate,
    record_provider_error,
    set_run_metrics,
)
from services.gateway.app.security import enforce_http_auth, get_security_state, websocket_authorized
from services.protocol import ProtocolValidationError, ProtocolValidator
from services.versioning import project_version

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8001")
AGENT_RUN_DB_PATH = Path(
    os.getenv("OPENCOMMOTION_AGENT_RUN_DB_PATH", str(PROJECT_ROOT / "runtime" / "agent-runs" / "agent_manager.db"))
)
ORCHESTRATOR_REQUEST_TIMEOUT_S = float(os.getenv("OPENCOMMOTION_ORCHESTRATOR_TIMEOUT_S", "20"))
ORCHESTRATOR_REQUEST_MAX_ATTEMPTS = max(1, int(os.getenv("OPENCOMMOTION_ORCHESTRATOR_MAX_ATTEMPTS", "3")))
ORCHESTRATOR_RETRY_BASE_DELAY_S = max(0.05, float(os.getenv("OPENCOMMOTION_ORCHESTRATOR_RETRY_BASE_DELAY_S", "0.2")))


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _looks_like_market_growth_prompt(prompt: str) -> bool:
    p = str(prompt or "").lower()
    keys = ("market growth", "segmented attach", "attach", "presentation", "graph", "timeline", "increase")
    hits = sum(1 for key in keys if key in p)
    return hits >= 2


def _resolve_runtime_path(env_key: str, default_path: Path) -> Path:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return default_path

    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if _truthy(os.getenv("OPENCOMMOTION_ALLOW_EXTERNAL_PATHS")):
        return candidate

    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
        return candidate
    except ValueError:
        return default_path


VOICE_AUDIO_ROOT = _resolve_runtime_path("OPENCOMMOTION_AUDIO_ROOT", PROJECT_ROOT / "data" / "audio")
UI_DIST_ROOT = _resolve_runtime_path("OPENCOMMOTION_UI_DIST_ROOT", PROJECT_ROOT / "apps" / "ui" / "dist")
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


class SetupValidateRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


class SetupStateRequest(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


class AgentRunCreateRequest(BaseModel):
    label: str = "default"
    session_id: str | None = None
    run_id: str | None = None
    auto_run: bool = True


class AgentRunEnqueueRequest(BaseModel):
    prompt: str


class AgentRunControlRequest(BaseModel):
    action: str


class WsManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, event: dict) -> None:
        await self.broadcast_typed(
            event_type="gateway.event",
            payload=event,
            session_id=event.get("session_id", "unknown-session"),
            turn_id=event.get("turn_id", str(uuid4())),
            actor="gateway",
        )

    async def broadcast_typed(
        self,
        event_type: str,
        payload: dict,
        session_id: str,
        turn_id: str,
        actor: str = "gateway",
    ) -> None:
        if not self.connections:
            return
        wrapped = _wrap_base_event(
            event_type=event_type,
            payload=payload,
            session_id=session_id,
            turn_id=turn_id,
            actor=actor,
        )
        _validate_or_422(wrapped, BASE_EVENT_SCHEMA, context=f"ws.{event_type}")
        await asyncio.gather(*(ws.send_json(wrapped) for ws in self.connections), return_exceptions=True)


def _wrap_base_event(event_type: str, payload: dict, session_id: str, turn_id: str, actor: str) -> dict:
    return {
        "event_type": event_type,
        "session_id": session_id,
        "turn_id": turn_id,
        "actor": actor,
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


app = FastAPI(title="OpenCommotion Gateway", version=project_version())
app.mount("/v1/audio", StaticFiles(directory=str(VOICE_AUDIO_ROOT)), name="opencommotion-audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

registry = ArtifactRegistry()
ws_manager = WsManager()
_run_manager: AgentRunManager | None = None


@app.middleware("http")
async def security_and_metrics(request: Request, call_next):  # type: ignore[override]
    started = perf_counter()
    status_code = 500
    try:
        enforce_http_auth(request)
        response = await call_next(request)
        status_code = response.status_code
        return response
    except HTTPException as exc:
        status_code = exc.status_code
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    finally:
        duration_s = perf_counter() - started
        record_http(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_s=duration_s,
        )


def _build_setup_state() -> dict[str, str]:
    values = parse_env(ENV_PATH)
    for key in EDITABLE_KEYS:
        if key not in values and key in os.environ:
            values[key] = os.getenv(key, "")
    return values


def _apply_setup_values(values: dict[str, str]) -> None:
    for key, value in values.items():
        os.environ[key] = value


async def _apply_setup_to_orchestrator(values: dict[str, str]) -> tuple[bool, str]:
    if not values:
        return True, ""
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/v1/runtime/config/apply",
                json={"values": values},
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            return False, "orchestrator runtime apply returned an unexpected response"
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def _emit_agent_runtime_event(event_type: str, payload: dict) -> None:
    session_id = str(payload.get("session_id", payload.get("run_id", "agent-runtime")))
    turn_id = str(payload.get("turn_id", payload.get("queue_id", uuid4())))
    await ws_manager.broadcast_typed(
        event_type=event_type,
        payload=payload,
        session_id=session_id,
        turn_id=turn_id,
        actor="agent-runtime",
    )
    if event_type == "agent.run.state":
        state = payload.get("state", {})
        if isinstance(state, dict):
            queue = state.get("queue", {})
            queued = int(queue.get("queued", 0)) if isinstance(queue, dict) else 0
            set_run_metrics(
                run_id=str(state.get("run_id", payload.get("run_id", "unknown"))),
                queued=queued,
                status=str(state.get("status", "unknown")),
            )


async def _post_orchestrator_with_retry(path: str, payload: dict, timeout_s: float | None = None) -> httpx.Response:
    last_exc: httpx.HTTPError | None = None
    timeout = timeout_s or ORCHESTRATOR_REQUEST_TIMEOUT_S

    for attempt in range(1, ORCHESTRATOR_REQUEST_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{ORCHESTRATOR_URL}{path}",
                    json=payload,
                )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt >= ORCHESTRATOR_REQUEST_MAX_ATTEMPTS:
                break
            await asyncio.sleep(ORCHESTRATOR_RETRY_BASE_DELAY_S * attempt)

    assert last_exc is not None
    raise last_exc


async def _execute_turn(session_id: str, prompt: str, source: str) -> dict:
    if len(prompt) > 4000:
        raise HTTPException(status_code=422, detail={"error": "prompt_too_long", "max_chars": 4000})

    started = perf_counter()
    try:
        resp = await _post_orchestrator_with_retry(
            path="/v1/orchestrate",
            payload={"session_id": session_id, "prompt": prompt},
            timeout_s=ORCHESTRATOR_REQUEST_TIMEOUT_S,
        )
        result = resp.json()
    except httpx.HTTPStatusError as exc:
        details: dict | str
        provider = "orchestrator"
        err_type = "http_status"
        try:
            payload = exc.response.json()
            details = payload.get("detail", payload)
            if isinstance(details, dict):
                provider = str(details.get("provider", details.get("engine", provider)))
                err_type = str(details.get("error", err_type))
        except ValueError:
            details = {
                "error": "orchestrator_http_error",
                "status_code": exc.response.status_code,
                "message": exc.response.text,
            }
        record_provider_error(provider=provider, error_type=err_type)
        raise HTTPException(status_code=exc.response.status_code, detail=details) from exc
    except httpx.HTTPError as exc:
        record_provider_error(provider="orchestrator", error_type="unreachable")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "orchestrator_unreachable",
                "message": str(exc),
                "orchestrator_url": ORCHESTRATOR_URL,
                "hint": "Check orchestrator health via opencommotion -status",
            },
        ) from exc

    _validate_orchestrator_payload(result)

    visual_strokes = result.get("visual_strokes", [])
    patches = compile_brush_batch(visual_strokes)
    quality_report: dict | None = None
    if _looks_like_market_growth_prompt(prompt):
        quality_report = evaluate_market_growth_scene(patches)
        if not quality_report.get("ok"):
            failures = quality_report.get("failures", [])
            message = (
                "Visual quality hardening: auto-detected market-graph issues - "
                + ", ".join(str(item) for item in failures[:3])
            )
            patches.append(
                {
                    "op": "add",
                    "path": "/annotations/-",
                    "value": {"text": message, "style": "warning"},
                    "at_ms": 0,
                }
            )
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
    if quality_report is not None:
        event["quality_report"] = quality_report
    await ws_manager.broadcast(event)
    record_orchestrate(duration_s=perf_counter() - started, source=source)
    return event


def _get_run_manager() -> AgentRunManager:
    global _run_manager
    if _run_manager is None:
        _run_manager = AgentRunManager(
            db_path=AGENT_RUN_DB_PATH,
            turn_executor=lambda session_id, prompt: _execute_turn(session_id=session_id, prompt=prompt, source="agent-run"),
            event_emitter=_emit_agent_runtime_event,
        )
    return _run_manager


@app.on_event("startup")
async def startup_event() -> None:
    await _get_run_manager().start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    manager = _get_run_manager()
    await manager.stop()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "gateway",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics")
def metrics() -> Response:
    payload, content_type = metrics_response()
    return Response(content=payload, media_type=content_type)


@app.websocket("/v1/events/ws")
async def events_ws(websocket: WebSocket) -> None:
    if not websocket_authorized(websocket):
        await websocket.close(code=4401)
        return
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
        record_provider_error(provider=str(exc.engine), error_type="stt_engine_unavailable")
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
        record_provider_error(provider=str(exc.engine), error_type="tts_engine_unavailable")
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

    security = get_security_state()
    return {
        "llm": llm_payload,
        "voice": {
            "stt": stt_capabilities(),
            "tts": tts_capabilities(),
        },
        "security": {
            "mode": security.mode,
            "enforcement_active": security.enforcement_active,
            "api_keys_configured": len(security.api_keys),
            "allowed_ips_configured": len(security.allowed_ips),
        },
    }


@app.get("/v1/setup/state")
def setup_state() -> dict:
    values = _build_setup_state()
    return {
        "state": masked_state(values),
        "editable_keys": sorted(EDITABLE_KEYS),
    }


@app.post("/v1/setup/validate")
def setup_validate(req: SetupValidateRequest) -> dict:
    current = _build_setup_state()
    incoming = normalized_editable(req.values)
    merged = {**current, **incoming}
    result = validate_setup(merged)
    return {"ok": result["ok"], "errors": result["errors"], "warnings": result["warnings"]}


@app.post("/v1/setup/state")
async def setup_save(req: SetupStateRequest) -> dict:
    current = _build_setup_state()
    incoming = normalized_editable(req.values)
    merged = {**current, **incoming}
    validation = validate_setup(merged)
    if not validation["ok"]:
        raise HTTPException(status_code=422, detail={"error": "invalid_setup", **validation})

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_env(ENV_PATH, merged)
    _apply_setup_values(incoming)
    restart_required = False
    warnings = list(validation["warnings"])
    applied_runtime = True
    apply_ok, apply_error = await _apply_setup_to_orchestrator(incoming)
    if not apply_ok:
        applied_runtime = False
        restart_required = True
        warnings.append(
            (
                "Setup saved, but automatic runtime apply failed for orchestrator. "
                f"Restart stack to apply all changes. Details: {apply_error}"
            )
        )
    return {
        "ok": True,
        "restart_required": restart_required,
        "applied_runtime": applied_runtime,
        "saved_keys": sorted(incoming.keys()),
        "warnings": warnings,
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
    return await _execute_turn(session_id=req.session_id, prompt=req.prompt, source="api")


@app.post("/v1/agent-runs")
async def create_agent_run(req: AgentRunCreateRequest) -> dict:
    manager = _get_run_manager()
    run = manager.create_run(
        label=req.label,
        session_id=req.session_id,
        run_id=req.run_id,
        auto_run=req.auto_run,
    )
    await _emit_agent_runtime_event(
        "agent.run.state",
        {
            "run_id": run["run_id"],
            "session_id": run["session_id"],
            "reason": "created",
            "state": run,
        },
    )
    return {"ok": True, "run": run}


@app.get("/v1/agent-runs")
def list_agent_runs() -> dict:
    manager = _get_run_manager()
    return {"runs": manager.list_runs()}


@app.get("/v1/agent-runs/{run_id}")
def get_agent_run(run_id: str) -> dict:
    manager = _get_run_manager()
    try:
        run = manager.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id}) from exc
    return {"run": run}


@app.post("/v1/agent-runs/{run_id}/enqueue")
async def enqueue_agent_run(run_id: str, req: AgentRunEnqueueRequest) -> dict:
    manager = _get_run_manager()
    try:
        item = manager.enqueue(run_id=run_id, prompt=req.prompt)
        run = manager.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_prompt", "message": str(exc)}) from exc

    await _emit_agent_runtime_event(
        "agent.run.state",
        {
            "run_id": run_id,
            "session_id": run["session_id"],
            "reason": "enqueue",
            "state": run,
            "item": item,
        },
    )
    return {"ok": True, "item": item, "run": run}


@app.post("/v1/agent-runs/{run_id}/control")
async def control_agent_run(run_id: str, req: AgentRunControlRequest) -> dict:
    manager = _get_run_manager()
    try:
        run = await manager.control(run_id=run_id, action=req.action)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": "run_not_found", "run_id": run_id}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "invalid_action", "message": str(exc)}) from exc
    return {"ok": True, "run": run}


if (UI_DIST_ROOT / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(UI_DIST_ROOT), html=True), name="opencommotion-ui")
