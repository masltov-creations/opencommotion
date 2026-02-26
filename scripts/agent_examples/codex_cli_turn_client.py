#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

import httpx


def _request_json(client: httpx.Client, method: str, url: str, op: str, **kwargs) -> dict:
    response = client.request(method, url, **kwargs)
    if response.is_success:
        return response.json()
    detail = response.text
    try:
        payload = response.json()
        detail_obj = payload.get("detail", payload)
        detail = json.dumps(detail_obj)
    except Exception:  # noqa: BLE001
        pass
    raise RuntimeError(f"{op} failed ({response.status_code}): {detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenCommotion turn client configured for codex-cli provider")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--session", default="codex-cli-demo")
    parser.add_argument("--prompt", default="moonwalk adoption chart with concise narration")
    parser.add_argument("--api-key", default=os.getenv("OPENCOMMOTION_GATEWAY_API_KEY", "dev-opencommotion-key"))
    parser.add_argument("--codex-bin", default=os.getenv("OPENCOMMOTION_CODEX_BIN", "codex"))
    parser.add_argument("--codex-model", default=os.getenv("OPENCOMMOTION_CODEX_MODEL", ""))
    parser.add_argument("--skip-setup", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gateway = args.gateway.rstrip("/")
    headers = {"x-api-key": args.api_key, "content-type": "application/json"} if args.api_key else {"content-type": "application/json"}

    with httpx.Client(timeout=30.0) as client:
        if not args.skip_setup:
            setup_payload = {
                "values": {
                    "OPENCOMMOTION_LLM_PROVIDER": "codex-cli",
                    "OPENCOMMOTION_CODEX_BIN": args.codex_bin,
                    "OPENCOMMOTION_CODEX_MODEL": args.codex_model,
                }
            }
            _request_json(
                client,
                "POST",
                f"{gateway}/v1/setup/state",
                "setup",
                headers=headers,
                json=setup_payload,
            )

        turn = _request_json(
            client,
            "POST",
            f"{gateway}/v2/orchestrate",
            "orchestrate",
            headers=headers,
            json={"session_id": args.session, "scene_id": f"scene-{args.session}", "base_revision": 0, "prompt": args.prompt},
        )

    segments = turn.get("voice", {}).get("segments", [])
    summary = {
        "provider": "codex-cli",
        "session_id": turn.get("session_id"),
        "turn_id": turn.get("turn_id"),
        "patch_count": len(turn.get("patches", []) or turn.get("legacy_visual_patches", []) or turn.get("visual_patches", [])),
        "voice_uri": segments[0].get("audio_uri", "") if segments else "",
        "text": turn.get("text", ""),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
