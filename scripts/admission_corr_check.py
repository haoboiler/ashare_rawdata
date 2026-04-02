#!/usr/bin/env python3
"""
A 股 Raw-Data 入库相关性检验脚本

检验候选 raw-data 因子与已入库因子的 PnL 相关性，决定是否具备入库的独立性。

两层检验：
  L1 (LS PnL Pearson)  — 多空绝对 PnL 的 Pearson |ρ| < 0.6
  L2 (LB PnL Pearson)  — 多头超额 PnL 的 Pearson |ρ| < 0.8

依赖：
  - PnL 缓存文件（由 build_pnl_cache.py 构建）
  - evaluate_rawdata.py（对候选因子跑回测）

用法:
    # 检验单个因子
    python scripts/admission_corr_check.py \
        --factors .claude-output/analysis/smart_money_0930_1030.pkl \
        --cache .claude-output/pnl_cache/pnl_cache.pkl

    # 检验多个因子
    python scripts/admission_corr_check.py \
        --factors factor1.pkl factor2.pkl \
        --cache .claude-output/pnl_cache/pnl_cache.pkl

    # 自定义阈值
    python scripts/admission_corr_check.py \
        --factors factor.pkl \
        --cache .claude-output/pnl_cache/pnl_cache.pkl \
        --ls-threshold 0.5 --lb-threshold 0.7

    # 保存结果为 JSON
    python scripts/admission_corr_check.py \
        --factors factor.pkl \
        --cache .claude-output/pnl_cache/pnl_cache.pkl \
        --save-json results.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path("/home/gkh/claude_tasks/ashare_rawdata")
EVALUATE_WRAPPER = str(PROJECT_ROOT / "scripts" / "evaluate_rawdata.py")
PYTHON = "/home/b0qi/anaconda3/envs/gkh-ashare/bin/python"
MOCK_PACKAGES = str(PROJECT_ROOT / ".claude-tmp" / "mock_packages")


def load_cache(cache_path: str) -> dict:
    """加载 PnL 缓存"""
    cache = pd.read_pickle(cache_path)
    ls_pnl = cache["ls_pnl"]
    lb_pnl = cache["lb_pnl"]
    print(f"[Cache] {cache_path}")
    print(f"  LS PnL: {ls_pnl.shape[1]} fields × {ls_pnl.shape[0]} dates")
    print(f"  LB PnL: {lb_pnl.shape[1]} fields × {lb_pnl.shape[0]} dates")
    print(f"  Built at: {cache.get('built_at', 'unknown')}")
    return cache


def run_evaluate_for_factor(factor_path: str, start: str, end: str) -> dict:
    """对候选因子跑项目 raw-data wrapper，提取 PnL 序列"""
    name = Path(factor_path).stem
    eval_dir = PROJECT_ROOT / ".claude-tmp" / "corr_check_evals" / name

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{MOCK_PACKAGES}:{env.get('PYTHONPATH', '')}"

    cmd = [
        PYTHON, EVALUATE_WRAPPER,
        "--file", str(factor_path),
        "--start", start,
        "--end", end,
        "--no-neutralize",
        "--quick",
        "--output-dir", str(eval_dir),
    ]

    print(f"  Running evaluate_rawdata.py...")
    t0 = time.time()
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env,
        cwd=str(PROJECT_ROOT), timeout=600,
    )
    elapsed = time.time() - t0
    print(f"  Evaluate done in {elapsed:.0f}s")

    # Find raw result
    raw_dir = None
    if eval_dir.exists():
        for d in eval_dir.iterdir():
            if d.is_dir() and "-raw" in d.name:
                raw_dir = d
                break

    if raw_dir is None or not (raw_dir / "result.pkl").exists():
        raise RuntimeError(f"Evaluation failed for {name}")

    res = pd.read_pickle(raw_dir / "result.pkl")
    stats = {}
    if (raw_dir / "stats.json").exists():
        with open(raw_dir / "stats.json") as f:
            stats = json.load(f)

    return {
        "ls_pnl": res.get("ret_net"),
        "lb_pnl": res.get("long_excess_ret_net"),
        "stats": stats,
    }


def check_corr(new_pnl: pd.Series, cache_pnl: pd.DataFrame,
               name: str, threshold: float, label: str) -> dict:
    """计算新因子与缓存所有因子的 Pearson 相关性"""
    print(f"\n--- {label}: {name} (threshold={threshold}) ---")

    common_idx = new_pnl.dropna().index.intersection(cache_pnl.index)
    print(f"  Common dates: {len(common_idx)}")

    if len(common_idx) < 100:
        print(f"  ⚠ WARNING: only {len(common_idx)} dates, result may be unreliable")
        if len(common_idx) < 30:
            print(f"  SKIP: too few dates")
            return {"passed": True, "max_corr": 0, "most_similar": "N/A",
                    "n_compared": 0, "skipped": True}

    new_aligned = new_pnl.loc[common_idx]
    cache_aligned = cache_pnl.loc[common_idx]

    corrs = cache_aligned.corrwith(new_aligned, method="pearson")
    abs_corr = corrs.abs().dropna().sort_values(ascending=False)

    if abs_corr.empty:
        print(f"  No valid correlations computed")
        return {"passed": True, "max_corr": 0, "most_similar": "N/A", "n_compared": 0}

    max_corr = float(abs_corr.iloc[0])
    most_sim = abs_corr.index[0]
    passed = max_corr < threshold

    tag = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {tag}  max|ρ|={max_corr:.4f}  → {most_sim}")
    print(f"  Top-10:")
    for i, (field, val) in enumerate(abs_corr.head(10).items()):
        flag = "⚠️" if val >= threshold else "  "
        print(f"    {flag}[{i+1:2d}] |ρ|={val:.4f}  {field}")
    print(f"  Distribution: mean={abs_corr.mean():.4f}, med={abs_corr.median():.4f}, "
          f">0.4={int((abs_corr>0.4).sum())}, >0.5={int((abs_corr>0.5).sum())}, "
          f">0.6={int((abs_corr>0.6).sum())}")

    return {
        "passed": passed,
        "max_corr": max_corr,
        "most_similar": most_sim,
        "mean_corr": float(abs_corr.mean()),
        "median_corr": float(abs_corr.median()),
        "above_04": int((abs_corr > 0.4).sum()),
        "above_05": int((abs_corr > 0.5).sum()),
        "above_06": int((abs_corr > 0.6).sum()),
        "n_compared": len(abs_corr),
    }


def parse_args():
    p = argparse.ArgumentParser(
        description="A 股 Raw-Data 入库相关性检验",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--factors", nargs="+", required=True,
                    help="候选因子 pkl 文件路径")
    p.add_argument("--cache", required=True,
                    help="PnL 缓存文件路径（由 build_pnl_cache.py 构建）")
    p.add_argument("--ls-threshold", type=float, default=0.60,
                    help="L1 LS PnL Pearson |ρ| 阈值 (default: 0.60)")
    p.add_argument("--lb-threshold", type=float, default=0.80,
                    help="L2 LB PnL Pearson |ρ| 阈值 (default: 0.80)")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2026-03-14")
    p.add_argument("--save-json", default=None,
                    help="保存结果为 JSON")
    return p.parse_args()


def main():
    args = parse_args()

    print("=" * 70)
    print("A 股 Raw-Data Admission Correlation Check")
    print("=" * 70)
    print(f"Factors: {[Path(f).stem for f in args.factors]}")
    print(f"Cache: {args.cache}")
    print(f"Thresholds: L1 LS |ρ| < {args.ls_threshold}, L2 LB |ρ| < {args.lb_threshold}")
    print()

    # Load cache
    cache = load_cache(args.cache)
    cache_ls = cache["ls_pnl"]
    cache_lb = cache["lb_pnl"]

    all_results = {}

    for factor_path in args.factors:
        name = Path(factor_path).stem
        print(f"\n{'#'*70}")
        print(f"# {name}")
        print(f"{'#'*70}")

        try:
            # Run evaluate on candidate
            data = run_evaluate_for_factor(factor_path, args.start, args.end)
        except Exception as e:
            print(f"  FAILED: {e}")
            all_results[name] = {"error": str(e)}
            continue

        res = {
            "factor_path": str(factor_path),
            "stats": data.get("stats", {}),
        }

        # L1: LS PnL Pearson
        if data["ls_pnl"] is not None:
            l1 = check_corr(data["ls_pnl"], cache_ls, name,
                            args.ls_threshold, "L1 LS PnL Pearson")
            res["l1_ls"] = l1
        else:
            res["l1_ls"] = {"passed": True, "skipped": True}

        # L2: LB PnL Pearson
        if data["lb_pnl"] is not None:
            l2 = check_corr(data["lb_pnl"], cache_lb, name,
                            args.lb_threshold, "L2 LB PnL Pearson")
            res["l2_lb"] = l2
        else:
            res["l2_lb"] = {"passed": True, "skipped": True}

        l1_ok = res["l1_ls"].get("passed", True)
        l2_ok = res["l2_lb"].get("passed", True)
        res["overall_pass"] = l1_ok and l2_ok

        all_results[name] = res

    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"Cache: {len(cache_ls.columns)} registered fields")
    print(f"Thresholds: L1 LS |ρ| < {args.ls_threshold}, L2 LB |ρ| < {args.lb_threshold}")
    print()

    for name, res in all_results.items():
        if "error" in res:
            print(f"  {name}: ERROR — {res['error']}")
            continue

        l1 = res["l1_ls"]
        l2 = res["l2_lb"]
        l1_tag = "✅" if l1["passed"] else "❌"
        l2_tag = "✅" if l2["passed"] else "❌"
        overall = "✅ PASS" if res["overall_pass"] else "❌ FAIL"

        stats = res.get("stats", {})
        sharpe = stats.get("sharpe_abs_net", "N/A")

        print(f"  {name}  (LS Sharpe={sharpe})")
        if not l1.get("skipped"):
            print(f"    L1 LS PnL:  {l1_tag} max|ρ|={l1['max_corr']:.4f} → {l1['most_similar']}")
        if not l2.get("skipped"):
            print(f"    L2 LB PnL:  {l2_tag} max|ρ|={l2['max_corr']:.4f} → {l2['most_similar']}")
        print(f"    >>> {overall}")
        print()

    # Save JSON
    if args.save_json:
        out = {
            "timestamp": datetime.now().isoformat(),
            "cache_path": args.cache,
            "cache_size": len(cache_ls.columns),
            "thresholds": {
                "ls_pnl_pearson": args.ls_threshold,
                "lb_pnl_pearson": args.lb_threshold,
            },
            "results": all_results,
        }
        with open(args.save_json, "w") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"[Saved] {args.save_json}")


if __name__ == "__main__":
    main()
