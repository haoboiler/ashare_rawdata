#!/usr/bin/env bash

# Dedicated-user preload bridge:
# researchers still run as gkh, but explicit preload-aware commands
# connect to the gkh_ray-owned screening Ray cluster only inside this wrapper.
umask 0002
export ASHARE_RAWDATA_PRELOAD_RAY_ADDRESS="127.0.0.1:43680"
export ASHARE_RAWDATA_PRELOAD_RAY_RUNTIME_DIR="/home/gkh_ray/rp"
export ASHARE_RAWDATA_RESEARCHER_MODE="1"
