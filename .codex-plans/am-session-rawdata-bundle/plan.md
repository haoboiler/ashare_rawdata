# Task: Morning Session Raw-Data Bundle And Research

## Goal
Draft a non-executed admission script for morning-session A-share raw-data and produce a research memo for additional morning 1m-derived raw-data candidates without colliding with admitted fields.

## Current Phase
Phase 4

## Phases

### Phase 1: Requirements And Discovery
- [x] Read project instructions and FOCUS
- [x] Check existing admission pattern using `pv_stats_0930_1130`
- [x] Inspect canonical `raw_value@1d` morning-related fields
- [x] Finalize duplicate boundary for requested outputs
- [x] Collect morning-session research sources
- **Status:** completed

### Phase 2: Implementation
- [x] Write the morning-session admission script
- [x] Write the research markdown document
- **Status:** completed

### Phase 3: Verification And Delivery
- [x] Sanity-check script metadata and formula/output alignment
- [x] Summarize overlap risks and research recommendations
- **Status:** completed

### Phase 4: Final Field Selection Handoff
- [x] Convert the broad research memo into a field-level shortlist with admission-vs-alpha boundaries
- [x] Capture the user's final selected optional fields
- [x] Write a dedicated implementation handoff markdown for colleagues
- [x] Sanity-check formulas, window conventions, and grouping against existing admission patterns
- **Status:** completed

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use `pv_stats_0930_1130` as the primary admission template | It already matches the desired window, slot, and registry workflow |
| Verify duplicates against canonical `ashare@live@stock@raw_value@1d` instead of docs alone | Knowledge-base and registry JSON are incomplete proxies for what is truly admitted |
| Define the requested morning return as `last_close / first_open - 1` | This keeps the field aligned with afternoon-trading use while avoiding exact duplication with admitted `window_return_0930_1130` |
| Put the long-form research memo under `.claude-output/research/` and update `.claude-output/index.md` | The memo is a durable output the user can review tomorrow and use for batch selection |
| Split the final deliverable into a separate handoff markdown instead of continuing to grow the broad research memo | The colleague implementing the final scripts needs one concise field-level spec rather than a mixed research + prioritization document |
| Use the standard half-hour convention `09:30 <= t < 10:00` for the opening segment | This matches the built-in raw-data window definitions already used in the wider A-share stack |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Global `~/.claude/FOCUS.md` missing | Checked required path directly | Proceeded with project `FOCUS.md`; note absence only |
