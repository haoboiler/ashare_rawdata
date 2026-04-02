#!/usr/bin/env python3
"""Register the microstructure noise bundle for the full-day window.

Bundle: microstructure_noise_0930_1130_1300_1457
- Input: close, open, high, low, volume, amount (from 1m bars)
- Output: 6 variables capturing microstructure noise via multi-scale
  realized variance comparison and amount-normalized autocovariance.

Physical hypothesis:
1. Microstructure noise (bid-ask bounce) inflates realized variance at
   higher frequencies. RV(1min) > RV(5min) because consecutive 1-min
   returns are negatively autocorrelated due to bid-ask bounce.
2. The DIFFERENCE (RV_1min - RV_kmin) isolates the noise component.
3. Amount normalization converts noise variance into "noise cost per
   unit of trading" — analogous to Amihud but measuring noise rather
   than total price impact.
4. This is theoretically independent from:
   - Amihud (total |return|/amount, not decomposed into signal/noise)
   - CS spread (bid-ask spread from adjacent bar H-L ranges)
   - Reversal ratio (frequency count of direction changes)
5. D-003 variance_ratio tested VR on 0930-1030 window WITHOUT amount
   normalization and failed on Long Excess. Amount normalization has
   been proven to rescue failed price metrics (conclusion #48).
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

NAME = "microstructure_noise_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "autocov_amihud_full",          # |sum(r_i*r_{i+1})| / (n_pairs * mean(amount)) * 1e9
    "noise_ratio_5_full",           # 1 - RV_5min / RV_1min (dimensionless noise fraction)
    "noise_amihud_5_full",          # (RV_1min - RV_5min) / mean(amount) * 1e9
    "noise_ratio_10_full",          # 1 - RV_10min / RV_1min
    "noise_amihud_10_full",         # (RV_1min - RV_10min) / mean(amount) * 1e9
    "high_vol_noise_amihud_full",   # noise_amihud_5 computed on high-volume bar pairs only
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

    # --- Pre-compute returns ---
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0 or c1 <= 0.0:
            rets[i] = np.nan
        else:
            rets[i] = c1 / c0 - 1.0
            valid_ret_count += 1

    if valid_ret_count < 20:
        return out

    # --- Compute mean(amount) for normalization ---
    amt_sum = 0.0
    amt_cnt = 0
    for i in range(n):
        if not np.isnan(amount[i]) and amount[i] > 0.0:
            amt_sum += amount[i]
            amt_cnt += 1
    if amt_cnt == 0:
        return out
    mean_amt = amt_sum / amt_cnt

    # --- Compute volume median for conditional features ---
    valid_vols = np.empty(n, dtype=np.float64)
    vol_cnt = 0
    for i in range(n):
        if not np.isnan(volume[i]) and volume[i] > 0.0:
            valid_vols[vol_cnt] = volume[i]
            vol_cnt += 1

    vol_median = 0.0
    if vol_cnt > 0:
        # Simple median via sorting
        sorted_vols = valid_vols[:vol_cnt].copy()
        sorted_vols.sort()
        if vol_cnt % 2 == 0:
            vol_median = (sorted_vols[vol_cnt // 2 - 1] + sorted_vols[vol_cnt // 2]) / 2.0
        else:
            vol_median = sorted_vols[vol_cnt // 2]

    # === Feature 0: autocov_amihud_full ===
    # First-order return autocovariance normalized by amount
    # autocov = sum(r_i * r_{i+1}) for consecutive valid pairs
    # autocov_amihud = |autocov| / (n_pairs * mean_amt) * 1e9
    autocov_sum = 0.0
    autocov_cnt = 0
    for i in range(n_ret - 1):
        if not np.isnan(rets[i]) and not np.isnan(rets[i + 1]):
            autocov_sum += rets[i] * rets[i + 1]
            autocov_cnt += 1
    if autocov_cnt > 5:
        out[0] = abs(autocov_sum) / (autocov_cnt * mean_amt) * 1e9

    # === Feature 1: noise_ratio_5_full ===
    # RV_1min = sum(r_i^2), RV_5min = sum(R_j^2) where R_j = sum of 5 consecutive r_i
    # noise_ratio = 1 - RV_5min / RV_1min
    rv_1min = 0.0
    rv_1min_cnt = 0
    for i in range(n_ret):
        if not np.isnan(rets[i]):
            rv_1min += rets[i] * rets[i]
            rv_1min_cnt += 1

    if rv_1min > 0.0 and rv_1min_cnt > 20:
        # Compute RV at 5-bar aggregation
        block_size = 5
        n_blocks = n_ret // block_size
        rv_5min = 0.0
        rv_5min_cnt = 0
        for b in range(n_blocks):
            start = b * block_size
            block_ret = 0.0
            block_valid = True
            for j in range(start, start + block_size):
                if j >= n_ret or np.isnan(rets[j]):
                    block_valid = False
                    break
                block_ret += rets[j]
            if block_valid:
                rv_5min += block_ret * block_ret
                rv_5min_cnt += 1

        if rv_5min_cnt > 4:
            out[1] = 1.0 - rv_5min / rv_1min

            # === Feature 2: noise_amihud_5_full ===
            noise_var = rv_1min - rv_5min
            out[2] = noise_var / mean_amt * 1e9

        # === Feature 3: noise_ratio_10_full ===
        block_size_10 = 10
        n_blocks_10 = n_ret // block_size_10
        rv_10min = 0.0
        rv_10min_cnt = 0
        for b in range(n_blocks_10):
            start = b * block_size_10
            block_ret = 0.0
            block_valid = True
            for j in range(start, start + block_size_10):
                if j >= n_ret or np.isnan(rets[j]):
                    block_valid = False
                    break
                block_ret += rets[j]
            if block_valid:
                rv_10min += block_ret * block_ret
                rv_10min_cnt += 1

        if rv_10min_cnt > 2:
            out[3] = 1.0 - rv_10min / rv_1min

            # === Feature 4: noise_amihud_10_full ===
            noise_var_10 = rv_1min - rv_10min
            out[4] = noise_var_10 / mean_amt * 1e9

    # === Feature 5: high_vol_noise_amihud_full ===
    # noise_amihud_5 computed only on bar pairs where BOTH bars have volume > median
    if vol_median > 0.0 and rv_1min > 0.0:
        # RV_1min for high-vol bars
        hv_rv_1min = 0.0
        hv_rv_cnt = 0
        # We need pairs of consecutive high-vol bars
        for i in range(n_ret):
            if (not np.isnan(rets[i]) and not np.isnan(volume[i]) and
                    not np.isnan(volume[i + 1]) and
                    volume[i] > vol_median and volume[i + 1] > vol_median):
                hv_rv_1min += rets[i] * rets[i]
                hv_rv_cnt += 1

        if hv_rv_cnt > 10:
            # RV_5min for high-vol blocks (all 5 consecutive bars must be high-vol)
            block_size = 5
            hv_n_blocks = hv_rv_cnt // block_size
            # Instead of trying to align blocks, use overlapping approach:
            # Accumulate consecutive high-vol returns into blocks
            hv_rets = np.empty(hv_rv_cnt, dtype=np.float64)
            idx = 0
            for i in range(n_ret):
                if (not np.isnan(rets[i]) and not np.isnan(volume[i]) and
                        not np.isnan(volume[i + 1]) and
                        volume[i] > vol_median and volume[i + 1] > vol_median):
                    hv_rets[idx] = rets[i]
                    idx += 1

            hv_rv_5min = 0.0
            hv_rv_5cnt = 0
            actual_blocks = hv_rv_cnt // block_size
            for b in range(actual_blocks):
                start = b * block_size
                block_ret = 0.0
                for j in range(start, start + block_size):
                    block_ret += hv_rets[j]
                hv_rv_5min += block_ret * block_ret
                hv_rv_5cnt += 1

            if hv_rv_5cnt > 2 and hv_rv_1min > 0.0:
                hv_noise_var = hv_rv_1min - hv_rv_5min
                out[5] = hv_noise_var / mean_amt * 1e9

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "open", "high", "low", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Microstructure noise factors for full trading day. "
            "Multi-scale realized variance comparison (1min vs 5min/10min) "
            "captures bid-ask bounce noise. Amount-normalized versions "
            "measure noise cost per unit of trading."
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()

    defn = build_definition()
    if args.register:
        from ashare_hf_variable.registry import upsert_definition

        upsert_definition(defn)
        print(f"[OK] Registered {NAME}")
    else:
        print(json.dumps(defn.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
