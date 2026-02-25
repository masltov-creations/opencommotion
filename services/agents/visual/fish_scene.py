from __future__ import annotations

import math
import random
from typing import Any

_SHADER_UNIFORM_LIMITS: dict[str, dict[str, tuple[float, float]]] = {
    "glass_refraction_like": {
        "ior": (1.0, 1.6),
        "distortion": (0.0, 0.35),
        "rim_strength": (0.0, 1.0),
    },
    "water_volume_tint": {
        "density": (0.0, 1.0),
        "blue_shift": (0.0, 1.0),
    },
    "caustic_overlay_shader": {
        "intensity": (0.0, 1.0),
        "scale": (0.1, 4.0),
        "speed": (0.05, 3.0),
    },
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def fish_path_spline_point(points: list[tuple[float, float]], t: float) -> tuple[float, float]:
    """Evaluate a closed-loop Catmull-Rom spline in normalized t=[0,1]."""
    if len(points) < 2:
        raise ValueError("fish path requires at least two points")

    if len(points) == 2:
        t_norm = _clamp(float(t), 0.0, 1.0)
        x = points[0][0] + (points[1][0] - points[0][0]) * t_norm
        y = points[0][1] + (points[1][1] - points[0][1]) * t_norm
        return (x, y)

    t_norm = _clamp(float(t), 0.0, 1.0)
    count = len(points)
    total = t_norm * count
    idx = int(math.floor(total)) % count
    local_t = total - math.floor(total)

    p0 = points[(idx - 1) % count]
    p1 = points[idx % count]
    p2 = points[(idx + 1) % count]
    p3 = points[(idx + 2) % count]

    tt = local_t * local_t
    ttt = tt * local_t

    x = 0.5 * (
        (2 * p1[0])
        + (-p0[0] + p2[0]) * local_t
        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * tt
        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * ttt
    )
    y = 0.5 * (
        (2 * p1[1])
        + (-p0[1] + p2[1]) * local_t
        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * tt
        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * ttt
    )
    return (x, y)


def bubble_emitter_particles(seed: int, count: int) -> list[dict[str, float]]:
    rng = random.Random(int(seed))
    particles: list[dict[str, float]] = []
    for idx in range(max(0, int(count))):
        particles.append(
            {
                "id": float(idx),
                "x": rng.uniform(0.26, 0.74),
                "start_y": rng.uniform(0.62, 0.9),
                "size": rng.uniform(2.0, 7.0),
                "rise_per_s": rng.uniform(0.04, 0.16),
                "drift": rng.uniform(-0.035, 0.035),
                "phase": rng.uniform(0.0, 1.0),
            }
        )
    return particles


def caustic_phase_value(at_ms: int, shimmer_period_ms: int) -> float:
    period = max(1, int(shimmer_period_ms))
    angle = (2.0 * math.pi * (float(at_ms) % period)) / float(period)
    return 0.5 + 0.5 * math.sin(angle)


def validate_shader_uniforms(
    shader_id: str,
    uniforms: dict[str, Any] | None,
) -> tuple[bool, str | None, dict[str, float]]:
    limits = _SHADER_UNIFORM_LIMITS.get(shader_id)
    if not limits:
        return False, "shader_not_whitelisted", {}

    values = uniforms or {}
    sanitized: dict[str, float] = {}
    for key, (lo, hi) in limits.items():
        raw = values.get(key, (lo + hi) / 2.0)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return False, f"uniform_not_numeric:{key}", {}
        if value < lo or value > hi:
            return False, f"uniform_out_of_range:{key}", {}
        sanitized[key] = value
    return True, None, sanitized
