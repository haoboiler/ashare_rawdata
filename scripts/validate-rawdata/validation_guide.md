# Raw-Data 入库后验证指南

本文档指导如何对新入库的 raw-data bundle 进行数据质量验证。

## 工具文件

`scripts/validate-rawdata/validate_rawdata_bundle.py` 提供三个工具函数，可在 Python 交互环境或脚本中调用。

## 验证项目

### 1. 价格范围检查

**适用场景**: bundle 中包含类价格字段（如 twap, vwap），检查其值是否落在当日日线 [low, high] 范围内。

```python
import sys
sys.path.insert(0, "/home/gkh/claude_tasks/ashare_rawdata/scripts/validate-rawdata")
from validate_rawdata_bundle import check_price_range

check_price_range("twap_0930_1030")
check_price_range("vwap_0930_1030")
```

**判断标准**:
- 上午窗口（0930_1030, 0930_1130）: 异常数应极少（< 0.001%）
- 下午/全天窗口（1300_1400, 0930_1130_1300_1457）: 可能出现 0.1% 左右的越界，**已确认为日线数据源问题**（近期日线 high/low 可能仅反映上午数据），非计算错误
- 常见可解释的异常: daily high=low（停牌/复权异常）

### 2. 覆盖率检查

**适用场景**: 所有 bundle，对比 daily close 检查覆盖完整性。

```python
from validate_rawdata_bundle import check_coverage

fields = [...]  # bundle 的所有 output fields
check_coverage(fields)
```

**关注点**:
- 覆盖率: 当天有 daily close 的股票中，有多少有 raw-data 值。一般应 > 99%
- 缺失: 有 close 但无 raw-data，少量缺失正常（停牌、数据缺失、corr 类方差为零等）
- **无 close 有值**: 当天没有 daily close 却有 raw-data 值 → 异常，应为 0

### 3. 极端值检查

**适用场景**: 所有 bundle，扫描 inf/-inf 和极端值。

```python
from validate_rawdata_bundle import check_extremes

check_extremes(fields)
```

**判断标准**:
- inf/-inf 数量应为 **0**，如果出现说明 formula 有除零等 bug
- min/max 应在合理范围内:
  - 价格类（twap/vwap）: ~1 到 ~100000（后复权）
  - 相关系数类: [-1, 1]
  - 比率类（cv, concentration, imbalance）: 检查是否在理论值域内
  - 绝对量类（volume_std）: 与股票成交量级相关，大值不一定异常

## 验证流程

对新入库的 bundle 执行以下步骤:

```python
import sys
sys.path.insert(0, "/home/gkh/claude_tasks/ashare_rawdata/scripts/validate-rawdata")
sys.path.insert(0, "/home/gkh/ashare/casimir_ashare")
from validate_rawdata_bundle import check_price_range, check_coverage, check_extremes
from casimir.core.ashare_rawdata.registry import list_definitions
import re

bundle_name = "pv_stats_0930_1030"  # 替换为目标 bundle
defs = [d for d in list_definitions() if d.name == bundle_name]
fields = list(defs[0].output_names)

# 1. 价格范围检查（仅对纯 twap/vwap 字段）
price_fields = [f for f in fields if re.match(r'^(twap|vwap)_\d{4}_\d{4}', f)]
for f in price_fields:
    check_price_range(f)

# 2. 覆盖率
check_coverage(fields)

# 3. 极端值
check_extremes(fields)
```

## 验证报告

验证完成后，将结果整理为 md 文件保存到对应 bundle 的目录下:
- `research/basic_rawdata/pv_stats/validation_pv_stats_0930_1030.md`
- `research/basic_rawdata/volatility/validation_volatility_0930_1030.md`
