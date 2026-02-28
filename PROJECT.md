Project: OpenCommotion

Updated: 2026-02-28

Current status:
- Overall project status: Stream E and Stream F complete
- Stream E status: complete (full verification chain passed on Windows)
- Stream F status: complete (governance probe remediated and green)

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
 - planned:
   - keep plan tracker synchronized with current verification evidence
   - run governance probes and capture bug candidates
   - remediate required prompt-probe failures and rerun probe
 - done in this session:
   - fixed Windows command orchestration in `scripts/opencommotion.py` (`npm` resolution, native e2e runner, security/perf steps)
   - hardened `scripts/dev_up.sh` interpreter selection and current-env mode for cross-shell compatibility
   - validated full gate with `python scripts/opencommotion.py test-complete` (pass)
   - validated governance sync with `python scripts/check_project_plan_sync.py` (pass)
   - enabled structured template scene routing by default in `services/agents/visual/worker.py` unless explicitly disabled via `OPENCOMMOTION_ENABLE_LEGACY_TEMPLATE_SCENES`
   - reran `python scripts/prompt_compat_probe.py --inprocess`; required failures are now 0 and report refreshed at `runtime/prompt-probe/latest.json`
   - ran `python scripts/prompt_compat_probe.py` against live local gateway/orchestrator services; required failures remain 0
 - in progress / not finished:
   - none for Stream F remediation
 - remaining:
   - none for Streams E/F

Change log:
- 2026-02-27: Closed Windows `test-complete` blockers by fixing npm resolution and replacing bash-only orchestration paths with Windows-safe execution.
- 2026-02-27: Stream E fully passed (`test`, `ui:test`, `e2e`, security, perf).
- 2026-02-27: Started Stream F governance; plan-sync check passed and prompt probe surfaced 4 required bug candidates for remediation.
- 2026-02-27: Completed Stream F prompt-probe remediation by restoring required template scene routing defaults; prompt compatibility probe now returns `required_failures=0`.
- 2026-02-27: Completed live-stack prompt compatibility probe with `required_failures=0`, closing Stream E and Stream F scope.
- 2026-02-28: Added `opencommotion -voice-setup` one-command Windows bootstrap for high-quality Piper speech (binary/model install + `.env` defaults + engine verification).
- 2026-02-28: Defaulted setup wizard TTS choice to Piper and high model path (`en_US-lessac-high`) for simpler first-run quality.
- 2026-02-28: Revalidated end-to-end after setup simplification with `python scripts/opencommotion.py fresh-agent-e2e` (pass).
