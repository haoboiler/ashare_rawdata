#!/usr/bin/env python3
"""Helpers for raw-data evaluation metadata and timing inference."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path("/home/gkh/claude_tasks/ashare_rawdata")
ASHARE_ROOT = Path("/home/gkh/ashare")
CASIMIR_ROOT = ASHARE_ROOT / "casimir_ashare"
EVALUATE_PY = Path("/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py")
EVALUATE_PYTHON = "/home/b0qi/anaconda3/envs/gkh-ashare/bin/python"
MOCK_PACKAGES = PROJECT_ROOT / ".claude-tmp" / "mock_packages"
RAWDATA_META_VERSION = 1
DEFAULT_EVAL_START = "2020-01-01"
DEFAULT_EVAL_END = "2024-12-31"
DEFAULT_EVAL_MODE = "long_short"
DEFAULT_EVAL_NUM_GROUPS = 8
DEFAULT_EVAL_EXECUTION_PRICE_FIELD = "twap_1300_1400"
DEFAULT_EVAL_BENCHMARK_INDEX = "csi1000"
DEFAULT_EVAL_POST_PROCESS_METHOD = "comp"
DEFAULT_EVAL_COMMISSION_RATE = 0.0001
DEFAULT_EVAL_STAMP_TAX_RATE = 0.0


def ensure_project_paths() -> None:
    for path in (ASHARE_ROOT, CASIMIR_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def get_sidecar_path(pkl_path: Path) -> Path:
    return pkl_path.with_suffix(".meta.json")


def _enum_value(value):
    return getattr(value, "value", value)


def build_rawdata_export_metadata(
    definition,
    output_name: str,
    *,
    source_path: Optional[str] = None,
    observed_start: Optional[str] = None,
    observed_end: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "schema": "ashare_rawdata_export_metadata",
        "schema_version": RAWDATA_META_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(),
        "definition_name": definition.name,
        "output_name": output_name,
        "output_names": list(definition.output_names),
        "input_names": list(definition.input_names),
        "input_time_filter": list(definition.params.input_time_filter),
        "data_available_at": int(definition.data_available_at),
        "execution_start_at": (
            int(definition.execution_start_at)
            if definition.execution_start_at is not None else None
        ),
        "execution_end_at": (
            int(definition.execution_end_at)
            if definition.execution_end_at is not None else None
        ),
        "expected_bars": definition.expected_bars,
        "completeness_policy": _enum_value(definition.completeness_policy),
        "price_basis": _enum_value(definition.price_basis),
        "source_path": source_path,
        "observed_start": observed_start,
        "observed_end": observed_end,
    }


def write_rawdata_sidecar(pkl_path: Path, metadata: Dict[str, Any]) -> Path:
    sidecar_path = get_sidecar_path(pkl_path)
    sidecar_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sidecar_path


def load_rawdata_sidecar(pkl_path: Path) -> Optional[Dict[str, Any]]:
    sidecar_path = get_sidecar_path(pkl_path)
    if not sidecar_path.exists():
        return None
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    payload.setdefault("metadata_source", "sidecar")
    payload.setdefault("sidecar_path", str(sidecar_path))
    return payload


@lru_cache(maxsize=1)
def _registry_definitions_by_output_name() -> Dict[str, list]:
    ensure_project_paths()
    from ashare_hf_variable.registry import list_definitions

    mapping: Dict[str, list] = {}
    for definition in list_definitions():
        for output_name in definition.output_names:
            mapping.setdefault(output_name, []).append(definition)
    return mapping


def load_registry_metadata_for_field(output_name: str) -> Optional[Dict[str, Any]]:
    try:
        matches = _registry_definitions_by_output_name().get(output_name, [])
    except Exception:
        return None
    if not matches:
        return None

    definition = matches[0]
    payload = build_rawdata_export_metadata(definition, output_name)
    payload["metadata_source"] = "registry"
    if len(matches) > 1:
        payload["metadata_ambiguous_matches"] = [m.name for m in matches]
    return payload


def resolve_rawdata_metadata(pkl_path: Path) -> Optional[Dict[str, Any]]:
    sidecar = load_rawdata_sidecar(pkl_path)
    if sidecar is not None:
        return sidecar
    return load_registry_metadata_for_field(pkl_path.stem)


def infer_rawdata_t_plus_n(
    metadata: Optional[Dict[str, Any]],
    execution_price_field: str,
    requested_t_plus_n: Optional[int] = None,
    logger=None,
) -> Optional[int]:
    if metadata is None:
        return requested_t_plus_n

    ensure_project_paths()
    from casimir.core.market.data_availability import get_field_timing

    execution_timing = get_field_timing("ashare", "daily", execution_price_field)
    if execution_timing.execution_start_at is None:
        if logger is not None:
            logger.warning(
                "Field '%s' has no execution window, using t_plus_n=1",
                execution_price_field,
            )
        return requested_t_plus_n if requested_t_plus_n is not None else 1

    data_available_at = int(metadata.get("data_available_at") or 0)
    execution_start_at = execution_timing.execution_start_at
    min_t_plus_n = 1 if data_available_at > execution_start_at else 0

    if requested_t_plus_n is not None:
        if requested_t_plus_n < min_t_plus_n:
            if logger is not None:
                logger.warning(
                    "Requested t_plus_n=%d is too aggressive (rawdata_available_at=%d, "
                    "execution_start_at=%d). Forced to %d.",
                    requested_t_plus_n,
                    data_available_at,
                    execution_start_at,
                    min_t_plus_n,
                )
            return min_t_plus_n
        return requested_t_plus_n

    if logger is not None:
        logger.info(
            "Auto t_plus_n: rawdata_available_at=%d, execution_start_at=%d, "
            "execution_field=%s -> t_plus_n=%d",
            data_available_at,
            execution_start_at,
            execution_price_field,
            min_t_plus_n,
        )
    return min_t_plus_n


def build_evaluate_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{MOCK_PACKAGES}:{env.get('PYTHONPATH', '')}"
    return env


def is_harmless_evaluate_failure(returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        return False
    text = f"{stdout}\n{stderr}"
    return "update_output_index" in text and "is not in the subpath of" in text
