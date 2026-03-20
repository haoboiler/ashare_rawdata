#!/usr/bin/env python3
"""本地计算 raw-data 因子值并导出为 pkl，不入库。

用于快速验证因子效果：计算 → 导出 pkl → 跑 evaluate.py → 根据结果决定是否入库。

用法：
    # 1. 直接传入 formula 文件（推荐）
    python scripts/compute_rawdata_local.py \
        --formula-file research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py \
        --output-dir .claude-output/analysis/

    # 2. 传入已注册的 bundle name
    python scripts/compute_rawdata_local.py \
        --bundle pv_stats_0930_1030 \
        --output-dir .claude-output/analysis/

    # 3. 只算部分 symbol（快速验证）
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py \
        --symbols 000001.SZ 600519.SH \
        --output-dir .claude-output/analysis/

    # 4. 只算部分 output fields
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py \
        --only-fields smart_money_0930_1030 volume_entropy_0930_1030 \
        --output-dir .claude-output/analysis/

    # 5. 快速模式（100 个 symbol 快速验证）
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py \
        --quick \
        --output-dir .claude-output/analysis/

formula 文件格式：
    与注册脚本相同，必须包含 build_definition() 函数返回 AShareRawDataDefinition。
    参考 research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py

输出：
    每个 output field 一个 pkl 文件，格式为 DataFrame(index=trade_date, columns=symbols)。
    与 evaluate.py --file 参数兼容。
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arcticdb import Arctic
from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_SOURCE_LIBRARY, SYMBOL_CACHE_FILE
from ashare_hf_variable.models import AShareRawDataDefinition, CompletenessPolicy, PriceBasis
from ashare_hf_variable.registry import compile_formula, list_definitions, validate_definition

logger = logging.getLogger(__name__)

_PRICE_FIELDS = {"open", "high", "low", "close"}


# ---------------------------------------------------------------------------
# Core helpers (copied from updater.py to avoid coupling)
# ---------------------------------------------------------------------------

def _normalize_symbol_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.index.name = "datetime"
    return df


def _parse_hhmm(text: str):
    from datetime import datetime as dt
    return dt.strptime(text, "%H:%M").time()


def _filter_day_df(day_df: pd.DataFrame, windows) -> pd.DataFrame:
    windows = list(windows)
    if not windows or day_df.empty:
        return day_df
    times = np.array(day_df.index.time)
    mask = np.zeros(len(day_df), dtype=bool)
    for start, end in windows:
        start_t = _parse_hhmm(start)
        end_t = _parse_hhmm(end)
        mask |= (times >= start_t) & (times < end_t)
    return day_df.loc[mask]


def _resolve_input_name(field: str, price_basis: PriceBasis) -> str:
    if field.startswith("origin_"):
        return field
    if field in _PRICE_FIELDS and price_basis == PriceBasis.ORIGIN:
        return f"origin_{field}"
    return field


def _load_symbols() -> List[str]:
    cache_path = Path(SYMBOL_CACHE_FILE)
    if cache_path.exists():
        return sorted({line.strip() for line in cache_path.read_text(encoding="utf-8").splitlines() if line.strip()})
    return []


# ---------------------------------------------------------------------------
# Load definition from file or registry
# ---------------------------------------------------------------------------

def load_definition_from_file(filepath: str) -> AShareRawDataDefinition:
    """Import a registration script and call build_definition()."""
    path = Path(filepath).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Formula file not found: {path}")

    spec = importlib.util.spec_from_file_location("_formula_module", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "build_definition"):
        raise AttributeError(f"{path} must define a build_definition() function")

    return module.build_definition()


def load_definition_from_registry(bundle_name: str) -> AShareRawDataDefinition:
    """Load a definition from the registry by name."""
    defs = list_definitions()
    for d in defs:
        if d.name == bundle_name:
            return d
    raise ValueError(f"Bundle '{bundle_name}' not found in registry")


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def compute_symbol(
    symbol_df: pd.DataFrame,
    definition: AShareRawDataDefinition,
    func,
) -> pd.DataFrame:
    """Compute one symbol, return DataFrame(index=dates, columns=output_names)."""
    symbol_df = _normalize_symbol_df(symbol_df)
    if symbol_df.empty:
        return pd.DataFrame(columns=definition.output_names, dtype="float64")

    resolved_inputs = [_resolve_input_name(n, definition.price_basis) for n in definition.input_names]
    missing = [n for n in resolved_inputs if n not in symbol_df.columns]
    if missing:
        return pd.DataFrame(columns=definition.output_names, dtype="float64")

    rows: Dict[pd.Timestamp, np.ndarray] = {}
    grouped = symbol_df.groupby(symbol_df.index.normalize())
    for trade_date, day_df in grouped:
        sliced = _filter_day_df(day_df, definition.params.input_time_filter)
        if sliced.empty:
            continue
        if (
            definition.expected_bars is not None
            and definition.completeness_policy == CompletenessPolicy.STRICT_FULL_WINDOW
        ):
            ref_count = pd.to_numeric(sliced[resolved_inputs[0]], errors="coerce").count()
            if ref_count < definition.expected_bars:
                continue

        arrays = []
        for name in resolved_inputs:
            arr = pd.to_numeric(sliced[name], errors="coerce").to_numpy(dtype=np.float64)
            arrays.append(arr)

        try:
            out = np.asarray(func(tuple(arrays)), dtype=np.float64).reshape(-1)
        except Exception:
            continue

        if out.shape[0] != len(definition.output_names):
            raise ValueError(
                f"{definition.name}: formula returned {out.shape[0]} outputs, "
                f"expected {len(definition.output_names)}"
            )
        rows[pd.Timestamp(trade_date)] = out

    if not rows:
        return pd.DataFrame(columns=definition.output_names, dtype="float64")

    result = pd.DataFrame.from_dict(rows, orient="index", columns=definition.output_names)
    result.index = pd.DatetimeIndex(result.index, name="datetime")
    return result.sort_index()


def compute_and_export(
    definition: AShareRawDataDefinition,
    output_dir: str,
    symbols: Optional[List[str]] = None,
    only_fields: Optional[List[str]] = None,
    start_date: Optional[str] = None,
):
    """Main entry: compute all symbols, assemble per-field DataFrames, export as pkl."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Compile formula
    logger.info(f"Compiling formula for {definition.name}...")
    func = compile_formula(definition)

    # Warm up numba JIT
    logger.info("Warming up numba JIT...")
    n_inputs = len(definition.input_names)
    dummy = tuple(np.random.randn(60) for _ in range(n_inputs))
    func(dummy)

    # Load symbols
    conn = Arctic(ARCTIC_URL)
    source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
    if symbols:
        all_symbols = symbols
    else:
        all_symbols = _load_symbols()
        if not all_symbols:
            all_symbols = sorted(source_lib.list_symbols())

    logger.info(f"Computing {definition.name}: {len(all_symbols)} symbols, "
                f"{len(definition.output_names)} outputs")

    # Determine date range
    start_time = None
    if start_date:
        start_time = pd.Timestamp(start_date)

    # Compute per symbol
    field_data: Dict[str, Dict[str, pd.Series]] = {}
    t0 = time.time()

    for i, symbol in enumerate(all_symbols):
        try:
            if start_time:
                df = source_lib.read(symbol, date_range=(start_time, None)).data
            else:
                df = source_lib.read(symbol).data
        except Exception:
            continue

        result = compute_symbol(df, definition, func)
        if result.empty:
            continue

        for field in definition.output_names:
            if only_fields and field not in only_fields:
                continue
            series = result[field].dropna()
            if series.empty:
                continue
            field_data.setdefault(field, {})[symbol] = series

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(all_symbols) - i - 1) / rate
            logger.info(f"  ...{i+1}/{len(all_symbols)} symbols "
                        f"({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")

    elapsed = time.time() - t0
    logger.info(f"Computation done: {len(all_symbols)} symbols in {elapsed:.0f}s")

    # Assemble and export per-field DataFrames
    exported = []
    for field, symbol_map in field_data.items():
        field_df = pd.DataFrame(symbol_map)
        field_df = field_df.reindex(sorted(field_df.columns), axis=1)
        field_df = field_df.sort_index()
        field_df.index = field_df.index.tz_localize("Asia/Shanghai")
        field_df.index.name = "trade_date"

        pkl_path = output_path / f"{field}.pkl"
        field_df.to_pickle(pkl_path)
        exported.append((field, field_df.shape, pkl_path))
        logger.info(f"  Exported: {pkl_path} ({field_df.shape[0]} dates x {field_df.shape[1]} symbols)")

    return exported


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute raw-data factors locally and export as pkl (no registry write)"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--formula-file", help="Path to a registration script with build_definition()")
    source.add_argument("--bundle", help="Name of a registered bundle in the registry")

    parser.add_argument("--output-dir", "-o", default=".claude-output/analysis",
                        help="Output directory for pkl files (default: .claude-output/analysis)")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Only compute these symbols (default: all)")
    parser.add_argument("--only-fields", nargs="+", default=None,
                        help="Only export these output fields (default: all)")
    parser.add_argument("--start-date", default=None,
                        help="Start date for 1m data reading (default: full history)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: use 100 random symbols for fast validation")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Load definition
    if args.formula_file:
        definition = load_definition_from_file(args.formula_file)
        logger.info(f"Loaded definition from file: {args.formula_file}")
    else:
        definition = load_definition_from_registry(args.bundle)
        logger.info(f"Loaded definition from registry: {args.bundle}")

    logger.info(f"  Name: {definition.name}")
    logger.info(f"  Inputs: {definition.input_names}")
    logger.info(f"  Outputs: {definition.output_names}")
    logger.info(f"  Time filter: {definition.params.input_time_filter}")

    # Handle --quick
    symbols = args.symbols
    if args.quick and not symbols:
        all_syms = _load_symbols()
        if not all_syms:
            conn = Arctic(ARCTIC_URL)
            lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
            all_syms = sorted(lib.list_symbols())
        np.random.seed(42)
        symbols = list(np.random.choice(all_syms, size=min(100, len(all_syms)), replace=False))
        logger.info(f"Quick mode: using {len(symbols)} random symbols")

    # Compute and export
    exported = compute_and_export(
        definition=definition,
        output_dir=args.output_dir,
        symbols=symbols,
        only_fields=args.only_fields,
        start_date=args.start_date,
    )

    # Print summary
    print(f"\n{'='*60}")
    print(f"Exported {len(exported)} fields to {args.output_dir}")
    print(f"{'='*60}")
    for field, shape, path in exported:
        print(f"  {field}: {shape[0]} dates x {shape[1]} symbols -> {path}")

    # Print evaluate.py command hint
    if exported:
        print(f"\n--- Next step: run evaluate.py ---")
        sample_field, _, sample_path = exported[0]
        print(f"cd /home/gkh/claude_tasks/ashare_rawdata")
        print(f"python /home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py \\")
        print(f"    --file {sample_path} \\")
        print(f"    --start 2020-01-01 --window 1 --num-groups 5 \\")
        print(f"    --execution-price-field twap_1300_1400 \\")
        print(f"    --benchmark-index csi1000 \\")
        print(f"    --neutralize \\")
        print(f"    --post-process-method csremovemedianbooksize \\")
        print(f"    --output-dir .claude-output/evaluations/{sample_field}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
