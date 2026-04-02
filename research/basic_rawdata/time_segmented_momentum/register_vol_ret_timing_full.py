#!/usr/bin/env python3
"""Volume-Return Timing Interaction — full-day (09:30-14:57)

D-012 variant: 结合成交量和收益时间分布，捕捉量价同步/异步模式。
假设：
  - 高量段的收益集中 = 信息驱动交易（知情交易者）
  - 高量段与高收益段错位 = 噪声交易主导
  - 成交量加权的段收益反转 = 更可靠的流动性信号

8 段定义同 register_time_seg_momentum_full.py
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

NAME = "vol_ret_timing_full"

OUTPUT_NAMES = [
    # --- 量价同步 (3) ---
    "vol_ret_rank_corr_full",       # 段成交量 vs 段|收益| Spearman 秩相关
    "high_vol_seg_ret_ratio_full",  # 高量段收益占比 / 低量段收益占比
    "vol_weighted_reversal_full",   # 成交量加权的段反转频率

    # --- 量加权收益时间分布 (3) ---
    "vol_weighted_ret_hhi_full",    # 成交量加权的收益集中度
    "informed_ratio_full",          # |vol_weighted_ret - equal_weighted_ret| / |equal_weighted_ret|
    "vol_ret_abs_corr_full",        # 段成交量 vs 段 |收益| Pearson 相关

    # --- 量的时间分布 (2) ---
    "vol_am_pm_ratio_full",         # AM 成交量 / PM 成交量
    "vol_timing_hhi_full",          # 成交量时间段 HHI
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]
    volume = inputs[1]

    n = close.size
    n_out = 8
    out = np.full(n_out, np.nan, dtype=np.float64)

    if n < 200:
        return out

    # --- 8 段边界 ---
    seg_starts = np.array([0, 30, 60, 90, 120, 150, 180, 210], dtype=np.int64)
    seg_ends   = np.array([29, 59, 89, 119, 149, 179, 209, 236], dtype=np.int64)
    n_seg = 8

    for s in range(n_seg):
        if seg_ends[s] >= n:
            seg_ends[s] = n - 1

    # --- 每段收益和成交量 ---
    seg_rets = np.full(n_seg, np.nan, dtype=np.float64)
    seg_vols = np.full(n_seg, np.nan, dtype=np.float64)
    valid_seg = 0

    for s in range(n_seg):
        si = seg_starts[s]
        ei = seg_ends[s]
        if si >= n or ei >= n:
            continue

        # 段收益
        c_start = close[si]
        c_end = close[ei]
        if np.isnan(c_start) or np.isnan(c_end) or c_start <= 0.0:
            continue

        seg_rets[s] = np.log(c_end / c_start)

        # 段成交量
        vol_sum = 0.0
        vol_cnt = 0
        for i in range(si, ei + 1):
            if i < n and not np.isnan(volume[i]):
                vol_sum += volume[i]
                vol_cnt += 1
        if vol_cnt > 0:
            seg_vols[s] = vol_sum
            valid_seg += 1

    if valid_seg < 6:
        return out

    # --- 绝对收益和成交量和 ---
    abs_ret_sum = 0.0
    vol_total = 0.0
    abs_rets = np.empty(n_seg, dtype=np.float64)

    for s in range(n_seg):
        if np.isnan(seg_rets[s]):
            abs_rets[s] = 0.0
        else:
            abs_rets[s] = abs(seg_rets[s])
        abs_ret_sum += abs_rets[s]
        if not np.isnan(seg_vols[s]):
            vol_total += seg_vols[s]

    if abs_ret_sum < 1e-10 or vol_total < 1e-10:
        return out

    # --- 0: vol_ret_rank_corr = Spearman(seg_vol_rank, seg_abs_ret_rank) ---
    # Simple rank correlation using bubble sort ranks
    vol_ranks = np.empty(n_seg, dtype=np.float64)
    ret_ranks = np.empty(n_seg, dtype=np.float64)
    for s in range(n_seg):
        vr = 0.0
        rr = 0.0
        vs = seg_vols[s] if not np.isnan(seg_vols[s]) else 0.0
        rs = abs_rets[s]
        for t in range(n_seg):
            vt = seg_vols[t] if not np.isnan(seg_vols[t]) else 0.0
            rt = abs_rets[t]
            if vt < vs:
                vr += 1.0
            if rt < rs:
                rr += 1.0
        vol_ranks[s] = vr
        ret_ranks[s] = rr

    # Pearson on ranks
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    for s in range(n_seg):
        x = vol_ranks[s]
        y = ret_ranks[s]
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
    denom = (n_seg * sxx - sx * sx) * (n_seg * syy - sy * sy)
    if denom > 0.0:
        out[0] = (n_seg * sxy - sx * sy) / np.sqrt(denom)

    # --- 1: high_vol_seg_ret_ratio ---
    # 按成交量排序段，top-4 段 |ret| / bottom-4 段 |ret|
    # 用排名判断
    top_abs = 0.0
    bot_abs = 0.0
    for s in range(n_seg):
        if vol_ranks[s] >= 4.0:  # top half by volume
            top_abs += abs_rets[s]
        else:
            bot_abs += abs_rets[s]
    if bot_abs > 1e-10:
        out[1] = top_abs / bot_abs

    # --- 2: vol_weighted_reversal = 成交量加权段反转频率 ---
    weighted_flip = 0.0
    weight_total = 0.0
    for s in range(n_seg - 1):
        r0 = seg_rets[s]
        r1 = seg_rets[s + 1]
        v0 = seg_vols[s] if not np.isnan(seg_vols[s]) else 0.0
        v1 = seg_vols[s + 1] if not np.isnan(seg_vols[s + 1]) else 0.0
        if np.isnan(r0) or np.isnan(r1):
            continue
        if abs(r0) < 1e-12 or abs(r1) < 1e-12:
            continue
        w = v0 + v1
        weight_total += w
        if (r0 > 0.0 and r1 < 0.0) or (r0 < 0.0 and r1 > 0.0):
            weighted_flip += w
    if weight_total > 0.0:
        out[2] = weighted_flip / weight_total

    # --- 3: vol_weighted_ret_hhi ---
    # HHI of (volume_share_i * |ret_i|) / sum(volume_share_i * |ret_i|)
    vr_products = np.empty(n_seg, dtype=np.float64)
    vr_sum = 0.0
    for s in range(n_seg):
        vs = seg_vols[s] if not np.isnan(seg_vols[s]) else 0.0
        vr_products[s] = (vs / vol_total) * abs_rets[s]
        vr_sum += vr_products[s]
    if vr_sum > 1e-10:
        hhi = 0.0
        for s in range(n_seg):
            share = vr_products[s] / vr_sum
            hhi += share * share
        out[3] = hhi

    # --- 4: informed_ratio ---
    # |VWAP_seg_ret - TWAP_seg_ret| / |TWAP_seg_ret|
    # VWAP_seg_ret: 成交量加权的段收益, TWAP: 等权段收益
    vw_ret = 0.0
    ew_ret = 0.0
    ew_cnt = 0
    for s in range(n_seg):
        if np.isnan(seg_rets[s]) or np.isnan(seg_vols[s]):
            continue
        vw_ret += seg_rets[s] * seg_vols[s]
        ew_ret += seg_rets[s]
        ew_cnt += 1
    if vol_total > 0.0:
        vw_ret /= vol_total
    if ew_cnt > 0:
        ew_ret /= ew_cnt
    if abs(ew_ret) > 1e-10:
        out[4] = abs(vw_ret - ew_ret) / abs(ew_ret)

    # --- 5: vol_ret_abs_corr = Pearson(seg_vol, seg_|ret|) ---
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    vc_cnt = 0
    for s in range(n_seg):
        if np.isnan(seg_vols[s]) or np.isnan(seg_rets[s]):
            continue
        x = seg_vols[s]
        y = abs_rets[s]
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
        vc_cnt += 1
    if vc_cnt >= 4:
        denom = (vc_cnt * sxx - sx * sx) * (vc_cnt * syy - sy * sy)
        if denom > 0.0:
            out[5] = (vc_cnt * sxy - sx * sy) / np.sqrt(denom)

    # --- 6: vol_am_pm_ratio ---
    am_vol = 0.0
    pm_vol = 0.0
    for s in range(4):
        if not np.isnan(seg_vols[s]):
            am_vol += seg_vols[s]
    for s in range(4, n_seg):
        if not np.isnan(seg_vols[s]):
            pm_vol += seg_vols[s]
    if pm_vol > 0.0:
        out[6] = am_vol / pm_vol

    # --- 7: vol_timing_hhi ---
    hhi = 0.0
    for s in range(n_seg):
        vs = seg_vols[s] if not np.isnan(seg_vols[s]) else 0.0
        share = vs / vol_total
        hhi += share * share
    out[7] = hhi

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
        data_available_at=1500,
        execution_start_at=930,
        execution_end_at=1457,
        expected_bars=157,
        description=(
            "Volume-return timing interaction for full day. "
            "Combines segment-level volume and return patterns: "
            "rank correlation, volume-weighted reversal, informed ratio, "
            "and volume timing concentration."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register vol-ret timing full-day bundle"
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
        upsert_definition(definition, validate=not args.skip_validate)
        print(f"registered: {definition.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
