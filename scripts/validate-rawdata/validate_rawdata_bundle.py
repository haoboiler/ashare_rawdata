#!/usr/bin/env python3
"""Raw-data bundle 入库后验证工具函数。

本文件提供三类验证的工具函数，供 agent 或交互式使用：
1. 价格范围检查 — 类价格字段是否在当日 daily high/low 范围内
2. 覆盖率检查 — 与 daily close 对比，统计缺失和异常覆盖
3. 极端值检查 — inf/-inf、极大/极小值扫描

用法参见同目录下 validation_guide.md
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arcticdb import Arctic
from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_TARGET_LIBRARY


def get_conn() -> Arctic:
    return Arctic(ARCTIC_URL)


def read_rawdata(field: str, conn: Arctic = None) -> pd.DataFrame:
    """读取一个 raw-data field (日期 x 股票)"""
    conn = conn or get_conn()
    lib = conn.get_library(DEFAULT_TARGET_LIBRARY, create_if_missing=False)
    return lib.read(field).data


def read_daily_kline_column(col: str, symbols: List[str], conn: Arctic = None) -> pd.DataFrame:
    """读取日线某列 (high/low/close)，返回 日期 x 股票 DataFrame"""
    conn = conn or get_conn()
    lib = conn.get_library("ashare@stock@kline@1d", create_if_missing=False)
    data = {}
    for i, sym in enumerate(symbols):
        try:
            data[sym] = lib.read(sym).data[col]
        except Exception:
            pass
        if (i + 1) % 1000 == 0:
            print(f"  ...read {i+1}/{len(symbols)}")
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# 检查 1: 价格范围
# ---------------------------------------------------------------------------

def check_price_range(field: str, conn: Arctic = None):
    """检查类价格字段是否在当日 daily [low, high] 范围内。
    适用于 twap, vwap 等有价格含义的字段。
    """
    conn = conn or get_conn()
    df = read_rawdata(field, conn)
    symbols = list(df.columns)
    print(f"Reading daily high/low for {len(symbols)} symbols...")
    daily_high = read_daily_kline_column("high", symbols, conn)
    daily_low = read_daily_kline_column("low", symbols, conn)

    cd = df.index.intersection(daily_high.index)
    cc = df.columns.intersection(daily_high.columns)
    fd, hi, lo = df.loc[cd, cc], daily_high.loc[cd, cc], daily_low.loc[cd, cc]

    valid = fd.notna() & hi.notna()
    total = int(valid.sum().sum())
    above = int(((fd > hi + 1e-6) & valid).sum().sum())
    below = int(((fd < lo - 1e-6) & valid).sum().sum())

    print(f"\n{field}: total={total:,}, above_high={above}, below_low={below}")

    # 打印异常样本
    viol = ((fd > hi + 1e-6) | (fd < lo - 1e-6)) & valid
    if viol.any().any():
        locs = list(zip(*np.where(viol.values)))[:10]
        print("Examples:")
        for r, c in locs:
            print(f"  {cd[r].date()} {cc[c]}: val={fd.iloc[r,c]:.4f} low={lo.iloc[r,c]:.4f} high={hi.iloc[r,c]:.4f}")


# ---------------------------------------------------------------------------
# 检查 2: 覆盖率
# ---------------------------------------------------------------------------

def check_coverage(fields: List[str], conn: Arctic = None):
    """检查 raw-data 覆盖率，对比 daily close。
    输出: 每个 field 的覆盖率 + 是否有 daily close 缺失但 raw-data 有值的异常情况。
    """
    conn = conn or get_conn()
    sample = read_rawdata(fields[0], conn)
    symbols = list(sample.columns)
    print(f"Reading daily close for {len(symbols)} symbols...")
    daily_close = read_daily_kline_column("close", symbols, conn)
    has_close = daily_close.notna()

    print(f"\n{'Field':<40} {'覆盖率':>8} {'缺失':>8} {'无close有值':>12}")
    print("-" * 72)
    for field in fields:
        df = read_rawdata(field, conn)
        cd = df.index.intersection(daily_close.index)
        cc = df.columns.intersection(daily_close.columns)
        fd = df.loc[cd, cc]
        dc = has_close.loc[cd, cc]
        has_val = fd.notna()

        has_both = (has_val & dc).sum().sum()
        has_close_total = int(dc.sum().sum())
        missing = has_close_total - int(has_both)
        coverage = has_both / has_close_total * 100 if has_close_total > 0 else 0
        # 异常: 没有 daily close 但有 raw-data 值
        ghost = int((has_val & ~dc).sum().sum())

        print(f"{field:<40} {coverage:>7.2f}% {missing:>8,} {ghost:>12,}")


# ---------------------------------------------------------------------------
# 检查 3: 极端值
# ---------------------------------------------------------------------------

def check_extremes(fields: List[str], conn: Arctic = None):
    """检查 inf/-inf 和极端值分布"""
    conn = conn or get_conn()
    print(f"{'Field':<40} {'inf':>6} {'-inf':>6} {'min':>14} {'p1':>12} {'p50':>12} {'p99':>12} {'max':>14}")
    print("-" * 120)
    for field in fields:
        df = read_rawdata(field, conn)
        vals = df.values.flatten()
        valid = vals[~np.isnan(vals)]
        finite = valid[np.isfinite(valid)]
        n_inf = int(np.sum(np.isinf(valid) & (valid > 0)))
        n_ninf = int(np.sum(np.isinf(valid) & (valid < 0)))
        if len(finite) > 0:
            print(f"{field:<40} {n_inf:>6} {n_ninf:>6} {np.min(finite):>14.6g} {np.percentile(finite,1):>12.6g} "
                  f"{np.percentile(finite,50):>12.6g} {np.percentile(finite,99):>12.6g} {np.max(finite):>14.6g}")
        else:
            print(f"{field:<40} {n_inf:>6} {n_ninf:>6} {'N/A':>14} {'N/A':>12} {'N/A':>12} {'N/A':>12} {'N/A':>14}")
