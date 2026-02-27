from __future__ import annotations

import asyncio
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.agent_runtime.manager import AgentRunManager
from services.agents.text.worker import LLMEngineError, rewrite_visual_prompt
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
from services.scene_v2 import (
    SceneApplyError,
    SceneV2Store,
    apply_ops,
    default_policy,
    list_recipes,
    patches_to_v2_ops,
    scene_summary,
)
from services.versioning import project_version

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8001")
AGENT_RUN_DB_PATH = Path(
    os.getenv("OPENCOMMOTION_AGENT_RUN_DB_PATH", str(PROJECT_ROOT / "runtime" / "agent-runs" / "agent_manager.db"))
)
AGENT_RUN_MAX_CONCURRENT_TURNS = max(
    1,
    int(os.getenv("OPENCOMMOTION_AGENT_RUN_MAX_CONCURRENT_TURNS", "3")),
)
ORCHESTRATOR_REQUEST_TIMEOUT_S = float(os.getenv("OPENCOMMOTION_ORCHESTRATOR_TIMEOUT_S", "20"))
ORCHESTRATOR_REQUEST_MAX_ATTEMPTS = max(1, int(os.getenv("OPENCOMMOTION_ORCHESTRATOR_MAX_ATTEMPTS", "3")))
ORCHESTRATOR_RETRY_BASE_DELAY_S = max(0.05, float(os.getenv("OPENCOMMOTION_ORCHESTRATOR_RETRY_BASE_DELAY_S", "0.2")))
AGENT_CONTEXT_REMINDER_SUFFIX = (
    "System reminder: you are OpenCommotion's visual runtime agent. "
    "You must return concrete visual scene updates (drawing/motion primitives), not text-only responses."
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _timeout_env(env_key: str, fallback_s: float) -> float:
    raw = str(os.getenv(env_key, "")).strip()
    if not raw:
        return fallback_s
    try:
        value = float(raw)
    except ValueError:
        return fallback_s
    return min(max(value, 0.5), 300.0)


def _orchestrator_turn_timeout_s() -> float:
    baseline = _timeout_env("OPENCOMMOTION_ORCHESTRATOR_TIMEOUT_S", ORCHESTRATOR_REQUEST_TIMEOUT_S)
    llm = _timeout_env("OPENCOMMOTION_LLM_TIMEOUT_S", 20.0)
    codex = _timeout_env("OPENCOMMOTION_CODEX_TIMEOUT_S", llm)
    openclaw = _timeout_env("OPENCOMMOTION_OPENCLAW_TIMEOUT_S", llm)
    openai_voice = _timeout_env("OPENCOMMOTION_VOICE_OPENAI_TIMEOUT_S", 20.0)
    expected_turn_budget = max(llm, codex, openclaw, openai_voice) + 5.0
    return min(300.0, max(baseline, expected_turn_budget))


def _httpx_error_message(exc: httpx.HTTPError, timeout_s: float | None = None) -> str:
    message = str(exc).strip()
    if message:
        return message
    if timeout_s is not None and isinstance(exc, httpx.TimeoutException):
        return f"request to orchestrator timed out after {timeout_s:.1f}s"
    return exc.__class__.__name__


SCENE_ID_SAFE_RE = re.compile(r"[^a-zA-Z0-9._:-]+")


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
UI_DIST_ROOT = _resolve_runtime_path("OPENCOMMOTION_UI_DIST_ROOT", PROJECT_ROOT / "runtime" / "ui-dist")
SCENE_V2_ROOT = _resolve_runtime_path("OPENCOMMOTION_SCENE_V2_ROOT", PROJECT_ROOT / "runtime" / "scenes")
VOICE_AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
SCENE_V2_ROOT.mkdir(parents=True, exist_ok=True)

protocol_validator = ProtocolValidator()
BRUSH_STROKE_SCHEMA = "types/brush_stroke_v1.schema.json"
SCENE_PATCH_SCHEMA = "types/scene_patch_v1.schema.json"
SCENE_PATCH_OP_V2_SCHEMA = "types/scene_patch_op_v2.schema.json"
SCENE_PATCH_ENVELOPE_V2_SCHEMA = "types/scene_patch_envelope_v2.schema.json"
RUNTIME_CAPABILITIES_V2_SCHEMA = "types/runtime_capabilities_v2.schema.json"
BASE_EVENT_SCHEMA = "events/base_event.schema.json"
ARTIFACT_BUNDLE_SCHEMA = "types/artifact_bundle_v1.schema.json"


class OrchestrateRequest(BaseModel):
    session_id: str
    prompt: str


class OrchestrateV2Intent(BaseModel):
    rebuild: bool = False


class OrchestrateV2Request(BaseModel):
    session_id: str
    prompt: str
    scene_id: str | None = None
    base_revision: int | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    intent: OrchestrateV2Intent = Field(default_factory=OrchestrateV2Intent)


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


class SceneSnapshotRequest(BaseModel):
    snapshot_name: str = ""
    persist_artifact: bool = False


class SceneRestoreRequest(BaseModel):
    snapshot_id: str


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


def _apply_v1_deprecation_headers(response: Response, path: str) -> Response:
    if path.startswith("/v1/"):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "2026-04-30T00:00:00Z"
        response.headers["Link"] = '</v2/orchestrate>; rel="successor-version"'
    return response


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
ws_manager_v2 = WsManager()
scene_store_v2 = SceneV2Store(SCENE_V2_ROOT)
scene_policy_v2 = default_policy()
_run_manager: AgentRunManager | None = None
_SESSION_CONTEXT_LOCK = Lock()
_SESSION_CONTEXT_CACHE: dict[str, dict[str, Any]] = {}


@app.middleware("http")
async def security_and_metrics(request: Request, call_next):  # type: ignore[override]
    started = perf_counter()
    status_code = 500
    try:
        enforce_http_auth(request)
        response = await call_next(request)
        status_code = response.status_code
        return _apply_v1_deprecation_headers(response, request.url.path)
    except HTTPException as exc:
        status_code = exc.status_code
        response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return _apply_v1_deprecation_headers(response, request.url.path)
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
        except httpx.TimeoutException as exc:
            last_exc = exc
            break
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt >= ORCHESTRATOR_REQUEST_MAX_ATTEMPTS:
                break
            await asyncio.sleep(ORCHESTRATOR_RETRY_BASE_DELAY_S * attempt)

    assert last_exc is not None
    raise last_exc


async def _execute_turn(
    session_id: str,
    prompt: str,
    source: str,
    *,
    broadcast_event: bool = True,
    reminder_prompt: str | None = None,
) -> dict:
    if len(prompt) > 4000:
        raise HTTPException(status_code=422, detail={"error": "prompt_too_long", "max_chars": 4000})

    started = perf_counter()
    request_timeout_s = _orchestrator_turn_timeout_s()
    context = _build_orchestrate_context(session_id=session_id, prompt=prompt, source=source, reminder_prompt=reminder_prompt)
    try:
        resp = await _post_orchestrator_with_retry(
            path="/v1/orchestrate",
            payload={"session_id": session_id, "prompt": prompt, "context": context},
            timeout_s=request_timeout_s,
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
    except httpx.TimeoutException as exc:
        record_provider_error(provider="orchestrator", error_type="timeout")
        raise HTTPException(
            status_code=504,
            detail={
                "error": "orchestrator_timeout",
                "message": _httpx_error_message(exc, timeout_s=request_timeout_s),
                "orchestrator_url": ORCHESTRATOR_URL,
                "timeout_s": request_timeout_s,
                "hint": "Check provider runtime and timeout settings in setup",
            },
        ) from exc
    except httpx.HTTPError as exc:
        record_provider_error(provider="orchestrator", error_type="unreachable")
        raise HTTPException(
            status_code=502,
            detail={
                "error": "orchestrator_unreachable",
                "message": _httpx_error_message(exc),
                "orchestrator_url": ORCHESTRATOR_URL,
                "hint": "Check orchestrator health via opencommotion -status",
            },
        ) from exc

    _validate_orchestrator_payload(result)

    visual_strokes = result.get("visual_strokes", [])
    _update_session_context(session_id=session_id, prompt=prompt, strokes=visual_strokes, source=source)
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
    if broadcast_event:
        await ws_manager.broadcast(event)
    record_orchestrate(duration_s=perf_counter() - started, source=source)
    return event


def _v2_limits_payload() -> dict[str, Any]:
    return {
        "max_entities_2d": scene_policy_v2.max_entities_2d,
        "max_entities_3d": scene_policy_v2.max_entities_3d,
        "max_patch_ops_per_turn": scene_policy_v2.max_patch_ops_per_turn,
        "max_materials": scene_policy_v2.max_materials,
        "max_behaviors": scene_policy_v2.max_behaviors,
        "max_texture_dimension": scene_policy_v2.max_texture_dimension,
        "max_texture_memory_mb": scene_policy_v2.max_texture_memory_mb,
        "max_uniform_update_hz": scene_policy_v2.max_uniform_update_hz,
    }


async def _runtime_capabilities_v2_payload() -> dict[str, Any]:
    llm_payload: dict[str, Any] = {
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
    payload = {
        "version": "v2",
        "renderers": ["svg-2d", "three-webgl"],
        "features": {
            "shaderRecipes": True,
            "gltfImport": False,
            "pbr": True,
            "particles": True,
            "physics": False,
        },
        "limits": _v2_limits_payload(),
        "shader_recipes": list_recipes(),
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
    _validate_or_422(payload, RUNTIME_CAPABILITIES_V2_SCHEMA, context="runtime.capabilities.v2")
    return payload


def _infer_explicit_rebuild(prompt: str, request_rebuild: bool) -> bool:
    if request_rebuild:
        return True
    lowered = str(prompt or "").lower()
    tokens = ("rebuild", "reset scene", "start over", "full redraw", "replace whole scene", "new scene")
    return any(token in lowered for token in tokens)


def _v2_has_visual_delta_ops(ops: list[dict[str, Any]]) -> bool:
    for op in ops:
        op_name = str(op.get("op", "")).strip()
        if not op_name:
            continue
        if op_name in {"createEntity", "updateEntity", "destroyEntity"}:
            entity_id = str(op.get("entity_id", "")).strip().lower()
            kind = str(op.get("kind", "")).strip().lower()
            if kind == "annotation" or "annotation" in entity_id:
                continue
            return True
        return True
    return False


def _preview_prompt(raw: str, limit: int = 140) -> str:
    text = " ".join(str(raw or "").strip().split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _scene_context_brief(scene: dict[str, Any], scene_id: str, revision: int) -> str:
    summary = scene_summary(scene)
    entities = sorted(str(key) for key in scene.get("entities", {}).keys())[:8]
    materials = sorted(str(key) for key in scene.get("materials", {}).keys())[:6]
    behaviors = sorted(str(key) for key in scene.get("behaviors", {}).keys())[:6]
    return (
        f"scene_id={scene_id}; revision={revision}; "
        f"entity_count={summary.get('entity_count', 0)}; "
        f"material_count={summary.get('material_count', 0)}; "
        f"behavior_count={summary.get('behavior_count', 0)}; "
        f"entities={','.join(entities) if entities else 'none'}; "
        f"materials={','.join(materials) if materials else 'none'}; "
        f"behaviors={','.join(behaviors) if behaviors else 'none'}"
    )


def _capability_context(req: OrchestrateV2Request) -> str:
    capabilities = req.capabilities if isinstance(req.capabilities, dict) else {}
    renderer = str(capabilities.get("renderer", "")).strip() or "auto"
    features = capabilities.get("features")
    feature_tokens: list[str] = []
    if isinstance(features, dict):
        for key in sorted(features.keys()):
            if len(feature_tokens) >= 8:
                break
            value = features.get(key)
            if isinstance(value, bool):
                feature_tokens.append(f"{key}={str(value).lower()}")
    if not feature_tokens:
        feature_tokens = ["features=default"]
    return f"renderer={renderer}; " + "; ".join(feature_tokens)


def _scene_context_expanded(scene: dict[str, Any], scene_id: str, revision: int) -> str:
    lines: list[str] = [_scene_context_brief(scene, scene_id, revision), "entity_details:"]
    entities = scene.get("entities", {})
    for idx, key in enumerate(sorted(str(k) for k in entities.keys())):
        if idx >= 20:
            break
        row = entities.get(key, {})
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind", "unknown"))
        lines.append(f"- {key} kind={kind}")
    return "\n".join(lines)


def _default_scene_brief(session_id: str) -> str:
    return f"session={session_id}; turn=0; entity_count=0; strokes=0"


def _describe_scene_brief(
    session_id: str,
    prompt: str,
    entity_details: list[dict[str, str]],
    strokes: int,
    turn_phase: str,
) -> str:
    preview = _preview_prompt(prompt, 120)
    entity_tokens = ",".join(entry["id"] for entry in entity_details[:4]) if entity_details else "none"
    return (
        f"session={session_id}; phase={turn_phase}; preview={preview}; "
        f"entities={entity_tokens}; entity_count={len(entity_details)}; strokes={strokes}"
    )


def _capability_brief(source: str) -> str:
    provider = os.getenv("OPENCOMMOTION_LLM_PROVIDER", "heuristic").strip() or "heuristic"
    model = os.getenv("OPENCOMMOTION_LLM_MODEL", "").strip() or "default"
    return f"source={source}; provider={provider}; model={model}"


def _extract_entity_id_from_stroke(stroke: dict[str, Any]) -> str | None:
    params = stroke.get("params")
    if isinstance(params, dict):
        for candidate in ("actor_id", "target_id", "entity_id", "source_id"):
            raw = params.get(candidate)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        program = params.get("program")
        if isinstance(program, dict):
            commands = program.get("commands")
            if isinstance(commands, list):
                for command in commands:
                    if not isinstance(command, dict):
                        continue
                    candidate = command.get("target_id") or command.get("actor_id")
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
    return None


def _extract_entity_details_from_strokes(strokes: list[dict[str, Any]]) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    seen: set[str] = set()
    for stroke in strokes:
        entity_id = _extract_entity_id_from_stroke(stroke)
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        details.append({"id": entity_id, "kind": str(stroke.get("kind", "unknown"))})
        if len(details) >= 8:
            break
    return details


def _build_orchestrate_context(
    session_id: str,
    prompt: str,
    *,
    source: str,
    reminder_prompt: str | None = None,
) -> dict[str, Any]:
    with _SESSION_CONTEXT_LOCK:
        state = _SESSION_CONTEXT_CACHE.setdefault(
            session_id,
            {"turns": 0, "entity_details": [], "scene_brief": "", "capability_brief": ""},
        )
        first_turn = state.get("turns", 0) == 0
        scene_brief = state.get("scene_brief") or _default_scene_brief(session_id)
        capability_brief = _capability_brief(source)
        context = {
            "scene_brief": scene_brief,
            "capability_brief": capability_brief,
            "turn_phase": "first-turn" if first_turn else "follow-up",
            "entity_details": list(state.get("entity_details", [])),
        }
    if reminder_prompt:
        context["system_prompt_override"] = reminder_prompt
    return context


def _update_session_context(session_id: str, prompt: str, strokes: list[dict[str, Any]], *, source: str) -> None:
    entity_details = _extract_entity_details_from_strokes(strokes)
    with _SESSION_CONTEXT_LOCK:
        state = _SESSION_CONTEXT_CACHE.setdefault(
            session_id,
            {"turns": 0, "entity_details": [], "scene_brief": "", "capability_brief": ""},
        )
        state["turns"] = state.get("turns", 0) + 1
        turn_phase = "first-turn" if state["turns"] == 1 else "follow-up"
        state["entity_details"] = entity_details
        state["scene_brief"] = _describe_scene_brief(session_id, prompt, entity_details, len(strokes), turn_phase)
        state["capability_brief"] = _capability_brief(source)


def _reset_session_context_cache() -> None:
    with _SESSION_CONTEXT_LOCK:
        _SESSION_CONTEXT_CACHE.clear()


def _resolve_orchestration_prompt_v2(
    *,
    req: OrchestrateV2Request,
    scene: dict[str, Any],
    scene_id: str,
    current_revision: int,
) -> tuple[str, list[str]]:
    prompt = str(req.prompt or "").strip()
    warnings: list[str] = []
    if not prompt:
        return prompt, warnings

    first_turn = current_revision <= 0
    phase = "first-turn" if first_turn else "follow-up-turn"
    context = (
        f"invocation={phase}; "
        + _capability_context(req)
        + "; "
        + _scene_context_brief(scene=scene, scene_id=scene_id, revision=current_revision)
    )

    try:
        rewritten, meta = rewrite_visual_prompt(prompt=prompt, context=context, first_turn=first_turn)
    except LLMEngineError as exc:
        warnings.append(f"prompt_rewrite_error:{exc.provider}")
        return prompt, warnings

    warnings.extend(str(row) for row in list(meta.get("warnings", []))[:8])
    if bool(meta.get("scene_request")):
        warnings.append("agent_scene_request_honored")
        expanded = _scene_context_expanded(scene=scene, scene_id=scene_id, revision=current_revision)
        try:
            rewritten_2, meta_2 = rewrite_visual_prompt(prompt=prompt, context=expanded, first_turn=first_turn)
            warnings.extend(str(row) for row in list(meta_2.get("warnings", []))[:8])
            if rewritten_2.strip():
                rewritten = rewritten_2
        except LLMEngineError as exc:
            warnings.append(f"agent_scene_request_failed:{exc.provider}")

    resolved = rewritten.strip() or prompt
    if resolved != prompt:
        warnings.append(f"prompt_rewrite_applied:{_preview_prompt(resolved, 120)}")
    return resolved, warnings


def _normalize_scene_id(scene_id: str | None, session_id: str) -> str:
    raw = str(scene_id or "").strip() or f"scene-{session_id}"
    compact = SCENE_ID_SAFE_RE.sub("-", raw).strip("-")
    return compact or f"scene-{session_id}"


def _snapshot_asset_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _persist_snapshot_artifact(scene_id: str, snapshot_meta: dict[str, Any]) -> dict[str, Any]:
    snapshot_path = Path(str(snapshot_meta.get("path", ""))).resolve()
    if not snapshot_path.exists():
        raise FileNotFoundError("snapshot file not found")
    artifact_id = str(uuid4())
    bundle = {
        "artifact_id": artifact_id,
        "version": "1.0.0",
        "title": f"Scene Snapshot {scene_id}",
        "summary": f"OpenCommotion V2 snapshot {snapshot_meta.get('snapshot_id', '')}",
        "tags": ["scene-v2", "snapshot", scene_id],
        "scene_entrypoint": str(snapshot_path.name),
        "assets": [
            {
                "path": str(snapshot_path.name),
                "type": "application/json",
                "sha256": _snapshot_asset_sha(snapshot_path),
            }
        ],
    }
    saved = registry.save_artifact(bundle, saved_by="v2-snapshot")
    return {
        "artifact_id": saved.get("artifact_id", artifact_id),
        "title": saved.get("title", ""),
        "bundle_path": saved.get("bundle_path", ""),
    }


async def _execute_turn_v2(req: OrchestrateV2Request) -> dict[str, Any]:
    scene_id = _normalize_scene_id(req.scene_id, req.session_id)
    scene = scene_store_v2.get_or_create(scene_id)
    current_revision = int(scene.get("revision", 0))
    if req.base_revision is not None and int(req.base_revision) != current_revision:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "revision_conflict",
                "scene_id": scene_id,
                "expected_revision": current_revision,
                "received_base_revision": int(req.base_revision),
            },
        )

    resolved_prompt, rewrite_warnings = _resolve_orchestration_prompt_v2(
        req=req,
        scene=scene,
        scene_id=scene_id,
        current_revision=current_revision,
    )

    turn = await _execute_turn(
        session_id=req.session_id,
        prompt=resolved_prompt,
        source="api-v2",
        broadcast_event=False,
    )
    legacy_patches = list(turn.get("visual_patches", []))
    ops, translator_warnings = patches_to_v2_ops(
        legacy_patches,
        turn_id=str(turn.get("turn_id", str(uuid4()))),
        prompt=resolved_prompt,
        scene=scene,
    )
    if not _v2_has_visual_delta_ops(ops):
        translator_warnings.append("agent_context_reminder_applied:no_visual_scene_delta")
        reminder_prompt = f"{resolved_prompt.strip()}\n\n{AGENT_CONTEXT_REMINDER_SUFFIX}"
        reminded_turn = await _execute_turn(
            session_id=req.session_id,
            prompt=reminder_prompt,
            source="api-v2-reminder",
            reminder_prompt=reminder_prompt,
            broadcast_event=False,
        )
        reminder_patches = list(reminded_turn.get("visual_patches", []))
        reminder_ops, reminder_warnings = patches_to_v2_ops(
            reminder_patches,
            turn_id=str(reminded_turn.get("turn_id", str(uuid4()))),
            prompt=reminder_prompt,
            scene=scene,
        )
        translator_warnings.extend(reminder_warnings)
        if _v2_has_visual_delta_ops(reminder_ops):
            turn = reminded_turn
            legacy_patches = reminder_patches
            ops = reminder_ops
        else:
            translator_warnings.append("agent_context_reminder_failed:no_visual_scene_delta")
    _validate_many(ops, SCENE_PATCH_OP_V2_SCHEMA, context_prefix="orchestrate.v2.patches")
    explicit_rebuild = _infer_explicit_rebuild(req.prompt, bool(req.intent.rebuild))
    try:
        apply_result = apply_ops(scene, ops, scene_policy_v2, explicit_rebuild=explicit_rebuild)
    except SceneApplyError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": exc.code,
                "message": exc.message,
                "scene_id": scene_id,
                "detail": exc.detail,
            },
        ) from exc

    scene_store_v2.autosave(scene_id)
    warnings = [*rewrite_warnings, *translator_warnings, *apply_result.get("warnings", [])]
    envelope: dict[str, Any] = {
        "version": "v2",
        "session_id": req.session_id,
        "scene_id": scene_id,
        "turn_id": str(turn.get("turn_id", str(uuid4()))),
        "base_revision": current_revision,
        "revision": int(scene.get("revision", current_revision)),
        "text": str(turn.get("text", "")),
        "voice": turn.get("voice", {}),
        "timeline": turn.get("timeline", {"duration_ms": 0}),
        "patches": apply_result.get("applied_ops", []),
        "warnings": warnings,
        "degrade_notes": apply_result.get("degrade_notes", []),
        "explanation_text": str(turn.get("text", "")),
        "legacy_visual_patches": legacy_patches,
    }
    if "quality_report" in turn:
        envelope["quality_report"] = turn["quality_report"]
    _validate_or_422(envelope, SCENE_PATCH_ENVELOPE_V2_SCHEMA, context="orchestrate.v2.envelope")
    await ws_manager_v2.broadcast_typed(
        event_type="gateway.v2.event",
        payload=envelope,
        session_id=req.session_id,
        turn_id=str(envelope["turn_id"]),
        actor="gateway-v2",
    )
    return envelope


def _get_run_manager() -> AgentRunManager:
    global _run_manager
    if _run_manager is None:
        _run_manager = AgentRunManager(
            db_path=AGENT_RUN_DB_PATH,
            turn_executor=lambda session_id, prompt: _execute_turn(session_id=session_id, prompt=prompt, source="agent-run"),
            event_emitter=_emit_agent_runtime_event,
            max_concurrent_turns=AGENT_RUN_MAX_CONCURRENT_TURNS,
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


@app.websocket("/v2/events/ws")
async def events_ws_v2(websocket: WebSocket) -> None:
    if not websocket_authorized(websocket):
        await websocket.close(code=4401)
        return
    await ws_manager_v2.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager_v2.disconnect(websocket)


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


@app.get("/v2/runtime/capabilities")
async def runtime_capabilities_v2() -> dict[str, Any]:
    return await _runtime_capabilities_v2_payload()


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


@app.post("/v2/orchestrate")
async def orchestrate_v2(req: OrchestrateV2Request) -> dict[str, Any]:
    return await _execute_turn_v2(req)


@app.get("/v2/scenes/{scene_id}")
def v2_scene_state(scene_id: str) -> dict[str, Any]:
    resolved_id = _normalize_scene_id(scene_id, scene_id)
    view = scene_store_v2.state_view(resolved_id)
    scene = scene_store_v2.get_or_create(resolved_id)
    return {
        "scene_id": resolved_id,
        "scene": view.get("scene", scene_summary(scene)),
        "snapshots": view.get("snapshots", []),
        "warnings": list(scene.get("warnings", []))[-30:],
    }


@app.post("/v2/scenes/{scene_id}/snapshot")
def v2_scene_snapshot(scene_id: str, req: SceneSnapshotRequest) -> dict[str, Any]:
    resolved_id = _normalize_scene_id(scene_id, scene_id)
    try:
        snapshot = scene_store_v2.snapshot(resolved_id, req.snapshot_name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "snapshot_failed", "scene_id": resolved_id, "message": str(exc)},
        ) from exc
    artifact: dict[str, Any] | None = None
    if req.persist_artifact:
        try:
            artifact = _persist_snapshot_artifact(resolved_id, snapshot)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail={"error": "snapshot_artifact_failed", "scene_id": resolved_id, "message": str(exc)},
            ) from exc
    return {"ok": True, "snapshot": snapshot, "artifact": artifact}


@app.post("/v2/scenes/{scene_id}/restore")
def v2_scene_restore(scene_id: str, req: SceneRestoreRequest) -> dict[str, Any]:
    resolved_id = _normalize_scene_id(scene_id, scene_id)
    try:
        restored = scene_store_v2.restore(resolved_id, req.snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "snapshot_not_found", "scene_id": resolved_id, "snapshot_id": req.snapshot_id},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "snapshot_restore_failed", "scene_id": resolved_id, "message": str(exc)},
        ) from exc
    return {"ok": True, "restored": restored}


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


UI_STATIC_ROOT = UI_DIST_ROOT
if not (UI_STATIC_ROOT / "index.html").exists():
    fallback_ui_dist = (PROJECT_ROOT / "apps" / "ui" / "dist").resolve()
    if fallback_ui_dist != UI_STATIC_ROOT.resolve() and (fallback_ui_dist / "index.html").exists():
        UI_STATIC_ROOT = fallback_ui_dist

if (UI_STATIC_ROOT / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(UI_STATIC_ROOT), html=True), name="opencommotion-ui")
