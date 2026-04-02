#!/usr/bin/env python3
"""Register the temporal microstructure v2 bundle for the full-day window.

Bundle: temporal_microstructure_v2_0930_1130_1300_1457
- Input: close, open, high, low, volume, amount (from 1m bars)
- Output: 6 variables capturing discrete temporal patterns.

Physical hypotheses (all use discrete counting, validated by conclusion #16):
1. gap_reversal_freq: Frequency of inter-bar gap sign reversals. Analogous to
   reversal_ratio (validated in D-009) but applied to |open_i - close_{i-1}| gaps.
   High reversal = market corrects overshoot quickly = better market quality.
2. gap_sign_run_mean: Average run length of consecutive same-sign gaps.
   Long runs = persistent microstructure friction direction. Inverse of gap_reversal.
3. volume_accel_freq: Frequency of volume-increasing bars (vol_{i+1} > vol_i).
   Discrete counting of volume acceleration events. Different from vol_regime_transitions
   (which counts transitions across median). This captures sequential momentum.
4. large_gap_vol_sync: Fraction of bars where |gap| and volume are both above
   their medians. High sync = gaps accompanied by volume = informed price adjustment.
   Low sync = gaps without volume confirmation = noise.
5. price_path_efficiency: |close_last - close_first| / sum(|close_{i+1} - close_i|).
   Ratio of net movement to total path. Different from Hurst (rescaled range) and
   variance_ratio (variance of multi-bar vs 1-bar). Directly measures path directness.
6. gap_cv: Coefficient of variation of |gap_i|. Measures stability of inter-bar gap
   magnitudes. Low CV = predictable microstructure friction = better market quality.
   Different from open_gap_amihud (which measures the level, not the stability).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ashare_hf_variable.models import AShareRawDataDefinition, RawDataParams, RawDataSlot

NAME = "temporal_microstructure_v2_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "gap_reversal_freq_full",       # count(sign(gap_i) != sign(gap_{i-1})) / pairs
    "gap_sign_run_mean_full",       # total_gaps / num_sign_changes
    "volume_accel_freq_full",       # count(vol_{i+1} > vol_i) / valid_pairs
    "large_gap_vol_sync_full",      # count(|gap|>med AND vol>med) / total
    "price_path_efficiency_full",   # |close[-1]-close[0]| / sum(|delta_close|)
    "gap_cv_full",                  # std(|gap|) / mean(|gap|)
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    open_ = inputs[1]
    high = inputs[2]
    low = inputs[3]
    volume = inputs[4]
    amount = inputs[5]

    n = close.size
    n_out = 6

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
        return out

    # --- Pre-compute inter-bar gaps: gap_i = open_{i} - close_{i-1} ---
    max_gaps = n - 1
    gaps = np.empty(max_gaps, dtype=np.float64)
    abs_gaps = np.empty(max_gaps, dtype=np.float64)
    gap_cnt = 0
    for i in range(1, n):
        o_i = open_[i]
        c_prev = close[i - 1]
        if np.isnan(o_i) or np.isnan(c_prev) or o_i <= 0.0 or c_prev <= 0.0:
            gaps[i - 1] = np.nan
            abs_gaps[i - 1] = np.nan
        else:
            g = o_i - c_prev
            gaps[i - 1] = g
            abs_gaps[i - 1] = abs(g)
            gap_cnt += 1

    if gap_cnt < 15:
        return out

    # --- Pre-compute valid volume array and volume median ---
    valid_vols = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        if not np.isnan(volume[i]) and volume[i] > 0.0:
            valid_vols[vol_cnt] = volume[i]
            vol_cnt += 1
    if vol_cnt < 10:
        return out

    sorted_vols = valid_vols[:vol_cnt].copy()
    sorted_vols.sort()
    if vol_cnt % 2 == 0:
        vol_median = (sorted_vols[vol_cnt // 2 - 1] + sorted_vols[vol_cnt // 2]) / 2.0
    else:
        vol_median = sorted_vols[vol_cnt // 2]

    # --- Compute |gap| median ---
    valid_abs_gaps = np.empty(max_gaps, dtype=np.float64)
    ag_cnt = 0
    for i in range(max_gaps):
        if not np.isnan(abs_gaps[i]):
            valid_abs_gaps[ag_cnt] = abs_gaps[i]
            ag_cnt += 1
    if ag_cnt < 10:
        return out

    sorted_ag = valid_abs_gaps[:ag_cnt].copy()
    sorted_ag.sort()
    if ag_cnt % 2 == 0:
        gap_median = (sorted_ag[ag_cnt // 2 - 1] + sorted_ag[ag_cnt // 2]) / 2.0
    else:
        gap_median = sorted_ag[ag_cnt // 2]

    # === Feature 0: gap_reversal_freq_full ===
    # Frequency of gap sign reversals: count(sign(gap_i) != sign(gap_{i-1})) / valid_pairs
    # Analogous to reversal_ratio applied to inter-bar gaps
    sign_change_cnt = 0
    sign_pair_total = 0
    prev_sign = 0.0  # 0 means uninitialized
    for i in range(max_gaps):
        if np.isnan(gaps[i]) or gaps[i] == 0.0:
            prev_sign = 0.0
            continue
        curr_sign = 1.0 if gaps[i] > 0.0 else -1.0
        if prev_sign != 0.0:
            sign_pair_total += 1
            if curr_sign != prev_sign:
                sign_change_cnt += 1
        prev_sign = curr_sign

    if sign_pair_total > 10:
        out[0] = float(sign_change_cnt) / float(sign_pair_total)

    # === Feature 1: gap_sign_run_mean_full ===
    # Average run length of consecutive same-sign gaps
    # total_valid_gaps / (num_sign_changes + 1)
    if sign_pair_total > 10 and sign_change_cnt > 0:
        # sign_pair_total + 1 = total valid gaps that participated in comparison
        total_valid_gaps_in_seq = sign_pair_total + 1
        num_runs = sign_change_cnt + 1
        out[1] = float(total_valid_gaps_in_seq) / float(num_runs)

    # === Feature 2: volume_accel_freq_full ===
    # Frequency of volume-increasing bars: count(vol_{i+1} > vol_i) / valid_pairs
    va_count = 0
    va_total = 0
    for i in range(n - 1):
        v_curr = volume[i]
        v_next = volume[i + 1]
        if np.isnan(v_curr) or np.isnan(v_next) or v_curr <= 0.0 or v_next <= 0.0:
            continue
        va_total += 1
        if v_next > v_curr:
            va_count += 1
    if va_total > 10:
        out[2] = float(va_count) / float(va_total)

    # === Feature 3: large_gap_vol_sync_full ===
    # Fraction of bars where |gap| > gap_median AND volume > vol_median
    sync_count = 0
    sync_total = 0
    for i in range(1, n):
        ag = abs_gaps[i - 1]
        v_i = volume[i]
        if np.isnan(ag) or np.isnan(v_i) or v_i <= 0.0:
            continue
        sync_total += 1
        if ag > gap_median and v_i > vol_median:
            sync_count += 1
    if sync_total > 10:
        out[3] = float(sync_count) / float(sync_total)

    # === Feature 4: price_path_efficiency_full ===
    # |close_last - close_first| / sum(|close_{i+1} - close_i|)
    first_close = np.nan
    last_close = np.nan
    total_path = 0.0
    path_cnt = 0
    for i in range(n):
        if not np.isnan(close[i]) and close[i] > 0.0:
            if np.isnan(first_close):
                first_close = close[i]
            last_close = close[i]

    for i in range(n - 1):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            continue
        total_path += abs(c1 - c0)
        path_cnt += 1

    if path_cnt > 10 and total_path > 0.0 and not np.isnan(first_close):
        net_move = abs(last_close - first_close)
        out[4] = net_move / total_path

    # === Feature 5: gap_cv_full ===
    # Coefficient of variation of |gap|: std(|gap|) / mean(|gap|)
    # Measures stability of gap magnitudes (market quality indicator)
    gap_sum = 0.0
    for i in range(ag_cnt):
        gap_sum += valid_abs_gaps[i]
    gap_mean = gap_sum / ag_cnt

    if gap_mean > 0.0:
        gap_var_sum = 0.0
        for i in range(ag_cnt):
            diff = valid_abs_gaps[i] - gap_mean
            gap_var_sum += diff * diff
        gap_std = (gap_var_sum / ag_cnt) ** 0.5
        out[5] = gap_std / gap_mean

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "open", "high", "low", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1500,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Temporal microstructure v2 dynamics for the full-day window. "
            "6 features using discrete counting pattern: gap reversal frequency, "
            "gap sign run length, volume acceleration frequency, gap-volume "
            "synchrony, price path efficiency, and gap magnitude stability."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the temporal microstructure v2 full-day bundle"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Write the definition into the configured registry backend",
    )
    parser.add_argument(
        "--skip-validate",
        action="store_true",
        help="Skip formula validation during registration",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the definition JSON payload",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    definition = build_definition()

    if args.print_json or not args.register:
        print(json.dumps(definition.to_document(), indent=2, ensure_ascii=True))

    if args.register:
        from ashare_hf_variable.registry import upsert_definition
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
