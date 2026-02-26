#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import websockets


@dataclass
class ClientConfig:
    gateway: str
    orchestrator: str
    session_id: str
    prompt: str
    api_key: str
    health_attempts: int
    rest_retries: int
    ws_timeout: float
    save: bool
    search: str


def _ws_url(gateway: str, api_key: str) -> str:
    base = gateway.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/v2/events/ws"
    if not api_key:
        return base
    return f"{base}?{urlencode({'api_key': api_key})}"


async def wait_for_health(gateway: str, orchestrator: str, attempts: int, api_key: str) -> None:
    headers = {"x-api-key": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=2.0, headers=headers) as client:
        for attempt in range(1, attempts + 1):
            ok = False
            try:
                g = await client.get(f"{gateway}/health")
                o = await client.get(f"{orchestrator}/health")
                ok = g.status_code == 200 and o.status_code == 200
            except httpx.HTTPError:
                ok = False

            if ok:
                return

            delay = min(0.5 * (2 ** (attempt - 1)), 3.0)
            await asyncio.sleep(delay)

    raise RuntimeError("health checks did not become ready in time")


async def post_orchestrate_with_retry(
    client: httpx.AsyncClient,
    gateway: str,
    session_id: str,
    scene_id: str,
    prompt: str,
    retries: int,
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            res = await client.post(
                f"{gateway}/v2/orchestrate",
                json={"session_id": session_id, "scene_id": scene_id, "base_revision": 0, "prompt": prompt},
            )
            if res.status_code >= 500 and attempt < retries:
                await asyncio.sleep(min(0.6 * (2 ** (attempt - 1)), 2.4))
                continue
            res.raise_for_status()
            return res.json()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            last_error = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise
            if attempt >= retries:
                break
            await asyncio.sleep(min(0.6 * (2 ** (attempt - 1)), 2.4))

    if last_error is None:
        raise RuntimeError("unknown orchestrate error")
    raise last_error


async def wait_for_turn_event(
    ws: websockets.WebSocketClientProtocol,
    session_id: str,
    turn_id: str,
    timeout_s: float,
) -> dict:
    seen: set[tuple[str, str]] = set()

    async def _recv() -> dict:
        while True:
            raw = await ws.recv()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sid = event.get("session_id")
            tid = event.get("turn_id")
            if sid != session_id or tid != turn_id:
                continue
            key = (sid, tid)
            if key in seen:
                continue
            seen.add(key)
            return event

    return await asyncio.wait_for(_recv(), timeout=timeout_s)


async def run(config: ClientConfig) -> None:
    gateway = config.gateway.rstrip("/")
    orchestrator = config.orchestrator.rstrip("/")

    await wait_for_health(
        gateway=gateway,
        orchestrator=orchestrator,
        attempts=config.health_attempts,
        api_key=config.api_key,
    )

    ws_url = _ws_url(gateway, config.api_key)
    scene_id = f"scene-{config.session_id}"
    async with websockets.connect(ws_url, ping_interval=10, ping_timeout=10) as ws:
        await ws.send("ping")

        headers = {"x-api-key": config.api_key} if config.api_key else {}
        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            rest_turn = await post_orchestrate_with_retry(
                client=client,
                gateway=gateway,
                session_id=config.session_id,
                scene_id=scene_id,
                prompt=config.prompt,
                retries=config.rest_retries,
            )

            turn_id = rest_turn["turn_id"]
            try:
                ws_event = await wait_for_turn_event(
                    ws=ws,
                    session_id=config.session_id,
                    turn_id=turn_id,
                    timeout_s=config.ws_timeout,
                )
                source = "websocket"
                payload = ws_event.get("payload", rest_turn)
            except TimeoutError:
                source = "rest-fallback"
                payload = rest_turn

            if config.save:
                save_res = await client.post(
                    f"{gateway}/v1/artifacts/save",
                    json={
                        "title": f"Turn {turn_id[:8]}",
                        "summary": payload.get("text", ""),
                        "tags": ["agent", "robust"],
                        "saved_by": "robust-turn-client",
                    },
                )
                save_res.raise_for_status()

            search_results: list[dict] = []
            if config.search:
                search_res = await client.get(
                    f"{gateway}/v1/artifacts/search",
                    params={"q": config.search, "mode": "hybrid"},
                )
                search_res.raise_for_status()
                search_results = search_res.json().get("results", [])

    voice_segments = payload.get("voice", {}).get("segments", [])
    voice_uri = voice_segments[0].get("audio_uri", "") if voice_segments else ""
    summary = {
        "source": source,
        "session_id": payload.get("session_id", config.session_id),
        "turn_id": payload.get("turn_id", ""),
        "patch_count": len(payload.get("patches", []) or payload.get("legacy_visual_patches", []) or payload.get("visual_patches", [])),
        "text": payload.get("text", ""),
        "voice_uri": voice_uri,
        "search_results_count": len(search_results),
    }

    print(json.dumps(summary, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Robust OpenCommotion agent client")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--orchestrator", default="http://127.0.0.1:8001")
    parser.add_argument("--session", default="agent-robust-demo")
    parser.add_argument("--prompt", default="moonwalk adoption chart with voice")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENCOMMOTION_GATEWAY_API_KEY", os.getenv("OPENCOMMOTION_API_KEY", "dev-opencommotion-key")),
    )
    parser.add_argument("--health-attempts", type=int, default=12)
    parser.add_argument("--rest-retries", type=int, default=3)
    parser.add_argument("--ws-timeout", type=float, default=20.0)
    parser.add_argument("--search", default="moonwalk")
    parser.add_argument("--no-save", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = ClientConfig(
        gateway=args.gateway,
        orchestrator=args.orchestrator,
        session_id=args.session,
        prompt=args.prompt,
        api_key=args.api_key,
        health_attempts=args.health_attempts,
        rest_retries=args.rest_retries,
        ws_timeout=args.ws_timeout,
        save=not args.no_save,
        search=args.search,
    )
    asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
