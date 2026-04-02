#!/usr/bin/env python3
"""Multi-scale and hybrid Corwin-Schultz spread variants for full trading day.

Bundle: cs_spread_multiscale_0930_1130_1300_1457
- Input: high, low, close, amount (from 1m bars)
- Output: 4 variables exploring CS spread at different scales and normalizations.

Physical hypotheses:
1. cs_5m_spread_full: CS spread computed on 5-bar (5m) aggregated blocks.
   At coarser resolution, H-L captures wider price excursions; CS decomposition
   separates a different (longer-horizon) spread component. May be less noisy
   than 1m CS spread while still capturing cross-sectional liquidity differences.

2. cs_multiscale_ratio_full: Ratio of 1m CS spread / 5m CS spread.
   If ratio > 1: microstructure noise dominates at fine scale.
   If ratio < 1: persistent illiquidity at longer horizons.
   The ratio captures the SCALE STRUCTURE of liquidity — a dimension orthogonal
   to spread level itself.

3. cs_spread_per_amount_full: CS spread * mean(close) / mean(amount).
   Dollar spread normalized by trading value = "cost of crossing the spread
   per unit of capital deployed". Combines the CS spread estimate (structural
   liquidity) with trading activity (flow-based liquidity) — a hybrid metric.

4. cs_session_asymmetry_full: Morning CS spread / Afternoon CS spread.
   Morning = 09:30-11:30 (120 bars), Afternoon = 13:00-14:57 (117 bars).
   Captures intraday liquidity dynamics: information asymmetry concentrated
   at open vs deteriorating afternoon liquidity.
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

NAME = "cs_spread_multiscale_0930_1130_1300_1457"

OUTPUT_NAMES = [
    "cs_5m_spread_full",             # CS spread at 5m resolution
    "cs_multiscale_ratio_full",      # 1m spread / 5m spread ratio
    "cs_spread_per_amount_full",     # Dollar spread / daily amount
    "cs_session_asymmetry_full",     # Morning spread / Afternoon spread
]

FORMULA = r"""@njit
def apply_func(inputs):
    high = inputs[0]
    low = inputs[1]
    close = inputs[2]
    amount = inputs[3]

    n = high.size
    n_out = 4
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 10:
        return out

    SQRT2 = 1.4142135623730951
    CS_DENOM = 3.0 - 2.0 * SQRT2

    # --- Helper: compute CS spread from beta_bar, gamma_bar ---
    # Returns (spread_value, valid_flag)

    # ============================================================
    # 1m CS spread (recompute for ratio; same as register_cs_spread_full.py)
    # ============================================================
    n_pairs_1m = n - 1
    beta_sum_1m = 0.0
    gamma_sum_1m = 0.0
    cnt_1m = 0

    for j in range(n_pairs_1m):
        h0 = high[j]
        l0 = low[j]
        h1 = high[j + 1]
        l1 = low[j + 1]

        if (np.isnan(h0) or np.isnan(l0) or np.isnan(h1) or np.isnan(l1)
                or l0 <= 0.0 or l1 <= 0.0 or h0 <= 0.0 or h1 <= 0.0):
            continue

        lr0 = np.log(h0 / l0)
        lr1 = np.log(h1 / l1)
        beta_j = lr0 * lr0 + lr1 * lr1

        hh = h0 if h0 > h1 else h1
        ll = l0 if l0 < l1 else l1
        lr2 = np.log(hh / ll)
        gamma_j = lr2 * lr2

        beta_sum_1m += beta_j
        gamma_sum_1m += gamma_j
        cnt_1m += 1

    spread_1m = np.nan
    if cnt_1m >= 5:
        bb = beta_sum_1m / cnt_1m
        gb = gamma_sum_1m / cnt_1m
        sq2b = np.sqrt(2.0 * bb)
        sqb = np.sqrt(bb)
        s2 = (sq2b - sqb) / CS_DENOM
        if s2 < 0.0:
            s2 = 0.0
        gt = gb / CS_DENOM
        if gt < 0.0:
            gt = 0.0
        a = s2 - np.sqrt(gt)
        if a >= 0.0:
            ea = np.exp(a)
            spread_1m = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            spread_1m = 0.0

    # ============================================================
    # 5m CS spread: aggregate bars into 5-bar blocks
    # ============================================================
    K = 5
    n_blocks = n // K
    if n_blocks < 3:
        # Not enough blocks, try smaller K
        K = 3
        n_blocks = n // K

    if n_blocks >= 3:
        # Compute block-level H/L
        block_h = np.empty(n_blocks, dtype=np.float64)
        block_l = np.empty(n_blocks, dtype=np.float64)

        for b in range(n_blocks):
            start = b * K
            bh = -1.0e30
            bl = 1.0e30
            valid = False
            for k in range(K):
                idx = start + k
                if idx < n:
                    hk = high[idx]
                    lk = low[idx]
                    if not np.isnan(hk) and not np.isnan(lk) and hk > 0.0 and lk > 0.0:
                        if hk > bh:
                            bh = hk
                        if lk < bl:
                            bl = lk
                        valid = True
            if valid:
                block_h[b] = bh
                block_l[b] = bl
            else:
                block_h[b] = np.nan
                block_l[b] = np.nan

        # CS on blocks
        n_bpairs = n_blocks - 1
        beta_sum_5m = 0.0
        gamma_sum_5m = 0.0
        cnt_5m = 0

        for j in range(n_bpairs):
            bh0 = block_h[j]
            bl0 = block_l[j]
            bh1 = block_h[j + 1]
            bl1 = block_l[j + 1]

            if (np.isnan(bh0) or np.isnan(bl0) or np.isnan(bh1) or np.isnan(bl1)
                    or bl0 <= 0.0 or bl1 <= 0.0 or bh0 <= 0.0 or bh1 <= 0.0):
                continue

            lr0 = np.log(bh0 / bl0)
            lr1 = np.log(bh1 / bl1)
            beta_j = lr0 * lr0 + lr1 * lr1

            hh = bh0 if bh0 > bh1 else bh1
            ll = bl0 if bl0 < bl1 else bl1
            lr2 = np.log(hh / ll)
            gamma_j = lr2 * lr2

            beta_sum_5m += beta_j
            gamma_sum_5m += gamma_j
            cnt_5m += 1

        spread_5m = np.nan
        if cnt_5m >= 3:
            bb = beta_sum_5m / cnt_5m
            gb = gamma_sum_5m / cnt_5m
            sq2b = np.sqrt(2.0 * bb)
            sqb = np.sqrt(bb)
            s2 = (sq2b - sqb) / CS_DENOM
            if s2 < 0.0:
                s2 = 0.0
            gt = gb / CS_DENOM
            if gt < 0.0:
                gt = 0.0
            a = s2 - np.sqrt(gt)
            if a >= 0.0:
                ea = np.exp(a)
                spread_5m = 2.0 * (ea - 1.0) / (1.0 + ea)
            else:
                spread_5m = 0.0

        # Output 0: cs_5m_spread_full
        out[0] = spread_5m

        # Output 1: cs_multiscale_ratio_full = 1m / 5m
        if not np.isnan(spread_1m) and not np.isnan(spread_5m) and spread_5m > 1.0e-12:
            out[1] = spread_1m / spread_5m

    # ============================================================
    # Output 2: cs_spread_per_amount_full = spread * mean(close) / mean(amount)
    # ============================================================
    if not np.isnan(spread_1m):
        close_sum = 0.0
        close_cnt = 0
        amount_sum = 0.0
        amount_cnt = 0
        for i in range(n):
            c = close[i]
            if not np.isnan(c) and c > 0.0:
                close_sum += c
                close_cnt += 1
            a = amount[i]
            if not np.isnan(a) and a > 0.0:
                amount_sum += a
                amount_cnt += 1
        if close_cnt > 0 and amount_cnt > 0 and amount_sum > 0.0:
            mean_close = close_sum / close_cnt
            mean_amount = amount_sum / amount_cnt
            # Dollar spread per bar / amount per bar
            out[2] = (spread_1m * mean_close) / mean_amount

    # ============================================================
    # Output 3: cs_session_asymmetry_full = morning spread / afternoon spread
    # ============================================================
    # Morning = first 120 bars (09:30-11:30)
    # Afternoon = remaining bars (13:00-14:57, ~117 bars)
    # With time filter, total is ~237 bars. Split at bar 120.
    morning_end = 120
    if n <= morning_end:
        morning_end = n // 2  # fallback for short days

    # Morning CS spread
    beta_sum_am = 0.0
    gamma_sum_am = 0.0
    cnt_am = 0
    am_limit = morning_end if morning_end < n else n
    for j in range(am_limit - 1):
        h0 = high[j]
        l0 = low[j]
        h1 = high[j + 1]
        l1 = low[j + 1]
        if (np.isnan(h0) or np.isnan(l0) or np.isnan(h1) or np.isnan(l1)
                or l0 <= 0.0 or l1 <= 0.0 or h0 <= 0.0 or h1 <= 0.0):
            continue
        lr0 = np.log(h0 / l0)
        lr1 = np.log(h1 / l1)
        beta_j = lr0 * lr0 + lr1 * lr1
        hh = h0 if h0 > h1 else h1
        ll = l0 if l0 < l1 else l1
        lr2 = np.log(hh / ll)
        gamma_j = lr2 * lr2
        beta_sum_am += beta_j
        gamma_sum_am += gamma_j
        cnt_am += 1

    spread_am = np.nan
    if cnt_am >= 5:
        bb = beta_sum_am / cnt_am
        gb = gamma_sum_am / cnt_am
        sq2b = np.sqrt(2.0 * bb)
        sqb = np.sqrt(bb)
        s2 = (sq2b - sqb) / CS_DENOM
        if s2 < 0.0:
            s2 = 0.0
        gt = gb / CS_DENOM
        if gt < 0.0:
            gt = 0.0
        a = s2 - np.sqrt(gt)
        if a >= 0.0:
            ea = np.exp(a)
            spread_am = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            spread_am = 0.0

    # Afternoon CS spread
    beta_sum_pm = 0.0
    gamma_sum_pm = 0.0
    cnt_pm = 0
    for j in range(morning_end, n - 1):
        h0 = high[j]
        l0 = low[j]
        h1 = high[j + 1]
        l1 = low[j + 1]
        if (np.isnan(h0) or np.isnan(l0) or np.isnan(h1) or np.isnan(l1)
                or l0 <= 0.0 or l1 <= 0.0 or h0 <= 0.0 or h1 <= 0.0):
            continue
        lr0 = np.log(h0 / l0)
        lr1 = np.log(h1 / l1)
        beta_j = lr0 * lr0 + lr1 * lr1
        hh = h0 if h0 > h1 else h1
        ll = l0 if l0 < l1 else l1
        lr2 = np.log(hh / ll)
        gamma_j = lr2 * lr2
        beta_sum_pm += beta_j
        gamma_sum_pm += gamma_j
        cnt_pm += 1

    spread_pm = np.nan
    if cnt_pm >= 5:
        bb = beta_sum_pm / cnt_pm
        gb = gamma_sum_pm / cnt_pm
        sq2b = np.sqrt(2.0 * bb)
        sqb = np.sqrt(bb)
        s2 = (sq2b - sqb) / CS_DENOM
        if s2 < 0.0:
            s2 = 0.0
        gt = gb / CS_DENOM
        if gt < 0.0:
            gt = 0.0
        a = s2 - np.sqrt(gt)
        if a >= 0.0:
            ea = np.exp(a)
            spread_pm = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            spread_pm = 0.0

    if not np.isnan(spread_am) and not np.isnan(spread_pm) and spread_pm > 1.0e-12:
        out[3] = spread_am / spread_pm

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["high", "low", "close", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Multi-scale and hybrid Corwin-Schultz spread variants for full trading day "
            "(09:30-11:30 + 13:00-14:57). Explores CS spread at 5m resolution, "
            "1m/5m scale ratio, spread/amount hybrid, and AM/PM session asymmetry. "
            "These are structural/scale modifications, not bar conditioning (conclusion #39)."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the multi-scale CS spread full-day bundle"
    )
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--print-json", action="store_true")
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
