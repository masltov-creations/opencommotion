from __future__ import annotations

from typing import Any


def compile_brush_batch(strokes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    for stroke in strokes:
        kind = stroke.get("kind", "")
        timing = stroke.get("timing", {})
        start_ms = int(timing.get("start_ms", 0))
        duration_ms = int(timing.get("duration_ms", 600))

        if kind == "spawnCharacter":
            actor_id = stroke.get("params", {}).get("actor_id", "guide")
            patches.append(
                {
                    "op": "add",
                    "path": f"/actors/{actor_id}",
                    "value": {
                        "type": "character",
                        "x": stroke.get("params", {}).get("x", 180),
                        "y": stroke.get("params", {}).get("y", 190),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "animateMoonwalk":
            actor_id = stroke.get("params", {}).get("actor_id", "guide")
            patches.append(
                {
                    "op": "replace",
                    "path": f"/actors/{actor_id}/animation",
                    "value": {
                        "name": "moonwalk",
                        "duration_ms": duration_ms,
                        "easing": timing.get("easing", "easeInOutCubic"),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "orbitGlobe":
            patches.extend(
                [
                    {
                        "op": "add",
                        "path": "/actors/globe",
                        "value": {"type": "globe", "x": 410, "y": 150},
                        "at_ms": start_ms,
                    },
                    {
                        "op": "add",
                        "path": "/actors/ufo",
                        "value": {
                            "type": "ufo",
                            "motion": "orbit",
                            "radius": stroke.get("params", {}).get("radius", 75),
                        },
                        "at_ms": start_ms + 40,
                    },
                ]
            )
            continue

        if kind == "ufoLandingBeat":
            patches.append(
                {
                    "op": "replace",
                    "path": "/actors/ufo/motion",
                    "value": {
                        "name": "landing",
                        "duration_ms": duration_ms,
                        "beam": True,
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "drawAdoptionCurve":
            patches.append(
                {
                    "op": "add",
                    "path": "/charts/adoption_curve",
                    "value": {
                        "type": "line",
                        "label": "Adoption",
                        "points": stroke.get("params", {}).get(
                            "points", [[0, 90], [20, 80], [40, 61], [60, 48], [80, 30], [100, 15]]
                        ),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "drawPieSaturation":
            patches.append(
                {
                    "op": "add",
                    "path": "/charts/saturation_pie",
                    "value": {
                        "type": "pie",
                        "slices": stroke.get("params", {}).get(
                            "slices",
                            [
                                {"label": "Adopted", "value": 68},
                                {"label": "Remaining", "value": 32},
                            ],
                        ),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "annotateInsight":
            patches.append(
                {
                    "op": "add",
                    "path": "/annotations/-",
                    "value": {
                        "text": stroke.get("params", {}).get("text", "Insight"),
                        "style": "callout",
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "sceneMorph":
            patches.append(
                {
                    "op": "replace",
                    "path": "/scene/transition",
                    "value": {
                        "name": "morph",
                        "duration_ms": duration_ms,
                        "easing": timing.get("easing", "easeInOutQuart"),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        patches.append(
            {
                "op": "add",
                "path": "/annotations/-",
                "value": {"text": f"Unsupported stroke kind: {kind}", "style": "warning"},
                "at_ms": start_ms,
            }
        )

    return patches
