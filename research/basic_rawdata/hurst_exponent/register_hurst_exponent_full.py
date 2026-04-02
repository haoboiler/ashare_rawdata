#!/usr/bin/env python3
"""Register the Hurst exponent bundle for full-day window.

Bundle: hurst_exponent_0930_1130_1300_1457
- Input: close, volume, amount, high, low (from 1m bars)
- Output: 6 variables capturing time-series persistence/roughness properties.

Full-day window (237 bars) for stable Hurst estimates.

Physical hypotheses:

1. hurst_volume_full: R/S Hurst exponent of the volume series.
   Measures persistence of trading activity. H>0.5 = persistent volume
   (institutional herding, order flow momentum). H<0.5 = anti-persistent
   (active→quiet alternation, market maker behavior). Stocks with more
   predictable (persistent) volume may have lower liquidity uncertainty,
   different from volume level or distribution shape.

2. hurst_return_full: R/S Hurst exponent of the log-return series.
   Control variable — expected to capture mean-reversion (H<0.5, bid-ask
   bounce) or trending (H>0.5). Related to D-003 variance_ratio but uses
   multi-scale R/S rather than single-scale VR. Risk: may fail like D-003.

3. hurst_amount_full: R/S Hurst exponent of the amount series.
   Amount = price × volume. Persistence in amount captures whether
   dollar-volume momentum exists. Risk: price component may introduce
   market-cap exposure (cf. conclusion #20).

4. hurst_range_full: R/S Hurst exponent of the bar range (high-low)/close.
   Measures volatility clustering at bar level. Persistent range =
   sustained high/low volatility episodes. Risk: may be volatility
   proxy (cf. conclusion #22, #28).

5. vol_roughness_full: Volume path roughness =
   mean(|vol[i+1]-vol[i]|) / mean(vol).
   Analogous to amihud_diff_mean (which passed at LS=1.24, LE=1.21).
   High roughness = erratic trading activity = execution uncertainty.
   Different from Hurst (multi-scale persistence vs local step size).

6. vol_var_ratio_full: Volume variance ratio =
   Var(2-bar vol) / (2 * Var(1-bar vol)).
   VR<1 = anti-persistent volume (cf. D-003 on returns).
   This is D-003 applied to volume instead of returns — testing whether
   the variance ratio signal exists in the volume dimension.
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

NAME = "hurst_exponent_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "hurst_volume_full",       # R/S Hurst on volume
    "hurst_return_full",       # R/S Hurst on returns (control)
    "hurst_amount_full",       # R/S Hurst on amount
    "hurst_range_full",        # R/S Hurst on bar range
    "vol_roughness_full",      # Volume path roughness
    "vol_var_ratio_full",      # Volume variance ratio
]

FORMULA = """@njit
def _rs_hurst(series, n_valid):
    \"\"\"Estimate Hurst exponent via Rescaled Range (R/S) analysis.

    Uses window sizes [8, 12, 16, 24, 32, 48, 64, 96, 128] and fits
    log(R/S) vs log(n) regression to get H.
    \"\"\"
    sizes_arr = np.array([8, 12, 16, 24, 32, 48, 64, 96, 128], dtype=np.int64)
    max_pts = 9

    log_n = np.empty(max_pts, dtype=np.float64)
    log_rs = np.empty(max_pts, dtype=np.float64)
    n_pts = 0

    for s_idx in range(max_pts):
        size = sizes_arr[s_idx]
        if size > n_valid:
            continue

        n_windows = n_valid // size
        if n_windows < 1:
            continue

        rs_sum = 0.0
        rs_count = 0

        for w in range(n_windows):
            start = w * size

            # mean of this window
            wm = 0.0
            for i in range(size):
                wm += series[start + i]
            wm /= size

            # cumulative deviation, range, and std
            max_dev = -1e30
            min_dev = 1e30
            cum_dev = 0.0
            ss = 0.0
            for i in range(size):
                d = series[start + i] - wm
                cum_dev += d
                ss += d * d
                if cum_dev > max_dev:
                    max_dev = cum_dev
                if cum_dev < min_dev:
                    min_dev = cum_dev

            R = max_dev - min_dev
            S = np.sqrt(ss / size)

            if S > 1e-15 and R > 0.0:
                rs_sum += R / S
                rs_count += 1

        if rs_count > 0:
            log_n[n_pts] = np.log(float(size))
            log_rs[n_pts] = np.log(rs_sum / rs_count)
            n_pts += 1

    if n_pts < 3:
        return np.nan

    # OLS: log_rs = H * log_n + c
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    sxy = 0.0
    for i in range(n_pts):
        sx += log_n[i]
        sy += log_rs[i]
        sxx += log_n[i] * log_n[i]
        sxy += log_n[i] * log_rs[i]

    denom = n_pts * sxx - sx * sx
    if abs(denom) < 1e-15:
        return np.nan

    H = (n_pts * sxy - sx * sy) / denom
    return H

@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]
    high = inputs[3]
    low = inputs[4]

    n = close.size
    n_out = 6
    out = np.full(n_out, np.nan, dtype=np.float64)

    if n < 32:
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

    # --- Build clean return series ---
    n_ret = n - 1
    clean_ret = np.empty(n_ret, dtype=np.float64)
    ret_valid = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if not np.isnan(c0) and not np.isnan(c1) and c0 > 0.0 and c1 > 0.0:
            clean_ret[ret_valid] = np.log(c1 / c0)
            ret_valid += 1

    # --- Build clean amount series ---
    clean_amt = np.empty(n, dtype=np.float64)
    amt_valid = 0
    for i in range(n):
        a = amount[i]
        if not np.isnan(a) and a >= 0.0:
            clean_amt[amt_valid] = a
            amt_valid += 1

    # --- Build clean bar range series: (high - low) / close ---
    clean_range = np.empty(n, dtype=np.float64)
    range_valid = 0
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        if not np.isnan(h) and not np.isnan(l) and not np.isnan(c) and c > 0.0:
            clean_range[range_valid] = (h - l) / c
            range_valid += 1

    # --- 0: hurst_volume_full ---
    if vol_valid >= 32:
        out[0] = _rs_hurst(clean_vol, vol_valid)

    # --- 1: hurst_return_full ---
    if ret_valid >= 32:
        out[1] = _rs_hurst(clean_ret, ret_valid)

    # --- 2: hurst_amount_full ---
    if amt_valid >= 32:
        out[2] = _rs_hurst(clean_amt, amt_valid)

    # --- 3: hurst_range_full ---
    if range_valid >= 32:
        out[3] = _rs_hurst(clean_range, range_valid)

    # --- 4: vol_roughness_full = mean(|vol[i+1]-vol[i]|) / mean(vol) ---
    if vol_valid >= 2 and vol_sum > 0.0:
        vol_mean = vol_sum / vol_valid
        diff_sum = 0.0
        diff_cnt = 0
        for i in range(vol_valid - 1):
            diff_sum += abs(clean_vol[i + 1] - clean_vol[i])
            diff_cnt += 1
        if diff_cnt > 0 and vol_mean > 0.0:
            out[4] = (diff_sum / diff_cnt) / vol_mean

    # --- 5: vol_var_ratio_full = Var(2-bar vol) / (2 * Var(1-bar vol)) ---
    if vol_valid >= 4:
        vol_mean = vol_sum / vol_valid
        # 1-bar variance: var of (vol - mean)
        var1 = 0.0
        for i in range(vol_valid):
            d = clean_vol[i] - vol_mean
            var1 += d * d
        var1 /= (vol_valid - 1)

        # 2-bar sum series variance
        n2 = vol_valid // 2
        if n2 >= 2:
            sum2 = np.empty(n2, dtype=np.float64)
            for i in range(n2):
                sum2[i] = clean_vol[2 * i] + clean_vol[2 * i + 1]
            mean2 = 0.0
            for i in range(n2):
                mean2 += sum2[i]
            mean2 /= n2
            var2 = 0.0
            for i in range(n2):
                d = sum2[i] - mean2
                var2 += d * d
            var2 /= (n2 - 1)

            if var1 > 1e-15:
                out[5] = var2 / (2.0 * var1)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount", "high", "low"],
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
            "Hurst exponent and persistence/roughness bundle for full-day window. "
            "R/S Hurst on volume, returns, amount, and bar range; "
            "volume path roughness; volume variance ratio. "
            "Tests whether time-series memory structure of intraday data "
            "provides cross-sectional signal for stock selection."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Hurst exponent full-day bundle"
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
