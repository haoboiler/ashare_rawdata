"""
admit_gates — 可插拔相关性检测 Gate

参照 ashare_alpha 的 admit_gates 架构：
  - 统一 GateResult 返回类型
  - 每个 gate 实现 check_gate() 接口
  - evaluation.yaml 中配置默认 gate 和阈值
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GateResult:
    """所有 gate 模块统一返回类型"""
    admitted: bool
    reason: str                          # 人类可读说明
    metrics: dict = field(default_factory=dict)  # gate-specific 数值
    raw_result: Any = None               # 原始结果对象
