#!/usr/bin/env python3
"""Compare pilot raw_value outputs with legacy feature fields where available."""

from __future__ import annotations

import argparse
import json
from typing import Dict

import pandas as pd
import arcticdb


ARCTIC_URL = "s3://192.168.2.180:arctic?access=bookdisco&secret=bookdiscono1&port=8122"
RAW_VALUE_LIB = "ashare@stock@raw_value@1d"
FEATURE_LIB = "ashare@stock@feature@1d"

PILOT_TO_LEGACY = {
    "twap_0930_1030_v1": "twap_0930_1030",
    "vwap_0930_1030_v1": "vwap_0930_1030",
}


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df.sort_index()


def _read_field(lib, field: str) -> pd.DataFrame:
    return _normalize(lib.read(field).data)


def compare_pair(new_df: pd.DataFrame, legacy_df: pd.DataFrame) -> Dict[str, object]:
    common_index = new_df.index.intersection(legacy_df.index)
    common_columns = new_df.columns.intersection(legacy_df.columns)

    if len(common_index) == 0 or len(common_columns) == 0:
        return {
            "comparable": False,
            "reason": "no overlapping dates or symbols",
        }

    lhs = new_df.loc[common_index, common_columns].sort_index().sort_index(axis=1)
    rhs = legacy_df.loc[common_index, common_columns].sort_index().sort_index(axis=1)

    diff = (lhs - rhs).abs()
    diff_stack = diff.stack(future_stack=True).dropna()

    if diff_stack.empty:
        return {
            "comparable": True,
            "overlap_dates": len(common_index),
            "overlap_symbols": len(common_columns),
            "points": 0,
            "max_abs_diff": 0.0,
            "mean_abs_diff": 0.0,
        }

    return {
        "comparable": True,
        "overlap_dates": len(common_index),
        "overlap_symbols": len(common_columns),
        "points": int(diff_stack.shape[0]),
        "max_abs_diff": float(diff_stack.max()),
        "mean_abs_diff": float(diff_stack.mean()),
        "sample_worst": {
            "date": str(diff_stack.idxmax()[0].date()),
            "symbol": diff_stack.idxmax()[1],
            "abs_diff": float(diff_stack.max()),
            "new_value": float(lhs.loc[diff_stack.idxmax()[0], diff_stack.idxmax()[1]]),
            "legacy_value": float(rhs.loc[diff_stack.idxmax()[0], diff_stack.idxmax()[1]]),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare pilot raw_value outputs with legacy features")
    parser.add_argument("--print-json", action="store_true", help="Print JSON instead of text summary")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ac = arcticdb.Arctic(ARCTIC_URL)
    raw_lib = ac.get_library(RAW_VALUE_LIB, create_if_missing=False)
    feature_lib = ac.get_library(FEATURE_LIB, create_if_missing=False)

    raw_fields = set(raw_lib.list_symbols())
    feature_fields = set(feature_lib.list_symbols())

    result = {}
    for new_field, legacy_field in PILOT_TO_LEGACY.items():
        if new_field not in raw_fields:
            result[new_field] = {"present": False, "reason": "raw_value field missing"}
            continue

        new_df = _read_field(raw_lib, new_field)
        payload = {
            "present": True,
            "rows": int(new_df.shape[0]),
            "symbols": int(new_df.shape[1]),
        }

        if legacy_field not in feature_fields:
            payload["legacy_present"] = False
            payload["legacy_field"] = legacy_field
            payload["note"] = "no like-for-like legacy feature field"
            result[new_field] = payload
            continue

        legacy_df = _read_field(feature_lib, legacy_field)
        payload["legacy_present"] = True
        payload["legacy_field"] = legacy_field
        payload["comparison"] = compare_pair(new_df, legacy_df)
        result[new_field] = payload

    if args.print_json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0

    for field, payload in result.items():
        print(f"[{field}]")
        for key, value in payload.items():
            print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
