#!/usr/bin/env python3
"""Register the conditioned Corwin-Schultz spread bundle for the full-day window.

Bundle: cs_spread_conditioned_0930_1130_1300_1457
- Input: high, low, close, volume, open (from 1m bars)
- Output: 5 variables capturing conditioned bid-ask spread estimates.

Physical hypothesis: Corwin-Schultz (2012) spread measured under specific market
conditions (high volume, price reversal, volume-weighted) captures different aspects
of the liquidity premium. Conditioning patterns that succeeded for Amihud (D-006)
are transferred to the CS spread framework, which uses adjacent-bar H-L differencing
to separate liquidity from volatility (conclusion #22).

Features:
1. cs_high_vol_spread_full — CS spread from high-volume bar pairs only.
   High-volume periods have more price discovery; spread during active trading
   is the most relevant execution cost metric.
2. cs_reversal_spread_full — CS spread from bar pairs where price direction
   reverses (close-open direction). Reversal = bid-ask bounce, the physical
   phenomenon CS spread is designed to measure.
3. cs_vw_spread_full — Volume-weighted CS spread. Higher weight to active
   periods makes the estimate more economically relevant.
4. cs_spread_roughness_full — Path roughness of pair-level spread estimates
   (|Δalpha| / mean(|alpha|)). High roughness = unpredictable execution cost
   → investors demand premium. Analogous to amihud_diff_mean_full (conclusion #31).
5. cs_high_vol_reversal_spread_full — Double-conditioned CS spread: high volume
   + reversal. The purest estimate of bid-ask bounce cost during active trading.
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

NAME = "cs_spread_conditioned_0930_1130_1300_1457"

OUTPUT_NAMES = [
    # --- Conditioned CS spread variants (4) ---
    "cs_high_vol_spread_full",              # CS spread from high-volume bar pairs
    "cs_reversal_spread_full",              # CS spread from reversal bar pairs
    "cs_vw_spread_full",                    # Volume-weighted CS spread
    # --- Second-order spread property (1) ---
    "cs_spread_roughness_full",             # Path roughness of pair spreads
    # --- Double condition (1) ---
    "cs_high_vol_reversal_spread_full",     # CS spread: high-vol + reversal
]

FORMULA = r"""@njit
def apply_func(inputs):
    high = inputs[0]
    low = inputs[1]
    close = inputs[2]
    volume = inputs[3]
    open_price = inputs[4]

    n = high.size
    n_out = 5
    out = np.full(n_out, np.nan, dtype=np.float64)
    if n < 4:
        return out

    SQRT2 = 1.4142135623730951
    CS_DENOM = 3.0 - 2.0 * SQRT2  # approx 0.1716
    MIN_PAIRS = 3
    n_pairs = n - 1

    # --- Pass 1: compute all pair-level metrics ---
    p_beta = np.empty(n_pairs, dtype=np.float64)
    p_gamma = np.empty(n_pairs, dtype=np.float64)
    p_alpha = np.empty(n_pairs, dtype=np.float64)
    p_vol = np.empty(n_pairs, dtype=np.float64)
    p_rev = np.zeros(n_pairs, dtype=np.int64)
    p_ok = np.zeros(n_pairs, dtype=np.int64)

    n_valid = 0

    for j in range(n_pairs):
        h0 = high[j]
        l0 = low[j]
        h1 = high[j + 1]
        l1 = low[j + 1]

        p_beta[j] = np.nan
        p_gamma[j] = np.nan
        p_alpha[j] = np.nan
        p_vol[j] = np.nan

        # Validate H/L data
        if (np.isnan(h0) or np.isnan(l0) or np.isnan(h1) or np.isnan(l1)
                or l0 <= 0.0 or l1 <= 0.0 or h0 <= 0.0 or h1 <= 0.0):
            continue

        # CS pair decomposition
        lr0 = np.log(h0 / l0)
        lr1 = np.log(h1 / l1)
        beta_j = lr0 * lr0 + lr1 * lr1

        hh = h0 if h0 > h1 else h1
        ll = l0 if l0 < l1 else l1
        lr2 = np.log(hh / ll)
        gamma_j = lr2 * lr2

        p_beta[j] = beta_j
        p_gamma[j] = gamma_j
        p_ok[j] = 1
        n_valid += 1

        # Per-pair alpha (for roughness)
        sq2b = np.sqrt(2.0 * beta_j)
        sqb = np.sqrt(beta_j)
        s2 = (sq2b - sqb) / CS_DENOM
        if s2 < 0.0:
            s2 = 0.0
        gt = gamma_j / CS_DENOM
        if gt < 0.0:
            gt = 0.0
        p_alpha[j] = s2 - np.sqrt(gt)

        # Average volume of the pair
        v0 = volume[j]
        v1 = volume[j + 1]
        vs = 0.0
        vc = 0
        if not np.isnan(v0) and v0 > 0.0:
            vs += v0
            vc += 1
        if not np.isnan(v1) and v1 > 0.0:
            vs += v1
            vc += 1
        if vc > 0:
            p_vol[j] = vs / vc

        # Reversal: adjacent bars have opposite close-open direction
        c0 = close[j]
        o0 = open_price[j]
        c1 = close[j + 1]
        o1 = open_price[j + 1]
        if (not np.isnan(c0) and not np.isnan(o0) and
                not np.isnan(c1) and not np.isnan(o1)
                and o0 > 0.0 and o1 > 0.0):
            d0 = c0 - o0
            d1 = c1 - o1
            if d0 * d1 < 0.0:
                p_rev[j] = 1

    if n_valid < 5:
        return out

    # --- Median volume for conditioning ---
    vbuf = np.empty(n_valid, dtype=np.float64)
    vi = 0
    for j in range(n_pairs):
        if p_ok[j] == 1 and not np.isnan(p_vol[j]):
            vbuf[vi] = p_vol[j]
            vi += 1
    med_vol = 0.0
    if vi > 0:
        vbuf_s = np.sort(vbuf[:vi])
        med_vol = vbuf_s[vi // 2]

    # === Feature 0: cs_high_vol_spread_full ===
    bs = 0.0
    gs = 0.0
    cnt = 0
    for j in range(n_pairs):
        if p_ok[j] == 1 and not np.isnan(p_vol[j]) and p_vol[j] > med_vol:
            bs += p_beta[j]
            gs += p_gamma[j]
            cnt += 1
    if cnt >= MIN_PAIRS:
        bb = bs / cnt
        gb = gs / cnt
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
            out[0] = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            out[0] = 0.0

    # === Feature 1: cs_reversal_spread_full ===
    bs = 0.0
    gs = 0.0
    cnt = 0
    for j in range(n_pairs):
        if p_ok[j] == 1 and p_rev[j] == 1:
            bs += p_beta[j]
            gs += p_gamma[j]
            cnt += 1
    if cnt >= MIN_PAIRS:
        bb = bs / cnt
        gb = gs / cnt
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
            out[1] = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            out[1] = 0.0

    # === Feature 2: cs_vw_spread_full ===
    bws = 0.0
    gws = 0.0
    wsum = 0.0
    for j in range(n_pairs):
        if p_ok[j] == 1 and not np.isnan(p_vol[j]) and p_vol[j] > 0.0:
            w = p_vol[j]
            bws += p_beta[j] * w
            gws += p_gamma[j] * w
            wsum += w
    if wsum > 0.0:
        bb = bws / wsum
        gb = gws / wsum
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
            out[2] = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            out[2] = 0.0

    # === Feature 3: cs_spread_roughness_full ===
    # Path roughness: mean(|alpha[j] - alpha[j-1]|) / mean(|alpha|)
    diff_s = 0.0
    dc = 0
    abs_s = 0.0
    ac = 0
    for j in range(n_pairs):
        if p_ok[j] == 1 and not np.isnan(p_alpha[j]):
            a_val = p_alpha[j]
            if a_val < 0.0:
                a_val = -a_val
            abs_s += a_val
            ac += 1
            if j > 0 and p_ok[j - 1] == 1 and not np.isnan(p_alpha[j - 1]):
                d = p_alpha[j] - p_alpha[j - 1]
                if d < 0.0:
                    d = -d
                diff_s += d
                dc += 1
    if dc >= MIN_PAIRS and ac > 0 and abs_s > 1.0e-12:
        out[3] = (diff_s / dc) / (abs_s / ac)

    # === Feature 4: cs_high_vol_reversal_spread_full ===
    bs = 0.0
    gs = 0.0
    cnt = 0
    for j in range(n_pairs):
        if (p_ok[j] == 1 and not np.isnan(p_vol[j])
                and p_vol[j] > med_vol and p_rev[j] == 1):
            bs += p_beta[j]
            gs += p_gamma[j]
            cnt += 1
    if cnt >= MIN_PAIRS:
        bb = bs / cnt
        gb = gs / cnt
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
            out[4] = 2.0 * (ea - 1.0) / (1.0 + ea)
        else:
            out[4] = 0.0

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["high", "low", "close", "volume", "open"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=[("09:30", "11:30"), ("13:00", "14:57")]),
        slot=RawDataSlot.EVENING,
        data_available_at=1458,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Conditioned Corwin-Schultz spread estimates for full trading day "
            "(09:30-11:30 + 13:00-14:57). Applies high-volume, reversal, and "
            "volume-weighting conditions to CS spread estimation. Also computes "
            "spread path roughness as a second-order property. "
            "Transfers the Amihud conditioning paradigm (D-006) to the CS framework."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register the conditioned CS spread full-day bundle"
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
