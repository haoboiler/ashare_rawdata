#!/usr/bin/env python3
"""Register the Roll spread liquidity bundle for the 09:30-10:30 window.

Bundle: roll_spread_0930_1030
- Input: close, volume (from 1m bars)
- Output: 5 variables capturing bid-ask spread and liquidity measures.

Physical hypothesis: Roll (1984, JFE) shows that the negative autocovariance
of price changes reflects the implicit bid-ask spread:
    cov(Δp_t, Δp_{t-1}) = -c²
where c is the half-spread. Thus:
    spread = 2 * sqrt(max(0, -cov(r_t, r_{t-1})))

The illiquidity premium (Amihud 2002, Pastor & Stambaugh 2003) predicts:
illiquid stocks (high spread) earn higher expected returns as compensation
for trading costs. Unlike microstructure dynamics factors (D-001/D-002/D-003)
that identify "bad stocks" via price anomalies, liquidity-level factors
can potentially select "good stocks" — those underpriced due to illiquidity.

Key features:
1. roll_spread_bps: Classic Roll spread in basis points
2. zero_return_pct: LOT (1999) zero-return proportion — staleness proxy
3. reversal_ratio: Bid-ask bounce frequency
4. spread_to_vol: Spread / realized_vol — spread importance decomposition
5. roll_impact: Spread × sqrt(mean_volume) — dollar-adjusted liquidity
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

NAME = "roll_spread_0930_1030"

OUTPUT_NAMES = [
    "roll_spread_bps_0930_1030",       # Roll (1984) spread in basis points
    "zero_return_pct_0930_1030",       # LOT zero-return proportion (%)
    "reversal_ratio_0930_1030",        # Price direction reversal frequency
    "spread_to_vol_0930_1030",         # Roll spread / realized volatility
    "roll_impact_0930_1030",           # Roll spread * sqrt(mean_volume)
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

    # ---- Pre-compute log returns ----
    n_ret = n - 1
    rets = np.empty(n_ret, dtype=np.float64)
    valid_ret_count = 0
    zero_ret_count = 0

    for i in range(n_ret):
        c0 = close[i]
        c1 = close[i + 1]
        if np.isnan(c0) or np.isnan(c1) or c0 <= 0.0:
            rets[i] = np.nan
        else:
            r = np.log(c1 / c0)
            rets[i] = r
            valid_ret_count += 1
            if abs(r) < 1e-12:
                zero_ret_count += 1

    if valid_ret_count < 5:
        return out

    # ---- Return statistics ----
    ret_sum = 0.0
    ret_cnt = 0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            ret_sum += r
            ret_cnt += 1

    if ret_cnt < 5:
        return out
    ret_mean = ret_sum / ret_cnt

    # ---- Realized volatility (for spread_to_vol) ----
    ss = 0.0
    for i in range(n_ret):
        r = rets[i]
        if not np.isnan(r):
            d = r - ret_mean
            ss += d * d
    realized_var = ss / (ret_cnt - 1)
    realized_vol = np.sqrt(realized_var) if realized_var > 0.0 else 0.0

    # ---- Lag-1 autocovariance of returns ----
    # gamma_1 = (1/m) * sum((r_t - r_bar) * (r_{t-1} - r_bar))
    autocov_sum = 0.0
    autocov_cnt = 0
    for i in range(1, n_ret):
        r0 = rets[i - 1]
        r1 = rets[i]
        if not np.isnan(r0) and not np.isnan(r1):
            autocov_sum += (r1 - ret_mean) * (r0 - ret_mean)
            autocov_cnt += 1

    if autocov_cnt < 3:
        return out

    gamma_1 = autocov_sum / autocov_cnt

    # ---- 0: roll_spread_bps ----
    # Roll spread = 2 * sqrt(max(0, -gamma_1))
    # Normalize to basis points: spread / mean_close * 10000
    neg_gamma = -gamma_1
    if neg_gamma < 0.0:
        neg_gamma = 0.0
    roll_spread = 2.0 * np.sqrt(neg_gamma)

    close_sum = 0.0
    close_cnt = 0
    for i in range(n):
        c = close[i]
        if not np.isnan(c) and c > 0.0:
            close_sum += c
            close_cnt += 1
    if close_cnt > 0:
        mean_close = close_sum / close_cnt
        out[0] = roll_spread / mean_close * 10000.0

    # ---- 1: zero_return_pct ----
    # LOT (1999) proportion of zero-return bars
    out[1] = float(zero_ret_count) / float(valid_ret_count) * 100.0

    # ---- 2: reversal_ratio ----
    # Frequency of consecutive return sign changes (bid-ask bounce)
    reversal_cnt = 0
    pair_cnt = 0
    for i in range(1, n_ret):
        r0 = rets[i - 1]
        r1 = rets[i]
        if np.isnan(r0) or np.isnan(r1):
            continue
        # Skip zero returns for sign comparison
        if abs(r0) < 1e-12 or abs(r1) < 1e-12:
            continue
        pair_cnt += 1
        # Sign reversal: positive->negative or negative->positive
        if (r0 > 0.0 and r1 < 0.0) or (r0 < 0.0 and r1 > 0.0):
            reversal_cnt += 1

    if pair_cnt >= 3:
        out[2] = float(reversal_cnt) / float(pair_cnt)

    # ---- 3: spread_to_vol ----
    # Roll spread / realized volatility (unitless ratio)
    # High ratio = spread dominates vol = more illiquid
    if realized_vol > 1e-12:
        out[3] = roll_spread / realized_vol

    # ---- 4: roll_impact ----
    # Roll spread * sqrt(mean_volume) — dollar-adjusted liquidity
    vol_sum = 0.0
    vol_cnt = 0
    for i in range(n):
        v = volume[i]
        if not np.isnan(v) and v > 0.0:
            vol_sum += v
            vol_cnt += 1
    if vol_cnt > 0:
        mean_vol = vol_sum / vol_cnt
        out[4] = roll_spread * np.sqrt(mean_vol)

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
            "Roll spread liquidity bundle for the 09:30-10:30 window. "
            "Emits 5 variables: Roll (1984) bid-ask spread in bps, "
            "LOT zero-return proportion, reversal ratio, "
            "spread-to-volatility ratio, and roll impact. "
            "Hypothesis: illiquid stocks (high spread) earn higher returns "
            "due to the liquidity premium."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the Roll spread 09:30-10:30 bundle"
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
