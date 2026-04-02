#!/usr/bin/env python3
"""Thin raw-data evolve driver built on top of compute_rawdata_local.py.

This script is intentionally a driver, not a second compute/backtest stack.
It reuses the existing raw-data compute and quick-eval hot path to batch-score
many candidates, keep the top-K, and optionally iterate for multiple
generations through a user-provided generator module.

Two modes are supported:

1. Fixed candidate batch
   python scripts/evolve_rawdata.py \
       --formula-file a.py --formula-file b.py --use-preload

2. Generator-driven generations
   python scripts/evolve_rawdata.py \
       --generator-file my_generator.py \
       --seed-formula-file research/.../register_xxx.py \
       --generations 5 --population-size 12 --top-k 4 --use-preload

Generator contract:
    Define one of:
      - generate_candidates(...)
      - build_candidates(...)

    The driver passes a flexible subset of these keyword arguments, depending on
    what the function accepts:
      seed_definition, generation, parents, rng, population_size, args

    Return an iterable of either:
      - AShareRawDataDefinition
      - dict with keys:
          definition: AShareRawDataDefinition or definition document dict
          label: optional candidate label
          metadata: optional free-form dict
          only_fields: optional list of output fields to quick-eval
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import logging
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
ASHARE_ROOT = Path("/home/gkh/ashare")

for path in (SCRIPTS_DIR, PROJECT_ROOT, ASHARE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import compute_rawdata_local as compute_mod
from arcticdb import Arctic
from ashare_hf_variable.config import ARCTIC_URL, DEFAULT_SOURCE_LIBRARY
from ashare_hf_variable.models import AShareRawDataDefinition
from ashare_hf_variable.registry import validate_definition

logger = logging.getLogger(__name__)

DEFAULT_SCREEN_START = "2020-01-01"
DEFAULT_SCREEN_END = "2023-12-31"
MIN_SCREEN_YEARS = 2
BLOCKED_UNIVERSE_FLAGS = ("--symbols", "--quick", "--quick-size")
RESEARCHER_MODE_ENV = "ASHARE_RAWDATA_RESEARCHER_MODE"


@dataclass
class Candidate:
    definition: AShareRawDataDefinition
    label: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    only_fields: Optional[List[str]] = None


@dataclass
class ExecutionContext:
    symbols: Optional[List[str]]
    source_lib: Any = None


def _parse_date_arg(value: str, flag: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(value)
    except Exception as exc:  # pragma: no cover - argparse handles most cases
        raise ValueError(f"Invalid date for {flag}: {value}") from exc


def _min_window_end(start: pd.Timestamp) -> pd.Timestamp:
    return start + pd.DateOffset(years=MIN_SCREEN_YEARS) - pd.Timedelta(days=1)


def _window_summary(start_value: str, end_value: str) -> Dict[str, Any]:
    start = _parse_date_arg(start_value, "start")
    end = _parse_date_arg(end_value, "end")
    return {
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "days": int((end - start).days + 1),
        "min_allowed_end": _min_window_end(start).strftime("%Y-%m-%d"),
    }


def _researcher_mode_enabled() -> bool:
    value = os.environ.get(RESEARCHER_MODE_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    slug = slug.strip("-._")
    return slug or "candidate"


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _coerce_definition(value: Any) -> AShareRawDataDefinition:
    if isinstance(value, AShareRawDataDefinition):
        return value
    if isinstance(value, dict):
        return AShareRawDataDefinition.model_validate(value)
    raise TypeError(f"Unsupported definition payload type: {type(value)!r}")


def _coerce_candidate(item: Any, *, source: str, default_label: str) -> Candidate:
    if isinstance(item, AShareRawDataDefinition):
        return Candidate(
            definition=item,
            label=item.name or default_label,
            source=source,
        )

    if isinstance(item, dict):
        definition_value = item.get("definition", item.get("document", item))
        definition = _coerce_definition(definition_value)
        only_fields = item.get("only_fields")
        if only_fields is not None:
            only_fields = list(only_fields)
        return Candidate(
            definition=definition,
            label=item.get("label") or definition.name or default_label,
            source=source,
            metadata=dict(item.get("metadata") or {}),
            only_fields=only_fields,
        )

    raise TypeError(f"Unsupported candidate type: {type(item)!r}")


def _dedupe_candidate_labels(candidates: List[Candidate]) -> List[Candidate]:
    seen: Dict[str, int] = {}
    normalized: List[Candidate] = []
    for candidate in candidates:
        base = _slugify(candidate.label)
        count = seen.get(base, 0) + 1
        seen[base] = count
        label = base if count == 1 else f"{base}-{count}"
        normalized.append(
            Candidate(
                definition=candidate.definition,
                label=label,
                source=candidate.source,
                metadata=candidate.metadata,
                only_fields=candidate.only_fields,
            )
        )
    return normalized


def _load_formula_candidates(paths: Sequence[str]) -> List[Candidate]:
    candidates = []
    for idx, raw_path in enumerate(paths, start=1):
        path = Path(raw_path).resolve()
        definition = compute_mod.load_definition_from_file(str(path))
        candidates.append(
            Candidate(
                definition=definition,
                label=path.stem,
                source=f"formula:{path}",
                metadata={"formula_file": str(path)},
            )
        )
    return candidates


def _load_bundle_candidates(names: Sequence[str]) -> List[Candidate]:
    candidates = []
    for idx, name in enumerate(names, start=1):
        definition = compute_mod.load_definition_from_registry(name)
        candidates.append(
            Candidate(
                definition=definition,
                label=name,
                source=f"bundle:{name}",
                metadata={"bundle": name},
            )
        )
    return candidates


def _load_seed_definition(args) -> AShareRawDataDefinition:
    if args.seed_formula_file:
        return compute_mod.load_definition_from_file(args.seed_formula_file)
    if args.seed_bundle:
        return compute_mod.load_definition_from_registry(args.seed_bundle)
    raise ValueError("Generator mode requires --seed-formula-file or --seed-bundle")


def _pick_generator_fn(module):
    for name in ("generate_candidates", "build_candidates"):
        fn = getattr(module, name, None)
        if callable(fn):
            return fn
    raise AttributeError("Generator module must define generate_candidates(...) or build_candidates(...)")


def _call_with_supported_kwargs(fn, **kwargs):
    signature = inspect.signature(fn)
    accepts_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    call_kwargs = {}
    for key, value in kwargs.items():
        if accepts_var_kwargs or key in signature.parameters:
            call_kwargs[key] = value
    return fn(**call_kwargs)


def _load_generator_candidates(
    generator_path: Path,
    *,
    seed_definition: AShareRawDataDefinition,
    generation: int,
    parents: List[Dict[str, Any]],
    rng: np.random.Generator,
    population_size: int,
    args,
) -> List[Candidate]:
    module = _load_module(generator_path, f"_evolve_generator_{generation}")
    generator_fn = _pick_generator_fn(module)
    raw_candidates = _call_with_supported_kwargs(
        generator_fn,
        seed_definition=seed_definition,
        generation=generation,
        parents=parents,
        rng=rng,
        population_size=population_size,
        args=args,
    )
    if raw_candidates is None:
        return []
    candidates = [
        _coerce_candidate(
            item,
            source=f"generator:{generator_path}",
            default_label=f"g{generation:03d}_c{idx:03d}",
        )
        for idx, item in enumerate(raw_candidates, start=1)
    ]
    return _dedupe_candidate_labels(candidates)


def _load_all_symbols(source_lib=None) -> List[str]:
    return compute_mod._load_symbol_universe(
        source_lib=source_lib,
        symbol_source=compute_mod.DEFAULT_SYMBOL_SOURCE,
    )


def _prepare_execution_context(args) -> ExecutionContext:
    if args.use_preload:
        return ExecutionContext(symbols=None, source_lib=None)

    conn = Arctic(ARCTIC_URL)
    source_lib = conn.get_library(DEFAULT_SOURCE_LIBRARY, create_if_missing=False)
    all_symbols = _load_all_symbols(source_lib=source_lib)
    return ExecutionContext(symbols=all_symbols, source_lib=source_lib)


def _build_quick_eval_args(args, report_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        eval_start=args.eval_start,
        eval_end=args.eval_end,
        eval_window=args.eval_window,
        eval_mode=args.eval_mode,
        eval_position_method=args.eval_position_method,
        eval_num_hold=args.eval_num_hold,
        eval_execution_price_field=args.eval_execution_price_field,
        eval_benchmark_index=args.eval_benchmark_index,
        eval_index_code=args.eval_index_code,
        eval_post_process_method=args.eval_post_process_method,
        eval_post_process_params=args.eval_post_process_params,
        eval_t_plus_n=args.eval_t_plus_n,
        eval_commission_rate=args.eval_commission_rate,
        eval_stamp_tax_rate=args.eval_stamp_tax_rate,
        eval_allow_st=args.eval_allow_st,
        eval_include_price_limit=args.eval_include_price_limit,
        eval_report_dir=str(report_dir),
        use_preload=args.use_preload,
    )


def _compute_serial_range(
    definition: AShareRawDataDefinition,
    symbols: Sequence[str],
    source_lib,
    *,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Dict[str, pd.Series]]:
    func = compute_mod.compile_formula(definition)
    dummy = tuple(np.random.randn(60) for _ in range(len(definition.input_names)))
    func(dummy)

    ts_start = pd.Timestamp(start_date) if start_date else None
    ts_end = pd.Timestamp(end_date) if end_date else None
    field_data: Dict[str, Dict[str, pd.Series]] = {}
    t0 = time.time()
    for idx, symbol in enumerate(symbols, start=1):
        try:
            if ts_start is None and ts_end is None:
                df = source_lib.read(symbol).data
            else:
                df = source_lib.read(symbol, date_range=(ts_start, ts_end)).data
        except Exception:
            continue

        result = compute_mod.compute_symbol(df, definition, func)
        if result.empty:
            continue
        for field in definition.output_names:
            series = result[field].dropna()
            if not series.empty:
                field_data.setdefault(field, {})[symbol] = series

        if idx % 500 == 0:
            elapsed = time.time() - t0
            rate = idx / elapsed if elapsed > 0 else 0.0
            eta = (len(symbols) - idx) / rate if rate > 0 else math.inf
            logger.info("  ...%d/%d symbols (%.0fs, ETA %.0fs)", idx, len(symbols), elapsed, eta)

    return field_data


def _compute_field_data(
    candidate: Candidate,
    args,
    context: ExecutionContext,
) -> Dict[str, Dict[str, pd.Series]]:
    definition = candidate.definition
    if args.use_preload:
        field_data = compute_mod.compute_fast_preload(definition, num_workers=args.num_workers)
    elif args.fast:
        field_data = compute_mod.compute_fast(
            definition,
            context.symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            num_workers=args.num_workers,
            field_preset=args.field_preset,
        )
    else:
        field_data = _compute_serial_range(
            definition,
            context.symbols,
            context.source_lib,
            start_date=args.start_date,
            end_date=args.end_date,
        )

    only_fields = set(args.only_fields or [])
    if candidate.only_fields:
        only_fields.update(candidate.only_fields)
    if only_fields:
        field_data = {field: value for field, value in field_data.items() if field in only_fields}
    return field_data


def _extract_metric(result_item: Dict[str, Any], metric: str) -> Optional[float]:
    if metric == "coverage_ratio":
        value = result_item.get("coverage_ratio")
    elif metric == "t_plus_n":
        value = result_item.get("t_plus_n")
    else:
        value = (result_item.get("stats") or {}).get(metric)

    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _transform_score(value: Optional[float], transform: str) -> Optional[float]:
    if value is None:
        return None
    if transform == "abs":
        return abs(value)
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_table_files(rows: List[Dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    _write_json(json_path, rows)
    if rows:
        pd.DataFrame(rows).to_csv(csv_path, index=False)
    else:
        pd.DataFrame().to_csv(csv_path, index=False)


def _save_candidate_definition(candidate: Candidate, path: Path) -> None:
    payload = {
        "label": candidate.label,
        "source": candidate.source,
        "metadata": candidate.metadata,
        "only_fields": candidate.only_fields,
        "definition": candidate.definition.model_dump(mode="json"),
    }
    _write_json(path, payload)


def _evaluate_candidate(
    candidate: Candidate,
    *,
    generation: int,
    ordinal: int,
    args,
    context: ExecutionContext,
    run_dir: Path,
) -> Dict[str, Any]:
    validate_definition(candidate.definition)

    generation_dir = run_dir / "generations" / f"generation_{generation:03d}"
    candidate_dir = generation_dir / "candidates" / f"{ordinal:03d}_{candidate.label}"
    report_dir = candidate_dir / "reports"
    definition_path = candidate_dir / "definition.json"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    _save_candidate_definition(candidate, definition_path)

    compute_started = time.time()
    field_data = _compute_field_data(candidate, args, context)
    compute_seconds = round(time.time() - compute_started, 3)

    quick_args = _build_quick_eval_args(args, report_dir)
    eval_started = time.time()
    quick_eval = compute_mod.run_quick_eval(field_data, candidate.definition, quick_args)
    eval_seconds = round(time.time() - eval_started, 3)

    results = {}
    report_path = None
    if quick_eval is not None:
        report_path, report = quick_eval
        results = report.get("results", {})

    field_rows: List[Dict[str, Any]] = []
    for field_name, result_item in sorted(results.items()):
        raw_score = _extract_metric(result_item, args.score_metric)
        fitness_score = _transform_score(raw_score, args.score_transform)
        row = {
            "generation": generation,
            "candidate_label": candidate.label,
            "candidate_name": candidate.definition.name,
            "candidate_source": candidate.source,
            "field": field_name,
            "status": "error" if "error" in result_item else "ok",
            "score_metric": args.score_metric,
            "score_transform": args.score_transform,
            "score_raw": raw_score,
            "score": fitness_score,
            "invert_sign": bool(raw_score is not None and raw_score < 0),
            "coverage_ratio": result_item.get("coverage_ratio"),
            "t_plus_n": result_item.get("t_plus_n"),
            "compute_seconds": compute_seconds,
            "eval_seconds": eval_seconds,
            "report_path": str(report_path) if report_path is not None else None,
            "definition_path": str(definition_path),
            "error": result_item.get("error"),
        }
        row.update(result_item.get("stats") or {})
        field_rows.append(row)

    best_row = None
    for row in field_rows:
        if row["score"] is None:
            continue
        if best_row is None or row["score"] > best_row["score"]:
            best_row = row

    candidate_result = {
        "generation": generation,
        "candidate_label": candidate.label,
        "candidate_name": candidate.definition.name,
        "candidate_source": candidate.source,
        "status": "ok" if best_row is not None else "no_valid_field",
        "fitness": best_row["score"] if best_row is not None else None,
        "best_field": best_row["field"] if best_row is not None else None,
        "best_score_raw": best_row["score_raw"] if best_row is not None else None,
        "best_invert_sign": best_row["invert_sign"] if best_row is not None else None,
        "score_metric": args.score_metric,
        "score_transform": args.score_transform,
        "num_fields_evaluated": len(field_rows),
        "compute_seconds": compute_seconds,
        "eval_seconds": eval_seconds,
        "report_path": str(report_path) if report_path is not None else None,
        "definition_path": str(definition_path),
        "metadata": candidate.metadata,
        "only_fields": candidate.only_fields,
        "field_rows": field_rows,
        "definition": candidate.definition,
    }
    if best_row is not None:
        candidate_result["best_field_metrics"] = {
            key: value
            for key, value in best_row.items()
            if key not in {"field", "candidate_label", "candidate_name", "candidate_source", "definition_path", "report_path"}
        }
    return candidate_result


def _generation_leaderboard(candidate_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    ordered = sorted(
        candidate_results,
        key=lambda item: item["fitness"] if item["fitness"] is not None else float("-inf"),
        reverse=True,
    )
    for rank, result in enumerate(ordered, start=1):
        rows.append(
            {
                "rank": rank,
                "generation": result["generation"],
                "candidate_label": result["candidate_label"],
                "candidate_name": result["candidate_name"],
                "status": result["status"],
                "fitness": result["fitness"],
                "best_field": result["best_field"],
                "best_score_raw": result["best_score_raw"],
                "best_invert_sign": result["best_invert_sign"],
                "score_metric": result["score_metric"],
                "score_transform": result["score_transform"],
                "num_fields_evaluated": result["num_fields_evaluated"],
                "compute_seconds": result["compute_seconds"],
                "eval_seconds": result["eval_seconds"],
                "report_path": result["report_path"],
                "definition_path": result["definition_path"],
            }
        )
    return rows


def _all_field_rows(candidate_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in candidate_results:
        rows.extend(result["field_rows"])
    rows.sort(
        key=lambda item: item["score"] if item["score"] is not None else float("-inf"),
        reverse=True,
    )
    for rank, row in enumerate(rows, start=1):
        row["field_rank"] = rank
    return rows


def _survivors(candidate_results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    ordered = sorted(
        candidate_results,
        key=lambda item: item["fitness"] if item["fitness"] is not None else float("-inf"),
        reverse=True,
    )
    return ordered[:top_k]


def _serialize_candidate_result(result: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(result)
    definition = payload.pop("definition", None)
    if definition is not None:
        payload["definition_document"] = definition.model_dump(mode="json")
    return compute_mod._to_builtin(payload)


def _write_generation_outputs(
    generation: int,
    candidate_results: List[Dict[str, Any]],
    run_dir: Path,
) -> None:
    generation_dir = run_dir / "generations" / f"generation_{generation:03d}"
    generation_dir.mkdir(parents=True, exist_ok=True)

    candidate_rows = _generation_leaderboard(candidate_results)
    field_rows = _all_field_rows(candidate_results)
    _write_table_files(
        candidate_rows,
        generation_dir / "leaderboard.json",
        generation_dir / "leaderboard.csv",
    )
    _write_table_files(
        field_rows,
        generation_dir / "field_scores.json",
        generation_dir / "field_scores.csv",
    )
    _write_json(
        generation_dir / "candidate_results.json",
        [compute_mod._to_builtin(_serialize_candidate_result(result)) for result in candidate_results],
    )


def _write_run_manifest(args, run_dir: Path) -> None:
    payload = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "args": vars(args),
        "screening_policy": {
            "full_market_only": True,
            "min_eval_years": MIN_SCREEN_YEARS,
            "blocked_universe_flags": list(BLOCKED_UNIVERSE_FLAGS),
            "field_preset": args.field_preset,
            "eval_window": _window_summary(args.eval_start, args.eval_end),
            "compute_window": None
            if args.use_preload
            else _window_summary(args.start_date, args.end_date),
            "policy_compliant": True,
        },
    }
    _write_json(run_dir / "run_manifest.json", compute_mod._to_builtin(payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Batch-evaluate or iterate raw-data candidates via compute_rawdata_local quick-eval",
    )
    parser.add_argument("--formula-file", action="append", default=[],
                        help="Path to a raw-data registration script; may be repeated")
    parser.add_argument("--bundle", action="append", default=[],
                        help="Registered raw-data bundle name; may be repeated")
    parser.add_argument("--generator-file", default=None,
                        help="Python module that generates candidates generation by generation")
    parser.add_argument("--seed-formula-file", default=None,
                        help="Seed definition for generator mode")
    parser.add_argument("--seed-bundle", default=None,
                        help="Seed bundle for generator mode")

    parser.add_argument("--output-dir", default=".claude-output/evolve",
                        help="Root directory for evolve run outputs")
    parser.add_argument("--run-name", default=None,
                        help="Optional stable run name; default uses timestamp")
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--population-size", type=int, default=8,
                        help="Requested candidate count per generation in generator mode")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of candidates retained between generations")
    parser.add_argument("--random-seed", type=int, default=42)

    parser.add_argument("--score-metric", default="sharpe_abs_net",
                        help="Metric extracted from quick-eval stats for ranking")
    parser.add_argument("--score-transform", choices=["abs", "raw"], default="abs",
                        help="Transform applied before ranking")
    parser.add_argument("--only-fields", nargs="+", default=None,
                        help="Restrict quick-eval to these output fields")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop immediately on the first candidate error")

    parser.add_argument("--start-date", default=DEFAULT_SCREEN_START)
    parser.add_argument("--end-date", default=DEFAULT_SCREEN_END)
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--quick", action="store_true",
                        help="Blocked by policy: keep the full-market universe and shorten the time window instead")
    parser.add_argument("--quick-size", type=int, default=100)
    parser.add_argument("--fast", action="store_true",
                        help="Use Ray fast mode without preload")
    parser.add_argument("--use-preload", action="store_true",
                        help="Use the detached preload actor")
    parser.add_argument("--num-workers", type=int, default=32)
    parser.add_argument("--field-preset", choices=sorted(compute_mod.FIELD_PRESETS),
                        default=compute_mod.DEFAULT_SCREEN_FIELD_PRESET,
                        help="Field preset for screening compute. basic6 is the default fast-screen profile")

    parser.add_argument("--eval-start", default=DEFAULT_SCREEN_START)
    parser.add_argument("--eval-end", default=DEFAULT_SCREEN_END)
    parser.add_argument("--eval-window", type=int, default=1)
    parser.add_argument("--eval-mode", default=compute_mod.DEFAULT_EVAL_MODE, choices=["long_only", "long_short"])
    parser.add_argument("--eval-position-method", default=compute_mod.DEFAULT_EVAL_POSITION_METHOD,
                        choices=["factor_weighted", "top_n"])
    parser.add_argument("--eval-num-hold", type=int, default=None)
    parser.add_argument("--eval-execution-price-field", default=compute_mod.DEFAULT_EVAL_EXECUTION_PRICE_FIELD)
    parser.add_argument("--eval-benchmark-index", default=compute_mod.DEFAULT_EVAL_BENCHMARK_INDEX)
    parser.add_argument("--eval-index-code", default=None)
    parser.add_argument("--eval-post-process-method", default=compute_mod.DEFAULT_EVAL_POST_PROCESS_METHOD)
    parser.add_argument("--eval-post-process-params", default=None)
    parser.add_argument("--eval-t-plus-n", type=int, default=None)
    parser.add_argument("--eval-commission-rate", type=float, default=compute_mod.DEFAULT_EVAL_COMMISSION_RATE)
    parser.add_argument("--eval-stamp-tax-rate", type=float, default=compute_mod.DEFAULT_EVAL_STAMP_TAX_RATE)
    parser.add_argument("--eval-allow-st", action="store_true")
    parser.add_argument("--eval-include-price-limit", action="store_true")

    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def _validate_args(parser: argparse.ArgumentParser, args) -> None:
    has_explicit_candidates = bool(args.formula_file or args.bundle)
    has_generator = bool(args.generator_file)

    if not has_explicit_candidates and not has_generator:
        parser.error("Provide candidates via --formula-file/--bundle or use --generator-file")
    if has_explicit_candidates and has_generator:
        parser.error("Use either explicit candidates or --generator-file, not both")
    if has_generator and bool(args.seed_formula_file) == bool(args.seed_bundle):
        parser.error("Generator mode requires exactly one of --seed-formula-file or --seed-bundle")
    if not has_generator and (args.seed_formula_file or args.seed_bundle):
        parser.error("--seed-formula-file/--seed-bundle only apply to generator mode")
    if args.generations <= 0:
        parser.error("--generations must be positive")
    if args.population_size <= 0:
        parser.error("--population-size must be positive")
    if args.top_k <= 0:
        parser.error("--top-k must be positive")
    if args.eval_position_method == "top_n" and not args.eval_num_hold:
        parser.error("--eval-num-hold is required when --eval-position-method top_n")
    if args.quick_size <= 0:
        parser.error("--quick-size must be positive")
    if args.fast and args.use_preload:
        parser.error("Choose either --fast or --use-preload")
    if _researcher_mode_enabled() and args.fast:
        parser.error(
            "Researcher sessions must not use --fast. "
            "Keep --use-preload, or stop the run and report the preload issue."
        )
    if args.symbols:
        parser.error(
            "--symbols is disabled for evolve quick screening. "
            "Keep the full-market universe and shorten the time window instead."
        )
    if args.quick:
        parser.error(
            "--quick is disabled for evolve quick screening. "
            "Small-universe sampling is blocked to avoid universe bias."
        )
    if args.quick_size != 100:
        parser.error(
            "--quick-size is unavailable because small-universe quick mode is disabled."
        )

    def validate_window(start_value: str, end_value: str, start_flag: str, end_flag: str) -> None:
        try:
            start_ts = _parse_date_arg(start_value, start_flag)
            end_ts = _parse_date_arg(end_value, end_flag)
        except ValueError as exc:
            parser.error(str(exc))
        if end_ts < start_ts:
            parser.error(f"{end_flag} must be on or after {start_flag}")
        min_end = _min_window_end(start_ts)
        if end_ts < min_end:
            parser.error(
                f"{start_flag}/{end_flag} must span at least {MIN_SCREEN_YEARS} years "
                f"for evolve quick screening. Example: {DEFAULT_SCREEN_START} to {DEFAULT_SCREEN_END}."
            )

    validate_window(args.eval_start, args.eval_end, "--eval-start", "--eval-end")
    if not args.use_preload:
        validate_window(args.start_date, args.end_date, "--start-date", "--end-date")


def _log_generation_summary(generation: int, candidate_results: List[Dict[str, Any]]) -> None:
    leaderboard = _generation_leaderboard(candidate_results)
    logger.info("Generation %03d complete", generation)
    for row in leaderboard[:5]:
        logger.info(
            "  #%d %s | fitness=%s | best_field=%s",
            row["rank"],
            row["candidate_label"],
            row["fitness"],
            row["best_field"],
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    run_name = args.run_name or time.strftime("%Y%m%d-%H%M%S")
    run_dir = (PROJECT_ROOT / args.output_dir / run_name).resolve() if not Path(args.output_dir).is_absolute() else (Path(args.output_dir).resolve() / run_name)
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_run_manifest(args, run_dir)

    context = _prepare_execution_context(args)
    rng = np.random.default_rng(args.random_seed)

    all_generation_summaries = []
    exit_code = 0

    if args.generator_file:
        seed_definition = _load_seed_definition(args)
        generator_path = Path(args.generator_file).resolve()
        parents: List[Dict[str, Any]] = []
        for generation in range(args.generations):
            candidates = _load_generator_candidates(
                generator_path,
                seed_definition=seed_definition,
                generation=generation,
                parents=parents,
                rng=rng,
                population_size=args.population_size,
                args=args,
            )
            if not candidates:
                logger.warning("Generation %03d produced no candidates; stopping", generation)
                break

            candidate_results: List[Dict[str, Any]] = []
            for ordinal, candidate in enumerate(candidates, start=1):
                logger.info(
                    "[G%03d %03d/%03d] %s (%s)",
                    generation,
                    ordinal,
                    len(candidates),
                    candidate.label,
                    candidate.definition.name,
                )
                try:
                    result = _evaluate_candidate(
                        candidate,
                        generation=generation,
                        ordinal=ordinal,
                        args=args,
                        context=context,
                        run_dir=run_dir,
                    )
                except Exception as exc:
                    logger.exception("Candidate failed: %s", candidate.label)
                    result = {
                        "generation": generation,
                        "candidate_label": candidate.label,
                        "candidate_name": candidate.definition.name,
                        "candidate_source": candidate.source,
                        "status": "error",
                        "fitness": None,
                        "best_field": None,
                        "best_score_raw": None,
                        "best_invert_sign": None,
                        "score_metric": args.score_metric,
                        "score_transform": args.score_transform,
                        "num_fields_evaluated": 0,
                        "compute_seconds": None,
                        "eval_seconds": None,
                        "report_path": None,
                        "definition_path": None,
                        "metadata": candidate.metadata,
                        "only_fields": candidate.only_fields,
                        "field_rows": [],
                        "definition": candidate.definition,
                        "error": str(exc),
                    }
                    exit_code = 1
                    if args.fail_fast:
                        raise
                candidate_results.append(result)

            _write_generation_outputs(generation, candidate_results, run_dir)
            _log_generation_summary(generation, candidate_results)
            survivors = _survivors(candidate_results, args.top_k)
            parents = survivors
            all_generation_summaries.append(
                {
                    "generation": generation,
                    "num_candidates": len(candidate_results),
                    "survivors": [
                        {
                            "candidate_label": item["candidate_label"],
                            "candidate_name": item["candidate_name"],
                            "fitness": item["fitness"],
                            "best_field": item["best_field"],
                            "metadata": item["metadata"],
                        }
                        for item in survivors
                    ],
                }
            )
    else:
        candidates = _dedupe_candidate_labels(
            _load_formula_candidates(args.formula_file) + _load_bundle_candidates(args.bundle)
        )
        candidate_results: List[Dict[str, Any]] = []
        for ordinal, candidate in enumerate(candidates, start=1):
            logger.info("[%03d/%03d] %s (%s)", ordinal, len(candidates), candidate.label, candidate.definition.name)
            try:
                result = _evaluate_candidate(
                    candidate,
                    generation=0,
                    ordinal=ordinal,
                    args=args,
                    context=context,
                    run_dir=run_dir,
                )
            except Exception as exc:
                logger.exception("Candidate failed: %s", candidate.label)
                result = {
                    "generation": 0,
                    "candidate_label": candidate.label,
                    "candidate_name": candidate.definition.name,
                    "candidate_source": candidate.source,
                    "status": "error",
                    "fitness": None,
                    "best_field": None,
                    "best_score_raw": None,
                    "best_invert_sign": None,
                    "score_metric": args.score_metric,
                    "score_transform": args.score_transform,
                    "num_fields_evaluated": 0,
                    "compute_seconds": None,
                    "eval_seconds": None,
                    "report_path": None,
                    "definition_path": None,
                    "metadata": candidate.metadata,
                    "only_fields": candidate.only_fields,
                    "field_rows": [],
                    "definition": candidate.definition,
                    "error": str(exc),
                }
                exit_code = 1
                if args.fail_fast:
                    raise
            candidate_results.append(result)

        _write_generation_outputs(0, candidate_results, run_dir)
        _log_generation_summary(0, candidate_results)
        all_generation_summaries.append(
            {
                "generation": 0,
                "num_candidates": len(candidate_results),
                "survivors": [
                    {
                        "candidate_label": item["candidate_label"],
                        "candidate_name": item["candidate_name"],
                        "fitness": item["fitness"],
                        "best_field": item["best_field"],
                    }
                    for item in _survivors(candidate_results, args.top_k)
                ],
            }
        )

    _write_json(
        run_dir / "summary.json",
        compute_mod._to_builtin(
            {
                "run_dir": str(run_dir),
                "score_metric": args.score_metric,
                "score_transform": args.score_transform,
                "generations": all_generation_summaries,
            }
        ),
    )

    print("\nSummary")
    print(f"  Run dir: {run_dir}")
    print(f"  Score: {args.score_metric} ({args.score_transform})")
    for generation in all_generation_summaries:
        survivors = generation["survivors"]
        if not survivors:
            print(f"  Generation {generation['generation']:03d}: no survivors")
            continue
        best = survivors[0]
        print(
            f"  Generation {generation['generation']:03d}: "
            f"best={best['candidate_label']} fitness={best['fitness']} field={best['best_field']}"
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
