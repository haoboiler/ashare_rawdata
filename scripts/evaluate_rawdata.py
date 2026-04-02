#!/usr/bin/env python3
"""Project wrapper around shared evaluate.py for raw-data factor files."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

from utils.rawdata_eval import (
    DEFAULT_EVAL_BENCHMARK_INDEX,
    DEFAULT_EVAL_COMMISSION_RATE,
    DEFAULT_EVAL_END,
    DEFAULT_EVAL_EXECUTION_PRICE_FIELD,
    DEFAULT_EVAL_MODE,
    DEFAULT_EVAL_NUM_GROUPS,
    DEFAULT_EVAL_POST_PROCESS_METHOD,
    DEFAULT_EVAL_START,
    DEFAULT_EVAL_STAMP_TAX_RATE,
    EVALUATE_PY,
    EVALUATE_PYTHON,
    PROJECT_ROOT,
    build_evaluate_env,
    infer_rawdata_t_plus_n,
    is_harmless_evaluate_failure,
    resolve_rawdata_metadata,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate raw-data pkl files with project defaults and timing metadata",
    )
    parser.add_argument(
        "--file",
        action="append",
        required=True,
        help="Raw-data pkl file to evaluate; can be repeated",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. For multiple files, subdirectories are created under it.",
    )
    parser.add_argument("--start", default=DEFAULT_EVAL_START)
    parser.add_argument("--end", default=DEFAULT_EVAL_END)
    parser.add_argument("--mode", default=DEFAULT_EVAL_MODE, choices=["long_only", "long_short"])
    parser.add_argument("--num-groups", type=int, default=DEFAULT_EVAL_NUM_GROUPS)
    parser.add_argument("--post-process-method", default=DEFAULT_EVAL_POST_PROCESS_METHOD)
    parser.add_argument("--execution-price-field", default=DEFAULT_EVAL_EXECUTION_PRICE_FIELD)
    parser.add_argument("--benchmark-index", default=DEFAULT_EVAL_BENCHMARK_INDEX)
    parser.add_argument("--commission-rate", type=float, default=DEFAULT_EVAL_COMMISSION_RATE)
    parser.add_argument("--stamp-tax-rate", type=float, default=DEFAULT_EVAL_STAMP_TAX_RATE)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--t-plus-n", type=int, default=None,
                        help="Explicit override. By default wrapper derives it from sidecar/registry metadata.")
    parser.add_argument("--python", default=EVALUATE_PYTHON,
                        help="Python interpreter used to run shared evaluate.py")
    parser.add_argument("--evaluate-py", default=str(EVALUATE_PY),
                        help="Path to shared evaluate.py")
    parser.add_argument("--show-command", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--neutralize", dest="neutralize", action="store_true",
                        help="Enable neutralized evaluation (default: enabled)")
    parser.add_argument("--no-neutralize", dest="neutralize", action="store_false",
                        help="Disable neutralized evaluation")
    parser.set_defaults(neutralize=True)
    return parser


def _resolve_output_dir(base: Path, pkl_path: Path, multi_file: bool, exact_single: bool) -> Path:
    if exact_single and not multi_file:
        return base
    if multi_file:
        return base / pkl_path.stem
    return base / pkl_path.stem


def _build_command(args, pkl_path: Path, output_dir: Path, passthrough, t_plus_n):
    cmd = [
        args.python,
        args.evaluate_py,
        "--file", str(pkl_path),
        "--start", args.start,
        "--end", args.end,
        "--mode", args.mode,
        "--num-groups", str(args.num_groups),
        "--post-process-method", args.post_process_method,
        "--execution-price-field", args.execution_price_field,
        "--benchmark-index", args.benchmark_index,
        "--commission-rate", str(args.commission_rate),
        "--stamp-tax-rate", str(args.stamp_tax_rate),
        "--output-dir", str(output_dir),
    ]
    if args.quick:
        cmd.append("--quick")
    if args.neutralize:
        cmd.append("--neutralize")
    if t_plus_n is not None:
        cmd.extend(["--t-plus-n", str(t_plus_n)])
    cmd.extend(passthrough)
    return cmd


def _run_one(args, pkl_path: Path, output_dir: Path, passthrough):
    metadata = resolve_rawdata_metadata(pkl_path)
    t_plus_n = infer_rawdata_t_plus_n(
        metadata,
        args.execution_price_field,
        requested_t_plus_n=args.t_plus_n,
    )
    metadata_source = metadata.get("metadata_source") if metadata else None

    cmd = _build_command(args, pkl_path, output_dir, passthrough, t_plus_n)
    if args.show_command:
        print("Command:", " ".join(shlex.quote(c) for c in cmd))
    print(
        f"[Evaluate] {pkl_path.name} | output={output_dir} | "
        f"t_plus_n={t_plus_n if t_plus_n is not None else 'evaluate_default'} | "
        f"metadata={metadata_source or 'none'}"
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=build_evaluate_env(),
        cwd=str(PROJECT_ROOT),
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)

    success = (
        result.returncode == 0
        or is_harmless_evaluate_failure(result.returncode, result.stdout, result.stderr)
    )
    if not success:
        return {
            "file": str(pkl_path),
            "output_dir": str(output_dir),
            "ok": False,
            "t_plus_n": t_plus_n,
            "metadata_source": metadata_source,
            "returncode": result.returncode,
        }

    if result.returncode != 0:
        print("[Evaluate] Ignored harmless update_output_index error")

    return {
        "file": str(pkl_path),
        "output_dir": str(output_dir),
        "ok": True,
        "t_plus_n": t_plus_n,
        "metadata_source": metadata_source,
        "returncode": result.returncode,
    }


def main() -> int:
    parser = build_parser()
    args, passthrough = parser.parse_known_args()

    files = [Path(p).resolve() for p in args.file]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        parser.error(f"file not found: {missing[0]}")

    multi_file = len(files) > 1
    exact_single_output = args.output_dir is not None
    if args.output_dir:
        base_output_dir = Path(args.output_dir).resolve()
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        base_output_dir = PROJECT_ROOT / ".claude-output" / "evaluations" / "rawdata_wrapper" / timestamp

    results = []
    for pkl_path in files:
        output_dir = _resolve_output_dir(
            base_output_dir,
            pkl_path,
            multi_file,
            exact_single_output,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        result = _run_one(args, pkl_path, output_dir, passthrough)
        results.append(result)
        if not result["ok"] and args.fail_fast:
            break

    failed = [r for r in results if not r["ok"]]
    print("\nSummary")
    for result in results:
        status = "OK" if result["ok"] else "FAIL"
        print(
            f"  {status} {Path(result['file']).name}: "
            f"t_plus_n={result['t_plus_n']} metadata={result['metadata_source']} "
            f"-> {result['output_dir']}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
