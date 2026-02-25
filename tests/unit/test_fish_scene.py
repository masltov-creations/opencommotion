from __future__ import annotations

from services.agents.visual.fish_scene import (
    bubble_emitter_particles,
    caustic_phase_value,
    fish_path_spline_point,
    validate_shader_uniforms,
)


def test_fish_path_spline_returns_stable_points() -> None:
    points = [(280.0, 210.0), (322.0, 182.0), (380.0, 205.0), (338.0, 234.0)]
    at_start = fish_path_spline_point(points, 0.0)
    at_mid = fish_path_spline_point(points, 0.5)
    at_end = fish_path_spline_point(points, 1.0)
    assert isinstance(at_start[0], float)
    assert isinstance(at_mid[1], float)
    # closed-loop semantics: start and end should be near each other
    assert abs(at_start[0] - at_end[0]) < 1.0
    assert abs(at_start[1] - at_end[1]) < 1.0


def test_bubble_emitter_is_deterministic_by_seed() -> None:
    first = bubble_emitter_particles(seed=42, count=8)
    second = bubble_emitter_particles(seed=42, count=8)
    third = bubble_emitter_particles(seed=43, count=8)
    assert first == second
    assert first != third


def test_shader_uniform_validation_and_fallback_path() -> None:
    ok, reason, uniforms = validate_shader_uniforms(
        shader_id="glass_refraction_like",
        uniforms={"ior": 1.22, "distortion": 0.11, "rim_strength": 0.4},
    )
    assert ok is True
    assert reason is None
    assert uniforms["ior"] == 1.22

    bad_ok, bad_reason, bad_uniforms = validate_shader_uniforms(
        shader_id="glass_refraction_like",
        uniforms={"ior": 4.7},
    )
    assert bad_ok is False
    assert bad_reason is not None
    assert bad_uniforms == {}


def test_caustic_phase_mapping_is_continuous() -> None:
    period = 2300
    samples = [caustic_phase_value(ms, period) for ms in range(0, 2000, 50)]
    assert all(0.0 <= value <= 1.0 for value in samples)
    deltas = [abs(samples[idx + 1] - samples[idx]) for idx in range(len(samples) - 1)]
    assert max(deltas) < 0.12
