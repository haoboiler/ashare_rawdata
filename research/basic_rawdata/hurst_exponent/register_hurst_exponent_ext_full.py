#!/usr/bin/env python3
"""Extended roughness/persistence features for D-010 hurst_exponent direction.

Bundle: hurst_exponent_ext_0930_1130_1300_1457
- Input: close, volume (from 1m bars, basic6 preset sufficient)
- Output: 3 features exploring roughness variants beyond vol_roughness_full.

Physical hypotheses:

1. log_vol_roughness_full: mean(|Δlog(vol+1)|)
   Log transform compresses extreme volume spikes. If vol_roughness is driven
   by a few outlier bars (e.g., block trades), log-roughness should be more
   robust. If signal survives log transform → roughness is pervasive, not
   outlier-driven. Normalization: log already normalizes scale, so no
   division by mean(log(vol+1)) needed (it would introduce level exposure).

2. vol_accel_full: mean(|Δ²vol|) / mean(vol)
   Second-order path roughness = "jerkiness" of volume trajectory.
   Δ²vol = vol[t] - 2*vol[t-1] + vol[t-2] measures how quickly volume
   *changes* are themselves changing. High acceleration = chaotic,
   unpredictable liquidity supply/demand transitions. Different from
   first-order roughness: a linearly trending volume series has high
   roughness but zero acceleration.

3. vol_change_asym_full: count(Δvol > 0) / count(Δvol != 0)
   Directional asymmetry of volume changes. Ratio near 0.5 = symmetric
   ups/downs. Deviation from 0.5 indicates whether volume tends to
   incrementally grow (>0.5, institutional accumulation) or decay
   (<0.5, activity fading). This is about the *sign* of changes,
   orthogonal to *magnitude* measured by roughness.
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

NAME = "hurst_exponent_ext_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "log_vol_roughness_full",   # Log-volume path roughness
    "vol_accel_full",           # Volume acceleration (2nd-order roughness)
    "vol_change_asym_full",     # Volume change directional asymmetry
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    n = close.size
    n_out = 3
    out = np.full(n_out, np.nan, dtype=np.float64)

    if n < 10:
        return out

    # --- Build clean volume series ---
    clean_vol = np.empty(n, dtype=np.float64)
    vol_valid = 0
    vol_sum = 0.0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v >= 0.0:
            clean_vol[vol_valid] = v
            vol_sum += v
            vol_valid += 1

    if vol_valid < 10:
        return out

    vol_mean = vol_sum / vol_valid

    # --- 0: log_vol_roughness_full = mean(|Δlog(vol+1)|) ---
    log_diff_sum = 0.0
    log_diff_cnt = 0
    for i in range(vol_valid - 1):
        lv0 = np.log(clean_vol[i] + 1.0)
        lv1 = np.log(clean_vol[i + 1] + 1.0)
        log_diff_sum += abs(lv1 - lv0)
        log_diff_cnt += 1
    if log_diff_cnt > 0:
        out[0] = log_diff_sum / log_diff_cnt

    # --- 1: vol_accel_full = mean(|Δ²vol|) / mean(vol) ---
    # Δ²vol[i] = vol[i] - 2*vol[i-1] + vol[i-2]
    if vol_valid >= 3 and vol_mean > 0.0:
        accel_sum = 0.0
        accel_cnt = 0
        for i in range(2, vol_valid):
            d2 = clean_vol[i] - 2.0 * clean_vol[i - 1] + clean_vol[i - 2]
            accel_sum += abs(d2)
            accel_cnt += 1
        if accel_cnt > 0:
            out[1] = (accel_sum / accel_cnt) / vol_mean

    # --- 2: vol_change_asym_full = count(Δvol > 0) / count(Δvol != 0) ---
    pos_count = 0
    nonzero_count = 0
    for i in range(vol_valid - 1):
        delta = clean_vol[i + 1] - clean_vol[i]
        if delta > 0.0:
            pos_count += 1
            nonzero_count += 1
        elif delta < 0.0:
            nonzero_count += 1
        # delta == 0.0 is excluded from count
    if nonzero_count > 10:
        out[2] = float(pos_count) / float(nonzero_count)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume"],
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
            "Extended roughness/persistence features for D-010 hurst_exponent. "
            "Log-volume roughness, volume acceleration (2nd-order roughness), "
            "and volume change directional asymmetry."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the hurst_exponent_ext full-day bundle"
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Write the definition into the configured registry backend",
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
        upsert_definition(definition, validate=True)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
