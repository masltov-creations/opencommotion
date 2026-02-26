#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenCommotion turn client configured for openclaw-openai provider")
    parser.add_argument("--gateway", default="http://127.0.0.1:8000")
    parser.add_argument("--session", default="openclaw-openai-demo")
    parser.add_argument("--prompt", default="orbiting globe with adoption curve and crisp narration")
    parser.add_argument("--api-key", default=os.getenv("OPENCOMMOTION_GATEWAY_API_KEY", "dev-opencommotion-key"))
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL", os.getenv("OPENCOMMOTION_OPENAI_BASE_URL", "http://127.0.0.1:8002/v1")),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENCOMMOTION_OPENCLAW_OPENAI_MODEL", os.getenv("OPENCOMMOTION_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")),
    )
    parser.add_argument(
        "--provider-api-key",
        default=os.getenv("OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY", os.getenv("OPENCOMMOTION_OPENAI_API_KEY", "")),
    )
    parser.add_argument("--skip-setup", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gateway = args.gateway.rstrip("/")
    headers = {"x-api-key": args.api_key, "content-type": "application/json"} if args.api_key else {"content-type": "application/json"}

    with httpx.Client(timeout=35.0) as client:
        if not args.skip_setup:
            setup_payload = {
                "values": {
                    "OPENCOMMOTION_LLM_PROVIDER": "openclaw-openai",
                    "OPENCOMMOTION_OPENCLAW_OPENAI_BASE_URL": args.base_url,
                    "OPENCOMMOTION_OPENCLAW_OPENAI_MODEL": args.model,
                    "OPENCOMMOTION_OPENCLAW_OPENAI_API_KEY": args.provider_api_key,
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
        "provider": "openclaw-openai",
        "session_id": turn.get("session_id"),
        "turn_id": turn.get("turn_id"),
        "patch_count": len(turn.get("patches", []) or turn.get("legacy_visual_patches", []) or turn.get("visual_patches", [])),
        "voice_uri": segments[0].get("audio_uri", "") if segments else "",
        "text": turn.get("text", ""),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
