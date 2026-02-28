Project: OpenCommotion

Updated: 2026-02-28

Current status:
- Overall project status: Stream G in progress — hard-deletion of all pre-canned visual scenes
- Stream E status: complete
- Stream F status: complete
- Stream G status: IN PROGRESS — worker.py edits done, tests not yet cleaned up or run

Latest verification evidence:
- `python scripts/opencommotion.py test-complete` (pass)
- `python scripts/check_project_plan_sync.py` (pass)
- `python scripts/prompt_compat_probe.py --inprocess` (pass, `required_failures=0`)
- `python scripts/prompt_compat_probe.py` against live local services (pass, `required_failures=0`)

Progress checklist:
- [x] V2 gateway/orchestrator prompt-context plumbing stabilized
- [x] Agent runtime manager concurrency hardening and recovery tests
- [x] Forced-progress narration guard and follow-up render reuse behavior
- [x] Runtime UI dist move to untracked path (`runtime/ui-dist`) to avoid pull conflicts
- [x] Pull/update flow hardened for generated dist churn (`opencommotion update` path)
- [x] Full automated verification gate on this branch (`test-complete`)
- [x] Stream E closeout and synchronization checks
- [x] Prompt probe bug-candidate remediation (4 required scenarios closed)
- [x] Final production readiness sign-off for Streams E/F scope

Active tasks:
1. Stream F governance + quality remediation (complete for this pass)
 - done in prior sessions (see change log)

2. Stream G — hard-delete ALL pre-canned visual scenes (IN PROGRESS)

 **Root cause / requirement:**
   The original commit (`06c75de`) only *gated* legacy template scenes behind
   `OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES` env var (default OFF). It did NOT
   physically delete the code.  Additionally, the fish-bowl scene, fish-actor scene,
   bouncing-balls scene, and line-composition scene were **never gated at all** —
   they fired unconditionally on keyword matches.  User confirmed intent is complete
   surgical deletion.

 **What "pre-canned scene" means:**
   Any code path in `services/agents/visual/worker.py` that uses hard-coded stroke
   sequences triggered by keyword matching rather than routing through the LLM or
   entity-decomposition pipeline.

 **worker.py — DONE (not yet committed):**
   - Deleted `_wants_fish_scene()`, `_wants_fish_actor_scene()` and their unconditional
     `if fish_scene:` / `if fish_actor_scene:` blocks in `generate_visual_strokes()`
   - Deleted `_wants_bouncing_balls_scene()`, `_build_bouncing_balls_strokes()`, and its
     `if bouncing_balls_scene:` block
   - Deleted `_extract_ball_count()`, `_extract_line_composition_counts()`,
     `_wants_line_composition()`, `_build_line_composition_strokes()`, and the
     `if line_composition_scene:` block
   - Deleted `_palette_fish_commands()` and the `elif subject == "fish":` branch in
     `_build_palette_script_strokes()`
   - All `legacy_template_scenes` gated blocks (moonwalk, globe/ufo, chart/adoption/pie,
     market_growth, day_night, cow_moon_lyric) remain — they were already gated behind
     `LEGACY_TEMPLATE_SCENES_ENV` and scheduled alongside this deletion
   - `VISUAL_TRUE_VALUES`, `VISUAL_FALSE_VALUES`, `LEGACY_TEMPLATE_SCENES_ENV`,
     `_wants_market_growth_scene()`, `_wants_day_night_scene()`,
     `_wants_cow_moon_lyric_scene()`, `_legacy_template_scenes_enabled()` and their
     variable assignments + if-blocks in `generate_visual_strokes()` — still present,
     must be deleted in same pass

 **tests/unit/test_visual_worker.py — NOT YET DONE:**
   Delete all tests that assert pre-canned scene strokes or monkeypatch the legacy env:
   - `test_fish_prompt_generates_base_scene_primitives` (asserts spawnSceneActor/emitFx on fish bowl prompt)
   - `test_fish_prompt_3d_includes_material_fx` (asserts applyMaterialFx on fish bowl prompt)
   - `test_fish_prompt_3_dfishbowl_uses_constituent_3d_scene` (asserts spawnSceneActor not runScreenScript)
   - `test_black_fish_square_bowl_prompt_uses_prompt_style` (asserts fish_bowl/goldfish actor ids)
   - `test_draw_fish_prompt_generates_fish_actor_and_not_dot_fallback` (asserts actor_type==fish)
   - `test_bouncing_ball_prompt_respects_requested_quantity` (asserts circle actors ball_1/ball_2)
   - `test_paint_straight_and_bendy_lines_generates_composable_script_commands` (asserts runScreenScript
     straight_line_/bendy_line_ ids) — delete ONLY if line-composition removal causes it to fail;
     alternatively redirect to entity/LLM path assertion
   - `test_paint_straight_and_bendy_lines_3d_sets_3d_mode` — same as above
   - `test_market_growth_prompt_includes_segmented_attach_chart` (monkeypatches legacy env)
   - `test_cow_moon_lyric_prompt_includes_lyrics_and_bounce` (monkeypatches legacy env)
   - `test_day_night_prompt_includes_environment_and_transition` (monkeypatches legacy env)
   - `test_legacy_scenes_off_by_default_for_market_growth` (tests now-moot gating behavior)

 **tests/e2e/visual-scene-capture.spec.ts — NOT YET DONE:**
   - Test `legacy canned scenes: market growth requires explicit env flag` — rename
     to `market growth prompt never produces chart strokes` and remove env-var manipulation;
     assertion that `drawAdoptionCurve` / `drawSegmentedAttachBars` are absent should still hold

 **Remaining worker.py legacy block deletions — NOT YET DONE:**
   From `generate_visual_strokes()`, lines approx 1278–1486 (pre-edit numbering):
   - Variable assignments: `market_growth_scene = ...`, `day_night_scene = ...`,
     `cow_moon_lyric_scene = ...`, `legacy_template_scenes = _legacy_template_scenes_enabled()`
   - `if legacy_template_scenes and "moonwalk" in p:` block
   - `if legacy_template_scenes and ("globe" in p or "ufo" in p):` block
   - `if legacy_template_scenes and ("chart" in p or "adoption" in p or ...):` block
   - `if legacy_template_scenes and market_growth_scene:` block
   - `if legacy_template_scenes and day_night_scene:` block
   - `if legacy_template_scenes and cow_moon_lyric_scene:` block
   Top-level helper functions (all still present):
   - `_wants_market_growth_scene()`, `_wants_day_night_scene()`, `_wants_cow_moon_lyric_scene()`
   - `_legacy_template_scenes_enabled()`
   Module-level constants (still present):
   - `VISUAL_TRUE_VALUES`, `VISUAL_FALSE_VALUES`, `LEGACY_TEMPLATE_SCENES_ENV`

 **Verification steps after deletion:**
   ```powershell
   python -m pytest --tb=short -q
   ```
   Expect ~108 passing (was 118 before; 10+ pre-canned tests removed).
   Then:
   ```powershell
   git add services/agents/visual/worker.py tests/unit/test_visual_worker.py tests/e2e/visual-scene-capture.spec.ts
   git commit -m "refactor(visual): hard-delete all pre-canned scenes — fish, balls, lines, legacy env-gated blocks"
   git push
   ```

Change log:
- 2026-02-27: Closed Windows `test-complete` blockers by fixing npm resolution and replacing bash-only orchestration paths with Windows-safe execution.
- 2026-02-27: Stream E fully passed (`test`, `ui:test`, `e2e`, security, perf).
- 2026-02-27: Started Stream F governance; plan-sync check passed and prompt probe surfaced 4 required bug candidates for remediation.
- 2026-02-27: Completed Stream F prompt-probe remediation by restoring required template scene routing defaults; prompt compatibility probe now returns `required_failures=0`.
- 2026-02-27: Completed live-stack prompt compatibility probe with `required_failures=0`, closing Stream E and Stream F scope.
- 2026-02-28: Added `opencommotion -voice-setup` one-command Windows bootstrap for high-quality Piper speech (binary/model install + `.env` defaults + engine verification).
- 2026-02-28: Defaulted setup wizard TTS choice to Piper and high model path (`en_US-lessac-high`) for simpler first-run quality.
- 2026-02-28: Revalidated end-to-end after setup simplification with `python scripts/opencommotion.py fresh-agent-e2e` (pass).
