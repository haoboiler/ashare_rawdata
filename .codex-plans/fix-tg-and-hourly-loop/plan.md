# Task: Fix researcher TG send and hourly report fallback

## Goal
Make researcher cycles reliably send TG notifications and ensure the hourly fallback actually runs at the next hour rather than many hours later.

## Current Phase
Phase 1

## Phases

### Phase 1: Diagnose current failure
- [x] Confirm whether the last researcher cycle actually executed `tg_send.py`
- [x] Confirm why wrapper did not advance to the next cycle
- [x] Confirm why `hourly_report_loop.sh` computed a next run far in the future
- **Status:** complete

### Phase 2: Implement fixes
- [x] Add a shell-side fallback so researcher reports are sent even if the model stops after writing the report
- [x] Fix hourly loop next-run computation
- [x] Ensure completed one-shot tasks can exit cleanly and advance the wrapper
- **Status:** complete

### Phase 3: Verify and summarize
- [x] Re-run the notification path and confirm TG send attempts happen
- [x] Re-check researcher state transitions and loop behavior
- [x] Summarize remaining risks
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Add a shell-side report-send fallback in `researcher_wrapper.sh` | TG send was previously enforced only by prompt instructions; shell fallback makes notification delivery robust even if the model stops after writing the report |
| Replace `date -d "... + 1 hour"` with epoch arithmetic in `hourly_report_loop.sh` | The old expression resolved to next-day `01:00` on this host, so the fallback report loop was not actually hourly |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `hourly_report_loop.sh` scheduled the next run ~7 hours later | Reproduced the expression locally with `date -d` | Switched to `((now_epoch / 3600 + 1) * 3600)` |
| Researcher completion/TG guarantee existed only in prompt text | Checked log, prompt, and sent ledger | Added post-session shell fallback keyed off the latest report path |
