from __future__ import annotations

from services.agents.visual.quality import evaluate_market_growth_scene


def test_market_growth_quality_passes_valid_payload() -> None:
    report = evaluate_market_growth_scene(
        [
            {"op": "replace", "path": "/render/mode", "value": "2d", "at_ms": 0},
            {
                "op": "add",
                "path": "/charts/adoption_curve",
                "value": {
                    "type": "line",
                    "trend": "growth",
                    "points": [[0, 90], [20, 75], [40, 60], [60, 48], [80, 33], [100, 20]],
                    "at_ms": 200,
                    "duration_ms": 1400,
                },
                "at_ms": 200,
            },
            {
                "op": "add",
                "path": "/charts/saturation_pie",
                "value": {"type": "pie", "slices": [{"label": "A", "value": 55}, {"label": "B", "value": 45}]},
                "at_ms": 400,
            },
            {
                "op": "add",
                "path": "/charts/segmented_attach",
                "value": {
                    "type": "bar-segmented",
                    "segments": [
                        {"label": "Enterprise", "target": 82},
                        {"label": "SMB", "target": 61},
                    ],
                    "duration_ms": 2100,
                },
                "at_ms": 600,
            },
        ]
    )
    assert report["ok"] is True


def test_market_growth_quality_flags_common_mistakes() -> None:
    report = evaluate_market_growth_scene(
        [
            {
                "op": "add",
                "path": "/charts/adoption_curve",
                "value": {"type": "line", "points": [[0, 40], [50, 80], [40, 20]], "duration_ms": 0},
                "at_ms": 100,
            },
            {
                "op": "add",
                "path": "/charts/saturation_pie",
                "value": {"type": "pie", "slices": [{"label": "A", "value": 30}, {"label": "B", "value": 30}]},
                "at_ms": 140,
            },
        ]
    )
    assert report["ok"] is False
    assert "adoption_curve_x_not_monotonic" in report["failures"]
    assert "pie_segments_not_100" in report["failures"]
    assert "missing_segmented_attach_chart" in report["failures"]
