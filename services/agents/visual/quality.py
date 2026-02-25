from __future__ import annotations

from typing import Any


def _latest_patch_value(patches: list[dict[str, Any]], path: str) -> Any:
    latest_value: Any = None
    latest_at = -1
    for patch in patches:
        if str(patch.get("path")) != path:
            continue
        at_ms = int(patch.get("at_ms", 0))
        if at_ms < latest_at:
            continue
        op = str(patch.get("op", "add"))
        latest_at = at_ms
        latest_value = None if op == "remove" else patch.get("value")
    return latest_value


def evaluate_market_growth_scene(patches: list[dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    render_mode = _latest_patch_value(patches, "/render/mode")
    if render_mode in {"2d", "3d"}:
        checks.append("render_mode_valid")
    else:
        warnings.append("render_mode_missing_or_invalid")

    line = _latest_patch_value(patches, "/charts/adoption_curve")
    if not isinstance(line, dict):
        failures.append("missing_adoption_curve_chart")
        line = {}
    points = line.get("points", []) if isinstance(line, dict) else []
    if not isinstance(points, list) or len(points) < 2:
        failures.append("adoption_curve_points_insufficient")
    else:
        parsed: list[tuple[float, float]] = []
        for row in points:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            try:
                parsed.append((float(row[0]), float(row[1])))
            except (TypeError, ValueError):
                continue
        if len(parsed) < 2:
            failures.append("adoption_curve_points_invalid")
        else:
            if all(parsed[idx + 1][0] > parsed[idx][0] for idx in range(len(parsed) - 1)):
                checks.append("adoption_curve_x_monotonic")
            else:
                failures.append("adoption_curve_x_not_monotonic")

            # In this coordinate system smaller y means higher visual growth.
            if all(parsed[idx + 1][1] <= parsed[idx][1] for idx in range(len(parsed) - 1)):
                checks.append("adoption_curve_growth_trend")
            else:
                failures.append("adoption_curve_not_growth_trend")

    if isinstance(line, dict):
        duration_ms = int(line.get("duration_ms", 0) or 0)
        if duration_ms > 0:
            checks.append("adoption_curve_timeline_duration")
        else:
            failures.append("adoption_curve_missing_duration")

    pie = _latest_patch_value(patches, "/charts/saturation_pie")
    if not isinstance(pie, dict):
        warnings.append("missing_saturation_pie")
    else:
        slices = pie.get("slices", [])
        if isinstance(slices, list) and slices:
            total = 0
            for row in slices:
                if isinstance(row, dict):
                    try:
                        total += int(round(float(row.get("value", 0))))
                    except (TypeError, ValueError):
                        pass
            if total == 100:
                checks.append("pie_segments_sum_100")
            else:
                failures.append("pie_segments_not_100")
        else:
            failures.append("pie_segments_missing")

    segmented = _latest_patch_value(patches, "/charts/segmented_attach")
    if not isinstance(segmented, dict):
        failures.append("missing_segmented_attach_chart")
    else:
        segments = segmented.get("segments", [])
        if not isinstance(segments, list) or len(segments) < 2:
            failures.append("segmented_attach_segments_insufficient")
        else:
            good_targets = 0
            for row in segments:
                if not isinstance(row, dict):
                    continue
                try:
                    target = float(row.get("target", 0))
                except (TypeError, ValueError):
                    continue
                if 0 <= target <= 100:
                    good_targets += 1
            if good_targets >= 2:
                checks.append("segmented_attach_targets_valid")
            else:
                failures.append("segmented_attach_targets_invalid")

        seg_duration_ms = int(segmented.get("duration_ms", 0) or 0)
        if seg_duration_ms > 0:
            checks.append("segmented_attach_timeline_duration")
        else:
            failures.append("segmented_attach_missing_duration")

    return {
        "ok": len(failures) == 0,
        "checks": checks,
        "warnings": warnings,
        "failures": failures,
    }
