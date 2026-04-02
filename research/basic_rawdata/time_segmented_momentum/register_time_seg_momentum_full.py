#!/usr/bin/env python3
"""Time-Segmented Return Pattern — full-day (09:30-14:57)

D-012: 将全天分为 8 个 ~30 分钟段，计算截面收益时间分布特征。
不关注方向性动量（已证实失败），而是关注：
  1. 收益在时间段上的集中度（信息事件离散性）
  2. 段间收益反转频率（类 reversal_ratio 的粗粒度版本）
  3. 价格路径粗糙度（路径复杂度 ≈ 微观结构流动性代理）

Segments (8 × ~30min):
  Seg0: bars 0-29   (09:30-10:00)
  Seg1: bars 30-59  (10:00-10:30)
  Seg2: bars 60-89  (10:30-11:00)
  Seg3: bars 90-119 (11:00-11:30)
  Seg4: bars 120-149 (13:00-13:30)
  Seg5: bars 150-179 (13:30-14:00)
  Seg6: bars 180-209 (14:00-14:30)
  Seg7: bars 210-236 (14:30-14:57)
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

NAME = "time_seg_momentum_full"

OUTPUT_NAMES = [
    # --- 收益时间集中度 (3) ---
    "return_hhi_full",              # 段收益 Herfindahl 集中度
    "max_segment_share_full",       # 最大单段占总绝对收益比
    "open_return_share_full",       # 首段(0930-1000)绝对收益占比

    # --- 段间动态 (3) ---
    "segment_reversal_ratio_full",  # 相邻段收益符号反转频率
    "segment_autocorr1_full",       # 段收益 lag-1 自相关
    "return_path_roughness_full",   # sum(|seg_ret|) / |total_ret| 路径粗糙度

    # --- AM/PM 结构 (2) ---
    "am_pm_abs_ratio_full",         # AM 绝对收益 / PM 绝对收益
    "close_return_share_full",      # 尾段(1430-1457)绝对收益占比

    # --- 分布形态 (2) ---
    "segment_return_std_full",      # 段收益标准差
    "segment_return_skew_full",     # 段收益偏度
]

FORMULA = """@njit
def apply_func(inputs):
    close = inputs[0]

    n = close.size
    n_out = 10
    out = np.full(n_out, np.nan, dtype=np.float64)

    # 需要至少 200 bars 确保 8 段各有足够数据
    if n < 200:
        return out

    # --- 定义 8 段边界 ---
    # 全天 237 bars: AM 120 (0-119) + PM 117 (120-236)
    seg_starts = np.array([0, 30, 60, 90, 120, 150, 180, 210], dtype=np.int64)
    seg_ends   = np.array([29, 59, 89, 119, 149, 179, 209, 236], dtype=np.int64)
    n_seg = 8

    # 限制段边界不超过实际 bar 数
    for s in range(n_seg):
        if seg_ends[s] >= n:
            seg_ends[s] = n - 1

    # --- 计算每段收益: log(close[end] / close[start]) ---
    seg_rets = np.full(n_seg, np.nan, dtype=np.float64)
    valid_seg = 0
    for s in range(n_seg):
        si = seg_starts[s]
        ei = seg_ends[s]
        if si >= n or ei >= n:
            continue
        c_start = close[si]
        c_end = close[ei]
        if np.isnan(c_start) or np.isnan(c_end) or c_start <= 0.0:
            continue
        seg_rets[s] = np.log(c_end / c_start)
        valid_seg += 1

    if valid_seg < 6:
        return out

    # --- 绝对段收益和 ---
    abs_sum = 0.0
    abs_max = 0.0
    abs_rets = np.empty(n_seg, dtype=np.float64)
    for s in range(n_seg):
        if np.isnan(seg_rets[s]):
            abs_rets[s] = 0.0
        else:
            abs_rets[s] = abs(seg_rets[s])
        abs_sum += abs_rets[s]
        if abs_rets[s] > abs_max:
            abs_max = abs_rets[s]

    # guard: 极小绝对收益和 → 全天无波动
    if abs_sum < 1e-10:
        return out

    # --- 0: return_hhi = HHI of |segment returns| ---
    # HHI = sum(share_i^2), share_i = |ret_i| / sum(|ret_i|)
    hhi = 0.0
    for s in range(n_seg):
        share = abs_rets[s] / abs_sum
        hhi += share * share
    out[0] = hhi

    # --- 1: max_segment_share = max(|ret_i|) / sum(|ret_i|) ---
    out[1] = abs_max / abs_sum

    # --- 2: open_return_share = |ret_seg0| / sum(|ret_i|) ---
    out[2] = abs_rets[0] / abs_sum

    # --- 3: segment_reversal_ratio = fraction of consecutive pairs with sign flip ---
    flip_count = 0
    pair_count = 0
    for s in range(n_seg - 1):
        r0 = seg_rets[s]
        r1 = seg_rets[s + 1]
        if np.isnan(r0) or np.isnan(r1):
            continue
        if abs(r0) < 1e-12 or abs(r1) < 1e-12:
            continue
        pair_count += 1
        if (r0 > 0.0 and r1 < 0.0) or (r0 < 0.0 and r1 > 0.0):
            flip_count += 1
    if pair_count >= 4:
        out[3] = float(flip_count) / float(pair_count)

    # --- 4: segment_autocorr1 = lag-1 autocorrelation of segment returns ---
    # Pearson corr(seg_rets[:-1], seg_rets[1:])
    sx = 0.0
    sy = 0.0
    sxx = 0.0
    syy = 0.0
    sxy = 0.0
    ac_cnt = 0
    for s in range(n_seg - 1):
        x = seg_rets[s]
        y = seg_rets[s + 1]
        if np.isnan(x) or np.isnan(y):
            continue
        sx += x
        sy += y
        sxx += x * x
        syy += y * y
        sxy += x * y
        ac_cnt += 1
    if ac_cnt >= 4:
        denom = (ac_cnt * sxx - sx * sx) * (ac_cnt * syy - sy * sy)
        if denom > 0.0:
            out[4] = (ac_cnt * sxy - sx * sy) / np.sqrt(denom)

    # --- 5: return_path_roughness = sum(|seg_ret|) / |total_ret| ---
    # 路径粗糙度：多段来回 → 高粗糙度 → 高流动性消耗
    total_ret = 0.0
    for s in range(n_seg):
        if not np.isnan(seg_rets[s]):
            total_ret += seg_rets[s]
    abs_total = abs(total_ret)
    if abs_total > 1e-10:
        out[5] = abs_sum / abs_total
    # 如果 total_ret ≈ 0 但 abs_sum 不小 → 高粗糙度，cap at 100
    elif abs_sum > 1e-10:
        out[5] = 100.0

    # --- 6: am_pm_abs_ratio = sum(|AM seg rets|) / sum(|PM seg rets|) ---
    am_abs = 0.0
    pm_abs = 0.0
    for s in range(4):
        am_abs += abs_rets[s]
    for s in range(4, n_seg):
        pm_abs += abs_rets[s]
    if pm_abs > 1e-10:
        out[6] = am_abs / pm_abs

    # --- 7: close_return_share = |ret_seg7| / sum(|ret_i|) ---
    out[7] = abs_rets[n_seg - 1] / abs_sum

    # --- 8: segment_return_std = std of segment returns ---
    seg_mean = 0.0
    seg_cnt = 0
    for s in range(n_seg):
        if not np.isnan(seg_rets[s]):
            seg_mean += seg_rets[s]
            seg_cnt += 1
    if seg_cnt >= 2:
        seg_mean /= seg_cnt
        ss = 0.0
        for s in range(n_seg):
            if not np.isnan(seg_rets[s]):
                d = seg_rets[s] - seg_mean
                ss += d * d
        out[8] = np.sqrt(ss / (seg_cnt - 1))

    # --- 9: segment_return_skew = skewness of segment returns ---
    if seg_cnt >= 3 and out[8] > 1e-12:
        m2 = 0.0
        m3 = 0.0
        for s in range(n_seg):
            if not np.isnan(seg_rets[s]):
                d = seg_rets[s] - seg_mean
                d2 = d * d
                m2 += d2
                m3 += d2 * d
        m2 /= seg_cnt
        m3 /= seg_cnt
        if m2 > 0.0:
            out[9] = m3 / (m2 * np.sqrt(m2))

    return out
"""


def build_definition() -> AShareRawDataDefinition:
    return AShareRawDataDefinition(
        name=NAME,
        formula=FORMULA,
        func_name="apply_func",
        input_names=["close"],
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
            "Time-segmented return pattern for full day (09:30-14:57). "
            "Divides into 8 x ~30min segments, computes return concentration "
            "(HHI, max share), segment reversal ratio, path roughness, "
            "AM/PM structure, and distributional stats. "
            "Focus on return timing patterns as liquidity proxy, not directional momentum."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or register time-segmented momentum full-day bundle"
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
