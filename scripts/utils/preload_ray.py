from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    return Path(value).expanduser()

PRELOAD_RAY_ACTOR = "ashare_rawdata_preload"
PRELOAD_RAY_NAMESPACE = "ashare_rawdata_preload"
PRELOAD_RAY_SESSION_NAME = os.environ.get(
    "ASHARE_RAWDATA_PRELOAD_RAY_SESSION_NAME",
    "ashare_rawdata_preload_ray",
)

PRELOAD_RAY_HOST = os.environ.get("ASHARE_RAWDATA_PRELOAD_RAY_HOST", "127.0.0.1")
PRELOAD_RAY_PORT = _env_int("ASHARE_RAWDATA_PRELOAD_RAY_PORT", 27680)
PRELOAD_RAY_ADDRESS = f"{PRELOAD_RAY_HOST}:{PRELOAD_RAY_PORT}"

PRELOAD_RAY_OBJECT_STORE_BYTES = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_OBJECT_STORE_BYTES",
    200_000_000_000,
)
PRELOAD_RAY_BASE_DIR = _env_path(
    "ASHARE_RAWDATA_PRELOAD_RAY_BASE_DIR",
    PROJECT_ROOT / ".claude-tmp" / "ray_preload_cluster",
)
PRELOAD_RAY_RUNTIME_DIR = _env_path(
    "ASHARE_RAWDATA_PRELOAD_RAY_RUNTIME_DIR",
    Path("/home/gkh/.cache/ashare_rawdata_preload_ray"),
)
PRELOAD_RAY_ADDRESS_PATH = _env_path(
    "ASHARE_RAWDATA_PRELOAD_RAY_ADDRESS_FILE",
    PRELOAD_RAY_BASE_DIR / "address",
)
PRELOAD_RAY_METADATA_PATH = _env_path(
    "ASHARE_RAWDATA_PRELOAD_RAY_METADATA_PATH",
    PRELOAD_RAY_BASE_DIR / "cluster.json",
)
PRELOAD_RAY_LOG_PATH = _env_path(
    "ASHARE_RAWDATA_PRELOAD_RAY_LOG_PATH",
    PROJECT_ROOT / "orchestration" / "logs" / "ray_preload_isolated.log",
)

PRELOAD_RAY_MIN_WORKER_PORT = _env_int("ASHARE_RAWDATA_PRELOAD_RAY_MIN_WORKER_PORT", 27800)
PRELOAD_RAY_MAX_WORKER_PORT = _env_int("ASHARE_RAWDATA_PRELOAD_RAY_MAX_WORKER_PORT", 28799)
PRELOAD_RAY_DASHBOARD_AGENT_LISTEN_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_DASHBOARD_AGENT_LISTEN_PORT",
    27790,
)
PRELOAD_RAY_DASHBOARD_AGENT_GRPC_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_DASHBOARD_AGENT_GRPC_PORT",
    27791,
)
PRELOAD_RAY_RUNTIME_ENV_AGENT_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_RUNTIME_ENV_AGENT_PORT",
    27792,
)
PRELOAD_RAY_METRICS_EXPORT_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_METRICS_EXPORT_PORT",
    27793,
)
PRELOAD_RAY_DASHBOARD_PORT = _env_int("ASHARE_RAWDATA_PRELOAD_RAY_DASHBOARD_PORT", 27794)
PRELOAD_RAY_DASHBOARD_GRPC_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_DASHBOARD_GRPC_PORT",
    27795,
)
PRELOAD_RAY_AUTOSCALER_METRIC_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_AUTOSCALER_METRIC_PORT",
    27796,
)
PRELOAD_RAY_DASHBOARD_METRIC_PORT = _env_int(
    "ASHARE_RAWDATA_PRELOAD_RAY_DASHBOARD_METRIC_PORT",
    27797,
)


def ensure_preload_ray_dirs() -> None:
    for path in (PRELOAD_RAY_BASE_DIR, PRELOAD_RAY_RUNTIME_DIR, PRELOAD_RAY_LOG_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)
    for path in (PRELOAD_RAY_BASE_DIR, PRELOAD_RAY_RUNTIME_DIR):
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass


def build_preload_ray_record(address: str = PRELOAD_RAY_ADDRESS) -> Dict[str, object]:
    return {
        "address": address,
        "host": PRELOAD_RAY_HOST,
        "port": PRELOAD_RAY_PORT,
        "namespace": PRELOAD_RAY_NAMESPACE,
        "actor_name": PRELOAD_RAY_ACTOR,
        "session_name": PRELOAD_RAY_SESSION_NAME,
        "temp_dir": str(PRELOAD_RAY_RUNTIME_DIR),
        "address_file": str(PRELOAD_RAY_ADDRESS_PATH),
        "log_path": str(PRELOAD_RAY_LOG_PATH),
        "object_store_bytes": PRELOAD_RAY_OBJECT_STORE_BYTES,
        "ports": {
            "port": PRELOAD_RAY_PORT,
            "min_worker_port": PRELOAD_RAY_MIN_WORKER_PORT,
            "max_worker_port": PRELOAD_RAY_MAX_WORKER_PORT,
            "dashboard_agent_listen_port": PRELOAD_RAY_DASHBOARD_AGENT_LISTEN_PORT,
            "dashboard_agent_grpc_port": PRELOAD_RAY_DASHBOARD_AGENT_GRPC_PORT,
            "runtime_env_agent_port": PRELOAD_RAY_RUNTIME_ENV_AGENT_PORT,
            "metrics_export_port": PRELOAD_RAY_METRICS_EXPORT_PORT,
            "dashboard_port": PRELOAD_RAY_DASHBOARD_PORT,
            "dashboard_grpc_port": PRELOAD_RAY_DASHBOARD_GRPC_PORT,
            "autoscaler_metric_port": PRELOAD_RAY_AUTOSCALER_METRIC_PORT,
            "dashboard_metric_port": PRELOAD_RAY_DASHBOARD_METRIC_PORT,
        },
    }


def write_preload_ray_record(address: str = PRELOAD_RAY_ADDRESS) -> Dict[str, object]:
    ensure_preload_ray_dirs()
    record = build_preload_ray_record(address=address)
    PRELOAD_RAY_ADDRESS_PATH.write_text(address + "\n", encoding="utf-8")
    PRELOAD_RAY_METADATA_PATH.write_text(
        json.dumps(record, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    for path in (PRELOAD_RAY_ADDRESS_PATH, PRELOAD_RAY_METADATA_PATH):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return record


def clear_preload_ray_record() -> None:
    for path in (PRELOAD_RAY_ADDRESS_PATH, PRELOAD_RAY_METADATA_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def load_preload_ray_record() -> Optional[Dict[str, object]]:
    if not PRELOAD_RAY_METADATA_PATH.exists():
        return None
    try:
        return json.loads(PRELOAD_RAY_METADATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def resolve_preload_ray_address(*, require_exists: bool = True) -> str:
    explicit = os.environ.get("ASHARE_RAWDATA_PRELOAD_RAY_ADDRESS")
    if explicit:
        return explicit

    address_path = Path(
        os.environ.get(
            "ASHARE_RAWDATA_PRELOAD_RAY_ADDRESS_FILE",
            str(PRELOAD_RAY_ADDRESS_PATH),
        )
    )
    if address_path.exists():
        value = address_path.read_text(encoding="utf-8").strip()
        if value:
            return value

    record = load_preload_ray_record()
    if record and record.get("address"):
        return str(record["address"])

    if require_exists:
        raise RuntimeError(
            "Managed preload Ray address is not configured. "
            "Start it with `bash orchestration/start_rawdata_preload_ray.sh`."
        )

    return PRELOAD_RAY_ADDRESS


def repair_preload_bridge_lockfiles() -> None:
    runtime_dir = _env_path(
        "ASHARE_RAWDATA_PRELOAD_RAY_RUNTIME_DIR",
        PRELOAD_RAY_RUNTIME_DIR,
    )
    if not runtime_dir.exists():
        return

    session_dirs = sorted(runtime_dir.glob("session_*"))
    if not session_dirs:
        return

    session_dir = session_dirs[-1]
    for name in ("node_ip_address.json.lock", "ports_by_node.json.lock"):
        path = session_dir / name
        if path.exists() and not os.access(path, os.W_OK):
            try:
                path.unlink()
            except OSError:
                continue

        if not path.exists():
            try:
                path.touch(exist_ok=True)
            except OSError:
                continue

        try:
            # Ray/FileLock may create these files with a hard-coded 0644 mode.
            # The preload bridge is shared between gkh and gkh_ray, so keep the
            # lock files world-writable to avoid cross-user worker startup races.
            os.chmod(path, 0o666)
        except OSError:
            pass
