#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


@dataclass
class ProbeCase:
    name: str
    prompt: str
    expected_paths: list[str]
    required: bool
    notes: str


def _seeded_cases(seed: int) -> list[ProbeCase]:
    random.seed(seed)
    creative_adjectives = ["neon", "quiet", "stormy", "minimalist", "retro"]
    moods = ["dawn", "dusk", "midnight", "rainy noon", "golden hour"]
    cities = ["skyline", "harbor", "desert town", "forest clearing", "spaceport"]
    adjective = random.choice(creative_adjectives)
    mood = random.choice(moods)
    place = random.choice(cities)

    return [
        ProbeCase(
            name="scenario-c-market-growth",
            prompt=(
                "animated presentation showcasing market growth and increases in segmented attach "
                "within certain markets; graphs should grow as timeline tick proceeds"
            ),
            expected_paths=["/charts/adoption_curve", "/charts/saturation_pie", "/charts/segmented_attach"],
            required=True,
            notes="Core scenario C requirement.",
        ),
        ProbeCase(
            name="scenario-d-fish-bowl-3d",
            prompt=(
                "3d fish bowl cinematic with refraction-like glass, water shimmer, bubbles, plant sway, "
                "and day-to-dusk mood progression"
            ),
            expected_paths=["/actors/fish_bowl", "/actors/goldfish", "/fx/bubble_emitter", "/render/mode"],
            required=True,
            notes="Core scenario D stretch requirement when enabled.",
        ),
        ProbeCase(
            name="scenario-a-cow-moon-lyric",
            prompt=(
                "A cow jumps over the moon while the phrase 'The cow jumps over the moon' appears with "
                "a bouncing ball synced to each word"
            ),
            expected_paths=["/actors/cow", "/actors/moon", "/lyrics/words", "/fx/bouncing_ball"],
            required=True,
            notes="Scenario A requirement in visual plan.",
        ),
        ProbeCase(
            name="scenario-b-day-night",
            prompt="Elegant scene transitioning from day to night with smooth lighting progression.",
            expected_paths=["/environment/mood", "/scene/transition"],
            required=True,
            notes="Scenario B requirement in visual plan.",
        ),
        ProbeCase(
            name="legacy-ufo-chart",
            prompt="show a moonwalk, orbiting globe, ufo landing, and adoption pie chart",
            expected_paths=["/actors/ufo", "/charts/adoption_curve", "/charts/saturation_pie"],
            required=True,
            notes="Legacy baseline behavior should remain stable.",
        ),
        ProbeCase(
            name="random-creative",
            prompt=f"{adjective} jellyfish over a {place} during {mood} with ambient narration",
            expected_paths=["/render/mode"],
            required=False,
            notes="Exploratory random prompt. Misses here are usually enhancement candidates.",
        ),
    ]


def _orchestrate_live(base_url: str, api_key: str, session_id: str, prompt: str) -> tuple[int, dict[str, Any]]:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    payload = {"session_id": session_id, "prompt": prompt}
    response = httpx.post(f"{base_url.rstrip('/')}/v1/orchestrate", headers=headers, json=payload, timeout=60)
    body = response.json() if response.content else {}
    return response.status_code, body


def _orchestrate_inprocess(session_id: str, prompt: str) -> tuple[int, dict[str, Any]]:
    from fastapi.testclient import TestClient

    from services.gateway.app import main as gateway_main
    from services.orchestrator.app.main import app as orchestrator_app

    if not hasattr(gateway_main, "_probe_original_async_client"):
        gateway_main._probe_original_async_client = gateway_main.httpx.AsyncClient  # type: ignore[attr-defined]
    original_async_client = gateway_main._probe_original_async_client  # type: ignore[attr-defined]

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

    if gateway_main.httpx.AsyncClient is not RoutedAsyncClient:
        gateway_main.httpx.AsyncClient = RoutedAsyncClient
    client = TestClient(gateway_main.app)
    response = client.post("/v1/orchestrate", json={"session_id": session_id, "prompt": prompt})
    return response.status_code, response.json()


def _extract_paths(patches: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for patch in patches:
        path = str(patch.get("path", ""))
        if not path:
            continue
        if path.startswith("/actors/"):
            parts = path.split("/")
            if len(parts) >= 3:
                paths.add("/actors/" + parts[2])
        elif path.startswith("/charts/"):
            parts = path.split("/")
            if len(parts) >= 3:
                paths.add("/charts/" + parts[2])
        elif path.startswith("/fx/"):
            parts = path.split("/")
            if len(parts) >= 3:
                paths.add("/fx/" + parts[2])
        else:
            paths.add(path)
    return paths


def run_probe(base_url: str, api_key: str, seed: int, inprocess: bool) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    required_failures = 0
    enhancement_candidates = 0
    bug_candidates = 0

    for idx, case in enumerate(_seeded_cases(seed), start=1):
        session_id = f"probe-{idx}"
        if inprocess:
            status_code, body = _orchestrate_inprocess(session_id=session_id, prompt=case.prompt)
        else:
            status_code, body = _orchestrate_live(base_url=base_url, api_key=api_key, session_id=session_id, prompt=case.prompt)
        patches = body.get("visual_patches", []) if isinstance(body, dict) else []
        present = _extract_paths(patches if isinstance(patches, list) else [])
        missing = sorted(path for path in case.expected_paths if path not in present)

        outcome = "pass"
        triage = "none"
        if status_code != 200:
            outcome = "fail"
            triage = "bug_candidate" if case.required else "enhancement_candidate"
        elif missing:
            outcome = "fail"
            if case.required:
                triage = "bug_candidate"
            else:
                triage = "enhancement_candidate"
        if case.required and outcome == "fail":
            required_failures += 1
        if triage == "bug_candidate":
            bug_candidates += 1
        if triage == "enhancement_candidate":
            enhancement_candidates += 1

        rows.append(
            {
                "name": case.name,
                "required": case.required,
                "notes": case.notes,
                "status_code": status_code,
                "prompt": case.prompt,
                "expected_paths": case.expected_paths,
                "present_paths": sorted(present),
                "missing_paths": missing,
                "quality_report": body.get("quality_report") if isinstance(body, dict) else None,
                "outcome": outcome,
                "triage": triage,
            }
        )

    summary = {
        "seed": seed,
        "total_cases": len(rows),
        "required_failures": required_failures,
        "bug_candidates": bug_candidates,
        "enhancement_candidates": enhancement_candidates,
    }
    return {"summary": summary, "cases": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run seeded random prompt compatibility probe.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="dev-opencommotion-key")
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--out", default="runtime/prompt-probe/latest.json")
    parser.add_argument("--inprocess", action="store_true", help="Run gateway/orchestrator in-process without a live stack.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_probe(base_url=args.base_url, api_key=args.api_key, seed=args.seed, inprocess=args.inprocess)
    except Exception as exc:  # noqa: BLE001
        print(f"probe failed: {exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"report_written: {out_path}")
    return 0 if report["summary"]["required_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
