Project: OpenCommotion

Updated: 2026-02-28

Current status:
- Overall project status: Streams E/F/G complete — no active stream
- Stream E status: complete
- Stream F status: complete
- Stream G status: complete (committed cbe9b12)

Latest verification evidence:
- `python -m pytest --tb=no -q` → 130 passed
- `python scripts/opencommotion.py test-complete` (pass)
- `python scripts/check_project_plan_sync.py` (pass)
- `python scripts/prompt_compat_probe.py --inprocess` (pass, `required_failures=0`)
- `python scripts/prompt_compat_probe.py` against live local services (pass, `required_failures=0`)
- `python scripts/opencommotion.py fresh-agent-e2e` (pass)

Open issue (not blocking):
- Windows Firewall rules `OpenCommotion-{8000,8001,8010,8011,5173}` are currently
  `Profile Any` — they work but allow inbound on public networks.
  To restrict to Private/Domain only, run from an **elevated PowerShell**:
  ```powershell
  $ports = @(8000,8001,8010,8011,5173)
  foreach ($p in $ports) {
    $r = "OpenCommotion-$p"
    Remove-NetFirewallRule -DisplayName $r -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName $r -Direction Inbound -Protocol TCP `
      -LocalPort $p -Action Allow -Profile Private,Domain | Out-Null
    Write-Output "Fixed: $r -> Private,Domain"
  }
  ```
  Future installs handle this automatically via `install_windows_shim.sh` (RunAs elevation, `4801ee6`).

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
- [x] Stream G — hard-delete all pre-canned visual scenes (fish, balls, lines, legacy env-gated blocks)
- [x] Parallel text+visual generation via `asyncio.to_thread`
- [x] Coherence assessment agent (opt-in via `OPENCOMMOTION_COHERENCE_ENABLED`)
- [x] Visual error recovery with `_translate_unsupported_op` (24 known translations)
- [x] High-quality Windows TTS bootstrap (`opencommotion voice-setup`, Piper `en_US-lessac-high`)
- [x] All services bind `0.0.0.0` by default; override with `OPENCOMMOTION_BIND_HOST`
- [x] Windows Firewall rules added during install (`install_windows_shim.sh`, `Private,Domain`)

Active tasks:
- None. All streams complete. See open issue above re: existing firewall rule profile.

Change log:
- 2026-02-27: Closed Windows `test-complete` blockers by fixing npm resolution and replacing bash-only orchestration paths with Windows-safe execution.
- 2026-02-27: Stream E fully passed (`test`, `ui:test`, `e2e`, security, perf).
- 2026-02-27: Started Stream F governance; plan-sync check passed and prompt probe surfaced 4 required bug candidates for remediation.
- 2026-02-27: Completed Stream F prompt-probe remediation by restoring required template scene routing defaults; prompt compatibility probe now returns `required_failures=0`.
- 2026-02-27: Completed live-stack prompt compatibility probe with `required_failures=0`, closing Stream E and Stream F scope.
- 2026-02-28: Stream G complete (`cbe9b12`) — hard-deleted all pre-canned visual scenes (fish, bouncing balls, line-composition, legacy env-gated blocks). All related tests removed/renamed. 130 passing.
- 2026-02-28: Added parallel text+visual generation via `asyncio.to_thread`, coherence assessment agent (`OPENCOMMOTION_COHERENCE_ENABLED`), visual error recovery with 24-op translation table, and `_fallback_visual_strokes` (`cbe9b12`).
- 2026-02-28: Added `opencommotion voice-setup` one-command Windows bootstrap for high-quality Piper TTS (binary + `en_US-lessac-high` model download + `.env` defaults).
- 2026-02-28: Defaulted setup wizard TTS choice to Piper `en_US-lessac-high` for simpler first-run quality.
- 2026-02-28: All services now bind `0.0.0.0` by default (`7bbe8c6`); `OPENCOMMOTION_BIND_HOST` overrides. Fixes WSL2→Windows browser access.
- 2026-02-28: Added Windows Firewall inbound rules for app ports during `install_windows_shim.sh` via RunAs elevation, `Profile Private,Domain` (`4801ee6`).
