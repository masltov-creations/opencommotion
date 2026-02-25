#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from services.agents.visual.quality import evaluate_market_growth_scene


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate market-growth graph compatibility for an orchestrated turn.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Gateway base URL.")
    parser.add_argument("--api-key", default="dev-opencommotion-key", help="Gateway API key.")
    parser.add_argument("--session", default="graph-eval", help="Session id for the orchestrate call.")
    parser.add_argument(
        "--prompt",
        default=(
            "animated presentation showcasing market growth and increases in segmented attach within certain markets; "
            "graphs should grow as the time tick proceeds across the timeline"
        ),
        help="Prompt to evaluate.",
    )
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="Run gateway+orchestrator in-process for evaluation instead of calling a live server.",
    )
    return parser.parse_args()


def _inprocess_turn(payload: dict) -> tuple[int, dict]:
    from fastapi.testclient import TestClient

    from services.gateway.app import main as gateway_main
    from services.orchestrator.app.main import app as orchestrator_app

    original_async_client = gateway_main.httpx.AsyncClient

    class RoutedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            timeout = kwargs.get("timeout", 20)
            self._client = original_async_client(
                timeout=timeout,
                transport=gateway_main.httpx.ASGITransport(app=orchestrator_app),
                base_url="http://127.0.0.1:8001",
            )

        async def __aenter__(self):
            await self._client.__aenter__()
            return self._client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return await self._client.__aexit__(exc_type, exc_val, exc_tb)

    gateway_main.httpx.AsyncClient = RoutedAsyncClient
    client = TestClient(gateway_main.app)
    response = client.post("/v1/orchestrate", json=payload)
    return response.status_code, response.json()


def main() -> int:
    args = parse_args()
    headers = {"content-type": "application/json"}
    if args.api_key:
        headers["x-api-key"] = args.api_key

    payload = {"session_id": args.session, "prompt": args.prompt}
    if args.inprocess:
        status_code, turn = _inprocess_turn(payload)
    else:
        try:
            response = httpx.post(
                f"{args.base_url.rstrip('/')}/v1/orchestrate",
                headers=headers,
                json=payload,
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"request failed: {exc}", file=sys.stderr)
            print("tip: rerun with --inprocess to evaluate without a running stack.", file=sys.stderr)
            return 2
        status_code = response.status_code
        turn = response.json() if response.content else {}

    if status_code != 200:
        print(f"orchestrate failed ({status_code}): {json.dumps(turn)}", file=sys.stderr)
        return 2

    report = turn.get("quality_report")
    if not isinstance(report, dict):
        report = evaluate_market_growth_scene(turn.get("visual_patches", []))

    print(json.dumps({"turn_id": turn.get("turn_id"), "quality_report": report}, indent=2))
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
