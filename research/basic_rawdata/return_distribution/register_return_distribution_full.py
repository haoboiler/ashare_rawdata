#!/usr/bin/env python3
"""Return distribution bundle for the full-day window.

Bundle: return_distribution_full
- Input: close, volume, amount (from 1m bars)
- Output: 5 variables capturing higher moments and tail structure
  of intraday 1-minute log returns.

Physical hypotheses:
1. return_skewness: Negative intraday skewness = asymmetric downside risk.
   Stocks with more negative skew carry a risk premium (lottery preference).
2. return_kurtosis: High excess kurtosis = frequent extreme jumps.
   Reflects information uncertainty and tail risk.
3. downside_deviation_ratio: Ratio of downside to upside semi-deviation.
   Directly measures downside risk asymmetry independent of skewness sign.
4. tail_asymmetry: Ratio of positive extreme returns to negative extreme
   returns (5th/95th percentile). Captures tail shape differences.
5. amihud_skew_interaction: Skewness weighted by Amihud illiquidity.
   Captures whether illiquid stocks also have worse return asymmetry
   (interaction of two proven alpha dimensions).
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

NAME = "return_distribution_full"

OUTPUT_NAMES = [
    "return_skewness_full",
    "return_kurtosis_full",
    "downside_deviation_ratio_full",
    "tail_asymmetry_full",
    "amihud_skew_interaction_full",
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
    rets = np.empty(n - 1, dtype=np.float64)
    valid_count = 0
    for i in range(n - 1):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_count += 1

    if valid_count < 20:
        return out

    # ---- compute mean and moments ----
    ret_mean = 0.0
    cnt = 0
    for i in range(n - 1):
        r = rets[i]
        if not np.isnan(r):
            ret_mean += r
            cnt += 1
    ret_mean /= cnt

    m2 = 0.0
    m3 = 0.0
    m4 = 0.0
    for i in range(n - 1):
        r = rets[i]
        if np.isnan(r):
            continue
        d = r - ret_mean
        d2 = d * d
        m2 += d2
        m3 += d2 * d
        m4 += d2 * d2
    m2 /= cnt
    m3 /= cnt
    m4 /= cnt

    # ---- 0: return_skewness = m3 / m2^1.5 ----
    if m2 > 1e-20:
        std = np.sqrt(m2)
        out[0] = m3 / (m2 * std)

        # ---- 1: return_kurtosis (excess) = m4 / m2^2 - 3 ----
        out[1] = m4 / (m2 * m2) - 3.0

    # ---- 2: downside_deviation_ratio = sqrt(downside_var / upside_var) ----
    down_ss = 0.0
    down_cnt = 0
    up_ss = 0.0
    up_cnt = 0
    for i in range(n - 1):
        r = rets[i]
        if np.isnan(r):
            continue
        d = r - ret_mean
        if d < 0.0:
            down_ss += d * d
            down_cnt += 1
        elif d > 0.0:
            up_ss += d * d
            up_cnt += 1
    if down_cnt > 0 and up_cnt > 0:
        down_var = down_ss / down_cnt
        up_var = up_ss / up_cnt
        if up_var > 1e-20:
            out[2] = np.sqrt(down_var / up_var)

    # ---- 3: tail_asymmetry = percentile_95 / abs(percentile_05) ----
    # Collect valid returns into a sorted array
    valid_rets = np.empty(cnt, dtype=np.float64)
    idx = 0
    for i in range(n - 1):
        r = rets[i]
        if not np.isnan(r):
            valid_rets[idx] = r
            idx += 1
    # Simple insertion sort for numba compatibility
    for i in range(1, cnt):
        key = valid_rets[i]
        j = i - 1
        while j >= 0 and valid_rets[j] > key:
            valid_rets[j + 1] = valid_rets[j]
            j -= 1
        valid_rets[j + 1] = key

    # Percentile via linear interpolation
    p05_idx = 0.05 * (cnt - 1)
    p05_lo = int(p05_idx)
    p05_frac = p05_idx - p05_lo
    if p05_lo >= cnt - 1:
        p05 = valid_rets[cnt - 1]
    else:
        p05 = valid_rets[p05_lo] * (1.0 - p05_frac) + valid_rets[p05_lo + 1] * p05_frac

    p95_idx = 0.95 * (cnt - 1)
    p95_lo = int(p95_idx)
    p95_frac = p95_idx - p95_lo
    if p95_lo >= cnt - 1:
        p95 = valid_rets[cnt - 1]
    else:
        p95 = valid_rets[p95_lo] * (1.0 - p95_frac) + valid_rets[p95_lo + 1] * p95_frac

    if abs(p05) > 1e-20:
        out[3] = p95 / abs(p05)

    # ---- 4: amihud_skew_interaction = skewness * mean(|r| / amount) ----
    if not np.isnan(out[0]):
        amihud_sum = 0.0
        amihud_cnt = 0
        for i in range(n - 1):
            r = rets[i]
            a = amount[i + 1]
            if np.isnan(r) or np.isnan(a) or a <= 0.0:
                continue
            amihud_sum += abs(r) / a
            amihud_cnt += 1
        if amihud_cnt > 0:
            amihud_mean = amihud_sum / amihud_cnt
            out[4] = out[0] * amihud_mean

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
            "Intraday return distribution bundle for the full-day window. "
            "Emits 5 variables: return skewness, excess kurtosis, "
            "downside deviation ratio, tail asymmetry (p95/|p05|), "
            "and Amihud-skewness interaction. Captures asymmetric risk "
            "structure and tail behavior of 1-minute log returns."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the return distribution full-day bundle"
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
