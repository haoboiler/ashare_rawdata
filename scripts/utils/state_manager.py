#!/usr/bin/env python3
"""
状态文件管理工具 — 带文件锁的 YAML 原子读写

Multi-Agent 系统中多个进程可能同时访问状态文件，
本模块通过 fcntl.flock 提供并发安全的读写操作。

Usage:
    from scripts.utils.state_manager import read_state, update_state, append_to_log

    # 读取状态
    state = read_state('orchestration/state/agent_states/ashare_rawdata_a.yaml')

    # 原子更新
    update_state('orchestration/state/agent_states/ashare_rawdata_a.yaml', {
        'status': 'in_progress',
        'current_direction_id': 'D-001',
    })

    # 向 EXPERIMENT-LOG.md 追加内容（带锁）
    append_to_log('research/EXPERIMENT-LOG.md', new_section_text)

测试:
    python scripts/utils/state_manager.py --test
"""

import fcntl
import os
import sys
import tempfile
import time
import yaml
from contextlib import contextmanager
from datetime import datetime


# === 文件锁 ===

@contextmanager
def file_lock(filepath, timeout=30):
    """
    基于 fcntl.flock 的文件锁。

    Args:
        filepath: 要锁定的文件路径（会创建 .lock 文件）
        timeout: 超时时间（秒）

    Raises:
        TimeoutError: 超时未获取到锁
    """
    lock_path = filepath + '.lock'
    lock_fd = None
    start = time.time()

    try:
        lock_fd = open(lock_path, 'w')
        while True:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_fd.write(f"pid={os.getpid()} time={datetime.now().isoformat()}\n")
                lock_fd.flush()
                break
            except (IOError, OSError):
                if time.time() - start > timeout:
                    raise TimeoutError(
                        f"无法在 {timeout}s 内获取文件锁: {lock_path}"
                    )
                time.sleep(0.1)

        yield lock_fd

    finally:
        if lock_fd:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                pass


# === YAML 状态操作 ===

def read_state(filepath: str) -> dict:
    """读取 YAML 状态文件。文件不存在则返回空字典。"""
    if not os.path.exists(filepath):
        return {}

    with file_lock(filepath):
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
    return data or {}


def update_state(filepath: str, updates: dict, merge: bool = True):
    """原子更新 YAML 状态文件。"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with file_lock(filepath):
        if merge and os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {}

        data.update(updates)
        data['_last_updated'] = datetime.now().isoformat()

        dir_name = os.path.dirname(filepath) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.yaml.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            os.rename(tmp_path, filepath)
        except Exception:
            os.unlink(tmp_path)
            raise


def write_state(filepath: str, data: dict):
    """完全覆写 YAML 状态文件。"""
    update_state(filepath, data, merge=False)


# === Markdown 日志追加 ===

def append_to_log(filepath: str, section: str, marker: str = None):
    """
    向 Markdown 日志文件追加内容（带锁）。

    Args:
        filepath: 日志文件路径
        section: 要追加的内容（Markdown 格式）
        marker: 可选，在此标记之前插入；为 None 则追加到文件末尾
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"日志文件不存在: {filepath}")

    with file_lock(filepath):
        with open(filepath, 'r') as f:
            content = f.read()

        timestamped = f"\n<!-- Agent append: {datetime.now().isoformat()} -->\n{section}\n"

        if marker and marker in content:
            content = content.replace(marker, timestamped + marker)
        else:
            content = content + timestamped

        dir_name = os.path.dirname(filepath) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.md.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(content)
            os.rename(tmp_path, filepath)
        except Exception:
            os.unlink(tmp_path)
            raise


# === 方向池操作 ===

def claim_direction(pool_path: str, agent_id: str) -> dict:
    """从方向池中认领一个最高优先级的可用方向。无可用方向时返回 None。"""
    priority_order = {'highest': 0, 'high': 1, 'medium': 2, 'low': 3}

    with file_lock(pool_path):
        with open(pool_path, 'r') as f:
            pool = yaml.safe_load(f) or {}

        directions = pool.get('directions', [])
        available = [d for d in directions if d.get('status') == 'available']
        if not available:
            return None

        available.sort(key=lambda d: priority_order.get(d.get('priority', 'low'), 99))
        chosen = available[0]

        chosen['status'] = 'claimed'
        chosen['claimed_by'] = agent_id
        chosen['claimed_at'] = datetime.now().isoformat()

        dir_name = os.path.dirname(pool_path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.yaml.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                yaml.dump(pool, f, default_flow_style=False, allow_unicode=True)
            os.rename(tmp_path, pool_path)
        except Exception:
            os.unlink(tmp_path)
            raise

    return chosen


def release_direction(pool_path: str, direction_id: str, new_status: str = 'available'):
    """释放一个方向（完成或放弃时调用）。"""
    with file_lock(pool_path):
        with open(pool_path, 'r') as f:
            pool = yaml.safe_load(f) or {}

        for d in pool.get('directions', []):
            if d.get('id') == direction_id:
                d['status'] = new_status
                d.pop('claimed_by', None)
                d.pop('claimed_at', None)
                break

        dir_name = os.path.dirname(pool_path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.yaml.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                yaml.dump(pool, f, default_flow_style=False, allow_unicode=True)
            os.rename(tmp_path, pool_path)
        except Exception:
            os.unlink(tmp_path)
            raise


# === 测试 ===

def _test():
    """简单的自检测试"""
    import tempfile as tf

    print("=== state_manager 自检测试 ===\n")

    with tf.NamedTemporaryFile(suffix='.yaml', delete=False, mode='w') as f:
        tmp = f.name
        yaml.dump({'a': 1, 'b': 'hello'}, f)

    try:
        data = read_state(tmp)
        assert data['a'] == 1, f"读取失败: {data}"
        print("  [PASS] read_state")

        update_state(tmp, {'c': 3, 'b': 'world'})
        data = read_state(tmp)
        assert data['a'] == 1 and data['b'] == 'world' and data['c'] == 3
        print("  [PASS] update_state (merge)")

        write_state(tmp, {'x': 99})
        data = read_state(tmp)
        assert 'a' not in data and data['x'] == 99
        print("  [PASS] write_state (overwrite)")
    finally:
        os.unlink(tmp)
        for ext in ['.lock', '.yaml.tmp']:
            p = tmp + ext
            if os.path.exists(p):
                os.unlink(p)

    with tf.NamedTemporaryFile(suffix='.yaml', delete=False, mode='w') as f:
        tmp_pool = f.name
        yaml.dump({
            'directions': [
                {'id': 'D-001', 'name': 'test_a', 'priority': 'high', 'status': 'available'},
                {'id': 'D-002', 'name': 'test_b', 'priority': 'highest', 'status': 'available'},
            ]
        }, f)

    try:
        chosen = claim_direction(tmp_pool, 'ashare_rawdata_a')
        assert chosen['id'] == 'D-002'
        print("  [PASS] claim_direction (highest priority)")

        chosen2 = claim_direction(tmp_pool, 'ashare_rawdata_b')
        assert chosen2['id'] == 'D-001'
        print("  [PASS] claim_direction (next available)")

        chosen3 = claim_direction(tmp_pool, 'ashare_rawdata_c')
        assert chosen3 is None
        print("  [PASS] claim_direction (none available)")

        release_direction(tmp_pool, 'D-002', 'exhausted')
        pool = read_state(tmp_pool)
        d002 = [d for d in pool['directions'] if d['id'] == 'D-002'][0]
        assert d002['status'] == 'exhausted'
        print("  [PASS] release_direction")
    finally:
        os.unlink(tmp_pool)
        for ext in ['.lock', '.yaml.tmp']:
            p = tmp_pool + ext
            if os.path.exists(p):
                os.unlink(p)

    print("\n=== 全部测试通过 ===")


if __name__ == '__main__':
    if '--test' in sys.argv:
        _test()
    else:
        print("Usage: python scripts/utils/state_manager.py --test")
