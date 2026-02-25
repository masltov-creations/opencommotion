from __future__ import annotations

from typing import Any

from services.agents.visual.fish_scene import (
    bubble_emitter_particles,
    caustic_phase_value,
    fish_path_spline_point,
    validate_shader_uniforms,
)


def _coerce_curve_points(raw_points: Any, fallback: list[list[float]], trend: str) -> list[list[float]]:
    points: list[list[float]] = []
    source = raw_points if isinstance(raw_points, list) else fallback
    for row in source:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            try:
                x = max(0.0, min(100.0, float(row[0])))
                y = max(0.0, min(100.0, float(row[1])))
            except (TypeError, ValueError):
                continue
            points.append([x, y])

    if len(points) < 2:
        points = [item[:] for item in fallback]

    points.sort(key=lambda item: item[0])
    deduped: list[list[float]] = []
    for x, y in points:
        if deduped and abs(deduped[-1][0] - x) < 1e-6:
            deduped[-1][1] = y
        else:
            deduped.append([x, y])
    points = deduped if len(deduped) >= 2 else [item[:] for item in fallback]

    if trend == "growth":
        adjusted: list[list[float]] = []
        max_y = points[0][1]
        for x, y in points:
            max_y = min(max_y, y)
            adjusted.append([x, max_y])
        points = adjusted
    return [[round(x, 3), round(y, 3)] for x, y in points]


def _coerce_pie_slices(raw_slices: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    source = raw_slices if isinstance(raw_slices, list) else fallback
    for row in source:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip() or "Segment"
        try:
            value = float(row.get("value", 0))
        except (TypeError, ValueError):
            continue
        slices.append({"label": label, "value": max(0.0, value)})

    if not slices:
        slices = [dict(item) for item in fallback]

    total = sum(float(item.get("value", 0.0)) for item in slices)
    if total <= 0:
        return [dict(item) for item in fallback]

    normalized: list[dict[str, Any]] = []
    running = 0
    for idx, item in enumerate(slices):
        if idx == len(slices) - 1:
            value = max(0, 100 - running)
        else:
            value = int(round(float(item["value"]) * 100.0 / total))
            running += value
        normalized.append({"label": str(item["label"]), "value": value})
    return normalized


def _coerce_segment_bars(raw_segments: Any) -> list[dict[str, Any]]:
    fallback = [
        {"label": "Enterprise", "target": 78, "color": "#22d3ee"},
        {"label": "Mid-Market", "target": 63, "color": "#34d399"},
        {"label": "SMB", "target": 49, "color": "#f59e0b"},
    ]
    segments: list[dict[str, Any]] = []
    source = raw_segments if isinstance(raw_segments, list) else fallback
    for row in source:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip() or "Segment"
        color = str(row.get("color", "#22d3ee")).strip() or "#22d3ee"
        try:
            target = float(row.get("target", 0))
        except (TypeError, ValueError):
            continue
        segments.append({"label": label, "target": round(max(0.0, min(100.0, target)), 3), "color": color})
    return segments or fallback


def _coerce_lyrics_words(raw_words: Any) -> list[str]:
    words: list[str] = []
    source = raw_words if isinstance(raw_words, list) else []
    for item in source:
        text = str(item).strip()
        if text:
            words.append(text)
    if not words:
        words = ["The", "cow", "jumps", "over", "the", "moon"]
    return words[:24]


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
            params = stroke.get("params", {})
            trend = str(params.get("trend", "")).strip().lower()
            points = _coerce_curve_points(
                raw_points=params.get("points"),
                fallback=[[0, 90], [20, 80], [40, 61], [60, 48], [80, 30], [100, 15]],
                trend=trend,
            )
            patches.append(
                {
                    "op": "add",
                    "path": "/charts/adoption_curve",
                    "value": {
                        "type": "line",
                        "label": "Adoption",
                        "trend": trend or "neutral",
                        "points": points,
                        "at_ms": start_ms,
                        "duration_ms": duration_ms,
                        "series": params.get("series", "adoption"),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "drawPieSaturation":
            params = stroke.get("params", {})
            slices = _coerce_pie_slices(
                raw_slices=params.get("slices"),
                fallback=[
                    {"label": "Adopted", "value": 68},
                    {"label": "Remaining", "value": 32},
                ],
            )
            patches.append(
                {
                    "op": "add",
                    "path": "/charts/saturation_pie",
                    "value": {
                        "type": "pie",
                        "slices": slices,
                        "at_ms": start_ms,
                        "duration_ms": duration_ms,
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "drawSegmentedAttachBars":
            params = stroke.get("params", {})
            patches.append(
                {
                    "op": "add",
                    "path": "/charts/segmented_attach",
                    "value": {
                        "type": "bar-segmented",
                        "trend": str(params.get("trend", "growth")),
                        "segments": _coerce_segment_bars(params.get("segments")),
                        "at_ms": start_ms,
                        "duration_ms": duration_ms,
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "setLyricsTrack":
            params = stroke.get("params", {})
            words = _coerce_lyrics_words(params.get("words"))
            start = int(params.get("start_ms", start_ms))
            step = max(120, int(params.get("step_ms", 420)))
            items = [{"text": text, "at_ms": start + idx * step} for idx, text in enumerate(words)]
            patches.append(
                {
                    "op": "replace",
                    "path": "/lyrics/words",
                    "value": {
                        "items": items,
                        "start_ms": start,
                        "step_ms": step,
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

        if kind == "setRenderMode":
            mode = str(stroke.get("params", {}).get("mode", "2d")).lower()
            if mode not in {"2d", "3d"}:
                mode = "2d"
            patches.append(
                {
                    "op": "replace",
                    "path": "/render/mode",
                    "value": mode,
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "spawnSceneActor":
            params = stroke.get("params", {})
            actor_id = str(params.get("actor_id", "actor"))
            actor_type = str(params.get("actor_type", "shape"))
            patches.append(
                {
                    "op": "add",
                    "path": f"/actors/{actor_id}",
                    "value": {
                        "type": actor_type,
                        "x": params.get("x", 180),
                        "y": params.get("y", 180),
                        "style": params.get("style", {}),
                    },
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "setActorMotion":
            params = stroke.get("params", {})
            actor_id = str(params.get("actor_id", "actor"))
            motion = params.get("motion", {})
            if isinstance(motion, dict):
                motion_name = str(motion.get("name", "motion"))
                if motion_name == "swim-cycle":
                    points_raw = motion.get("path_points", [[280, 210], [322, 182], [380, 205], [338, 234]])
                    path_points: list[tuple[float, float]] = []
                    for row in points_raw if isinstance(points_raw, list) else []:
                        if isinstance(row, (list, tuple)) and len(row) >= 2:
                            path_points.append((float(row[0]), float(row[1])))
                    if len(path_points) >= 2:
                        sample_points = [fish_path_spline_point(path_points, t / 7.0) for t in range(8)]
                    else:
                        sample_points = [(310.0, 205.0)]
                    motion = {
                        **motion,
                        "sample_points": [[round(x, 2), round(y, 2)] for x, y in sample_points],
                    }
            patches.append(
                {
                    "op": "replace",
                    "path": f"/actors/{actor_id}/motion",
                    "value": motion,
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "setActorAnimation":
            params = stroke.get("params", {})
            actor_id = str(params.get("actor_id", "actor"))
            animation = params.get("animation", {"name": "idle"})
            patches.append(
                {
                    "op": "replace",
                    "path": f"/actors/{actor_id}/animation",
                    "value": animation,
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "emitFx":
            params = stroke.get("params", {})
            fx_id = str(params.get("fx_id", "effect"))
            value: dict[str, Any] = {**params, "type": fx_id}
            if fx_id == "bubble_emitter":
                value["particles"] = bubble_emitter_particles(
                    seed=int(params.get("seed", 42)),
                    count=int(params.get("count", 18)),
                )
            elif fx_id == "caustic_pattern":
                shimmer_period_ms = int(params.get("shimmer_period_ms", 2300))
                value["phase"] = round(caustic_phase_value(start_ms, shimmer_period_ms), 5)
            patches.append(
                {
                    "op": "add",
                    "path": f"/fx/{fx_id}",
                    "value": value,
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "setEnvironmentMood":
            patches.append(
                {
                    "op": "replace",
                    "path": "/environment/mood",
                    "value": stroke.get("params", {}).get("mood", {}),
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "setCameraMove":
            patches.append(
                {
                    "op": "replace",
                    "path": "/camera/motion",
                    "value": stroke.get("params", {}),
                    "at_ms": start_ms,
                }
            )
            continue

        if kind == "applyMaterialFx":
            params = stroke.get("params", {})
            material_id = str(params.get("material_id", "material"))
            shader_id = str(params.get("shader_id", ""))
            uniforms = params.get("uniforms", {})
            ok, reason, sanitized = validate_shader_uniforms(shader_id=shader_id, uniforms=uniforms)
            if ok:
                patches.append(
                    {
                        "op": "replace",
                        "path": f"/materials/{material_id}",
                        "value": {
                            "shader_id": shader_id,
                            "uniforms": sanitized,
                            "fallback": False,
                        },
                        "at_ms": start_ms,
                    }
                )
            else:
                patches.extend(
                    [
                        {
                            "op": "replace",
                            "path": f"/materials/{material_id}",
                            "value": {
                                "shader_id": "flat_fallback",
                                "uniforms": {},
                                "fallback": True,
                                "reason": reason or "shader_validation_failed",
                            },
                            "at_ms": start_ms,
                        },
                        {
                            "op": "add",
                            "path": "/annotations/-",
                            "value": {
                                "text": f"Material fallback for {material_id}: {reason or 'shader_validation_failed'}",
                                "style": "warning",
                            },
                            "at_ms": start_ms,
                        },
                    ]
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
