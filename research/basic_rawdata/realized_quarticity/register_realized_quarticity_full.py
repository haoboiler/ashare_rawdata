#!/usr/bin/env python3
"""Register the realized quarticity bundle for the full-day window.

Bundle: realized_quarticity_0930_1130_1300_1457
- Input: close, volume, amount (from 1m bars)
- Output: 8 variables covering realized quarticity and liquidity-adjusted
  tail risk measures.

Physical hypothesis:
Higher-order return moments, when normalized by trading activity (amount),
measure extreme price impact — a dimension of liquidity. Stocks where
large price moves happen with small trading activity have poor liquidity.
The discrete extreme-bar counting aligns with the finding that
discrete regime counting >> continuous distribution statistics.
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
from ashare_hf_variable.registry import upsert_definition

NAME = "realized_quarticity_0930_1130_1300_1457"

OUTPUT_NAMES = [
    # --- baseline (1) ---
    "realized_quarticity_full",
    # --- liquidity-adjusted quarticity (1) ---
    "amihud_quarticity_full",
    # --- scale-free tail measure (1) ---
    "kurtosis_ratio_full",
    # --- discrete tail counting (1) ---
    "extreme_bar_ratio_full",
    # --- conditional price impact (3) ---
    "extreme_amihud_full",
    "extreme_amihud_ratio_full",
    "quarticity_concentration_full",
    # --- tail-volume relationship (1) ---
    "tail_volume_share_full",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 8

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n == 0:
        return out

    # ---- pre-compute returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret_count += 1

    if valid_ret_count < 20:
        return out

    # ---- pre-compute per-bar r^2, r^4, |r|, amihud ----
    r2_arr = np.empty(n_ret, dtype=np.float64)
    r4_arr = np.empty(n_ret, dtype=np.float64)
    abs_r_arr = np.empty(n_ret, dtype=np.float64)
    amihud_arr = np.empty(n_ret, dtype=np.float64)

    sum_r2 = 0.0
    sum_r4 = 0.0
    cnt_r = 0
    sum_amihud_q = 0.0
    cnt_aq = 0

    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            r2_arr[i] = np.nan
            r4_arr[i] = np.nan
            abs_r_arr[i] = np.nan
            amihud_arr[i] = np.nan
            continue

        ar = abs(r)
        r2 = r * r
        r4 = r2 * r2
        abs_r_arr[i] = ar
        r2_arr[i] = r2
        r4_arr[i] = r4
        sum_r2 += r2
        sum_r4 += r4
        cnt_r += 1

        a = amount[i + 1]
        if np.isnan(a) or a <= 0.0:
            amihud_arr[i] = np.nan
        else:
            amihud_arr[i] = ar / a
            sum_amihud_q += r4 / a
            cnt_aq += 1

    if cnt_r < 20:
        return out

    # ---- 0: realized_quarticity = mean(r^4) ----
    mean_r4 = sum_r4 / cnt_r
    out[0] = mean_r4

    # ---- 1: amihud_quarticity = mean(r^4 / amount) * 1e18 ----
    if cnt_aq > 0:
        out[1] = (sum_amihud_q / cnt_aq) * 1.0e18

    # ---- 2: kurtosis_ratio = mean(r^4) / mean(r^2)^2 ----
    mean_r2 = sum_r2 / cnt_r
    if mean_r2 > 0.0:
        out[2] = mean_r4 / (mean_r2 * mean_r2)

    # ---- compute median(|r|) for extreme bar threshold ----
    valid_abs_r = np.empty(cnt_r, dtype=np.float64)
    j = 0
    for i in range(n_ret):
        if not np.isnan(abs_r_arr[i]):
            valid_abs_r[j] = abs_r_arr[i]
            j += 1
    valid_abs_r_sorted = np.sort(valid_abs_r[:j])
    median_abs_r = valid_abs_r_sorted[j // 2]

    # extreme threshold = 2 * median(|r|)
    threshold = 2.0 * median_abs_r

    # ---- 3: extreme_bar_ratio = count(|r| > threshold) / total ----
    extreme_cnt = 0
    normal_cnt = 0
    extreme_amihud_sum = 0.0
    extreme_amihud_cnt = 0
    normal_amihud_sum = 0.0
    normal_amihud_cnt = 0
    extreme_vol_sum = 0.0
    total_vol_sum = 0.0
    max_r4 = 0.0

    for i in range(n_ret):
        if np.isnan(abs_r_arr[i]):
            continue

        r4_val = r4_arr[i]
        if r4_val > max_r4:
            max_r4 = r4_val

        v = volume[i + 1]
        if not np.isnan(v):
            total_vol_sum += v

        if abs_r_arr[i] > threshold:
            extreme_cnt += 1
            if not np.isnan(amihud_arr[i]):
                extreme_amihud_sum += amihud_arr[i]
                extreme_amihud_cnt += 1
            if not np.isnan(v):
                extreme_vol_sum += v
        else:
            normal_cnt += 1
            if not np.isnan(amihud_arr[i]):
                normal_amihud_sum += amihud_arr[i]
                normal_amihud_cnt += 1

    out[3] = float(extreme_cnt) / float(cnt_r)

    # ---- 4: extreme_amihud = mean(|r|/amount for extreme bars) * 1e9 ----
    if extreme_amihud_cnt > 0:
        out[4] = (extreme_amihud_sum / extreme_amihud_cnt) * 1.0e9

    # ---- 5: extreme_amihud_ratio = extreme_amihud / normal_amihud ----
    if extreme_amihud_cnt > 0 and normal_amihud_cnt > 0:
        extreme_mean = extreme_amihud_sum / extreme_amihud_cnt
        normal_mean = normal_amihud_sum / normal_amihud_cnt
        if normal_mean > 0.0:
            out[5] = extreme_mean / normal_mean

    # ---- 6: quarticity_concentration = max(r^4) / sum(r^4) ----
    if sum_r4 > 0.0:
        out[6] = max_r4 / sum_r4

    # ---- 7: tail_volume_share = volume in extreme bars / total volume ----
    if total_vol_sum > 0.0:
        out[7] = extreme_vol_sum / total_vol_sum

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Realized quarticity bundle for the full-day window. "
            "Emits 8 variables: raw quarticity, liquidity-adjusted quarticity "
            "(Amihud 4th moment), scale-free kurtosis ratio, extreme bar ratio "
            "(discrete counting), conditional Amihud on extreme bars, "
            "extreme/normal Amihud ratio, quarticity concentration, "
            "and tail volume share."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the realized quarticity full-day bundle"
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
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
