# Task: Continue interrupted Claude session on raw-data speed analysis

## Goal
Recover the interrupted Claude Code discussion, identify the colleague-link code under discussion, and continue the speed analysis with concrete technical reasons.

## Current Phase
Phase 7

## Phases

### Phase 1: Context recovery
- [x] Read project constraints
- [x] Locate the exact Claude session and relevant turns
- [x] Identify the colleague link / target code under discussion
**Status:** completed

### Phase 2: Technical analysis
- [x] Compare current project implementation with colleague code path
- [x] Extract concrete reasons for faster evolution / computation
**Status:** completed

### Phase 3: Delivery
- [x] Summarize recovered context
- [x] Continue the discussion with actionable conclusions
**Status:** completed

### Phase 4: Quick-Eval Hot Path
- [x] Reuse shared `ashare_alpha/backtest/evaluate.py` helpers instead of copying Tier 1 logic
- [x] Add in-memory `--quick-eval` / `--skip-export` workflow to `scripts/compute_rawdata_local.py`
- [ ] Validate `--use-preload + --quick-eval` against a freshly rebuilt preload actor
**Status:** in_progress

### Phase 5: Wrapper + Metadata
- [x] Add per-field raw-data sidecar metadata on compute export
- [x] Add `scripts/evaluate_rawdata.py` wrapper to align formal evaluate timing with raw-data metadata
- [x] Validate sidecar-based and registry-based timing inference through the wrapper
**Status:** completed

### Phase 6: Evolve Driver
- [x] Add a thin raw-data evolve driver that reuses existing compute + quick-eval paths
- [x] Support both fixed candidate batches and generator-driven candidate generation
- [x] Validate both fixed-candidate and generator smoke flows
**Status:** completed

### Phase 7: Preload Actor Stability
- [x] Confirm current researcher failures are no longer caused by small-universe quick mode
- [x] Capture evidence that preload actor is being terminated externally during rebuild/use
- [x] Identify the preload actor lifecycle flaw and patch it
- [x] Validate safe fallback and fail-fast behavior around preload actor state
- [x] Validate end-to-end successful preload completion on the patched actor
- [x] Validate leader-launched researchers can complete at least one preload-backed evolve run
- [ ] Diagnose why the managed preload Ray/actor later dies with `Socket closed` during second-round researcher runs
**Status:** in_progress

### Phase 8: Dedicated-User Preload Isolation
- [x] Prepare preload scripts to support per-user/per-port overrides
- [x] Prepare `gkh_ray`-specific wrapper scripts and ports
- [ ] Create Unix user `gkh_ray` and grant minimal path access
- [ ] Start isolated preload Ray under `gkh_ray` and validate behavior
**Status:** in_progress

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Search local Claude session JSONL files first | User explicitly asked to continue from interrupted Claude Code context |
| Use local git branch `origin/evolve/ashare-hf-var` as primary source | The exact GitHub path exists locally, so code can be inspected directly without relying on remote web access |
| Implement only optimization priority #1 in this turn | User explicitly asked to record FOCUS and then modify the first priority item |
| Reuse shared `evaluate.py` helpers instead of copying Tier 1 evaluation logic | User pointed out `evaluate.py` changes frequently, so the quick-eval path should track that shared logic |
| Align formal raw-data evaluation via a project wrapper instead of patching shared `evaluate.py` first | Lower risk than editing shared ashare_alpha code and sufficient to make quick-eval and formal evaluate use the same timing assumptions |
| Implement evolve as a thin driver instead of hard-coding mutation logic into the project | User wants a future `/evolve` skill; keeping mutation generation external lets the driver remain stable while strategies iterate independently |
| Clamp researcher fallback to full-market quick-eval instead of allowing `--quick` or Ray restarts | User explicitly rejected small-universe bias, and researcher-level infra restarts are too disruptive for a shared local environment |
| Build a soft-isolated managed preload Ray at `127.0.0.1:27680` | Avoid accidental bare `ray.init()` attachment and keep preload lifecycle separate from other local Ray usage |
| For stronger kill isolation, move preload Ray to a dedicated Unix user instead of only changing ports | Same-user `ray stop` remains risky; user-level process ownership is the more meaningful boundary |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `--use-preload` actor lacked new quick-eval methods | Called `ensure_quick_eval_context` on the existing detached actor | Rebuilt the preload actor with the updated class; local quick-eval path validated first while the new actor continued loading |
| Ray GCS became temporarily unavailable during wrapper+metadata validation | Tried a preload-based compute smoke test first | Switched validation to serial `--quick` compute for sidecar coverage and separate registry-fallback smoke test, which exercised the wrapper logic without depending on Ray |
| Researchers drifted toward small-universe quick mode and then toward `ray stop/start` | Relied on base prompt plus one-shot instruction only | Hardened `researcher.md`, injected stricter `leader_instruction`, and restarted researchers onto a compliant full-market fallback path |
| Rebuilding preload from an existing detached actor often died with `SIGTERM` | Old code always killed the actor and recreated it immediately | Added preload state/health checks, default actor reuse/wait behavior, fail-safe refusal to auto-kill unresponsive actors, and a controlled `--force-preload-rebuild` path with grace delay |
| Managed preload-backed second-round researcher runs failed with actor `Socket closed` | First assumed researchers were only misdetecting tmux/session liveness | Confirmed both second-round evolve runs recorded real actor-unavailable errors, and later the managed status script reported `ray_status=down`; fallback path remained policy-compliant |
| Creating dedicated Unix user `gkh_ray` | Tried non-interactive `sudo -n` and then interactive `sudo` provisioning | Blocked by password-required sudo in this session; prepared scripts and ACL step so only the privileged user-creation action remains |
