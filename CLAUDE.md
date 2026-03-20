# AShare RawData — A 股高频聚合原始数据挖掘项目

## 项目目的

基于 `casimir_ashare` 量化框架和 `ashare_hf_variable` 注册体系，从 **A 股 1 分钟 K 线数据**中系统性地挖掘和构造**日度级别的 Raw-Data 因子**，目标是：

- **扩充 Raw-Data 库** — 从分钟数据中提炼出有信息量的日度特征
- **增强 Alpha 底层基础** — 强的 Raw-Data 本身即可作为 Alpha 因子，为下游 Alpha 挖掘提供更丰富的原料
- **提高数据质量** — 确保每一个入库的 Raw-Data 都具备可解释性、计算高效性、横截面分类能力

## 研究链路

```
1m K 线数据 → rawdata(本项目) → alpha(ashare_alpha) → model → portfolio
                ↑
             本项目
```

- **输入**：`ashare@stock@kline@1m`（5191 只 A 股，240 bars/天，2020 年起）
- **输出**：入库到 `ashare@stock@raw_value@1d` 的日度矩阵（per-field: index=trade_date, columns=symbols）
- **关联项目**：`ashare_alpha`（下游 Alpha 挖掘，**共享回测体系**）

## 与 Alpha 挖掘的本质区别

| 维度 | Raw-Data 挖掘（本项目） | Alpha 挖掘（ashare_alpha） |
|------|------------------------|--------------------------|
| 数据来源 | 1 分钟 K 线（高频聚合） | Raw-Data + casimir 算子组合 |
| 地位 | 链路最底层，Alpha 的基础原料 | 由 Raw-Data 构建的信号 |
| 计算要求 | **必须** numba 兼容、向量化、快速计算 | 可使用 casimir 公式语言（pandas 级） |
| 可解释性 | **严格要求**，必须有清晰物理含义 | 推荐但非强制 |
| 入库方式 | `ashare_hf_variable` 注册 + staging/publish updater | `register_alpha.py` 写入 ashare_alpha store |
| 评估重点 | 横截面分类能力（window=1） | Sharpe / IC / 分组 |

## 依赖库路径（强制）

| 库 | 路径 | 说明 |
|---|---|---|
| `casimir_ashare` | `/home/gkh/ashare/casimir_ashare` | casimir A 股定制版 |
| `ashare_hf_variable` | `/home/gkh/ashare/ashare_hf_variable` | A 股高频变量注册体系 |

在所有脚本和 notebook 中，**必须在任何 casimir import 之前**插入：

```python
import sys
sys.path.insert(0, '/home/gkh/ashare/casimir_ashare')
```

## 运行环境

- **服务器**: bookdisco
- **Python**: `/home/b0qi/anaconda3/envs/gkh-ashare/bin/python`（执行注册和更新器必须使用此路径）
- **核心依赖**: casimir_ashare, ashare_hf_variable, numpy, pandas, numba, arcticdb
- **数据源**: A 股 1m K 线数据（通过 casimir_ashare/ArcticDB）
- **存储**: ArcticDB (S3) `192.168.2.180:8122` + MongoDB

## 硬约束（不可更改）

| 约束 | 值 | 理由 |
|------|-----|------|
| 输入数据 | `ashare@stock@kline@1m`（1 分钟 OHLCV） | 从分钟聚合到日度是核心任务 |
| 输出频率 | 日度（per-field 矩阵写入 `raw_value@1d`） | 下游 Alpha 和 Model 的标准输入频率 |
| 计算引擎 | **必须 numba 兼容** | 5000+ 只股票 × 240 bars/天，必须保证计算速度 |
| 向量化 | **强制** | 不允许 Python 级循环，必须全程向量化 |
| 可解释性 | **强制** | 每个 Raw-Data 必须有清晰的物理含义 |
| 回测窗口 | **window=1** | 只看 1 天持仓 |
| 评估起始 | **2020-01-01** | 覆盖完整牛熊周期（A 股 1m 数据起始） |
| 评估流程 | **必须跑标准评估**（横截面分类 + PNL） | 不能只看 IC 下结论 |
| **入库审批** | **禁止自行注册到 registry** | 必须按 admission 流程审核，用户确认后才能入库 |
| 产出索引 | 每次向 `.claude-output/` 写入数据后**必须更新** `index.md` | 保证可追溯 |

## 评估标准

> **自动筛选阈值待定** — 等第一批实验数据出来后确定合理阈值。
> 当前使用 TODO 占位。

评估原则（强制）：
1. 从 **2020-01-01** 开始评估，覆盖完整牛熊周期
2. 只评估 **window=1**（1 天持仓）
3. Net Sharpe ≥ **TODO**
4. 必须 numba 全程兼容、有清晰物理含义、有可解释的预期行为
5. 分组单调性 Mono ≥ **TODO**（w1 分组回测单调性评分）

量化阈值（待实验后确定）：

| 指标 | 阈值 | 说明 |
|------|------|------|
| Net Sharpe | TODO | w1 Net Sharpe |
| 分组单调性 Mono | TODO | w1 分组回测单调性评分 |
| FFR 贡献占比 | TODO | \|FFR return\| / \|Gross return\| |

## 共享回测体系

> **强制**：所有 Agent 在执行评估/回测之前，**必须先阅读 `docs/BACKTEST.md`**，确保使用正确的默认参数。

评估脚本：`/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py`（从项目根目录运行确保 .env 生效）

```bash
# ⭐ 标准评估（RawData 强制，window=1）
cd /home/gkh/claude_tasks/ashare_rawdata
python /home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py \
    --file .claude-output/analysis/{feature_name}.pkl \
    --start 2020-01-01 --window 1 --num-groups 5 \
    --execution-price-field twap_1300_1400 \
    --benchmark-index csi1000 \
    --neutralize \
    --output-dir .claude-output/evaluations/{direction}/{feature_name}/
```

### 参数说明

| 参数 | A 股 rawdata 值 | 说明 |
|------|----------------|------|
| `--file` | `.claude-output/analysis/{feat}.pkl` | 因子值 pickle（index=trade_date, columns=symbols） |
| `--start` | `2020-01-01` | 评估起始日期 |
| `--window` | `1` | 持仓周期（1 天） |
| `--num-groups` | `5` | 横截面分组数 |
| `--execution-price-field` | `twap_1300_1400` | 执行价字段 |
| `--benchmark-index` | `csi1000` | 基准指数（中证 1000） |
| `--neutralize` | 启用 | 行业 + 市值中性化 |
| `--fee` | 默认（含佣金+印花税） | A 股交易成本 |
| `--output-dir` | 本项目 `.claude-output/evaluations/` | 评估结果输出目录 |

### 重要规则

1. **从本项目根目录运行**（确保 `.env` 生效）
2. **不要修改 evaluate.py** — 所有修改需先与 ashare_alpha 项目协调，该文件头部注明 "Any AI agent MUST ask the user before modifying this file"
3. 因子值 pickle 格式：`index=trade_date(DatetimeIndex)`, `columns=symbols(str)`, `values=factor_value(float64)`

## 核心工作流

```
物理假设 → 1m 特征设计 → Numba 实现 → 本地计算 pkl → 回测评估 → 入库审批
```

1. **假设驱动设计**：每个特征必须有清晰的物理含义和预期横截面行为
2. **Numba 实现**：`@njit` 装饰器，纯 numpy，显式 NaN 处理
3. **本地计算**：`scripts/compute_rawdata_local.py` 计算因子值导出 pkl（不入库）
4. **评估验证**：使用共享 `evaluate.py` 评估（window=1），根据回测结果判断是否值得入库
5. **入库审批**：通过评估后，`ashare_hf_variable` 注册体系入库（详见 `docs/ASHARE_ADMISSION.md`）

### 本地计算工具

`scripts/compute_rawdata_local.py` — 从注册脚本加载 formula，读取 1m 数据计算因子值，导出为 pkl。

```bash
# 快速验证（100 个 symbol）
python scripts/compute_rawdata_local.py --formula-file {script.py} --quick -o .claude-output/analysis/

# 全量计算
python scripts/compute_rawdata_local.py --formula-file {script.py} -o .claude-output/analysis/

# 从 registry 加载已注册 bundle
python scripts/compute_rawdata_local.py --bundle {bundle_name} -o .claude-output/analysis/
```

输出 pkl 格式与 `evaluate.py --file` 兼容，可直接用于回测。

## 多 Agent 编排系统

本项目支持 Leader + Researcher 自动化挖掘架构：

| 组件 | 路径 | 说明 |
|------|------|------|
| 研究员工作流 | `orchestration/prompts/researcher.md` | 完整自动研究+评估流程 |
| 组长手册 | `orchestration/prompts/lead.md` | 启动/停止/审批/监控研究员 |
| 外部循环 | `orchestration/researcher_wrapper.sh` | tmux 启动，预算管控+冷却+重启 |
| 方向池 | `orchestration/state/direction_pool.yaml` | 研究方向（可扩展） |
| 运行配置 | `orchestration/config.yaml` | TG token、预算、评估参数 |
| KB 生成器 | `scripts/regenerate_kb.py` | 从实验日志+方向池自动生成 KB |

## 知识检索规范（三层架构）

> 启动研究任务时，按 **Layer 0 → Layer 1 → Layer 2** 递进阅读，避免重复已排除方向。
> 详见 `docs/THREE-LAYER-GUIDE.md`

| 层级 | 文件 | 说明 |
|------|------|------|
| Layer 0 | `research/KNOWLEDGE-BASE.md` | 自动生成摘要（已注册 RawData + 结论 + 方向池） |
| Layer 1 | `research/EXPERIMENT-LOG.md` | 实验登记簿（已验证结论 + 已排除方向 + 实验记录） |
| Layer 2 | `.claude-output/` 下各文件 | 原始评估报告/数据（按需跳转） |
| 参考 | `docs/ASHARE_ADMISSION.md` | A 股 RawData 入库完整流程（10 节） |

**规则**: 已排除方向中的内容**绝对不重复研究**。

## 环境配置

### .env 配置（强制）

项目根目录需创建 `.env`（**不要删除，不要提交到 git**）：

```env
CA_AES_256_KEY_PATH=/home/gkh/.ssh/aes.key
CA_IV_PATH=/home/gkh/.ssh/iv
```

**注意**：`.env` 基于 CWD 读取，**运行脚本时必须从项目根目录执行**。

### Casimir 初始化

```python
import sys
sys.path.insert(0, '/home/gkh/ashare/casimir_ashare')

import os
os.environ.setdefault('CA_AES_256_KEY_PATH', '/home/gkh/.ssh/aes.key')
os.environ.setdefault('CA_IV_PATH', '/home/gkh/.ssh/iv')

from casimir.casimir import init_casimir
init_casimir('bookdisco', 'bookdiscono1')
```

## A 股市场特性（强制了解）

| 特性 | 说明 |
|------|------|
| **复权** | **必须使用后复权 (hfq)**，禁止前复权 (qfq) |
| **交易时间** | 09:30-11:30, 13:00-15:00 |
| **T+1 制度** | 当日买入次日才能卖出 |
| **涨跌停** | ±10%（±20% 创业板/科创板） |
| **停牌** | A 股存在停牌机制，需处理缺失数据 |

## 自主研究模式规范

> 以下规范在执行「自主研究任务」时强制生效。

### 角色定位

你是一个**高频聚合数据研究员助手**，专注于从 1 分钟 K 线数据中提炼有意义的日度特征。你的价值在于**理解市场微观结构**，不在于暴力遍历特征组合。

### 启动流程（强制 — 三层架构）

> 详见 `docs/THREE-LAYER-GUIDE.md`

核心读取顺序：KB(`research/KNOWLEDGE-BASE.md`) → ASHARE_ADMISSION.md(`docs/ASHARE_ADMISSION.md`) → 方向专属文档 → 按需读 EXPERIMENT-LOG

### 研究纪律（强制）

1. **假设驱动**：每个 Raw-Data 都要有**清晰的物理含义**，不做无意义的数学变换
2. **单变量迭代**：一次只改一个维度（聚合方式 / 时间窗口 / 标准化方式），明确归因
3. **必须做分组回测**：重点关注横截面分类能力，中间组亏钱的特征不可入库
4. **推荐做分段评估**：检验跨时段稳定性
5. **必须验证 Numba 兼容性**：入库前确认全程 numba 可执行
6. **保留基线对照**：所有新 Raw-Data 和已有最优特征对比
7. **连续 2 个特征无突破时必须停下来**，回顾失败模式，写阶段性反思

### 分析深度要求（强制）

- **不要只看整体 IC**：必须看分组、分时段、Long/Short 分离
- **分析篇幅 >= 实现篇幅**：如果你发现自己在换特征而不是在思考，停下来
- **失败特征必须写诊断**，格式：

  ```
  ❌ Raw-Data xxx 失败分析

  特征：[名称、物理含义、计算方式]
  假设：[为什么预期有横截面分类能力]
  实际：[量化数字]
  诊断：[为什么不行 — 是假设错误还是实现问题]
  证据：[分组/分段的具体数据]
  结论：[这告诉我们什么关于市场微观结构的信息]
  下一步：[基于此结论应该做什么]
  ```

### 文件产出规范

| 产出类型 | 存放位置 | 说明 |
|---------|---------|------|
| 评估报告 | `.claude-output/evaluations/` | evaluate.py 标准输出 |
| 研究报告 | `.claude-output/reports/` | 每轮研究一份 |
| 分析结果 | `.claude-output/analysis/` | 因子值 pickle、相关性分析等 |
| 特征灵感 | `research/ideas.md` | 累积追加 |
| 临时脚本 | `.claude-tmp/` | 一次性脚本、调试 |

## 项目目录结构

```
ashare_rawdata/
├── CLAUDE.md                          # 操作规范与硬约束（本文件）
├── docs/
│   ├── ASHARE_ADMISSION.md                 # A 股 RawData 入库完整流程
│   ├── BACKTEST.md                         # 回测默认参数（Agent 必读）
│   └── THREE-LAYER-GUIDE.md                # 三层结构写入规范
├── orchestration/                     # 多 Agent 编排系统
│   ├── config.yaml                         # 运行配置（TG token、预算、参数）
│   ├── researcher_wrapper.sh               # 研究员外部循环脚本
│   ├── hourly_report.sh                    # 每小时 TG 播报
│   ├── tg_send.py                          # TG 通知 CLI
│   ├── prompts/                            # Agent 提示词
│   │   ├── researcher.md                        # 研究员工作流
│   │   └── lead.md                              # 组长操作手册
│   ├── state/                              # 运行时状态（gitignore）
│   │   ├── direction_pool.yaml                  # 研究方向池
│   │   ├── cost_tracker.yaml                    # 周预算追踪
│   │   └── agent_states/                        # 各 Agent 状态文件
│   └── logs/                               # 运行日志（gitignore）
├── research/                          # 研究笔记与因子探索记录
│   ├── KNOWLEDGE-BASE.md                   # Layer 0 知识库（≤300行，自动生成）
│   ├── EXPERIMENT-LOG.md                   # Layer 1 实验登记簿
│   ├── ideas.md                            # 因子灵感与假设记录
│   ├── basic_rawdata/                      # 已注册 bundle 的设计与代码
│   ├── agent_reports/                      # 研究员产出
│   │   ├── screening/                           # 初筛报告
│   │   ├── corr_check/                          # 相关性检测
│   │   └── feedback/                            # 组长→研究员反馈
│   ├── pending-rawdata/                    # 通过自动筛选的候选
│   ├── waiting-rawdata/                    # 已审批待入库
│   └── rejected-rawdata/                   # 被拒绝的
├── scripts/                           # 工具脚本
│   ├── regenerate_kb.py                    # KB 自动生成器
│   ├── validate-rawdata/                   # 数据验证工具
│   │   ├── validate_rawdata_bundle.py
│   │   └── validation_guide.md
│   └── utils/
│       └── state_manager.py                     # YAML 原子读写 + 方向池管理
├── .claude-output/                    # 有价值的产出（必须维护 index.md）
│   ├── index.md                            # 产出导航索引
│   ├── evaluations/                        # 评估输出
│   ├── reports/                            # 研究报告
│   └── analysis/                           # 分析结果
└── .claude-tmp/                       # 临时文件（gitignore）
```

## 关键关联目录

| 目录 | 说明 |
|------|------|
| `/home/gkh/ashare/casimir_ashare` | casimir A 股框架源码 |
| `/home/gkh/ashare/ashare_hf_variable` | A 股高频变量注册体系 |
| `/home/gkh/claude_tasks/ashare_alpha` | 下游：A 股 Alpha 挖掘项目（**共享回测体系**） |
| `/home/gkh/claude_tasks/ashare_alpha/backtest/evaluate.py` | 共享评估脚本（本项目直接调用） |

## 注意事项

- **Numba 优先**: 所有核心计算必须 numba 兼容，这是硬性入库要求
- **避免过拟合**: 参数优化时注意样本内/外分割，警惕数据窥探偏差
- **交易成本**: 高换手率因子需确认扣费后仍有收益
- **A 股特有**：注意 ST/退市股处理、涨跌停流动性约束、T+1 影响
- **复权一致性**: 涉及绝对价格比较时，两侧必须在同一价格空间
