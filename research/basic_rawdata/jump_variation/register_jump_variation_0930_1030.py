#!/usr/bin/env python3
"""Register the jump variation bundle for the 09:30-10:30 window.

Bundle: jump_variation_0930_1030
- Input: close, volume (from 1m bars)
- Output: 5 variables covering jump/diffusion decomposition of intraday variance

Physical hypothesis:
  Realized variance (RV) = sum(r^2) captures total price variation.
  Bipower variation (BPV) = (π/2) * sum(|r_i|*|r_{i-1}|) estimates the continuous
  (diffusion) component robustly, so max(RV - BPV, 0) isolates the jump component.
  Stocks with different jump profiles (intensity, direction, volume absorption)
  exhibit different risk/return characteristics.

Reference: Barndorff-Nielsen & Shephard (2006), Tauchen & Zhou (2011)
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

NAME = "jump_variation_0930_1030"

OUTPUT_NAMES = [
    # --- Variance decomposition (2) ---
    "bipower_var_0930_1030",       # continuous variance estimator (BPV)
    "jump_var_ratio_0930_1030",    # max(1 - BPV/RV, 0): fraction of variance from jumps
    # --- Jump characteristics (3) ---
    "jump_intensity_0930_1030",    # fraction of bars classified as jumps
    "signed_jump_0930_1030",       # directional bias of jumps: sum(r_jump)/sum(|r_jump|)
    "jump_vol_fraction_0930_1030", # volume on jump bars / total volume
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    n = close.size
    n_out = 5

    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 5:
        return out

    # ---- Compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = np.log(c1 / c0)
            valid_count += 1

    if valid_count < 5:
        return out

    # ---- Realized Variance: RV = sum(r_i^2) ----
    rv = 0.0
    rv_count = 0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            rv += r * r
            rv_count += 1

    if rv_count < 3 or rv <= 0.0:
        return out

    # ---- Bipower Variation: BPV = (pi/2) * sum(|r_i|*|r_{i-1}|) * n/(n-1) ----
    bpv_sum = 0.0
    bpv_count = 0
    for i in range(1, n_ret):
        r_prev = rets[i - 1]
        r_curr = rets[i]
        if not np.isnan(r_prev) and not np.isnan(r_curr):
            bpv_sum += abs(r_prev) * abs(r_curr)
            bpv_count += 1

    if bpv_count < 2:
        return out

    # Scale factor: (pi/2) * (n/(n-1)) to make BPV an unbiased estimator of IV
    bpv = (np.pi / 2.0) * bpv_sum * (float(rv_count) / float(rv_count - 1))

    # [0] bipower_var
    out[0] = bpv

    # [1] jump_var_ratio = max(1 - BPV/RV, 0)
    jvr = max(1.0 - bpv / rv, 0.0)
    out[1] = jvr

    # ---- Jump detection: |r_i| > 3 * median(|r_i|) ----
    # Collect absolute returns for median computation
    abs_rets = np.empty(rv_count, dtype=np.float64)
    k = 0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            abs_rets[k] = abs(r)
            k += 1

    # Sort for median (insertion sort, n<=60 so fine)
    for i in range(1, k):
        key = abs_rets[i]
        j = i - 1
        while j >= 0 and abs_rets[j] > key:
            abs_rets[j + 1] = abs_rets[j]
            j -= 1
        abs_rets[j + 1] = key

    if k % 2 == 0:
        med_abs = (abs_rets[k // 2 - 1] + abs_rets[k // 2]) / 2.0
    else:
        med_abs = abs_rets[k // 2]

    # Threshold: 3x median absolute return
    threshold = 3.0 * med_abs

    # ---- Compute jump bar metrics ----
    n_jumps = 0
    jump_ret_sum = 0.0
    jump_abs_ret_sum = 0.0
    jump_vol = 0.0
    total_vol = 0.0

    for i in range(n_ret):
        r = rets[i]
        if np.isnan(r):
            continue

        v = volume[i + 1]
        if not np.isnan(v) and v > 0.0:
            total_vol += v

        if abs(r) > threshold:
            n_jumps += 1
            jump_ret_sum += r
            jump_abs_ret_sum += abs(r)
            if not np.isnan(v) and v > 0.0:
                jump_vol += v

    # [2] jump_intensity = n_jumps / rv_count
    out[2] = float(n_jumps) / float(rv_count)

    # [3] signed_jump = sum(r_jump) / sum(|r_jump|), range [-1, 1]
    if jump_abs_ret_sum > 0.0:
        out[3] = jump_ret_sum / jump_abs_ret_sum
    else:
        out[3] = 0.0

    # [4] jump_vol_fraction = volume on jump bars / total volume
    if total_vol > 0.0:
        out[4] = jump_vol / total_vol

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "10:30")]),
        slot=RawDataSlot.MIDDAY,
        data_available_at=1031,
        execution_start_at=930,
        execution_end_at=1030,
        expected_bars=40,
        description=(
            "Jump variation bundle for the 09:30-10:30 window. "
            "Decomposes realized variance into continuous (bipower variation) and "
            "jump components using Barndorff-Nielsen & Shephard (2006) methodology. "
            "Outputs: BPV, jump variance ratio, jump intensity, signed jump direction, "
            "and volume fraction on jump bars."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the jump variation 09:30-10:30 bundle"
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
