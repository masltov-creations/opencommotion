#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenCommotion turn client configured for openclaw-cli provider")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--session", default="openclaw-cli-demo")
    parser.add_argument("--prompt", default="ufo landing with pie chart and narrated insight")
    parser.add_argument("--api-key", default=os.getenv("OPENCOMMOTION_GATEWAY_API_KEY", "dev-opencommotion-key"))
    parser.add_argument("--openclaw-bin", default=os.getenv("OPENCOMMOTION_OPENCLAW_BIN", "openclaw"))
    parser.add_argument("--openclaw-session-prefix", default=os.getenv("OPENCOMMOTION_OPENCLAW_SESSION_PREFIX", "opencommotion"))
    parser.add_argument("--skip-setup", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gateway = args.gateway.rstrip("/")
    headers = {"x-api-key": args.api_key, "content-type": "application/json"} if args.api_key else {"content-type": "application/json"}

    with httpx.Client(timeout=45.0) as client:
        if not args.skip_setup:
            setup_payload = {
                "values": {
                    "OPENCOMMOTION_LLM_PROVIDER": "openclaw-cli",
                    "OPENCOMMOTION_OPENCLAW_BIN": args.openclaw_bin,
                    "OPENCOMMOTION_OPENCLAW_SESSION_PREFIX": args.openclaw_session_prefix,
                }
            }
            setup = client.post(f"{gateway}/v1/setup/state", headers=headers, json=setup_payload)
            setup.raise_for_status()

        orchestrate = client.post(
            f"{gateway}/v2/orchestrate",
            headers=headers,
            json={"session_id": args.session, "scene_id": f"scene-{args.session}", "base_revision": 0, "prompt": args.prompt},
        )
        orchestrate.raise_for_status()
        turn = orchestrate.json()

    segments = turn.get("voice", {}).get("segments", [])
    summary = {
        "provider": "openclaw-cli",
        "session_id": turn.get("session_id"),
        "turn_id": turn.get("turn_id"),
        "patch_count": len(turn.get("patches", []) or turn.get("legacy_visual_patches", []) or turn.get("visual_patches", [])),
        "voice_uri": segments[0].get("audio_uri", "") if segments else "",
        "text": turn.get("text", ""),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
