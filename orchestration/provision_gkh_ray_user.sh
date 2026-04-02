#!/usr/bin/env bash
set -euo pipefail

USER_NAME="gkh_ray"
USER_HOME="/home/${USER_NAME}"

if ! id -u "$USER_NAME" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$USER_NAME"
fi

mkdir -p \
  "$USER_HOME/.config/ashare_rawdata/preload_ray" \
  "$USER_HOME/.cache/ashare_rawdata_preload_ray" \
  "$USER_HOME/.local/state/ashare_rawdata"

chown -R "$USER_NAME:$USER_NAME" \
  "$USER_HOME/.config/ashare_rawdata" \
  "$USER_HOME/.cache/ashare_rawdata_preload_ray" \
  "$USER_HOME/.local/state/ashare_rawdata"
