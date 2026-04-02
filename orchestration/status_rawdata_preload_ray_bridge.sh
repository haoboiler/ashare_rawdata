#!/usr/bin/env bash
umask 0002
set -euo pipefail

ROOT="/home/gkh/claude_tasks/ashare_rawdata"
cd "$ROOT"

source orchestration/researcher_runtime_env.sh

python3 - <<'PY'
import json
import os

import ray

from scripts.utils.preload_ray import (
    PRELOAD_RAY_ACTOR,
    PRELOAD_RAY_NAMESPACE,
    repair_preload_bridge_lockfiles,
)

address = os.environ.get("ASHARE_RAWDATA_PRELOAD_RAY_ADDRESS", "").strip()
print(f"bridge_address={address or 'unconfigured'}")
print("bridge_owner=gkh_ray")

if not address:
    print("ray_status=unconfigured")
    raise SystemExit(0)

repair_preload_bridge_lockfiles()

try:
    ray.init(address=address, namespace=PRELOAD_RAY_NAMESPACE, log_to_driver=False)
except Exception as exc:
    print("ray_status=down")
    print(f"error={exc}")
    raise SystemExit(0)

print("ray_status=running")
try:
    actor = ray.get_actor(PRELOAD_RAY_ACTOR, namespace=PRELOAD_RAY_NAMESPACE)
    info = ray.get(actor.get_preload_info.remote())
    meta = ray.get(actor.get_metadata.remote())
    payload = {
        "status": info.get("status"),
        "loaded": info.get("stats", {}).get("loaded"),
        "total": info.get("stats", {}).get("total"),
        "fields": info.get("fields"),
        "symbol_source": info.get("symbol_source"),
        "trading_days": len(meta.get("trading_days", [])),
        "symbols": len(meta.get("symbols", [])),
        "loaded_at": info.get("loaded_at"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
except Exception as exc:
    print(f"actor_status_error={exc}")
finally:
    ray.shutdown()
PY
