# Tool Enhancement Backlog

Updated: 2026-02-25

Purpose:
- Track discovered tool gaps that block or degrade baseline requirements.
- Keep these gaps visible in release planning until closed with evidence.

How to use:
1. Add a new row when a requirement is unmet due to tool limitation.
2. Include concrete impact and acceptance criteria.
3. Mark status only when tests/evidence prove closure.

Statuses:
- `open`: identified, not yet implemented.
- `in_progress`: implementation started.
- `blocked`: cannot proceed due to dependency.
- `done`: implemented and validated.

## Active Items

| ID | Area | Requirement Impact | Enhancement Needed | Owner | Status | Severity | Acceptance Criteria |
|---|---|---|---|---|---|---|---|
| TE-001 | Visual Runtime 3D | Full 3D scenario certification (A/B/C/D-3D) | Replace SVG-based 3D simulation with true 3D scene runtime (mesh/camera/light pipeline). | visual-runtime | open | high | 3D scenarios render with true geometry/camera/light and pass scenario certification tests. |
| TE-002 | Shader Runtime | Robust material effects with budget control | Add shader compilation/execution layer with budget metrics and fallback telemetry. | visual-runtime | open | high | Shader whitelist + uniform validation + runtime budget checks + fallback reason metrics exposed. |
| TE-003 | Visual QA Tooling | End-to-end visual compatibility for all scenarios | Extend quality evaluator beyond market graphs to scenario-level checks (A/B/C/D in 2D+3D). | qa-automation | in_progress | high | `quality_report` coverage for all scenario families and CI pass/fail gates wired. |
| TE-004 | Visual Regression | Detect rendering drift across updates | Add deterministic frame-capture + golden-image diff workflow for scene checkpoints. | qa-automation | open | medium | CI job compares key frames and fails on threshold violations. |
| TE-005 | Agent Prompt Tooling | Agent consistency across scenarios | Add prompt-to-primitive linting tool to detect missing required tracks (`actors/fx/materials/camera/environment`). | agent-runtime | open | medium | Lint command flags missing primitives before orchestration and integrates into examples/tests. |
| TE-008 | Open-Vocabulary Prompt Coverage | Exploratory prompts degrade to generic guide-only scene | Add fallback semantic mapper for unseen nouns/themes (e.g., jellyfish, skyline) into generic primitives. | agent-runtime | open | low | Random-prompt probe yields at least one non-generic scene primitive for exploratory prompts without breaking required scenarios. |

## Recently Closed

| ID | Area | Closure Summary | Evidence |
|---|---|---|---|
| TE-000 | Market Graph Compatibility | Added compiler hardening + compatibility evaluator + gateway `quality_report`. | `tests/unit/test_visual_quality.py`, `tests/integration/test_gateway_contracts.py`, `scripts/evaluate_market_graph.py` |
| TE-006 | Scenario A Tooling Gap | Implemented cow/moon lyric scene support with lyric track + bouncing ball FX and UI/runtime rendering. | `tests/unit/test_visual_worker.py`, `tests/unit/test_brush_compiler.py`, `tests/integration/test_orchestrate_path.py`, `runtime/prompt-probe/latest.json` |
| TE-007 | Scenario B Tooling Gap | Implemented day/night semantic mapping to environment mood + scene transition tracks. | `tests/unit/test_visual_worker.py`, `tests/integration/test_orchestrate_path.py`, `runtime/prompt-probe/latest.json` |

## Triage Notes

Latest prompt probe:
- Command: `python3 scripts/prompt_compat_probe.py --inprocess --seed 23`
- Report: `runtime/prompt-probe/latest.json`
- Summary:
  - required failures: 0
  - bug candidates: 0
  - enhancement candidates: 1
- Additional randomized seeds:
  - `seed7`: required failures 0, enhancement candidates 1 (`runtime/prompt-probe/seed7.json`)
  - `seed19`: required failures 0, enhancement candidates 1 (`runtime/prompt-probe/seed19.json`)
  - `seed31`: required failures 0, enhancement candidates 1 (`runtime/prompt-probe/seed31.json`)
