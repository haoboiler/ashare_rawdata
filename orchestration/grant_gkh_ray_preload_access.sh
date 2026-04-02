#!/usr/bin/env bash
set -euo pipefail

USER_NAME="gkh_ray"

if ! id -u "$USER_NAME" >/dev/null 2>&1; then
  echo "User $USER_NAME does not exist yet" >&2
  exit 1
fi

setfacl -m "u:${USER_NAME}:x" /home/gkh
setfacl -Rm "u:${USER_NAME}:rX" /home/gkh/claude_tasks/ashare_rawdata
setfacl -Rm "u:${USER_NAME}:rX" /home/gkh/ashare

echo "Granted read/execute access for $USER_NAME to project code and /home/gkh traversal"
