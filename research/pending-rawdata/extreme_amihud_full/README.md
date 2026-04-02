# extreme_amihud_full — Pending Admission

## 概要

- **方向**: D-007 realized_quarticity
- **Agent**: ashare_rawdata_b
- **Bundle**: realized_quarticity_0930_1130_1300_1457
- **特征**: extreme_amihud_full
- **物理含义**: 极端收益 bar 上的 Amihud 非流动性指标 — 衡量市场在压力下的价格冲击

## 关键指标

| 指标 | Raw | Neutral |
|------|-----|---------|
| LS Sharpe | 1.47 | 1.26 |
| IR(LS) | 0.39 | 0.45 |
| LE Sharpe | 1.19 | 1.36 |
| Mono | 0.86 | 0.71 |

## 文件结构

```
extreme_amihud_full/
├── README.md          # 本文件
├── report.md          # 筛选报告
├── factor_values.pkl  # 因子值 (symlink)
├── factor_values.meta.json  # 元数据 (symlink)
└── eval_charts/
    ├── w1_pnl_curve_raw.png
    ├── w1_group_pnl_raw.png
    ├── w1_pnl_curve_neutral.png
    └── w1_group_pnl_neutral.png
```

## 注册脚本

`research/basic_rawdata/realized_quarticity/register_realized_quarticity_full.py`

## 注意

- 数据仅覆盖 2020-2023（preload 窗口），2024 未评估
- 与 amihud_illiq_full / high_vol_illiq_full 可能相关，需用户审批时决定
- 入库需执行完整 2020-2024 评估确认
