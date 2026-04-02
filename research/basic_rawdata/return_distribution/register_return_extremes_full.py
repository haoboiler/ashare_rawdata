#!/usr/bin/env python3
"""Return extremes bundle for the full-day window.

Bundle: return_extremes_full
- Input: close, volume, amount (from 1m bars)
- Output: 5 variables capturing extreme return frequency and asymmetry
  using discrete count-based measures (following the reversal_ratio/
  regime_transitions paradigm that has been validated).

Physical hypotheses:
1. extreme_return_freq: Fraction of bars with |return| > 2× median(|return|).
   High frequency of extreme moves = information-rich but uncertain trading
   environment. Discretization removes absolute magnitude exposure.
2. positive_extreme_freq: Fraction of bars with return > 2× median(|return|).
   Captures upside jump frequency (lottery-like behavior).
3. extreme_asymmetry_freq: positive_extreme_count / total_extreme_count.
   Measures directional bias of extreme moves. Stocks with asymmetric
   extreme returns carry different risk premia.
4. extreme_volume_ratio: mean volume of extreme bars / mean volume of
   non-extreme bars. If extreme moves happen on high volume = informed trading;
   on low volume = noise.
5. extreme_amihud_ratio: mean Amihud of extreme bars / mean Amihud of
   non-extreme bars. Captures whether price impact is higher during extreme
   moves (market stress vs normal liquidity).
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

NAME = "return_extremes_full"

OUTPUT_NAMES = [
    "extreme_return_freq_full",
    "positive_extreme_freq_full",
    "extreme_asymmetry_freq_full",
    "extreme_volume_ratio_full",
    "extreme_amihud_ratio_full",
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    # ---- compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    abs_rets = np.empty(n_ret, dtype=np.float64)
    valid_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
            abs_rets[i] = np.nan
        else:
            r = np.log(c1 / c0)
            rets[i] = r
            abs_rets[i] = abs(r)
            valid_count += 1

    if valid_count < 30:
        return out

    # ---- compute median of |return| via sorting ----
    valid_abs = np.empty(valid_count, dtype=np.float64)
    idx = 0
    for i in range(n_ret):
        if not np.isnan(abs_rets[i]):
            valid_abs[idx] = abs_rets[i]
            idx += 1

    # insertion sort for numba
    for i in range(1, valid_count):
        key = valid_abs[i]
        j = i - 1
        while j >= 0 and valid_abs[j] > key:
            valid_abs[j + 1] = valid_abs[j]
            j -= 1
        valid_abs[j + 1] = key

    if valid_count % 2 == 0:
        median_abs = (valid_abs[valid_count // 2 - 1] + valid_abs[valid_count // 2]) / 2.0
    else:
        median_abs = valid_abs[valid_count // 2]

    if median_abs < 1e-20:
        return out

    threshold = 2.0 * median_abs

    # ---- classify extreme bars ----
    total_extreme = 0
    positive_extreme = 0
    negative_extreme = 0

    # For volume/amihud stats
    vol_extreme_sum = 0.0
    vol_extreme_cnt = 0
    vol_normal_sum = 0.0
    vol_normal_cnt = 0
    amihud_extreme_sum = 0.0
    amihud_extreme_cnt = 0
    amihud_normal_sum = 0.0
    amihud_normal_cnt = 0

    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue
        v = volume[i + 1]
        a = amount[i + 1]
        is_extreme = abs(r) > threshold

        if is_extreme:
            total_extreme += 1
            if r > 0:
                positive_extreme += 1
            else:
                negative_extreme += 1
            # volume stats for extreme bars
            if not np.isnan(v):
                vol_extreme_sum += v
                vol_extreme_cnt += 1
            # amihud for extreme bars
            if not np.isnan(a) and a > 0.0:
                amihud_extreme_sum += abs(r) / a
                amihud_extreme_cnt += 1
        else:
            # volume stats for normal bars
            if not np.isnan(v):
                vol_normal_sum += v
                vol_normal_cnt += 1
            # amihud for normal bars
            if not np.isnan(r) and not np.isnan(a) and a > 0.0:
                amihud_normal_sum += abs(r) / a
                amihud_normal_cnt += 1

    # ---- 0: extreme_return_freq = total_extreme / valid_count ----
    out[0] = float(total_extreme) / float(valid_count)

    # ---- 1: positive_extreme_freq = positive_extreme / valid_count ----
    out[1] = float(positive_extreme) / float(valid_count)

    # ---- 2: extreme_asymmetry_freq = pos_extreme / total_extreme ----
    if total_extreme > 0:
        out[2] = float(positive_extreme) / float(total_extreme)

    # ---- 3: extreme_volume_ratio = mean_vol_extreme / mean_vol_normal ----
    if vol_extreme_cnt > 0 and vol_normal_cnt > 0:
        mean_vol_ext = vol_extreme_sum / vol_extreme_cnt
        mean_vol_norm = vol_normal_sum / vol_normal_cnt
        if mean_vol_norm > 0.0:
            out[3] = mean_vol_ext / mean_vol_norm

    # ---- 4: extreme_amihud_ratio = mean_amihud_extreme / mean_amihud_normal ----
    if amihud_extreme_cnt > 0 and amihud_normal_cnt > 0:
        mean_ami_ext = amihud_extreme_sum / amihud_extreme_cnt
        mean_ami_norm = amihud_normal_sum / amihud_normal_cnt
        if mean_ami_norm > 0.0:
            out[4] = mean_ami_ext / mean_ami_norm

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(
            input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]
        ),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Return extremes bundle for the full-day window. "
            "Emits 5 variables: extreme return frequency, positive extreme frequency, "
            "extreme asymmetry, extreme-to-normal volume ratio, "
            "and extreme-to-normal Amihud ratio. Uses discrete count-based measures "
            "following the reversal_ratio paradigm."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the return extremes full-day bundle"
    )
    parser.add_argument(
        "--register", action="store_true",
        help="Write the definition into the configured registry backend",
    )
    parser.add_argument(
        "--skip-validate", action="store_true",
        help="Skip formula validation during registration",
    )
    parser.add_argument(
        "--print-json", action="store_true",
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
