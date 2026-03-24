#!/usr/bin/env python3
"""构建已入库 raw-data 的 PnL 缓存。

对 ashare@stock@raw_value@1d 中的所有 field 跑 evaluate.py 回测，
提取日度 PnL 序列（LS absolute + Long-benchmark excess），存为缓存 pkl。

用法:
    # 全量构建（所有已入库 field）
    python scripts/build_pnl_cache.py --output-dir .claude-output/pnl_cache/

    # 只构建指定 field
    python scripts/build_pnl_cache.py --fields twap_0930_1030 vwap_0930_1030 \
        --output-dir .claude-output/pnl_cache/

    # 增量构建（跳过已有缓存的 field）
    python scripts/build_pnl_cache.py --output-dir .claude-output/pnl_cache/ --incremental

缓存格式:
    pnl_cache.pkl = {
        'ls_pnl': DataFrame(index=dates, columns=field_names),   # ret_net
        'lb_pnl': DataFrame(index=dates, columns=field_names),   # long_excess_ret_net
        'metadata': {field_name: {sharpe, ic_ls, ...}, ...},
        'params': {start, end, mode, ...},
        'built_at': timestamp,
    }
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EVALUATE_PY = "/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py"
PYTHON = "/home/b0qi/anaconda3/envs/gkh-ashare/bin/python"
PROJECT_ROOT = Path("/home/gkh/claude_tasks/ashare_rawdata")
MOCK_PACKAGES = str(PROJECT_ROOT / ".claude-tmp" / "mock_packages")


def get_all_rawdata_fields():
    """从 Arctic 获取所有已入库的 raw-data field 名"""
    from arcticdb import Arctic
    from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_TARGET_LIBRARY
    conn = Arctic(ARCTIC_URL)
    lib = conn.get_library(DEFAULT_TARGET_LIBRARY, create_if_missing=False)
    return sorted(lib.list_symbols())


def export_field_to_pkl(field: str, output_dir: Path) -> Path:
    """从 Arctic 导出一个 field 为 pkl（带时区）"""
    from arcticdb import Arctic
    from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_TARGET_LIBRARY
    conn = Arctic(ARCTIC_URL)
    lib = conn.get_library(DEFAULT_TARGET_LIBRARY, create_if_missing=False)
    df = lib.read(field).data
    df.index = pd.to_datetime(df.index)
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Shanghai")
    pkl_path = output_dir / f"{field}.pkl"
    df.to_pickle(pkl_path)
    return pkl_path


def run_evaluate(pkl_path: Path, output_dir: Path, start: str, end: str) -> Path:
    """运行 evaluate.py 并返回结果目录"""
    field_name = pkl_path.stem
    eval_dir = output_dir / field_name

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{MOCK_PACKAGES}:{env.get('PYTHONPATH', '')}"

    cmd = [
        PYTHON, EVALUATE_PY,
        "--file", str(pkl_path),
        "--start", start,
        "--end", end,
        "--mode", "long_short",
        "--num-groups", "8",
        "--post-process-method", "comp",
        "--execution-price-field", "twap_1300_1400",
        "--benchmark-index", "csi1000",
        "--commission-rate", "0.0001",
        "--stamp-tax-rate", "0.0",
        "--quick",
        "--output-dir", str(eval_dir),
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, env=env,
        cwd=str(PROJECT_ROOT), timeout=600,
    )

    if result.returncode != 0:
        # Check if it's just the update_output_index error (harmless)
        if "is not in the subpath of" in result.stderr and "update_output_index" in result.stderr:
            pass  # Harmless cross-project path error
        elif "update_output_index" in result.stdout:
            pass
        else:
            raise RuntimeError(f"evaluate.py failed for {field_name}:\n{result.stderr[-500:]}")

    return eval_dir


def extract_pnl(eval_dir: Path, field_name: str) -> dict:
    """从评估结果中提取 PnL 序列和指标"""
    # Find result.pkl — try raw variant first, then any subdir with result.pkl
    raw_dir = None
    for d in eval_dir.iterdir():
        if d.is_dir() and "-raw" in d.name:
            raw_dir = d
            break
    if raw_dir is None:
        for d in eval_dir.iterdir():
            if d.is_dir() and (d / "result.pkl").exists():
                raw_dir = d
                break

    if raw_dir is None:
        raise FileNotFoundError(f"No result dir found in {eval_dir}")

    result_pkl = raw_dir / "result.pkl"
    stats_json = raw_dir / "stats.json"

    if not result_pkl.exists():
        raise FileNotFoundError(f"result.pkl not found in {raw_dir}")

    result = pd.read_pickle(result_pkl)

    out = {
        "ls_pnl": result["ret_net"] if "ret_net" in result.columns else None,
        "lb_pnl": result["long_excess_ret_net"] if "long_excess_ret_net" in result.columns else None,
    }

    if stats_json.exists():
        with open(stats_json) as f:
            stats = json.load(f)
        out["stats"] = {
            "sharpe_abs_net": stats.get("sharpe_abs_net"),
            "sharpe_long_excess_net": stats.get("sharpe_long_excess_net"),
            "ic_ls": stats.get("ic_ls_mean"),
            "ir_ls": stats.get("ir_ls"),
        }

    return out


def build_parser():
    p = argparse.ArgumentParser(description="Build PnL cache for registered raw-data fields")
    p.add_argument("--output-dir", "-o", default=".claude-output/pnl_cache",
                    help="Cache output directory")
    p.add_argument("--fields", nargs="+", default=None,
                    help="Only build cache for these fields (default: all)")
    p.add_argument("--incremental", action="store_true",
                    help="Skip fields already in cache")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2026-03-14")
    p.add_argument("--batch-size", type=int, default=10,
                    help="Save checkpoint every N fields")
    return p


def main():
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pkl_dir = output_dir / "field_pkls"
    eval_dir = output_dir / "evaluations"
    pkl_dir.mkdir(exist_ok=True)
    eval_dir.mkdir(exist_ok=True)

    cache_path = output_dir / "pnl_cache.pkl"

    # Load existing cache if incremental
    existing_cache = {}
    if args.incremental and cache_path.exists():
        existing_cache = pd.read_pickle(cache_path)
        print(f"Loaded existing cache: {len(existing_cache.get('ls_pnl', {}).columns)} fields")

    # Get fields to process
    if args.fields:
        fields = args.fields
    else:
        fields = get_all_rawdata_fields()

    if args.incremental and existing_cache:
        cached_fields = set(existing_cache.get("ls_pnl", pd.DataFrame()).columns)
        fields = [f for f in fields if f not in cached_fields]
        print(f"Incremental: {len(fields)} new fields to process")

    print(f"Total fields: {len(fields)}")
    print(f"Params: start={args.start}, end={args.end}")
    print(f"Output: {output_dir}")

    ls_pnl_dict = {}
    lb_pnl_dict = {}
    metadata = {}
    failed = []

    # Load existing data if incremental
    if existing_cache:
        for col in existing_cache.get("ls_pnl", pd.DataFrame()).columns:
            ls_pnl_dict[col] = existing_cache["ls_pnl"][col]
        for col in existing_cache.get("lb_pnl", pd.DataFrame()).columns:
            lb_pnl_dict[col] = existing_cache["lb_pnl"][col]
        metadata = existing_cache.get("metadata", {})

    t0 = time.time()

    for i, field in enumerate(fields):
        print(f"\n[{i+1}/{len(fields)}] {field}")

        try:
            # Export from Arctic
            pkl_path = export_field_to_pkl(field, pkl_dir)
            print(f"  Exported pkl: {pkl_path}")

            # Run evaluate
            t1 = time.time()
            edir = run_evaluate(pkl_path, eval_dir, args.start, args.end)
            print(f"  Evaluated in {time.time()-t1:.0f}s")

            # Extract PnL
            data = extract_pnl(edir, field)
            if data["ls_pnl"] is not None:
                ls_pnl_dict[field] = data["ls_pnl"]
            if data["lb_pnl"] is not None:
                lb_pnl_dict[field] = data["lb_pnl"]
            if "stats" in data:
                metadata[field] = data["stats"]
            print(f"  OK: LS Sharpe={data.get('stats', {}).get('sharpe_abs_net', 'N/A')}")

        except Exception as e:
            print(f"  FAILED: {e}")
            failed.append((field, str(e)))

        # Save checkpoint
        if (i + 1) % args.batch_size == 0:
            _save_cache(cache_path, ls_pnl_dict, lb_pnl_dict, metadata, args, failed)
            print(f"  [Checkpoint saved: {len(ls_pnl_dict)} fields]")

    # Final save
    _save_cache(cache_path, ls_pnl_dict, lb_pnl_dict, metadata, args, failed)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"Done: {len(ls_pnl_dict)} fields cached, {len(failed)} failed, {elapsed:.0f}s")
    print(f"Cache: {cache_path}")
    if failed:
        print(f"Failed fields: {[f[0] for f in failed]}")


def _save_cache(path, ls_pnl_dict, lb_pnl_dict, metadata, args, failed):
    cache = {
        "ls_pnl": pd.DataFrame(ls_pnl_dict),
        "lb_pnl": pd.DataFrame(lb_pnl_dict),
        "metadata": metadata,
        "params": {
            "start": args.start,
            "end": args.end,
            "mode": "long_short",
            "post_process": "comp",
            "execution_price": "twap_1300_1400",
            "benchmark": "csi1000",
        },
        "failed": failed,
        "built_at": datetime.now().isoformat(),
    }
    pd.to_pickle(cache, path)


if __name__ == "__main__":
    main()
