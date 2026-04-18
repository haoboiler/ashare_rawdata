#!/usr/bin/env python3
"""Register the long-short battle (多空博弈) bundle.

Bundle: hf_longshort_battle
- history_days: 0 (single-day)
- pad_mode: packed (legacy 1D path)
- window: 09:35-11:29 + 13:00-14:56 (skips open 5 min and close 3 min / auction)
- inputs: close, high, low, volume (1m bars)
- outputs: 3 daily fields (sorted_cumsum_diff variants)
    * vol_contest_ret_0935_1130_1300_1457
    * vol_contest_pos_0935_1130_1300_1457
    * amp_contest_0935_1130_1300_1457

B5 = 0.25*vol_contest_ret + 0.25*vol_contest_pos + 0.5*amp_contest is composed
at the alpha layer; we do NOT materialize longshort_battle as a raw field.

Aligned with exact-pkl:
    ashare_alpha_book/.claude-tmp/scripts/20260416_方正_多空博弈因子/calc_longshort_battle.py

NOTE: exact-pkl skips bars by INDEX (first 5, last 3) after packing NaN.  Our
time-filter-based approach matches on full-bar days, diverges only on days
with interior missing bars (expected to be rare in A-share 1m data).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CASIMIR_ROOT = Path("/home/gkh/ashare/casimir_ashare")
if str(CASIMIR_ROOT) not in sys.path:
    sys.path.insert(0, str(CASIMIR_ROOT))

from casimir.core.ashare_rawdata.models import (
    AShareRawDataDefinition,
    CompletenessPolicy,
    RawDataParams,
    RawDataSlot,
)
from casimir.core.ashare_rawdata.registry import upsert_definition, validate_definition

NAME = "hf_longshort_battle"
WINDOW = [("09:35", "11:30"), ("13:00", "14:57")]

OUTPUT_NAMES = [
    "vol_contest_ret_0935_1130_1300_1457",
    "vol_contest_pos_0935_1130_1300_1457",
    "amp_contest_0935_1130_1300_1457",
]

FORMULA = """
@njit
def _sorted_cumsum_diff(values, sort_key, min_valid):
    n = values.shape[0]
    packed_vals = np.empty(n, dtype=np.float64)
    packed_keys = np.empty(n, dtype=np.float64)
    m = 0
    for i in range(n):
        v = values[i]
        k = sort_key[i]
        if np.isfinite(v) and np.isfinite(k):
            packed_vals[m] = v
            packed_keys[m] = k
            m += 1
    if m < min_valid:
        return np.nan
    # Stable sort to get deterministic tie ordering; numpy's default quicksort
    # is unstable and its tie-breaking differs between numba and numpy, which
    # makes sorted_cumsum_diff non-reproducible. kind='mergesort' is stable in
    # both numba and numpy.
    asc_idx = np.argsort(packed_keys[:m], kind='mergesort')
    csum_asc = 0.0
    csum_desc = 0.0
    total = 0.0
    for i in range(m):
        csum_asc += packed_vals[asc_idx[i]]
        csum_desc += packed_vals[asc_idx[m - 1 - i]]
        total += csum_asc - csum_desc
    return total


@njit
def apply_func(inputs):
    close = inputs[0]
    high = inputs[1]
    low = inputs[2]
    volume = inputs[3]

    n = close.shape[0]
    n_out = 3
    out = np.full(n_out, np.nan, dtype=np.float64)

    RET_LOOKBACK = 5
    MIN_VALID = 5

    if n < RET_LOOKBACK + MIN_VALID:
        return out

    # 5-bar simple return (aligned with exact-pkl: c[i]/c[i-5] - 1)
    ret5 = np.full(n, np.nan, dtype=np.float64)
    for i in range(RET_LOOKBACK, n):
        cp = close[i - RET_LOOKBACK]
        cc = close[i]
        if np.isfinite(cp) and np.isfinite(cc) and cp > 0.0:
            ret5[i] = cc / cp - 1.0

    # Running high / low (NaN-aware cumulative max/min) + relative position + amplitude
    rel_pos = np.full(n, np.nan, dtype=np.float64)
    amp = np.full(n, np.nan, dtype=np.float64)
    running_high = -np.inf
    running_low = np.inf
    for i in range(n):
        h = high[i]
        l = low[i]
        c = close[i]
        if np.isfinite(h) and h > running_high:
            running_high = h
        if np.isfinite(l) and l < running_low:
            running_low = l
        if (running_low > 0.0 and running_high > 0.0 and np.isfinite(c)):
            up_from_low = (c - running_low) / running_low
            down_from_high = (c - running_high) / running_high
            rel_pos[i] = 0.5 * up_from_low + 0.5 * down_from_high
        if np.isfinite(h) and np.isfinite(l) and np.isfinite(c) and c > 0.0:
            amp[i] = (h - l) / c

    out[0] = _sorted_cumsum_diff(volume, ret5, MIN_VALID)
    out[1] = _sorted_cumsum_diff(volume, rel_pos, MIN_VALID)
    out[2] = _sorted_cumsum_diff(amp, ret5, MIN_VALID)

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "high", "low", "volume"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=WINDOW),
        slot=RawDataSlot.EVENING,
        data_available_at=1457,
        execution_start_at=None,
        execution_end_at=None,
        expected_bars=10,
        completeness_policy=CompletenessPolicy.STRICT_FULL_WINDOW,
        description=(
            "Long-short battle (多空博弈) bundle. Outputs 3 daily sorted-cumsum-diff "
            "fields derived from 1m bars over 09:35-11:29 + 13:00-14:56 (skips "
            "opening 5 min and closing auction). alpha layer recomposes "
            "longshort_battle = 0.25*vol_contest_ret + 0.25*vol_contest_pos + 0.5*amp_contest."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Build or register the {NAME} bundle")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    definition = build_definition()

    if args.validate_only or not args.register:
        validate_definition(definition)
        print(f"validated: {definition.name}")

    if args.print_json or (not args.register and not args.validate_only):
        print(json.dumps(definition.to_document(), indent=2, ensure_ascii=True))

    if args.register:
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
