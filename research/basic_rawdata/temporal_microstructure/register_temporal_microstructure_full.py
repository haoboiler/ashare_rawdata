#!/usr/bin/env python3
"""Register the temporal microstructure bundle for the full-day window.

Bundle: temporal_microstructure_0930_1130_1300_1457
- Input: close, open, high, low, volume, amount (from 1m bars)
- Output: 8 variables capturing intraday temporal structure dynamics.

Physical hypotheses:
1. open_gap_amihud: Inter-bar gaps |open_i - close_{i-1}| normalized by amount
   measure "microstructure spread cost per unit trading". A novel Amihud
   numerator capturing price discontinuity between bars.
2. volume_lead_return_freq: Discrete count of (high-vol bar → large-|ret| next bar)
   events. Measures information flow direction: volume leading price = informed
   trading. Follows validated discrete counting pattern (#16).
3. ret_lead_volume_freq: Count of (large-|ret| bar → high-vol next bar) events.
   Returns leading volume = momentum-chasing/reactive flow.
4. high_timing: Normalized bar index where daily close-price maximum occurs.
   Temporal structure of price discovery — completely novel dimension.
5. extremum_spread: |high_bar_idx - low_bar_idx| / n. Temporal distance between
   daily extremes. Clustered extremes = event-driven; spread = trending.
6. gap_body_ratio: mean|O_i-C_{i-1}| / mean|C_i-O_i|. Ratio of inter-bar to
   intra-bar price movement. High = price changes happen between bars (jumpy);
   Low = smooth within-bar movement.
7. range_contraction_freq: Count(range_i < range_{i-1}) / total_pairs.
   Discrete counting of bar-range narrowing events. Related to but less strict
   than inside_bar (which requires full containment). Captures consolidation
   frequency.
8. volume_return_lag_diff: vol_lead - ret_lead difference. Net information flow
   direction indicator. Positive = volume leads price (informed); Negative =
   price leads volume (reactive).
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

NAME = "temporal_microstructure_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "open_gap_amihud_full",           # mean(|O_i - C_{i-1}|) / mean(amount) * 1e9
    "volume_lead_return_freq_full",   # count(vol_i>med AND |ret_{i+1}|>med) / total
    "ret_lead_volume_freq_full",      # count(|ret_i|>med AND vol_{i+1}>vol_med) / total
    "high_timing_full",               # bar_index_of_max_close / n
    "extremum_spread_full",           # |high_idx - low_idx| / n
    "gap_body_ratio_full",            # mean|O_i - C_{i-1}| / mean|C_i - O_i|
    "range_contraction_freq_full",    # count(range_i < range_{i-1}) / total_pairs
    "volume_return_lag_diff_full",    # vol_lead_freq - ret_lead_freq (net info flow)
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
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 20:
        return out

    # --- Pre-compute returns ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    abs_rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
            abs_rets[i] = np.nan
        else:
            r = c1 / c0 - 1.0
            rets[i] = r
            abs_rets[i] = abs(r)
            valid_ret_count += 1

    if valid_ret_count < 20:
        return out

    # --- Compute mean(amount) ---
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        if not np.isnan(amount[i]) and amount[i] > 0.0:
            amt_sum += amount[i]
            amt_cnt += 1
    if amt_cnt == 0:
        return out
    mean_amt = amt_sum / amt_cnt

    # --- Compute volume median ---
    valid_vols = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        if not np.isnan(volume[i]) and volume[i] > 0.0:
            valid_vols[vol_cnt] = volume[i]
            vol_cnt += 1

    vol_median = 0.0
    if vol_cnt > 0:
        sorted_vols = valid_vols[:vol_cnt].copy()
        sorted_vols.sort()
        if vol_cnt % 2 == 0:
            vol_median = (sorted_vols[vol_cnt // 2 - 1] + sorted_vols[vol_cnt // 2]) / 2.0
        else:
            vol_median = sorted_vols[vol_cnt // 2]

    # --- Compute |ret| median ---
    valid_abs_rets = np.empty(n_ret, dtype=np.float64)
    ar_cnt = 0
    for i in range(n_ret):
        if not np.isnan(abs_rets[i]):
            valid_abs_rets[ar_cnt] = abs_rets[i]
            ar_cnt += 1

    ret_median = 0.0
    if ar_cnt > 0:
        sorted_ars = valid_abs_rets[:ar_cnt].copy()
        sorted_ars.sort()
        if ar_cnt % 2 == 0:
            ret_median = (sorted_ars[ar_cnt // 2 - 1] + sorted_ars[ar_cnt // 2]) / 2.0
        else:
            ret_median = sorted_ars[ar_cnt // 2]

    # === Feature 0: open_gap_amihud_full ===
    # mean(|open_i - close_{i-1}|) / mean(amount) * 1e9
    # Inter-bar gap normalized by trading cost
    gap_sum = 0.0
    gap_cnt = 0
    for i in range(1, n):
        o_i = open_[i]
        c_prev = close[i - 1]
        if np.isnan(o_i) or np.isnan(c_prev) or o_i <= 0.0 or c_prev <= 0.0:
            continue
        gap_sum += abs(o_i - c_prev)
        gap_cnt += 1
    if gap_cnt > 5 and mean_amt > 0.0:
        out[0] = (gap_sum / gap_cnt) / mean_amt * 1e9

    # === Feature 1: volume_lead_return_freq_full ===
    # count(vol_i > vol_median AND |ret_{i+1}| > ret_median) / valid_pairs
    # Does high volume predict large subsequent returns?
    vl_count = 0
    vl_total = 0
    for i in range(n_ret - 1):
        v_i = volume[i]
        ar_next = abs_rets[i + 1]  # ret from close[i+1] to close[i+2]
        if np.isnan(v_i) or np.isnan(ar_next) or v_i <= 0.0:
            continue
        vl_total += 1
        if v_i > vol_median and ar_next > ret_median:
            vl_count += 1
    if vl_total > 10:
        out[1] = float(vl_count) / float(vl_total)

    # === Feature 2: ret_lead_volume_freq_full ===
    # count(|ret_i| > ret_median AND vol_{i+1} > vol_median) / valid_pairs
    # Do large returns predict high subsequent volume?
    rl_count = 0
    rl_total = 0
    for i in range(n_ret - 1):
        ar_i = abs_rets[i]
        v_next = volume[i + 2]  # volume of bar i+2 (aligned with ret i+1)
        if np.isnan(ar_i) or np.isnan(v_next) or v_next <= 0.0:
            continue
        rl_total += 1
        if ar_i > ret_median and v_next > vol_median:
            rl_count += 1
    if rl_total > 10:
        out[2] = float(rl_count) / float(rl_total)

    # === Feature 3: high_timing_full ===
    # Normalized bar index where close reaches its maximum
    max_close = -np.inf
    max_idx = 0
    valid_close_cnt = 0
    for i in range(n):
        if not np.isnan(close[i]):
            valid_close_cnt += 1
            if close[i] > max_close:
                max_close = close[i]
                max_idx = i
    if valid_close_cnt > 10:
        out[3] = float(max_idx) / float(n - 1)

    # === Feature 4: extremum_spread_full ===
    # |max_close_idx - min_close_idx| / n
    min_close = np.inf
    min_idx = 0
    for i in range(n):
        if not np.isnan(close[i]):
            if close[i] < min_close:
                min_close = close[i]
                min_idx = i
    if valid_close_cnt > 10:
        out[4] = abs(float(max_idx) - float(min_idx)) / float(n - 1)

    # === Feature 5: gap_body_ratio_full ===
    # mean(|open_i - close_{i-1}|) / mean(|close_i - open_i|)
    body_sum = 0.0
    body_cnt = 0
    for i in range(n):
        c_i = close[i]
        o_i = open_[i]
        if np.isnan(c_i) or np.isnan(o_i):
            continue
        body_sum += abs(c_i - o_i)
        body_cnt += 1
    if body_cnt > 5 and gap_cnt > 5:
        mean_body = body_sum / body_cnt
        mean_gap = gap_sum / gap_cnt
        if mean_body > 0.0:
            out[5] = mean_gap / mean_body

    # === Feature 6: range_contraction_freq_full ===
    # count(range_i < range_{i-1}) / total_valid_pairs
    rc_count = 0
    rc_total = 0
    prev_range = np.nan
    for i in range(n):
        h_i = high[i]
        l_i = low[i]
        if np.isnan(h_i) or np.isnan(l_i):
            prev_range = np.nan
            continue
        curr_range = h_i - l_i
        if not np.isnan(prev_range) and prev_range > 0.0:
            rc_total += 1
            if curr_range < prev_range:
                rc_count += 1
        prev_range = curr_range
    if rc_total > 10:
        out[6] = float(rc_count) / float(rc_total)

    # === Feature 7: volume_return_lag_diff_full ===
    # vol_lead_freq - ret_lead_freq (net information flow direction)
    if not np.isnan(out[1]) and not np.isnan(out[2]):
        out[7] = out[1] - out[2]

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
            "Temporal microstructure dynamics for the full-day window. "
            "8 features: inter-bar gap Amihud, volume-return lead-lag frequencies, "
            "extremum timing, gap-body ratio, range contraction frequency, "
            "and net information flow direction. Explores non-Amihud temporal "
            "structure dimensions."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the temporal microstructure full-day bundle"
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
