#!/usr/bin/env python3
"""本地计算 raw-data 因子值并导出为 pkl，不入库。

用于快速验证因子效果：计算 → 导出 pkl → 跑 evaluate.py → 根据结果决定是否入库。

用法：
    # 1. 标准模式（单进程串行，~30-60 分钟全量）
    python scripts/compute_rawdata_local.py \
        --formula-file research/basic_rawdata/pv_stats/register_pv_stats_0930_1030.py \
        --output-dir .claude-output/analysis/

    # 2. 快速模式（100 个 symbol，~1-2 分钟）
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py --quick \
        --output-dir .claude-output/analysis/

    # 3. Ray 并行加速模式（~5-10 分钟全量，需要 Ray）
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py --fast \
        --output-dir .claude-output/analysis/

    # 4. Ray 预加载模式（首次加载 ~9 分钟，后续每次 ~5 秒）
    python scripts/compute_rawdata_local.py --preload   # 预加载数据到 Ray
    python scripts/compute_rawdata_local.py \
        --formula-file my_formula.py --fast --use-preload \
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
from typing import Dict, List, Optional, Tuple

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
BARS_PER_DAY = 240
_ALL_FIELDS = ["close", "open", "high", "low", "volume", "amount",
               "origin_close", "origin_open", "origin_high", "origin_low"]
RAY_PRELOAD_ACTOR = "ashare_rawdata_preload"


# ---------------------------------------------------------------------------
# Core helpers
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


def _time_str_to_bar_index(t_str: str) -> int:
    """Convert HH:MM to bar index (0-239). Morning: 0-119, Afternoon: 120-239."""
    h, m = map(int, t_str.split(":"))
    if h < 12:
        return (h - 9) * 60 + m - 30
    else:
        return (h - 13) * 60 + m + 120


def _time_filter_to_bar_mask(time_filter: List[Tuple[str, str]]) -> np.ndarray:
    """Convert multi-window time_filter to a boolean mask over 240 bars."""
    mask = np.zeros(BARS_PER_DAY, dtype=bool)
    for start_str, end_str in time_filter:
        bar_start = max(0, _time_str_to_bar_index(start_str))
        bar_end = min(BARS_PER_DAY, _time_str_to_bar_index(end_str))
        mask[bar_start:bar_end] = True
    return mask


# ---------------------------------------------------------------------------
# Load definition
# ---------------------------------------------------------------------------

def load_definition_from_file(filepath: str) -> AShareRawDataDefinition:
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
    defs = list_definitions()
    for d in defs:
        if d.name == bundle_name:
            return d
    raise ValueError(f"Bundle '{bundle_name}' not found in registry")


# ---------------------------------------------------------------------------
# Standard (serial) compute
# ---------------------------------------------------------------------------

def compute_symbol(symbol_df, definition, func):
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
        if (definition.expected_bars is not None
                and definition.completeness_policy == CompletenessPolicy.STRICT_FULL_WINDOW):
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
            raise ValueError(f"{definition.name}: formula returned {out.shape[0]} outputs, expected {len(definition.output_names)}")
        rows[pd.Timestamp(trade_date)] = out

    if not rows:
        return pd.DataFrame(columns=definition.output_names, dtype="float64")
    result = pd.DataFrame.from_dict(rows, orient="index", columns=definition.output_names)
    result.index = pd.DatetimeIndex(result.index, name="datetime")
    return result.sort_index()


def compute_serial(definition, symbols, source_lib, start_time=None):
    """Standard serial computation."""
    func = compile_formula(definition)
    logger.info("Warming up numba JIT...")
    n_inputs = len(definition.input_names)
    func(tuple(np.random.randn(60) for _ in range(n_inputs)))

    field_data: Dict[str, Dict[str, pd.Series]] = {}
    t0 = time.time()
    for i, symbol in enumerate(symbols):
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
            series = result[field].dropna()
            if not series.empty:
                field_data.setdefault(field, {})[symbol] = series
        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(symbols) - i - 1) / rate
            logger.info(f"  ...{i+1}/{len(symbols)} symbols ({elapsed:.0f}s, ETA {eta:.0f}s)")
    logger.info(f"Serial compute done: {len(symbols)} symbols in {time.time()-t0:.0f}s")
    return field_data


# ---------------------------------------------------------------------------
# Fast (Ray parallel) compute
# ---------------------------------------------------------------------------

def _make_ray_compute_task():
    """Create Ray remote function. Defined as factory to avoid import issues."""
    import ray

    @ray.remote
    def _ray_compute_batch(
        symbols, lib_name, arctic_url, all_fields, start_date, end_date,
        trading_days, func_code, field_indices, bar_mask, expected_bars, n_outputs,
    ):
        from arcticdb import Arctic as _Arctic
        from numba import njit as _njit

        conn = _Arctic(arctic_url)
        lib = conn.get_library(lib_name, create_if_missing=False)
        n_days = len(trading_days)
        n_fields = len(all_fields)
        day_to_idx = {d: i for i, d in enumerate(trading_days)}
        _ts_start = pd.Timestamp(start_date)
        _ts_end = pd.Timestamp(end_date)

        # Compile numba
        ns = {"np": np, "njit": _njit}
        exec(func_code, ns)
        func = ns["apply_func"]
        dummy = tuple([np.array([1.0, 2.0, 3.0])] * len(field_indices))
        try:
            func(dummy)
        except Exception:
            pass

        # bar_mask indices
        bar_indices_selected = np.where(bar_mask)[0]

        results = {}
        for symbol in symbols:
            try:
                df = lib.read(symbol, date_range=(_ts_start, _ts_end)).data
                if df.empty:
                    continue

                # Build 3D array: (n_days, 240, n_fields)
                arr = np.full((n_days, BARS_PER_DAY, n_fields), np.nan, dtype=np.float64)
                dates = df.index.date
                hours = df.index.hour.values
                minutes = df.index.minute.values
                bar_idx = np.where(
                    hours < 12,
                    (hours - 9) * 60 + minutes - 30,
                    (hours - 13) * 60 + minutes + 120,
                )
                valid_bars = (bar_idx >= 0) & (bar_idx < BARS_PER_DAY)

                for date_val in np.unique(dates):
                    di = day_to_idx.get(date_val)
                    if di is None:
                        continue
                    date_mask = (dates == date_val) & valid_bars
                    bi = bar_idx[date_mask]
                    for fi, field in enumerate(all_fields):
                        if field in df.columns:
                            arr[di, bi, fi] = df[field].values[date_mask].astype(np.float64)

                # Compute per day
                out = np.full((n_days, n_outputs), np.nan, dtype=np.float64)
                for i in range(n_days):
                    day_slice = arr[i, :, :]
                    selected = day_slice[bar_indices_selected, :]
                    # Check expected_bars
                    first_col = selected[:, field_indices[0]]
                    valid_count = np.sum(~np.isnan(first_col))
                    if valid_count == 0:
                        continue
                    if expected_bars is not None and valid_count < expected_bars:
                        continue
                    inputs = tuple(selected[:, fi] for fi in field_indices)
                    try:
                        res = func(inputs)
                        if res is not None and len(res) >= n_outputs:
                            out[i, :] = res[:n_outputs]
                    except Exception:
                        pass

                results[symbol] = out
            except Exception:
                pass

        return results

    return _ray_compute_batch


def compute_fast(definition, symbols, start_date="2020-01-01", end_date="2024-12-31",
                 num_workers=32):
    """Ray parallel computation."""
    import ray

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)

    conn = Arctic(ARCTIC_URL)
    source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)

    # Get trading days from first symbol
    ts_start = pd.Timestamp(start_date)
    ts_end = pd.Timestamp(end_date)
    sample_df = source_lib.read(symbols[0], date_range=(ts_start, ts_end)).data
    days = sorted(sample_df.index.normalize().unique())
    trading_days = [d.date() for d in days]
    date_index = pd.DatetimeIndex([pd.Timestamp(d) for d in trading_days])
    logger.info(f"  {len(symbols)} symbols, {len(trading_days)} trading days")

    # Resolve field indices
    all_fields = ["close", "open", "high", "low", "volume", "amount",
                  "origin_close", "origin_open", "origin_high", "origin_low"]
    field_to_idx = {f: i for i, f in enumerate(all_fields)}
    resolved_inputs = [_resolve_input_name(n, definition.price_basis) for n in definition.input_names]
    field_indices = [field_to_idx[f] for f in resolved_inputs]

    # Build multi-window bar mask
    bar_mask = _time_filter_to_bar_mask(definition.params.input_time_filter)
    n_outputs = len(definition.output_names)
    expected_bars = definition.expected_bars if (
        definition.completeness_policy == CompletenessPolicy.STRICT_FULL_WINDOW
    ) else None

    # Split into batches
    batch_size = max(1, (len(symbols) + num_workers - 1) // num_workers)
    _ray_compute_batch = _make_ray_compute_task()

    t0 = time.time()
    futures = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        futures.append(_ray_compute_batch.remote(
            batch, DEFAULT_SOURCE_LIBRARY, ARCTIC_URL, all_fields,
            start_date, end_date, trading_days,
            definition.formula, field_indices, bar_mask, expected_bars, n_outputs,
        ))

    logger.info(f"  Dispatched {len(futures)} Ray workers...")
    all_vals = {}
    for i, ref in enumerate(futures):
        batch_result = ray.get(ref)
        all_vals.update(batch_result)
        if (i + 1) % 4 == 0 or i == len(futures) - 1:
            elapsed = time.time() - t0
            logger.info(f"  batch {i+1}/{len(futures)}: {len(all_vals)}/{len(symbols)} stocks ({elapsed:.0f}s)")

    logger.info(f"  Ray compute done: {len(all_vals)} stocks in {time.time()-t0:.0f}s")

    # Build per-field dict
    field_data: Dict[str, Dict[str, pd.Series]] = {}
    for k, oname in enumerate(definition.output_names):
        sym_dict = {}
        for sym, arr in all_vals.items():
            col = arr[:, k]
            valid = ~np.isnan(col)
            if valid.any():
                sym_dict[sym] = pd.Series(col, index=date_index, name=oname)
        if sym_dict:
            field_data[oname] = sym_dict

    return field_data


# ---------------------------------------------------------------------------
# Preload (Ray actor)
# ---------------------------------------------------------------------------

def run_preload(start_date="2020-01-01", end_date="2024-12-31"):
    """Preload 1m data into Ray object store for fast repeated compute."""
    import ray

    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)

    conn = Arctic(ARCTIC_URL)
    source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
    all_symbols = sorted(source_lib.list_symbols())

    logger.info(f"Preloading {len(all_symbols)} symbols [{start_date} ~ {end_date}]...")
    t0 = time.time()

    refs = {}
    loaded = 0
    for i, sym in enumerate(all_symbols):
        try:
            df = source_lib.read(sym, date_range=(start_date, end_date)).data
            refs[sym] = ray.put(df)
            loaded += 1
        except Exception:
            pass
        if (i + 1) % 500 == 0:
            logger.info(f"  ...{i+1}/{len(all_symbols)} ({time.time()-t0:.0f}s)")

    elapsed = time.time() - t0
    logger.info(f"Preload done: {loaded} symbols in {elapsed:.0f}s")

    # Store refs in a named actor
    @ray.remote
    class _PreloadStore:
        def __init__(self, refs, symbols):
            self.refs = refs
            self.symbols = symbols
        def get_refs(self):
            return self.refs
        def get_symbols(self):
            return self.symbols

    try:
        ray.get_actor(RAY_PRELOAD_ACTOR)
        logger.info(f"Replacing existing preload actor...")
        ray.kill(ray.get_actor(RAY_PRELOAD_ACTOR))
    except ValueError:
        pass

    store = _PreloadStore.options(
        name=RAY_PRELOAD_ACTOR, lifetime="detached", num_cpus=0,
    ).remote(refs, list(refs.keys()))
    logger.info(f"Preload actor '{RAY_PRELOAD_ACTOR}' ready with {loaded} symbols")
    return loaded


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_fields(field_data, output_dir, only_fields=None):
    """Assemble per-field DataFrames and export as pkl."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exported = []
    for field, symbol_map in field_data.items():
        if only_fields and field not in only_fields:
            continue
        field_df = pd.DataFrame(symbol_map)
        field_df = field_df.reindex(sorted(field_df.columns), axis=1)
        field_df = field_df.sort_index()
        if field_df.index.tz is None:
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

def build_parser():
    parser = argparse.ArgumentParser(
        description="Compute raw-data factors locally and export as pkl (no registry write)"
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--formula-file", help="Path to a registration script with build_definition()")
    source.add_argument("--bundle", help="Name of a registered bundle in the registry")

    parser.add_argument("--output-dir", "-o", default=".claude-output/analysis",
                        help="Output directory for pkl files")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--only-fields", nargs="+", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 100 random symbols")
    parser.add_argument("--fast", action="store_true",
                        help="Ray parallel mode: ~5x faster for full compute")
    parser.add_argument("--num-workers", type=int, default=32,
                        help="Number of Ray workers for --fast mode")
    parser.add_argument("--preload", action="store_true",
                        help="Preload 1m data into Ray (run once, then use --use-preload)")
    parser.add_argument("--use-preload", action="store_true",
                        help="Use preloaded data from Ray actor (requires prior --preload)")
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

    # Handle --preload
    if args.preload:
        start = args.start_date or "2020-01-01"
        run_preload(start_date=start, end_date="2024-12-31")
        return 0

    # Need formula-file or bundle
    if not args.formula_file and not args.bundle:
        parser.error("--formula-file or --bundle is required (unless --preload)")

    # Load definition
    if args.formula_file:
        definition = load_definition_from_file(args.formula_file)
        logger.info(f"Loaded definition from file: {args.formula_file}")
    else:
        definition = load_definition_from_registry(args.bundle)
        logger.info(f"Loaded definition from registry: {args.bundle}")

    logger.info(f"  Name: {definition.name}")
    logger.info(f"  Inputs: {definition.input_names}")
    logger.info(f"  Outputs ({len(definition.output_names)}): {definition.output_names}")
    logger.info(f"  Time filter: {definition.params.input_time_filter}")

    # Resolve symbols
    symbols = args.symbols
    if args.quick and not symbols:
        all_syms = _load_symbols()
        if not all_syms:
            conn = Arctic(ARCTIC_URL)
            lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
            all_syms = sorted(lib.list_symbols())
        np.random.seed(42)
        symbols = list(np.random.choice(all_syms, size=min(100, len(all_syms)), replace=False))
        logger.info(f"Quick mode: {len(symbols)} random symbols")

    # Compute
    if args.fast:
        if not symbols:
            all_syms = _load_symbols()
            if not all_syms:
                conn = Arctic(ARCTIC_URL)
                lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
                all_syms = sorted(lib.list_symbols())
            symbols = all_syms
        logger.info(f"Fast mode (Ray): {len(symbols)} symbols, {args.num_workers} workers")
        start = args.start_date or "2020-01-01"
        field_data = compute_fast(definition, symbols, start_date=start,
                                  end_date="2024-12-31", num_workers=args.num_workers)
    else:
        conn = Arctic(ARCTIC_URL)
        source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
        if not symbols:
            symbols = _load_symbols()
            if not symbols:
                symbols = sorted(source_lib.list_symbols())
        logger.info(f"Serial mode: {len(symbols)} symbols")
        start_time = pd.Timestamp(args.start_date) if args.start_date else None
        field_data = compute_serial(definition, symbols, source_lib, start_time)

    # Export
    exported = export_fields(field_data, args.output_dir, args.only_fields)

    # Summary
    print(f"\n{'='*60}")
    print(f"Exported {len(exported)} fields to {args.output_dir}")
    mode = "fast (Ray)" if args.fast else ("quick" if args.quick else "serial")
    print(f"Mode: {mode}")
    print(f"{'='*60}")
    for field, shape, path in exported:
        print(f"  {field}: {shape[0]} dates x {shape[1]} symbols -> {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
