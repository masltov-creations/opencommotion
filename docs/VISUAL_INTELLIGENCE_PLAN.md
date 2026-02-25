# Visual Intelligence v2 Plan (Parallel Execution)

Updated: 2026-02-25

## Goal

Ship a generic visual intelligence system where scenes are composed from reusable primitives, not one-off templates, and certify required scenarios in both `2d` and `3d`.

## Parallel Workstreams

1. Contract and schema lane
- Define generic stroke primitives:
  - `setRenderMode`
  - `spawnSceneActor`
  - `setActorMotion`
  - `setActorAnimation`
  - `emitFx`
  - `setEnvironmentMood`
  - `setCameraMove`
  - `applyMaterialFx`
- Keep backward compatibility with existing stroke kinds.

2. Compiler and runtime lane
- Compile generic primitives into deterministic scene patches.
- Add shader guardrails (whitelist + uniform validation + fallback reason code).
- Add runtime state support for:
  - `render`
  - `fx`
  - `materials`
  - `environment`
  - `camera`

3. UI rendering lane
- Render primitives for 2D and 3D-leaning scenes.
- Support bubble/caustic/water effects.
- Support actor motion playback (fish swim loop, plant sway).

4. Validation and QA lane
- Unit tests for spline/path, deterministic FX seed replay, shader validation fallback, and caustic continuity.
- Integration tests for orchestrated `2d` and `3d` fish-scene prompts.
- UI runtime tests for new primitive patch application.

5. Documentation and onboarding lane
- Canonical scenario prompts + requirements matrix.
- Agent guidance for reusable constituent parts and scenario composition.

## Core Constituent Parts

Use these as the base composition model for all current/future scenes:

1. Actors
- Characters, fish, plants, objects, data glyphs, etc.
- Spawn/configure via `spawnSceneActor`.
- Move via `setActorMotion`.
- Animate via `setActorAnimation`.

2. Effects (`fx_track`)
- Emitters and overlays via `emitFx`.
- Initial required set:
  - `bubble_emitter`
  - `caustic_pattern`
  - `water_shimmer`

3. Materials (`material_fx`)
- Apply style/shader behavior via `applyMaterialFx`.
- Initial required set:
  - `glass_refraction_like`
  - `water_volume_tint`
  - `caustic_overlay_shader`

4. Environment
- Scene mood, light sources, and progression via `setEnvironmentMood`.

5. Camera
- Motion constraints and framing via `setCameraMove`.

6. Render mode
- `2d` optimized scene path and `3d` extended path via `setRenderMode`.

## Certification Matrix

Required scenarios for release of visual-intelligence v2 mode:

1. Scenario A: Cow jumps over moon with lyric timing
- `A-2D` required
- `A-3D` required

2. Scenario B: Elegant day-to-night scene
- `B-2D` required
- `B-3D` required

3. Scenario C: Market growth presentation with segmented attach progression
- `C-2D` required
- `C-3D` required

4. Scenario D (Stretch, now fully specified): Fish-in-bowl cinematic
- `D-2D` required when stretch mode enabled
- `D-3D` required when stretch mode enabled

## Scenario D Canonical Prompt

Use this exact prompt for planner/template and integration tests:

> Create a serene cinematic scene of a goldfish swimming inside a clear glass fish bowl on a wooden desk near a window. Show gentle water movement, soft caustic light patterns on the desk, tiny bubbles rising, subtle plant sway inside the bowl, and realistic fish turn/fin motion. Include a calm day-to-evening mood shift over the timeline. Keep composition elegant and readable, with smooth camera framing and no abrupt transitions. In 2D mode, preserve the same story with stylized layers and motion depth cues. In 3D mode, include glass, refraction-like behavior, water surface shimmer, and soft volumetric light feel. Synchronize optional narration pacing with scene beats.

## Scenario D Acceptance

1. D-2D
- Layered parallax cues and stylized distortion/refraction.
- Fish swim loop with smooth interpolation.
- Bubble and caustic effects visible and deterministic from seed.
- Mood progression day -> dusk without abrupt transitions.

2. D-3D
- Bowl/water/fish composition with material FX path.
- Shader guardrails enforce whitelist and ranges.
- On shader failure, runtime falls back and emits reason.
- Camera motion remains smooth and stable.

## Common Mistakes and Hardening

Common mistakes now guarded:

1. Non-monotonic chart x-axis points
- Hardening: curve points are sorted and deduped by x in compiler.

2. “Growth” graph accidentally trending down in semantic meaning
- Hardening: for `trend=growth`, y-values are coerced to non-increasing (screen-space upward trend).

3. Pie slices not summing to 100
- Hardening: pie values are normalized to a 100% total.

4. Segmented attach targets outside valid range
- Hardening: segment targets are clamped to `0..100`.

5. Missing market-graph compatibility checks during test runs
- Hardening: `evaluate_market_growth_scene(...)` is used by integration tests and gateway emits `quality_report` for market-growth prompts.

## Current Implementation State

Implemented in repo:

1. Generic primitive stroke kinds + compiler support.
2. Fish scene orchestration path using generic primitives.
3. Deterministic bubble emitter, spline path utility, and shader uniform guardrails.
4. Runtime state support for `fx/materials/environment/camera/render`.
5. Stage rendering for fish-bowl visual elements in UI.
6. Unit/integration test coverage for Scenario D core behaviors.

Pending for full production-grade v2:

1. Full 3D renderer pipeline (current path is 3D-leaning metadata + SVG presentation).
2. Dedicated shader runtime with GPU compile/telemetry budgets.
3. Full A/B/C certification in both 2D and 3D tracks under v2 contract.
4. Long-haul performance soak for all scenario variants.

## Tool-Enhancement Tracking

When scenario requirements expose tooling limitations, track them in:
- `docs/TOOL_ENHANCEMENT_BACKLOG.md`

Tracking rule:
- Do not mark scenario implementation complete if a required tool gap remains open at high severity.
