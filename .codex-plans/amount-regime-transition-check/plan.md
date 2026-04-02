# Task: Check amount_regime_transitions_full and update pending rawdata

## Goal
Locate the failing evaluation metric(s) for `amount_regime_transitions_full` and add the corresponding rawdata to the pending rawdata list.

## Current Phase
Phase 3

## Phases

### Phase 1: Discovery
- [x] Find the factor evaluation artifacts
- [x] Find the pending rawdata source file
- **Status:** completed

### Phase 2: Update
- [x] Edit pending rawdata source
- **Status:** completed

### Phase 3: Verification & Delivery
- [x] Verify the edit
- [x] Report failing metrics and file change
- **Status:** completed

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use project-local planning files | Task spans discovery plus repo edit |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Verification command initially used zsh read-only variable `status` | Summarized pending package metadata with a shell loop | Reran with variable name `rpt_status` |
