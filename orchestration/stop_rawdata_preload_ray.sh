#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/gkh/claude_tasks/ashare_rawdata"
cd "$ROOT"

eval "$(python3 - <<'PY'
from scripts.utils.preload_ray import PRELOAD_RAY_ADDRESS, PRELOAD_RAY_SESSION_NAME
print(f"ADDRESS={PRELOAD_RAY_ADDRESS!r}")
print(f"SESSION_NAME={PRELOAD_RAY_SESSION_NAME!r}")
PY
)"

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
fi

python3 - <<'PY'
from scripts.utils.preload_ray import clear_preload_ray_record
clear_preload_ray_record()
PY

for _ in $(seq 1 10); do
  if ! ray status --address "$ADDRESS" >/dev/null 2>&1; then
    echo "Managed preload Ray stopped"
    exit 0
  fi
  sleep 1
done

echo "Ray process may still be shutting down; verify with status script." >&2
exit 0
