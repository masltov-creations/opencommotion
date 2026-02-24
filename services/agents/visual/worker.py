from __future__ import annotations


def generate_visual_strokes(prompt: str) -> list[dict]:
    p = prompt.lower()
    strokes: list[dict] = [
        {
            "stroke_id": "spawn-guide",
            "kind": "spawnCharacter",
            "params": {"actor_id": "guide", "x": 180, "y": 190},
            "timing": {"start_ms": 0, "duration_ms": 200, "easing": "easeOutCubic"},
        }
    ]

    if "moonwalk" in p:
        strokes.append(
            {
                "stroke_id": "moonwalk-guide",
                "kind": "animateMoonwalk",
                "params": {"actor_id": "guide"},
                "timing": {"start_ms": 250, "duration_ms": 1300, "easing": "easeInOutCubic"},
            }
        )

    if "globe" in p or "ufo" in p:
        strokes.extend(
            [
                {
                    "stroke_id": "orbit-globe",
                    "kind": "orbitGlobe",
                    "params": {"radius": 82},
                    "timing": {"start_ms": 300, "duration_ms": 1200, "easing": "linear"},
                },
                {
                    "stroke_id": "ufo-landing",
                    "kind": "ufoLandingBeat",
                    "params": {},
                    "timing": {"start_ms": 1400, "duration_ms": 1000, "easing": "easeInQuart"},
                },
            ]
        )

    if "chart" in p or "adoption" in p or "pie" in p:
        strokes.extend(
            [
                {
                    "stroke_id": "chart-line",
                    "kind": "drawAdoptionCurve",
                    "params": {},
                    "timing": {"start_ms": 200, "duration_ms": 900, "easing": "easeOutQuart"},
                },
                {
                    "stroke_id": "chart-pie",
                    "kind": "drawPieSaturation",
                    "params": {},
                    "timing": {"start_ms": 1100, "duration_ms": 800, "easing": "easeOutCubic"},
                },
            ]
        )

    strokes.append(
        {
            "stroke_id": "insight",
            "kind": "annotateInsight",
            "params": {"text": "Synchronized visual cue active."},
            "timing": {"start_ms": 150, "duration_ms": 150, "easing": "linear"},
        }
    )
    return strokes
