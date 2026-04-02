#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/gkh/claude_tasks/ashare_rawdata"
cd "$ROOT"

python3 - <<'PY'
from scripts.utils.preload_ray import (
    PRELOAD_RAY_ADDRESS,
    PRELOAD_RAY_METADATA_PATH,
    PRELOAD_RAY_SESSION_NAME,
    load_preload_ray_record,
)

record = load_preload_ray_record() or {}
print(f"session_name={PRELOAD_RAY_SESSION_NAME}")
print(f"configured_address={record.get('address', PRELOAD_RAY_ADDRESS)}")
print(f"metadata_path={PRELOAD_RAY_METADATA_PATH}")
print(f"temp_dir={record.get('temp_dir', 'unconfigured')}")
print(f"namespace={record.get('namespace', 'unconfigured')}")
print(f"actor_name={record.get('actor_name', 'unconfigured')}")
print(f"log_path={record.get('log_path', 'unconfigured')}")
PY

if tmux has-session -t "$(python3 - <<'PY'
from scripts.utils.preload_ray import PRELOAD_RAY_SESSION_NAME
print(PRELOAD_RAY_SESSION_NAME)
PY
)" 2>/dev/null; then
  echo "tmux_session=running"
else
  echo "tmux_session=missing"
fi

ADDRESS="$(python3 - <<'PY'
from scripts.utils.preload_ray import resolve_preload_ray_address
try:
    print(resolve_preload_ray_address(require_exists=False))
except Exception:
    print("")
PY
)"

if [ -n "$ADDRESS" ] && ray status --address "$ADDRESS" >/dev/null 2>&1; then
  echo "ray_status=running"
  ray status --address "$ADDRESS" | head -n 20
else
  echo "ray_status=down"
fi
