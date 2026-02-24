#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass

import httpx
import websockets


@dataclass
class TurnResult:
    session_id: str
    turn_id: str
    text: str
    patch_count: int
    voice_uri: str


async def run_agent_flow(
    gateway: str,
    session_id: str,
    prompt: str,
    save: bool,
    search_query: str,
    timeout_s: float,
) -> TurnResult:
    gateway = gateway.rstrip("/")
    ws_url = gateway.replace("http://", "ws://").replace("https://", "wss://") + "/v1/events/ws"

    async with websockets.connect(ws_url) as ws:
        await ws.send("ping")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{gateway}/v1/orchestrate",
                json={"session_id": session_id, "prompt": prompt},
            )
            response.raise_for_status()
            turn = response.json()

            turn_id = turn["turn_id"]
            ws_event = await _wait_for_turn_event(ws=ws, session_id=session_id, turn_id=turn_id, timeout_s=timeout_s)

            if save:
                save_resp = await client.post(
                    f"{gateway}/v1/artifacts/save",
                    json={
                        "title": f"Agent Turn {turn_id[:8]}",
                        "summary": turn.get("text", ""),
                        "tags": ["agent", "demo"],
                        "saved_by": "agent-example",
                    },
                )
                save_resp.raise_for_status()

            if search_query:
                search_resp = await client.get(
                    f"{gateway}/v1/artifacts/search",
                    params={"q": search_query, "mode": "hybrid"},
                )
                search_resp.raise_for_status()
                results = search_resp.json().get("results", [])
                print(f"search results ({len(results)}):")
                for row in results[:5]:
                    title = row.get("title", "untitled")
                    mode = row.get("match_mode", "n/a")
                    score = row.get("score")
                    if isinstance(score, (float, int)):
                        print(f"  - {title} [{mode}:{score:.3f}]")
                    else:
                        print(f"  - {title} [{mode}]")

    payload = ws_event.get("payload", {})
    segments = payload.get("voice", {}).get("segments", [])
    voice_uri = segments[0].get("audio_uri", "") if segments else ""

    return TurnResult(
        session_id=payload.get("session_id", session_id),
        turn_id=payload.get("turn_id", turn_id),
        text=payload.get("text", ""),
        patch_count=len(payload.get("visual_patches", [])),
        voice_uri=voice_uri,
    )


async def _wait_for_turn_event(
    ws: websockets.WebSocketClientProtocol,
    session_id: str,
    turn_id: str,
    timeout_s: float,
) -> dict:
    async def _recv() -> dict:
        while True:
            message = await ws.recv()
            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                continue
            if event.get("session_id") != session_id:
                continue
            if event.get("turn_id") != turn_id:
                continue
            return event

    return await asyncio.wait_for(_recv(), timeout=timeout_s)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenCommotion REST + WS agent example client")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000", help="Gateway base URL")
    parser.add_argument("--session", default="agent-session-demo", help="Session ID")
    parser.add_argument("--prompt", default="moonwalk adoption chart with voice", help="Prompt to orchestrate")
    parser.add_argument("--search", default="moonwalk", help="Search query after save")
    parser.add_argument("--no-save", action="store_true", help="Skip artifact save step")
    parser.add_argument("--timeout", type=float, default=20.0, help="WS wait timeout in seconds")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    turn = asyncio.run(
        run_agent_flow(
            gateway=args.gateway,
            session_id=args.session,
            prompt=args.prompt,
            save=not args.no_save,
            search_query=args.search,
            timeout_s=args.timeout,
        )
    )

    print("turn complete:")
    print(f"  session_id: {turn.session_id}")
    print(f"  turn_id: {turn.turn_id}")
    print(f"  patch_count: {turn.patch_count}")
    print(f"  text: {turn.text}")
    print(f"  voice_uri: {turn.voice_uri}")


if __name__ == "__main__":
    main()
