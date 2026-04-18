#!/usr/bin/env python3
"""Register the high-frequency price-volume correlation + illiquidity bundle.

Bundle: hf_pv_corr_illiq_20d
- history_days: 20 (+ current day = 21-day matrix per symbol call)
- pad_mode: slot_aligned (240 slots, 09:30-11:29 + 13:00-14:59)
- inputs: close, volume, amount (1m bars)
- outputs: 8 daily fields
    * copa / cora / cora_a / cora_r                  — Scheme A basic corrs
    * adj_cora_a / adj_cora_r                        — Scheme A per-slot 20d-normalized corrs
    * illiq_abnormal_21d / illiq_normal_21d          — Scheme C 21-day flattened illiq

Aligned with exact-pkl reference implementations:
    ashare_alpha_book/.claude-tmp/scripts/20260417_方正_量价关系高频乐章/calc_hf_panels.py
    ashare_alpha_book/.claude-tmp/scripts/20260416_长江_高频微观划分/calc_micro_panels.py

By default prints the definition JSON. Use --register to persist it.
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
    PAD_MODE_SLOT_ALIGNED,
    RawDataParams,
    RawDataSlot,
)
from casimir.core.ashare_rawdata.registry import upsert_definition, validate_definition

NAME = "hf_pv_corr_illiq_20d"

WINDOW = [("09:30", "11:30"), ("13:00", "15:00")]
MAX_BARS = 240

OUTPUT_NAMES = [
    "copa_0930_1130_1300_1500",
    "cora_0930_1130_1300_1500",
    "cora_a_0930_1130_1300_1500",
    "cora_r_0930_1130_1300_1500",
    "adj_cora_a_0930_1130_1300_1500",
    "adj_cora_r_0930_1130_1300_1500",
    "illiq_abnormal_21d_0930_1130_1300_1500",
    "illiq_normal_21d_0930_1130_1300_1500",
]

FORMULA = """
@njit
def _pearson(x, y, min_valid):
    n = x.shape[0]
    s_x = 0.0
    s_y = 0.0
    cnt = 0
    for i in range(n):
        xi = x[i]
        yi = y[i]
        if not np.isfinite(xi) or not np.isfinite(yi):
            continue
        s_x += xi
        s_y += yi
        cnt += 1
    if cnt < min_valid:
        return np.nan
    mx = s_x / cnt
    my = s_y / cnt
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for i in range(n):
        xi = x[i]
        yi = y[i]
        if not np.isfinite(xi) or not np.isfinite(yi):
            continue
        dx = xi - mx
        dy = yi - my
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    denom = np.sqrt(sxx * syy)
    if denom <= 1e-12:
        return np.nan
    return sxy / denom


@njit
def _pearson_filter_y_abs(x, y, min_valid, y_abs_threshold):
    n = x.shape[0]
    s_x = 0.0
    s_y = 0.0
    cnt = 0
    for i in range(n):
        xi = x[i]
        yi = y[i]
        if not np.isfinite(xi) or not np.isfinite(yi):
            continue
        if np.abs(yi) <= y_abs_threshold:
            continue
        s_x += xi
        s_y += yi
        cnt += 1
    if cnt < min_valid:
        return np.nan
    mx = s_x / cnt
    my = s_y / cnt
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for i in range(n):
        xi = x[i]
        yi = y[i]
        if not np.isfinite(xi) or not np.isfinite(yi):
            continue
        if np.abs(yi) <= y_abs_threshold:
            continue
        dx = xi - mx
        dy = yi - my
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    denom = np.sqrt(sxx * syy)
    if denom <= 1e-12:
        return np.nan
    return sxy / denom


@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]
    amount = inputs[2]

    n_rows, n_cols = close.shape
    n_out = 8
    out = np.full(n_out, np.nan, dtype=np.float64)

    MIN_VALID_POINTS = 30
    MIN_BARS_PER_DAY = 10
    MIN_VALID_DAYS = 10
    cur_row = n_rows - 1

    # --- Section A: current-day packed arrays under A-validity (close & amount finite, close>0) ---
    cur_close = np.empty(n_cols, dtype=np.float64)
    cur_amt = np.empty(n_cols, dtype=np.float64)
    cur_slots = np.empty(n_cols, dtype=np.int64)
    cur_n = 0
    for c in range(n_cols):
        cl = close[cur_row, c]
        am = amount[cur_row, c]
        if not np.isfinite(cl) or not np.isfinite(am) or cl <= 0.0:
            continue
        cur_close[cur_n] = cl
        cur_amt[cur_n] = am
        cur_slots[cur_n] = c
        cur_n += 1

    cur_absret = np.full(cur_n, np.nan, dtype=np.float64)
    for i in range(1, cur_n):
        cur_absret[i] = np.abs(np.log(cur_close[i] / cur_close[i - 1]))

    if cur_n >= MIN_VALID_POINTS:
        out[0] = _pearson(cur_close[:cur_n], cur_amt[:cur_n], MIN_VALID_POINTS)
        out[1] = _pearson(cur_absret[:cur_n], cur_amt[:cur_n], MIN_VALID_POINTS)
        if cur_n >= 2:
            out[2] = _pearson(cur_amt[: cur_n - 1], cur_absret[1:cur_n], MIN_VALID_POINTS)
            out[3] = _pearson(cur_absret[: cur_n - 1], cur_amt[1:cur_n], MIN_VALID_POINTS)

    # --- Section B: per-slot 20-day adj_amount normalization (A filter on close+amount) ---
    adj_amount_slot = np.full(n_cols, np.nan, dtype=np.float64)
    for c in range(n_cols):
        s = 0.0
        cnt = 0
        for r in range(n_rows - 1):
            cl = close[r, c]
            am = amount[r, c]
            if not np.isfinite(cl) or not np.isfinite(am) or cl <= 0.0:
                continue
            s += am
            cnt += 1
        if cnt < 2:
            continue
        mu = s / cnt
        ss = 0.0
        for r in range(n_rows - 1):
            cl = close[r, c]
            am = amount[r, c]
            if not np.isfinite(cl) or not np.isfinite(am) or cl <= 0.0:
                continue
            dev = am - mu
            ss += dev * dev
        sigma = np.sqrt(ss / cnt)
        if sigma <= 1e-12:
            continue
        cl_cur = close[cur_row, c]
        am_cur = amount[cur_row, c]
        if not np.isfinite(cl_cur) or not np.isfinite(am_cur) or cl_cur <= 0.0:
            continue
        adj_amount_slot[c] = (am_cur - mu) / sigma

    cur_adj = np.empty(cur_n, dtype=np.float64)
    for i in range(cur_n):
        cur_adj[i] = adj_amount_slot[cur_slots[i]]

    if cur_n >= 2:
        out[4] = _pearson_filter_y_abs(
            cur_adj[: cur_n - 1], cur_absret[1:cur_n], MIN_VALID_POINTS, 1e-12
        )
        # by symmetry of Pearson: corr(abs_ret[:-1], adj_amount[1:]) with filter on abs_ret[:-1]
        out[5] = _pearson_filter_y_abs(
            cur_adj[1:cur_n], cur_absret[: cur_n - 1], MIN_VALID_POINTS, 1e-12
        )

    # --- Section C: 21-day flattened illiquidity (C-validity: all three finite, cl>0, vol>=0, amt>=0) ---
    sum_log1p_abn = 0.0
    sum_amt_abn = 0.0
    sum_log1p_norm = 0.0
    sum_amt_norm = 0.0
    cnt_abn = 0
    cnt_norm = 0
    valid_days = 0

    for r in range(n_rows):
        row_valid = 0
        for c in range(n_cols):
            cl = close[r, c]
            vo = volume[r, c]
            am = amount[r, c]
            if (np.isfinite(cl) and np.isfinite(vo) and np.isfinite(am)
                    and cl > 0.0 and vo >= 0.0 and am >= 0.0):
                row_valid += 1
        if row_valid < MIN_BARS_PER_DAY:
            continue
        valid_days += 1

        s_vol = 0.0
        cnt_vol = 0
        for c in range(n_cols):
            vo = volume[r, c]
            if np.isfinite(vo):
                s_vol += vo
                cnt_vol += 1
        if cnt_vol == 0:
            continue
        mean_vol = s_vol / cnt_vol
        ss_vol = 0.0
        for c in range(n_cols):
            vo = volume[r, c]
            if np.isfinite(vo):
                dev = vo - mean_vol
                ss_vol += dev * dev
        std_vol = np.sqrt(ss_vol / cnt_vol)
        threshold = mean_vol + std_vol

        row_close = np.empty(n_cols, dtype=np.float64)
        row_vol = np.empty(n_cols, dtype=np.float64)
        row_amt = np.empty(n_cols, dtype=np.float64)
        row_n = 0
        for c in range(n_cols):
            cl = close[r, c]
            vo = volume[r, c]
            am = amount[r, c]
            if (np.isfinite(cl) and np.isfinite(vo) and np.isfinite(am)
                    and cl > 0.0 and vo >= 0.0 and am >= 0.0):
                row_close[row_n] = cl
                row_vol[row_n] = vo
                row_amt[row_n] = am
                row_n += 1

        row_ret = np.full(row_n, np.nan, dtype=np.float64)
        for i in range(1, row_n):
            cp = row_close[i - 1]
            cc = row_close[i]
            if cp > 0.0 and cc > 0.0:
                row_ret[i] = np.log(cc / cp)

        for i in range(row_n):
            rv = row_ret[i]
            if not np.isfinite(rv):
                continue
            vo = row_vol[i]
            am = row_amt[i]
            if am <= 0.0:
                continue
            log1p_abs_r = np.log1p(np.abs(rv))
            if vo > threshold:
                sum_log1p_abn += log1p_abs_r
                sum_amt_abn += am
                cnt_abn += 1
            else:
                sum_log1p_norm += log1p_abs_r
                sum_amt_norm += am
                cnt_norm += 1

    if valid_days >= MIN_VALID_DAYS:
        if sum_amt_abn > 0.0:
            out[6] = sum_log1p_abn / sum_amt_abn
        if sum_amt_norm > 0.0:
            out[7] = sum_log1p_norm / sum_amt_norm

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close", "volume", "amount"],
        output_names=OUTPUT_NAMES,
        params=RawDataParams(input_time_filter=WINDOW),
        slot=RawDataSlot.EVENING,
        data_available_at=1500,
        execution_start_at=None,
        execution_end_at=None,
        expected_bars=10,
        history_days=20,
        pad_mode=PAD_MODE_SLOT_ALIGNED,
        max_bars=MAX_BARS,
        description=(
            "HF price-volume corr + 21-day illiq bundle. Outputs 8 daily fields. "
            "Scheme A (方正 量价关系高频乐章): copa/cora/cora_a/cora_r/adj_cora_a/adj_cora_r. "
            "Scheme C (长江 高频微观划分): illiq_abnormal_21d/illiq_normal_21d. "
            "Window 09:30-11:29 + 13:00-14:59 (240 slots, includes closing auction). "
            "history_days=20 (slot-aligned matrix for per-slot amount normalization and "
            "21-day bar pool flattening)."
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
