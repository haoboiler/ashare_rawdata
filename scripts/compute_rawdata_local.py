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
import gc
import importlib.util
import json
import logging
import math
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import types

import numpy as np
import pandas as pd
from utils.rawdata_eval import (
    DEFAULT_EVAL_BENCHMARK_INDEX,
    DEFAULT_EVAL_COMMISSION_RATE,
    DEFAULT_EVAL_END,
    DEFAULT_EVAL_EXECUTION_PRICE_FIELD,
    DEFAULT_EVAL_MODE,
    DEFAULT_EVAL_POST_PROCESS_METHOD,
    DEFAULT_EVAL_START,
    DEFAULT_EVAL_STAMP_TAX_RATE,
    build_rawdata_export_metadata,
    infer_rawdata_t_plus_n,
    write_rawdata_sidecar,
)
from utils.preload_ray import (
    PRELOAD_RAY_ACTOR,
    PRELOAD_RAY_NAMESPACE,
    repair_preload_bridge_lockfiles,
    resolve_preload_ray_address,
)

ROOT = Path("/home/gkh/ashare")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

from arcticdb import Arctic
from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_SOURCE_LIBRARY, SYMBOL_CACHE_FILE
from ashare_hf_variable.models import AShareRawDataDefinition, CompletenessPolicy, PriceBasis
from ashare_hf_variable.registry import compile_formula, list_definitions, validate_definition

logger = logging.getLogger(__name__)

_PRICE_FIELDS = {"open", "high", "low", "close"}
BARS_PER_DAY = 240
_BASIC6_FIELDS = ["close", "open", "high", "low", "volume", "amount"]
_FULL10_FIELDS = _BASIC6_FIELDS + [
    "origin_close", "origin_open", "origin_high", "origin_low",
]
_ALL_FIELDS = list(_FULL10_FIELDS)
FIELD_PRESETS = {
    "basic6": list(_BASIC6_FIELDS),
    "full10": list(_FULL10_FIELDS),
}
DEFAULT_FIELD_PRESET = "full10"
DEFAULT_SCREEN_FIELD_PRESET = "basic6"
DEFAULT_SYMBOL_SOURCE = "cache"
RAY_PRELOAD_ACTOR = "ashare_rawdata_preload"
EVALUATE_PY = Path("/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py")
DEFAULT_EVAL_POSITION_METHOD = "factor_weighted"
DEFAULT_EVAL_REPORT_DIR = ".claude-output/reports/quick_eval"
PRELOAD_STATE_PATH = PROJECT_ROOT / ".claude-tmp/preload/ashare_rawdata_preload_state.json"
PRELOAD_STATE_PATH = Path(
    os.environ.get(
        "ASHARE_RAWDATA_PRELOAD_STATE_PATH",
        str(PRELOAD_STATE_PATH),
    )
).expanduser()
PRELOAD_HEALTH_TIMEOUT_S = 5
PRELOAD_REBUILD_GRACE_S = 20
RESEARCHER_MODE_ENV = "ASHARE_RAWDATA_RESEARCHER_MODE"

_EVALUATE_MODULE = None
_EVALUATE_MODULE_LOCK = threading.Lock()
_EVALUATE_MODULE_ATTRS = (
    "ensure_casimir",
    "parse_post_process_params",
    "compute_alpha_ic",
    "_empty_ic_stats",
    "_apply_normalizer",
)


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


def _load_symbol_universe(source_lib=None, symbol_source: str = DEFAULT_SYMBOL_SOURCE) -> List[str]:
    if symbol_source == "cache":
        symbols = _load_symbols()
        if symbols:
            return list(symbols)
    if source_lib is None:
        conn = Arctic(ARCTIC_URL)
        source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
    return sorted(source_lib.list_symbols())


def _get_field_preset(field_preset: str) -> List[str]:
    try:
        return list(FIELD_PRESETS[field_preset])
    except KeyError as exc:
        raise ValueError(
            f"Unknown field preset '{field_preset}'. Choices: {sorted(FIELD_PRESETS)}"
        ) from exc


def _resolve_definition_inputs(definition, available_fields: List[str], *, context: str) -> List[str]:
    resolved_inputs = [_resolve_input_name(n, definition.price_basis) for n in definition.input_names]
    missing = [field for field in resolved_inputs if field not in available_fields]
    if missing:
        raise RuntimeError(
            f"{context} is missing fields required by definition '{definition.name}': {missing}. "
            f"Available fields: {available_fields}. Rebuild preload / fast compute with a compatible field preset."
        )
    return resolved_inputs


def _resolve_trading_days(source_lib, symbols: List[str], ts_start: pd.Timestamp, ts_end: pd.Timestamp) -> List:
    for symbol in symbols:
        try:
            df = source_lib.read(symbol, date_range=(ts_start, ts_end)).data
        except Exception:
            continue
        if df is None or df.empty:
            continue
        days = sorted(df.index.normalize().unique())
        return [d.date() for d in days]
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


def _build_symbol_3d_array(
    df: pd.DataFrame,
    trading_days: List,
    all_fields: List[str],
) -> np.ndarray:
    """Convert one symbol's 1m DataFrame to (n_days, 240, n_fields) float64 array."""
    n_days = len(trading_days)
    n_fields = len(all_fields)
    arr = np.full((n_days, BARS_PER_DAY, n_fields), np.nan, dtype=np.float64)
    if df is None or df.empty:
        return arr

    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)

    day_to_idx = {d: i for i, d in enumerate(trading_days)}
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

    return arr


def _ensure_bookdisco_ml_mock() -> None:
    if "bookdisco_ml" in sys.modules:
        return
    mock_module = types.ModuleType("bookdisco_ml")
    mock_module.AutoML = type("AutoML", (), {})
    sys.modules["bookdisco_ml"] = mock_module


def _load_evaluate_module():
    global _EVALUATE_MODULE

    def _module_ready(module) -> bool:
        return module is not None and all(
            hasattr(module, attr) for attr in _EVALUATE_MODULE_ATTRS
        )

    if _module_ready(_EVALUATE_MODULE):
        return _EVALUATE_MODULE
    if not EVALUATE_PY.exists():
        raise FileNotFoundError(f"evaluate.py not found: {EVALUATE_PY}")

    module_name = "ashare_alpha_backtest_evaluate"
    with _EVALUATE_MODULE_LOCK:
        if _module_ready(_EVALUATE_MODULE):
            return _EVALUATE_MODULE

        existing = sys.modules.get(module_name)
        if existing is not None and not _module_ready(existing):
            logger.warning(
                "Detected incomplete evaluate.py module in sys.modules; reloading it"
            )
            sys.modules.pop(module_name, None)
            existing = None

        if _module_ready(existing):
            _EVALUATE_MODULE = existing
            return existing

        _ensure_bookdisco_ml_mock()
        spec = importlib.util.spec_from_file_location(module_name, str(EVALUATE_PY))
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load evaluate.py from {EVALUATE_PY}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise

        if not _module_ready(module):
            sys.modules.pop(module_name, None)
            raise ImportError(
                f"Loaded evaluate.py from {EVALUATE_PY} but required helpers are missing"
            )

        _EVALUATE_MODULE = module
        return module


def _assemble_field_df(symbol_map: Dict[str, pd.Series]) -> pd.DataFrame:
    field_df = pd.DataFrame(symbol_map)
    field_df = field_df.reindex(sorted(field_df.columns), axis=1)
    field_df = field_df.sort_index()
    if field_df.index.tz is None:
        field_df.index = field_df.index.tz_localize("Asia/Shanghai")
    field_df.index.name = "trade_date"
    return field_df


def _to_builtin(value):
    if isinstance(value, dict):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    return value


def _write_preload_state(payload: Dict[str, object]) -> None:
    PRELOAD_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = dict(payload)
    state["updated_at"] = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
    PRELOAD_STATE_PATH.write_text(
        json.dumps(_to_builtin(state), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _fetch_preload_info(store, timeout_s: int = PRELOAD_HEALTH_TIMEOUT_S) -> Dict[str, object]:
    import ray

    get_info = getattr(store, "get_preload_info", None)
    if get_info is not None:
        info = ray.get(get_info.remote(), timeout=timeout_s)
        info.setdefault("legacy", False)
        return info

    stats = ray.get(store.get_stats.remote(), timeout=timeout_s)
    return {
        "status": "ready",
        "start_date": None,
        "end_date": None,
        "stats": stats,
        "legacy": True,
        "quick_eval_contexts": None,
    }


def _wait_for_preload_ready(
    store,
    *,
    requested_start: str,
    requested_end: str,
    timeout_s: int = 900,
) -> Dict[str, object]:
    deadline = time.time() + timeout_s
    last_exc = None
    while time.time() < deadline:
        try:
            info = _fetch_preload_info(store)
        except Exception as exc:  # pragma: no cover - depends on Ray runtime
            last_exc = exc
            time.sleep(5)
            continue

        same_range = (
            info.get("start_date") == requested_start and
            info.get("end_date") == requested_end
        )
        if info.get("status") == "ready" and same_range:
            return info
        if info.get("status") == "error":
            raise RuntimeError(
                f"Preload actor entered error state: {info.get('last_error')}"
            )
        time.sleep(5)

    if last_exc is not None:
        raise RuntimeError(
            f"Timed out waiting for preload actor to become ready: {last_exc}"
        ) from last_exc
    raise RuntimeError("Timed out waiting for preload actor to become ready")


def _compute_coverage_ratio(field_df: pd.DataFrame) -> float:
    total = field_df.shape[0] * field_df.shape[1]
    if total == 0:
        return 0.0
    return float(field_df.notna().sum().sum() / total)


def _build_eval_config(args) -> Dict[str, object]:
    return {
        "start": args.eval_start,
        "end": args.eval_end,
        "period": "daily",
        "window": args.eval_window,
        "mode": args.eval_mode,
        "position_method": args.eval_position_method,
        "num_hold": args.eval_num_hold,
        "execution_price_field": args.eval_execution_price_field,
        "benchmark_index": args.eval_benchmark_index,
        "index_code": args.eval_index_code,
        "post_process_method": args.eval_post_process_method,
        "post_process_params": args.eval_post_process_params,
        "t_plus_n": args.eval_t_plus_n,
        "commission_rate": args.eval_commission_rate,
        "stamp_tax_rate": args.eval_stamp_tax_rate,
        "allow_st": args.eval_allow_st,
        "include_price_limit": args.eval_include_price_limit,
    }


def _build_eval_args_namespace(eval_config: Dict[str, object]):
    return argparse.Namespace(
        start=eval_config["start"],
        end=eval_config["end"],
        period=eval_config["period"],
        window=eval_config["window"],
        mode=eval_config["mode"],
        position_method=eval_config["position_method"],
        num_hold=eval_config["num_hold"],
        execution_price_field=eval_config["execution_price_field"],
        benchmark_index=eval_config["benchmark_index"],
        index_code=eval_config["index_code"],
        post_process_method=eval_config["post_process_method"],
        post_process_params=eval_config["post_process_params"],
        t_plus_n=eval_config["t_plus_n"],
        commission_rate=eval_config["commission_rate"],
        stamp_tax_rate=eval_config["stamp_tax_rate"],
        allow_st=eval_config["allow_st"],
        include_price_limit=eval_config["include_price_limit"],
    )


def _normalize_post_process_method(pp_method: Optional[str]) -> Optional[str]:
    if pp_method is None:
        return None
    if pp_method.lower() == "none":
        return None
    return pp_method


def _definition_payload(definition: AShareRawDataDefinition) -> Dict[str, object]:
    return {
        "name": definition.name,
        "data_available_at": definition.data_available_at,
    }


def _infer_rawdata_t_plus_n(definition_payload: Dict[str, object], eval_args) -> Optional[int]:
    return infer_rawdata_t_plus_n(
        definition_payload,
        eval_args.execution_price_field or DEFAULT_EVAL_EXECUTION_PRICE_FIELD,
        requested_t_plus_n=eval_args.t_plus_n,
        logger=logger,
    )


def _promote_benchmark_metrics(stats: Dict[str, object], result: pd.DataFrame, eval_args) -> None:
    if eval_args.benchmark_index == "none":
        return

    from casimir.core.backtest.ashare_common import aggregate_result_by_actual_days

    daily = aggregate_result_by_actual_days(result)
    stats["sharpe_abs_net"] = stats.get("sharpe_net", 0)
    stats["yearly_yield_abs"] = stats.get("yearly_yield", 0)
    stats["mdd_abs_net"] = stats.get("mdd_net", 0)

    if eval_args.mode == "long_short" and "long_excess_ret_net" in daily.columns:
        day_long_excess = daily["long_excess_ret_net"]
        if len(day_long_excess) > 0 and day_long_excess.std() > 0:
            ann_factor = np.sqrt(252)
            stats["sharpe_net"] = float(day_long_excess.mean() / day_long_excess.std() * ann_factor)
            stats["yearly_yield"] = float(day_long_excess.mean() * 252)
            try:
                excess_cum = (1 + day_long_excess).cumprod()
                stats["mdd_net"] = float((excess_cum / excess_cum.cummax() - 1).min())
            except Exception:
                pass
        stats["sharpe_ls_abs"] = stats.get("sharpe_abs_net")
    elif "sharpe_excess_net" in stats:
        stats["sharpe_net"] = stats["sharpe_excess_net"]
        stats["yearly_yield"] = stats.get(
            "yearly_excess_net",
            stats.get("yearly_excess", stats.get("yearly_yield", 0)),
        )
        try:
            if "excess_ret_net" in daily.columns:
                excess_cum = (1 + daily["excess_ret_net"]).cumprod()
                stats["mdd_net"] = float((excess_cum / excess_cum.cummax() - 1).min())
        except Exception:
            pass


def _build_quick_eval_context(eval_config: Dict[str, object], sample_df: pd.DataFrame):
    eval_module = _load_evaluate_module()
    eval_module.ensure_casimir()
    from casimir.core.backtest.ashare_examine import prepare_ashare_backtest_context

    benchmark_index = eval_config["benchmark_index"]
    if benchmark_index == "none":
        benchmark_index = None

    return prepare_ashare_backtest_context(
        alpha_value=sample_df,
        period=eval_config["period"],
        index_code=eval_config["index_code"],
        exclude_st=not eval_config["allow_st"],
        exclude_price_limit=not eval_config["include_price_limit"],
        custom_symbols=None,
        start_time=eval_config["start"],
        end_time=eval_config["end"],
        benchmark_index=benchmark_index,
        execution_price_field=eval_config["execution_price_field"],
    )


def _run_quick_eval_on_frames(
    field_frames: Dict[str, pd.DataFrame],
    definition_payload: Dict[str, object],
    eval_config: Dict[str, object],
    backtest_context=None,
) -> Dict[str, Dict[str, object]]:
    if not field_frames:
        return {}

    eval_module = _load_evaluate_module()
    eval_module.ensure_casimir()
    from casimir.core.backtest.ashare_examine import examine_value_ashare

    eval_args = _build_eval_args_namespace(eval_config)
    post_process_method = _normalize_post_process_method(eval_args.post_process_method)
    post_process_params = eval_module.parse_post_process_params(eval_args.post_process_params)
    effective_t_plus_n = _infer_rawdata_t_plus_n(definition_payload, eval_args)

    if backtest_context is None:
        sample_df = next(iter(field_frames.values()))
        backtest_context = _build_quick_eval_context(eval_config, sample_df)

    common_kwargs = dict(
        window=eval_args.window,
        mode=eval_args.mode,
        num_hold=eval_args.num_hold,
        index_code=eval_args.index_code,
        exclude_st=not eval_args.allow_st,
        exclude_price_limit=not eval_args.include_price_limit,
        custom_symbols=None,
        start_time=eval_args.start,
        end_time=eval_args.end,
        plot=False,
        period=eval_args.period,
        benchmark_index=None if eval_args.benchmark_index == "none" else eval_args.benchmark_index,
        print_stats=False,
        execution_price_field=eval_args.execution_price_field,
        t_plus_n=effective_t_plus_n,
        commission_rate=eval_args.commission_rate,
        stamp_tax_rate=eval_args.stamp_tax_rate,
        position_method=eval_args.position_method,
    )
    stats_keys = [
        "sharpe_net",
        "sharpe_abs_net",
        "sharpe_ls_abs",
        "sharpe_long_excess_net",
        "yearly_yield",
        "yearly_yield_abs",
        "yearly_yield_long_excess_net",
        "mdd_net",
        "mdd_abs_net",
        "mdd_long_excess_net",
        "ic_ls_mean",
        "ir_ls",
        "ic_lo_mean",
        "ir_lo",
        "ic_ls_positive_pct",
        "ic_lo_positive_pct",
        "day_tvr",
        "win_rate",
        "margin_net",
        "num_days",
    ]

    quick_results = {}
    for field_name, factor_values in field_frames.items():
        factor_values = factor_values.sort_index()
        coverage_ratio = _compute_coverage_ratio(factor_values)
        ic_stats = eval_module._empty_ic_stats()
        long_mask = None
        try:
            normalized_values = eval_module._apply_normalizer(
                factor_values,
                backtest_context.close,
                post_process_method,
                post_process_params,
            )
            long_mask = normalized_values > 0
        except Exception as exc:
            logger.warning("Quick-eval normalizer failed for %s: %s", field_name, exc)

        try:
            ic_stats, _, _ = eval_module.compute_alpha_ic(
                factor_values,
                backtest_context.close,
                long_mask=long_mask,
            )
        except Exception as exc:
            logger.warning("Quick-eval IC failed for %s: %s", field_name, exc)

        try:
            result, stats = examine_value_ashare(
                alpha_value=factor_values,
                post_process_method=post_process_method,
                post_process_params=post_process_params if post_process_method is not None else None,
                backtest_context=backtest_context,
                **common_kwargs,
            )
            stats.update(ic_stats)
            _promote_benchmark_metrics(stats, result, eval_args)
            quick_results[field_name] = {
                "field": field_name,
                "coverage_ratio": round(coverage_ratio, 6),
                "shape": [int(factor_values.shape[0]), int(factor_values.shape[1])],
                "t_plus_n": effective_t_plus_n,
                "post_process_method": post_process_method,
                "stats": {
                    key: _to_builtin(stats.get(key))
                    for key in stats_keys
                    if key in stats
                },
            }
        except Exception as exc:
            quick_results[field_name] = {
                "field": field_name,
                "coverage_ratio": round(coverage_ratio, 6),
                "shape": [int(factor_values.shape[0]), int(factor_values.shape[1])],
                "t_plus_n": effective_t_plus_n,
                "post_process_method": post_process_method,
                "error": str(exc),
            }

    return quick_results


def run_quick_eval(
    field_data: Dict[str, Dict[str, pd.Series]],
    definition: AShareRawDataDefinition,
    args,
) -> Optional[Tuple[Path, Dict[str, object]]]:
    field_frames = {
        field: _assemble_field_df(symbol_map)
        for field, symbol_map in field_data.items()
        if symbol_map
    }
    if not field_frames:
        logger.warning("Quick-eval skipped: no non-empty fields to evaluate")
        return None

    eval_config = _build_eval_config(args)
    definition_payload = _definition_payload(definition)
    cache_info = {"mode": "local"}
    if args.use_preload:
        import ray

        _ray_init_preload()
        store = ray.get_actor(RAY_PRELOAD_ACTOR, namespace=PRELOAD_RAY_NAMESPACE)
        try:
            payload = ray.get(store.evaluate_fields.remote(field_frames, definition_payload, eval_config))
            quick_results = payload["results"]
            cache_info = payload.get("cache", {"mode": "preload_actor"})
        except Exception as exc:
            logger.warning(
                "Preload actor quick-eval failed; falling back to local quick-eval in caller process: %s",
                exc,
            )
            quick_results = _run_quick_eval_on_frames(field_frames, definition_payload, eval_config)
            cache_info = {
                "mode": "local_fallback",
                "fallback_from": "preload_actor",
                "fallback_error": str(exc)[:500],
            }
    else:
        quick_results = _run_quick_eval_on_frames(field_frames, definition_payload, eval_config)

    report = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "definition_name": definition.name,
        "eval_settings": eval_config,
        "cache": cache_info,
        "results": quick_results,
    }
    report_dir = Path(args.eval_report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{definition.name}_{time.strftime('%Y%m%d-%H%M%S')}.json"
    report_path.write_text(
        json.dumps(_to_builtin(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Quick-eval report saved to %s", report_path)
    return report_path, report


def print_quick_eval_summary(report_path: Path, report: Dict[str, object]) -> None:
    print("\nQuick Eval")
    print(f"  Report: {report_path}")
    results = report.get("results", {})
    for field_name in sorted(results):
        item = results[field_name]
        if "error" in item:
            print(f"  {field_name}: ERROR {item['error']}")
            continue
        stats = item.get("stats", {})
        print(
            f"  {field_name}: cov={item.get('coverage_ratio', 0):.1%}, "
            f"sharpe_abs={stats.get('sharpe_abs_net')}, "
            f"sharpe_long_excess={stats.get('sharpe_long_excess_net')}, "
            f"ir_ls={stats.get('ir_ls')}, "
            f"ic_ls={stats.get('ic_ls_mean')}"
        )


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


def _make_ray_preload_task():
    """Create Ray remote function for parallel preload batches."""
    import ray

    @ray.remote
    def _ray_preload_batch(
        symbols,
        lib_name,
        arctic_url,
        all_fields,
        start_date,
        end_date,
        trading_days,
    ):
        from arcticdb import Arctic as _Arctic

        conn = _Arctic(arctic_url)
        lib = conn.get_library(lib_name, create_if_missing=False)
        ts_start = pd.Timestamp(start_date)
        ts_end = pd.Timestamp(end_date)

        refs = {}
        loaded_symbols = []
        failed = 0
        total_bytes = 0
        last_failure = None

        for symbol in symbols:
            try:
                df = lib.read(symbol, date_range=(ts_start, ts_end)).data
                if df.empty:
                    continue
                arr = _build_symbol_3d_array(df, trading_days, all_fields)
                refs[symbol] = ray.put(arr)
                loaded_symbols.append(symbol)
                total_bytes += arr.nbytes
                last_failure = None
            except Exception as exc:
                failed += 1
                last_failure = {
                    "symbol": symbol,
                    "error": str(exc)[:300],
                }

        return {
            "refs": refs,
            "loaded_symbols": loaded_symbols,
            "processed": len(symbols),
            "loaded": len(loaded_symbols),
            "failed": failed,
            "total_bytes": total_bytes,
            "last_symbol": symbols[-1] if symbols else None,
            "last_failure": last_failure,
        }

    return _ray_preload_batch


def compute_fast(
    definition,
    symbols,
    start_date="2020-01-01",
    end_date="2023-12-31",
    num_workers=32,
    field_preset: str = DEFAULT_FIELD_PRESET,
):
    """Ray parallel computation."""
    import ray
    _ray_init_general()

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
    all_fields = _get_field_preset(field_preset)
    field_to_idx = {f: i for i, f in enumerate(all_fields)}
    resolved_inputs = _resolve_definition_inputs(
        definition,
        all_fields,
        context=f"field preset '{field_preset}'",
    )
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

GENERAL_RAY_NAMESPACE = "ashare_rawdata_local"


def _current_ray_gcs_address(ray) -> Optional[str]:
    if not ray.is_initialized():
        return None
    try:
        return ray.get_runtime_context().gcs_address
    except Exception:
        try:
            worker = ray._private.worker.global_worker
            node = getattr(worker, "node", None)
            if node is not None:
                return node.address_info.get("gcs_address")
        except Exception:
            return None
    return None


def _ray_init(address: str, namespace: str):
    """Initialize Ray, forcing an explicit cluster choice."""
    import ray

    if ray.is_initialized():
        current_address = _current_ray_gcs_address(ray)
        if current_address == address:
            return
        ray.shutdown()

    ray.init(address=address, ignore_reinit_error=True, namespace=namespace)


def _researcher_mode_enabled() -> bool:
    value = os.environ.get(RESEARCHER_MODE_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _prepare_shared_preload_client_runtime() -> None:
    # Keep lock files group-writable when gkh researchers attach to gkh_ray-owned preload.
    try:
        os.umask(0o0002)
    except Exception:
        pass
    repair_preload_bridge_lockfiles()


def _ray_init_general():
    addr = os.environ.get("RAY_ADDRESS")
    if addr:
        _ray_init(addr, namespace=GENERAL_RAY_NAMESPACE)
        return
    _ray_init("local", namespace=GENERAL_RAY_NAMESPACE)


def _ray_init_preload():
    _prepare_shared_preload_client_runtime()
    try:
        address = resolve_preload_ray_address(require_exists=True)
    except Exception as exc:
        raise RuntimeError(
            "Managed preload Ray is not configured. "
            "Start it with `bash orchestration/start_rawdata_preload_ray.sh`."
        ) from exc

    try:
        _ray_init(address, namespace=PRELOAD_RAY_NAMESPACE)
        # ray.init() itself may create bridge lock files with restrictive perms.
        # Repair them again after connect so gkh client + gkh_ray workers can
        # share the same runtime session without PermissionError on *.lock.
        repair_preload_bridge_lockfiles()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to connect to managed preload Ray at {address}. "
            "Check `bash orchestration/status_rawdata_preload_ray.sh` "
            "or restart it with `bash orchestration/start_rawdata_preload_ray.sh`."
        ) from exc


def run_preload(
    start_date="2020-01-01",
    end_date="2023-12-31",
    force_rebuild=False,
    field_preset: str = DEFAULT_FIELD_PRESET,
    symbol_source: str = DEFAULT_SYMBOL_SOURCE,
    load_workers: int = 32,
):
    """Preload 1m data into Ray actor. Data lives inside the actor, survives caller exit."""
    import ray
    _ray_init_preload()

    selected_fields = _get_field_preset(field_preset)
    requested_range = {"start_date": start_date, "end_date": end_date}

    # Define actor class that loads data internally
    @ray.remote
    class _PreloadStore:
        def __init__(self):
            self.kline_refs = {}
            self.symbols = []
            self.trading_days = []
            self.fields = list(_ALL_FIELDS)
            self._stats = {}
            self.quick_eval_contexts = {}
            self.status = "empty"
            self.start_date = None
            self.end_date = None
            self.symbol_source = DEFAULT_SYMBOL_SOURCE
            self.loaded_at = None
            self.load_started_at = None
            self.last_error = None

        def _state_payload(self):
            return {
                "status": self.status,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "loaded_at": self.loaded_at,
                "load_started_at": self.load_started_at,
                "last_error": self.last_error,
                "fields": list(self.fields),
                "symbol_source": self.symbol_source,
                "stats": self._stats,
                "quick_eval_contexts": len(self.quick_eval_contexts),
                "actor_name": RAY_PRELOAD_ACTOR,
                "namespace": PRELOAD_RAY_NAMESPACE,
            }

        def _write_state(self):
            _write_preload_state(self._state_payload())

        def _clear_refs(self):
            refs = list(self.kline_refs.values())
            if refs:
                try:
                    ray.internal.free(refs, local_only=False)
                except Exception:
                    pass
            self.kline_refs = {}
            self.symbols = []
            self.trading_days = []
            self._stats = {}
            self.quick_eval_contexts = {}
            gc.collect()

        def _build_loading_stats(
            self,
            *,
            processed,
            total,
            loaded,
            failed,
            total_bytes,
            last_symbol=None,
            last_failure=None,
        ):
            elapsed_s = None
            if self.load_started_at:
                try:
                    elapsed_s = round(
                        (
                            pd.Timestamp.now(tz="Asia/Shanghai")
                            - pd.Timestamp(self.load_started_at)
                        ).total_seconds(),
                        1,
                    )
                except Exception:
                    elapsed_s = None
            progress_pct = round((processed / total) * 100, 2) if total else 0.0
            stats = {
                "processed": processed,
                "loaded": loaded,
                "failed": failed,
                "total": total,
                "progress_pct": progress_pct,
                "n_days": len(self.trading_days),
                "n_fields": len(self.fields),
                "total_gb": round(total_bytes / 1e9, 2),
                "array_shape": f"({len(self.trading_days)}, {BARS_PER_DAY}, {len(self.fields)})",
                "elapsed_s": elapsed_s,
                "last_symbol": last_symbol,
            }
            if last_failure is not None:
                stats["last_failure"] = last_failure
            return stats

        def _checkpoint_loading_progress(
            self,
            *,
            processed,
            total,
            loaded,
            failed,
            total_bytes,
            last_symbol=None,
            last_failure=None,
        ):
            self._stats = self._build_loading_stats(
                processed=processed,
                total=total,
                loaded=loaded,
                failed=failed,
                total_bytes=total_bytes,
                last_symbol=last_symbol,
                last_failure=last_failure,
            )
            self._write_state()

        def get_preload_info(self):
            return self._state_payload()

        def load(
            self,
            arctic_url,
            lib_name,
            start_date,
            end_date,
            fields,
            symbol_source,
            load_workers,
            force=False,
        ):
            requested_fields = list(fields)
            same_config = (
                self.start_date == start_date
                and self.end_date == end_date
                and list(self.fields) == requested_fields
                and self.symbol_source == symbol_source
            )
            if self.status == "ready" and same_config and self._stats.get("loaded", 0) > 0 and not force:
                return self._state_payload()

            self.status = "loading"
            self.start_date = start_date
            self.end_date = end_date
            self.fields = requested_fields
            self.symbol_source = symbol_source
            self.last_error = None
            self.loaded_at = None
            self.load_started_at = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
            self._clear_refs()
            self._write_state()

            try:
                from arcticdb import Arctic as _Arc

                conn = _Arc(arctic_url)
                lib = conn.get_library(lib_name, create_if_missing=False)
                all_syms = _load_symbol_universe(lib, symbol_source=symbol_source)
                ts_start = pd.Timestamp(start_date)
                ts_end = pd.Timestamp(end_date)
                self.trading_days = _resolve_trading_days(lib, all_syms, ts_start, ts_end)
                loaded = 0
                failed = 0
                total_bytes = 0
                last_failure = None
                self._checkpoint_loading_progress(
                    processed=0,
                    total=len(all_syms),
                    loaded=loaded,
                    failed=failed,
                    total_bytes=total_bytes,
                )
                if not self.trading_days or not all_syms:
                    self._stats = self._build_loading_stats(
                        processed=len(all_syms),
                        total=len(all_syms),
                        loaded=0,
                        failed=0,
                        total_bytes=0,
                        last_symbol=None,
                        last_failure=None,
                    )
                    self.status = "ready"
                    self.loaded_at = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
                    self._write_state()
                    return self._state_payload()

                preload_task = _make_ray_preload_task()
                worker_count = max(1, min(int(load_workers or 1), len(all_syms)))
                batch_size = max(1, math.ceil(len(all_syms) / worker_count))
                pending = []
                for offset in range(0, len(all_syms), batch_size):
                    batch = all_syms[offset:offset + batch_size]
                    pending.append(
                        preload_task.remote(
                            batch,
                            lib_name,
                            arctic_url,
                            self.fields,
                            start_date,
                            end_date,
                            self.trading_days,
                        )
                    )

                processed = 0
                while pending:
                    ready_refs, pending = ray.wait(pending, num_returns=1)
                    payload = ray.get(ready_refs[0])
                    processed += payload["processed"]
                    loaded += payload["loaded"]
                    failed += payload["failed"]
                    total_bytes += payload["total_bytes"]
                    self.kline_refs.update(payload["refs"])
                    self.symbols.extend(payload["loaded_symbols"])
                    last_failure = payload.get("last_failure")
                    self._checkpoint_loading_progress(
                        processed=processed,
                        total=len(all_syms),
                        loaded=loaded,
                        failed=failed,
                        total_bytes=total_bytes,
                        last_symbol=payload.get("last_symbol"),
                        last_failure=last_failure,
                    )
                    if processed % 500 == 0 or processed == len(all_syms):
                        print(
                            f"  preload progress: processed={processed}/{len(all_syms)} "
                            f"loaded={loaded} failed={failed} total_gb={total_bytes / 1e9:.2f}",
                            flush=True,
                        )

                self._stats = self._build_loading_stats(
                    processed=len(all_syms),
                    total=len(all_syms),
                    loaded=loaded,
                    failed=failed,
                    total_bytes=total_bytes,
                    last_symbol=all_syms[-1] if all_syms else None,
                    last_failure=last_failure,
                )
                self.status = "ready"
                self.loaded_at = pd.Timestamp.now(tz="Asia/Shanghai").isoformat()
                self._write_state()
                return self._state_payload()
            except Exception as exc:
                self.status = "error"
                self.last_error = str(exc)
                self._write_state()
                raise

        def get_symbol_refs_batch(self, symbols):
            return {s: self.kline_refs[s] for s in symbols if s in self.kline_refs}

        def get_symbols(self):
            return self.symbols

        def get_trading_days(self):
            return self.trading_days

        def get_fields(self):
            return self.fields

        def get_metadata(self):
            return {
                "symbols": self.symbols,
                "trading_days": self.trading_days,
                "fields": self.fields,
                "stats": self._stats,
            }

        def get_stats(self):
            return self._stats

        def _make_quick_eval_cache_key(self, eval_config):
            cache_config = {
                "start": eval_config["start"],
                "end": eval_config["end"],
                "period": eval_config["period"],
                "index_code": eval_config["index_code"],
                "allow_st": eval_config["allow_st"],
                "include_price_limit": eval_config["include_price_limit"],
                "benchmark_index": eval_config["benchmark_index"],
                "execution_price_field": eval_config["execution_price_field"],
            }
            return json.dumps(cache_config, sort_keys=True)

        def _build_quick_eval_context(self, eval_config):
            date_index = pd.DatetimeIndex(
                [pd.Timestamp(d) for d in self.trading_days],
                name="trade_date",
            )
            dummy_alpha = pd.DataFrame(0.0, index=date_index, columns=sorted(self.symbols))
            return _build_quick_eval_context(eval_config, dummy_alpha)

        def ensure_quick_eval_context(self, eval_config):
            cache_key = self._make_quick_eval_cache_key(eval_config)
            if cache_key in self.quick_eval_contexts:
                ctx = self.quick_eval_contexts[cache_key]
                return {
                    "mode": "preload_actor",
                    "cache_key": cache_key,
                    "cache_hit": True,
                    "num_dates": int(len(ctx.close.index)),
                    "num_symbols": int(len(ctx.close.columns)),
                }

            ctx = self._build_quick_eval_context(eval_config)
            self.quick_eval_contexts[cache_key] = ctx
            return {
                "mode": "preload_actor",
                "cache_key": cache_key,
                "cache_hit": False,
                "num_dates": int(len(ctx.close.index)),
                "num_symbols": int(len(ctx.close.columns)),
            }

        def evaluate_fields(self, field_frames, definition_payload, eval_config):
            cache_info = self.ensure_quick_eval_context(eval_config)
            ctx = self.quick_eval_contexts[cache_info["cache_key"]]
            quick_results = _run_quick_eval_on_frames(
                field_frames,
                definition_payload,
                eval_config,
                backtest_context=ctx,
            )
            return {"cache": cache_info, "results": quick_results}

    store = None
    try:
        store = ray.get_actor(RAY_PRELOAD_ACTOR, namespace=PRELOAD_RAY_NAMESPACE)
    except ValueError:
        store = None

    if store is not None:
        try:
            info = _fetch_preload_info(store)
        except Exception as exc:
            if not force_rebuild:
                _write_preload_state({
                    "status": "error",
                    **requested_range,
                    "actor_name": RAY_PRELOAD_ACTOR,
                    "namespace": PRELOAD_RAY_NAMESPACE,
                    "last_error": f"Existing preload actor is unresponsive: {exc}",
                })
                raise RuntimeError(
                    "Existing preload actor is unresponsive. "
                    "Refusing to auto-kill it because immediate rebuilds can destabilize the 50GB object store. "
                    "Use --force-preload-rebuild only when no researchers are using preload."
                ) from exc

            logger.warning(
                "Existing preload actor is unresponsive; killing because --force-preload-rebuild was provided"
            )
            ray.kill(store, no_restart=True)
            time.sleep(PRELOAD_REBUILD_GRACE_S)
            store = None
            info = None

        if store is not None and info is not None:
            if force_rebuild:
                logger.warning(
                    "Force rebuild requested; killing existing preload actor before rebuild"
                )
                ray.kill(store, no_restart=True)
                time.sleep(PRELOAD_REBUILD_GRACE_S)
                store = None
                info = None

        if store is not None and info is not None:
            same_range = (
                info.get("start_date") == start_date and
                info.get("end_date") == end_date
            )
            same_fields = list(info.get("fields") or []) == selected_fields
            same_symbol_source = info.get("symbol_source", DEFAULT_SYMBOL_SOURCE) == symbol_source
            same_config = same_range and same_fields and same_symbol_source
            if (
                info.get("status") == "ready"
                and same_config
                and info.get("stats", {}).get("loaded", 0) > 0
                and not force_rebuild
            ):
                logger.info(
                    "Reusing existing preload actor for [%s ~ %s, preset=%s, symbols=%s] (%s symbols)",
                    start_date,
                    end_date,
                    field_preset,
                    symbol_source,
                    info["stats"]["loaded"],
                )
                _write_preload_state(info)
                return int(info["stats"]["loaded"])

            if info.get("status") == "loading" and same_config and not force_rebuild:
                logger.info(
                    "Existing preload actor is already loading [%s ~ %s, preset=%s, symbols=%s]; waiting for readiness",
                    start_date,
                    end_date,
                    field_preset,
                    symbol_source,
                )
                ready_info = _wait_for_preload_ready(
                    store,
                    requested_start=start_date,
                    requested_end=end_date,
                )
                _write_preload_state(ready_info)
                return int(ready_info["stats"]["loaded"])

            if info.get("legacy") and (force_rebuild or not same_range):
                logger.warning(
                    "Existing preload actor is a legacy actor; killing it before rebuild"
                )
                ray.kill(store, no_restart=True)
                time.sleep(PRELOAD_REBUILD_GRACE_S)
                store = None

    if store is None:
        store = _PreloadStore.options(
            name=RAY_PRELOAD_ACTOR, lifetime="detached", num_cpus=0,
            namespace=PRELOAD_RAY_NAMESPACE, max_concurrency=4,
        ).remote()
        logger.info("Created new preload actor")
    else:
        logger.info(
            "Reloading preload actor in place for [%s ~ %s, preset=%s, symbols=%s]",
            start_date,
            end_date,
            field_preset,
            symbol_source,
        )

    logger.info(
        "Loading data inside actor [%s ~ %s, preset=%s, symbols=%s]...",
        start_date,
        end_date,
        field_preset,
        symbol_source,
    )
    t0 = time.time()
    payload = ray.get(
        store.load.remote(
            ARCTIC_URL,
            DEFAULT_SOURCE_LIBRARY,
            start_date,
            end_date,
            selected_fields,
            symbol_source,
            load_workers,
            True,
        )
    )
    stats = payload["stats"]
    elapsed = time.time() - t0
    logger.info(
        f"Preload done: {stats['loaded']}/{stats['total']} symbols in {elapsed:.0f}s "
        f"(shape={stats['array_shape']}, {stats['total_gb']:.2f} GB)"
    )
    logger.info(f"Actor '{RAY_PRELOAD_ACTOR}' ready (namespace={PRELOAD_RAY_NAMESPACE})")
    return stats["loaded"]


def compute_fast_preload(definition, num_workers=32):
    """Compute using preloaded data from Ray actor. Ultra fast (~5-10s)."""
    import ray
    _ray_init_preload()

    # Get preloaded data from actor
    store = ray.get_actor(RAY_PRELOAD_ACTOR, namespace=PRELOAD_RAY_NAMESPACE)
    try:
        info = _fetch_preload_info(store)
    except Exception as exc:
        raise RuntimeError(
            "Preload actor exists but is not responsive. "
            "Check `bash orchestration/status_rawdata_preload_ray.sh`; "
            "if needed, restart the isolated preload Ray with "
            "`bash orchestration/start_rawdata_preload_ray.sh` and rebuild preload."
        ) from exc

    if info.get("status") == "loading":
        raise RuntimeError(
            "Preload actor is still loading data. Wait for it to finish before using --use-preload."
        )
    if info.get("status") == "error":
        raise RuntimeError(
            f"Preload actor is in error state: {info.get('last_error')}"
        )

    metadata = ray.get(store.get_metadata.remote())
    symbols = metadata["symbols"]
    trading_days = metadata["trading_days"]
    all_fields = metadata["fields"]
    logger.info(f"  Using preloaded data: {len(symbols)} symbols")
    date_index = pd.DatetimeIndex([pd.Timestamp(d) for d in trading_days])
    logger.info(f"  {len(symbols)} symbols, {len(trading_days)} trading days")

    # Resolve field indices and bar mask
    field_to_idx = {f: i for i, f in enumerate(all_fields)}
    resolved_inputs = _resolve_definition_inputs(
        definition,
        all_fields,
        context=f"preload actor '{RAY_PRELOAD_ACTOR}'",
    )
    field_indices = [field_to_idx[f] for f in resolved_inputs]
    bar_mask = _time_filter_to_bar_mask(definition.params.input_time_filter)
    bar_indices_selected = np.where(bar_mask)[0]
    n_outputs = len(definition.output_names)
    expected_bars = definition.expected_bars if (
        definition.completeness_policy == CompletenessPolicy.STRICT_FULL_WINDOW
    ) else None

    # Compile numba function
    func = compile_formula(definition)
    n_inputs = len(definition.input_names)
    func(tuple(np.random.randn(60) for _ in range(n_inputs)))  # warmup

    @ray.remote
    def _compute_from_refs(symbol_refs, func_code, field_indices_list, bar_indices_list,
                           expected_bars_val, n_outputs_val):
        from numba import njit as _njit

        ns = {"np": np, "njit": _njit}
        exec(func_code, ns)
        fn = ns["apply_func"]
        dummy = tuple([np.array([1.0, 2.0, 3.0])] * len(field_indices_list))
        try:
            fn(dummy)
        except Exception:
            pass

        results = {}
        for sym, ref in symbol_refs.items():
            try:
                arr = ray.get(ref)
                n_days = arr.shape[0]
                out = np.full((n_days, n_outputs_val), np.nan, dtype=np.float64)
                for i in range(n_days):
                    selected = arr[i, bar_indices_list, :]
                    first_col = selected[:, field_indices_list[0]]
                    vc = np.sum(~np.isnan(first_col))
                    if vc == 0:
                        continue
                    if expected_bars_val is not None and vc < expected_bars_val:
                        continue
                    inputs = tuple(selected[:, fi] for fi in field_indices_list)
                    try:
                        res = fn(inputs)
                        if res is not None and len(res) >= n_outputs_val:
                            out[i, :] = res[:n_outputs_val]
                    except Exception:
                        pass
                results[sym] = out
            except Exception:
                pass
        return results

    # Split into batches
    batch_size = max(1, (len(symbols) + num_workers - 1) // num_workers)
    t0 = time.time()
    futures = []
    for i in range(0, len(symbols), batch_size):
        batch_syms = symbols[i:i + batch_size]
        batch_refs = ray.get(store.get_symbol_refs_batch.remote(batch_syms))
        futures.append(_compute_from_refs.remote(
            batch_refs, definition.formula, field_indices, bar_indices_selected,
            expected_bars, n_outputs,
        ))

    logger.info(f"  Dispatched {len(futures)} workers (preload mode)...")
    all_vals = {}
    for i, ref in enumerate(futures):
        batch_result = ray.get(ref)
        all_vals.update(batch_result)
        if (i + 1) % 4 == 0 or i == len(futures) - 1:
            elapsed = time.time() - t0
            logger.info(f"  batch {i+1}/{len(futures)}: {len(all_vals)}/{len(symbols)} ({elapsed:.0f}s)")

    logger.info(f"  Preload compute done: {len(all_vals)} stocks in {time.time()-t0:.0f}s")

    # Build per-field dict
    field_data: Dict[str, Dict[str, pd.Series]] = {}
    for k, oname in enumerate(definition.output_names):
        sym_dict = {}
        for sym, arr_val in all_vals.items():
            col = arr_val[:, k]
            valid = ~np.isnan(col)
            if valid.any():
                sym_dict[sym] = pd.Series(col, index=date_index, name=oname)
        if sym_dict:
            field_data[oname] = sym_dict

    return field_data


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_fields(field_data, output_dir, only_fields=None, definition=None):
    """Assemble per-field DataFrames and export as pkl."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exported = []
    for field, symbol_map in field_data.items():
        if only_fields and field not in only_fields:
            continue
        field_df = _assemble_field_df(symbol_map)

        pkl_path = output_path / f"{field}.pkl"
        field_df.to_pickle(pkl_path)
        if definition is not None:
            meta = build_rawdata_export_metadata(
                definition,
                field,
                source_path=str(pkl_path),
                observed_start=field_df.index.min().isoformat() if len(field_df.index) > 0 else None,
                observed_end=field_df.index.max().isoformat() if len(field_df.index) > 0 else None,
            )
            sidecar_path = write_rawdata_sidecar(pkl_path, meta)
            logger.info(f"  Metadata: {sidecar_path}")
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
    parser.add_argument("--symbol-source", choices=["cache", "library"], default=DEFAULT_SYMBOL_SOURCE,
                        help="Default symbol universe source when --symbols is not provided")
    parser.add_argument("--only-fields", nargs="+", default=None)
    parser.add_argument("--start-date", default=None,
                        help="Compute/preload start date (screening default: 2020-01-01)")
    parser.add_argument("--end-date", default=None,
                        help="Compute/preload end date (screening default: 2023-12-31)")
    parser.add_argument("--field-preset", choices=sorted(FIELD_PRESETS), default=DEFAULT_FIELD_PRESET,
                        help="Input field preset for --fast / --preload. basic6 is the lightweight screening preset")
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 100 random symbols")
    parser.add_argument("--fast", action="store_true",
                        help="Ray parallel mode: ~5x faster for full compute")
    parser.add_argument("--num-workers", type=int, default=32,
                        help="Number of Ray workers for --fast mode")
    parser.add_argument("--preload", action="store_true",
                        help="Preload 1m data into Ray (run once, then use --use-preload)")
    parser.add_argument("--force-preload-rebuild", action="store_true",
                        help="Force rebuild of the detached preload actor (only when no one else is using preload)")
    parser.add_argument("--use-preload", action="store_true",
                        help="Use preloaded data from Ray actor (requires prior --preload)")
    parser.add_argument("--quick-eval", action="store_true",
                        help="Run in-memory quick evaluation after compute using shared evaluate.py helpers")
    parser.add_argument("--skip-export", action="store_true",
                        help="Do not export pkl files (useful with --quick-eval)")
    parser.add_argument("--eval-start", default=DEFAULT_EVAL_START,
                        help="Quick-eval start date (default: 2020-01-01)")
    parser.add_argument("--eval-end", default=DEFAULT_EVAL_END,
                        help="Quick-eval end date (default: 2024-12-31)")
    parser.add_argument("--eval-window", type=int, default=1,
                        help="Quick-eval rolling window")
    parser.add_argument("--eval-mode", default=DEFAULT_EVAL_MODE,
                        choices=["long_only", "long_short"],
                        help="Quick-eval backtest mode")
    parser.add_argument("--eval-position-method", default=DEFAULT_EVAL_POSITION_METHOD,
                        choices=["factor_weighted", "top_n"],
                        help="Quick-eval position method")
    parser.add_argument("--eval-num-hold", type=int, default=None,
                        help="Required when --eval-position-method top_n")
    parser.add_argument("--eval-execution-price-field", default=DEFAULT_EVAL_EXECUTION_PRICE_FIELD,
                        help="Quick-eval execution price field")
    parser.add_argument("--eval-benchmark-index", default=DEFAULT_EVAL_BENCHMARK_INDEX,
                        help="Quick-eval benchmark index (use 'none' to disable)")
    parser.add_argument("--eval-index-code", default=None,
                        help="Optional quick-eval stock universe index code")
    parser.add_argument("--eval-post-process-method", default=DEFAULT_EVAL_POST_PROCESS_METHOD,
                        help="Quick-eval post-process method (use 'none' to disable)")
    parser.add_argument("--eval-post-process-params", default=None,
                        help="JSON dict forwarded to quick-eval post-process method")
    parser.add_argument("--eval-t-plus-n", type=int, default=None,
                        help="Override quick-eval t_plus_n")
    parser.add_argument("--eval-commission-rate", type=float, default=DEFAULT_EVAL_COMMISSION_RATE,
                        help="Quick-eval commission rate")
    parser.add_argument("--eval-stamp-tax-rate", type=float, default=DEFAULT_EVAL_STAMP_TAX_RATE,
                        help="Quick-eval stamp tax rate")
    parser.add_argument("--eval-allow-st", action="store_true",
                        help="Allow ST names in quick-eval long universe")
    parser.add_argument("--eval-include-price-limit", action="store_true",
                        help="Disable price-limit exclusion in quick-eval")
    parser.add_argument("--eval-report-dir", default=DEFAULT_EVAL_REPORT_DIR,
                        help="Directory for quick-eval JSON reports")
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

    if args.skip_export and not args.quick_eval:
        parser.error("--skip-export requires --quick-eval")
    if args.eval_position_method == "top_n" and not args.eval_num_hold:
        parser.error("--eval-num-hold is required when --eval-position-method top_n")
    if _researcher_mode_enabled() and args.fast:
        parser.error(
            "Researcher sessions must not use --fast. "
            "Keep --use-preload, or stop the run and report the preload issue."
        )

    # Handle --preload
    if args.preload:
        start = args.start_date or "2020-01-01"
        run_preload(
            start_date=start,
            end_date=args.end_date or "2023-12-31",
            force_rebuild=args.force_preload_rebuild,
            field_preset=args.field_preset,
            symbol_source=args.symbol_source,
            load_workers=args.num_workers,
        )
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
        all_syms = _load_symbol_universe(symbol_source=args.symbol_source)
        np.random.seed(42)
        symbols = list(np.random.choice(all_syms, size=min(100, len(all_syms)), replace=False))
        logger.info(f"Quick mode: {len(symbols)} random symbols")

    # Compute
    if args.use_preload:
        logger.info(f"Preload mode (Ray): using preloaded data, {args.num_workers} workers")
        field_data = compute_fast_preload(definition, num_workers=args.num_workers)
    elif args.fast:
        if not symbols:
            symbols = _load_symbol_universe(symbol_source=args.symbol_source)
        logger.info(f"Fast mode (Ray): {len(symbols)} symbols, {args.num_workers} workers")
        start = args.start_date or "2020-01-01"
        field_data = compute_fast(definition, symbols, start_date=start,
                                  end_date=args.end_date or "2023-12-31", num_workers=args.num_workers,
                                  field_preset=args.field_preset)
    else:
        conn = Arctic(ARCTIC_URL)
        source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
        if not symbols:
            symbols = _load_symbol_universe(source_lib, symbol_source=args.symbol_source)
        logger.info(f"Serial mode: {len(symbols)} symbols")
        start_time = pd.Timestamp(args.start_date) if args.start_date else None
        field_data = compute_serial(definition, symbols, source_lib, start_time)

    selected_field_data = {
        field: symbol_map
        for field, symbol_map in field_data.items()
        if not args.only_fields or field in args.only_fields
    }

    quick_eval_report = None
    if args.quick_eval:
        quick_eval_report = run_quick_eval(selected_field_data, definition, args)

    # Export
    exported = []
    if not args.skip_export:
        exported = export_fields(selected_field_data, args.output_dir, definition=definition)

    # Summary
    print(f"\n{'='*60}")
    if args.skip_export:
        print("Export skipped")
    else:
        print(f"Exported {len(exported)} fields to {args.output_dir}")
    if args.use_preload:
        mode = "preload (Ray)"
    elif args.fast:
        mode = "fast (Ray)"
    else:
        mode = "quick" if args.quick else "serial"
    print(f"Mode: {mode}")
    print(f"{'='*60}")
    for field, shape, path in exported:
        print(f"  {field}: {shape[0]} dates x {shape[1]} symbols -> {path}")
    if quick_eval_report is not None:
        report_path, report = quick_eval_report
        print_quick_eval_summary(report_path, report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
