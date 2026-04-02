# Findings

## Admission Pattern
- `research/basic_rawdata/pv_stats/register_pv_stats_0930_1130.py` uses one multi-output bundle, `slot=midday`, `input_time_filter=[("09:30", "11:30")]`, `data_available_at=1131`, `execution_start_at=930`, `execution_end_at=1130`, and defaults to JSON preview unless `--register` is passed.

## Admitted Morning Overlaps
- Canonical library `ashare@live@stock@raw_value@1d` had 151 fields on 2026-03-27.
- Morning-window admitted fields already include:
  - `twap_0930_1130`, `vwap_0930_1130`
  - `amihud_0930_1130`, `price_volume_corr_0930_1130`, `return_volume_corr_0930_1130`, `volume_imbalance_0930_1130`, `amount_imbalance_0930_1130`, `vwap_deviation_0930_1130`, `kyle_lambda_0930_1130`
  - `volume_std_0930_1130`, `volume_cv_0930_1130`, `volume_skew_0930_1130`, `volume_concentration_0930_1130`, `volume_trend_0930_1130`, `amount_cv_0930_1130`
  - `window_return_0930_1130` and 19 volatility-family fields such as `realized_vol_0930_1130`, `garman_klass_vol_0930_1130`, `price_range_0930_1130`, `close_position_0930_1130`
- Requested `return` needs explicit semantic handling because `window_return_0930_1130` already exists.

## Knowledge-Base State
- `research/KNOWLEDGE-BASE.md` currently records 8 validated bundles: 4 `pv_stats` + 4 `volatility`.
- The knowledge base confirms admitted bundle families but does not enumerate all canonical raw-value fields.

## Literature-Backed Candidate Priorities
- Highest-priority next bundles from research:
  - `am_gap_digest_0930_1130`
  - `am_price_limit_state_0930_1130`
  - `am_opening_impulse_0930_1130`
  - `am_time_weighted_liquidity_0930_1130`
- Medium-priority bundles:
  - `am_candlestick_structure_0930_1130`
  - `am_extremum_timing_0930_1130`
  - `am_order_toxicity_proxy_0930_1130`
- Lower-priority / more caution:
  - `am_jump_risk_0930_1130`
  - `am_volume_profile_0930_1130`
  - anchor / support-resistance transforms that can be derived downstream once basics are admitted

## Current Implementation Scope
- The user’s final handoff scope is narrower than the broad research memo: it combines the direct-admission shortlist with selected optional fields only.
- The selected optional fields are:
  - `am_near_high_minutes_0930_1130`
  - `am_near_low_minutes_0930_1130`
  - `am_vpin_proxy_0930_1130`
  - `am_toxicity_trend_0930_1130`
  - `am_unfinished_one_sided_flow_0930_1130`
  - `am_jump_count_proxy_0930_1130`
  - `am_jump_direction_imbalance_0930_1130`
  - `am_jump_after_volume_burst_0930_1130`
  - `am_u_shape_deviation_0930_1130`
  - `am_vwap_cross_count_0930_1130`
- The final output for this turn should therefore be a colleague-facing handoff markdown rather than another expansion of the broad research memo.

## Window Convention
- The wider A-share stack already defines `0930_1000` as `09:30 <= t < 10:00` with 30 expected bars, via `casimir_ashare/.../standard_definitions.py` and `docs/data_update_system.md`.
- The handoff doc should reuse that convention for opening-segment fields so colleagues can align new admission scripts with the existing raw-data ecosystem.

## Output Artifacts
- Admission draft script:
  - `research/basic_rawdata/am_session_basics/register_am_session_basics_0930_1130.py`
- Research memo:
  - `.claude-output/research/2026-03-27_morning_session_rawdata_research.md`
- Pending handoff doc:
  - `.claude-output/research/2026-03-27_morning_session_selected_fields_handoff.md`
- Output index updated:
  - `.claude-output/index.md`
