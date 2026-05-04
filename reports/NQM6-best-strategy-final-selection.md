# NQM6 最佳策略最终选择

## 结论

当前目标改为“盈利能力最强、风险可控、稳定”后，综合排名第一的候选是：

`adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`

这是一个欧洲时段、全波动过滤、盘口失衡阈值 0.3 的短持仓均值回归策略。它来自原最佳策略的局部邻域 walk-forward 搜索，不是固定 2R 策略；此前 2R 黑盒搜索没有找到合格候选。

## 核心指标

| 指标 | 数值 |
| --- | ---: |
| 候选总数 | 522 |
| balanced_best 候选数 | 30 |
| 交易次数 | 942 |
| 净点数 | 3,318.00 |
| 最大回撤点数 | 190.875 |
| 净点数/最大回撤 | 17.3831 |
| Profit Factor | 1.6891 |
| 胜率 | 54.88% |
| 稳定性 | 0.8476 |
| 正收益折比例 | 100.00% |
| 正收益 10 日滚动窗口比例 | 100.00% |
| 最差 10 日滚动窗口净点数 | 28.375 |
| 3x 成本压力净点数 | 2,376.00 |
| 训练选择未来测试净点数 | 1,444.375 |

## 机器审计结论

新增审计脚本：`scripts/audit_mbp_best_strategy_readiness.py`

当前审计报告：`reports/NQM6-best-strategy-readiness-audit.md`

| 审计项 | 结果 |
| --- | --- |
| Research status | pass |
| Live status | blocked |
| 逐笔交易数 | 942 |
| 逐笔净点数 | 3,318.00 |
| 逐笔最大回撤 | 190.875 |
| 完整 10 日窗口盈利率 | 100.00% |
| 最差完整 10 日窗口 | 494.625 |
| 最差单日 | -64.5 |
| 最差不完整尾部窗口 | 59.5 |
| 历史跨度 | 61 日 |

因此，当前可以明确选择它作为“已挖掘候选中盈利能力、回撤控制、稳定性综合最强”的研究候选；但不能标记为直接实盘策略。Live 阻塞原因包括：历史跨度只有 61 日、缺少 `DATABENTO_API_KEY`、没有已提交的 IBKR paper 订单、没有至少 20 笔 paper outcome。

## Gate 与 Walk-Forward 复核

导出的逐笔交易文件：`.tmp/mbp-best-strategy-trades.csv`

| 验证 | 原始结果 | Gate 后结果 |
| --- | ---: | ---: |
| 全样本净点数 | 3,318.00 | 3,184.75 |
| 全样本最大回撤 | 190.875 | 231.5625 |
| 全样本 PF | 1.6891 | 1.7060 |
| 全样本交易数 | 942 | 902 |
| Walk-forward 测试折 | 4 | 4 |
| Walk-forward 正收益折 | 4 | 4 |
| Walk-forward 净点数 | 2,062.00 | 2,045.65625 |
| Walk-forward 最大单折回撤 | 142.75 | 180.65625 |

Gate 保护机制阻断了 40 笔交易。该保护在本样本中略微降低净收益、提高 PF，但增加了最大回撤；因此当前最佳版本仍应以“原始策略 + 独立风控/纸盘验证”为主，而不是默认依赖现有 performance gate 提升收益质量。

## 长历史 Bar-Only 复核

新增长历史非 2R 搜索脚本：`scripts/search_nq_bar_best_strategy_walkforward.py`

该脚本使用本地 Databento 2010-2026 OHLCV 1m 压缩包构造连续 NQ bar-only 数据，不使用 MBP/order-book 特征；训练窗口只在历史训练段选择候选，再在未来 90 日测试窗验证。

2020-01-01 至 2026-04-27 的 US RTH 均值回归网格结果显示，最稳定的 bar-only 候选是：

`bar_best_mean_reversion_lb30_thr1_hold30_us_rth`

| 指标 | 数值 |
| --- | ---: |
| 入选测试折 | 7 |
| 正收益测试折比例 | 85.71% |
| 测试净点数 | 10,929.50 |
| 测试最大回撤点数 | 4,022.75 |
| 测试净点数/最大回撤 | 2.7169 |
| 平均测试 PF | 1.1090 |
| 平均测试胜率 | 51.12% |

结论：长历史 bar-only 数据中确实存在弱正收益均值回归结构，但 PF、回撤效率和特征粒度都明显弱于当前 MBP 最佳候选。因此它是“市场结构方向未被长期数据否定”的补充证据，不替代当前 `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`。当前最强策略仍是 MBP/order-book 版本；live 阻塞仍主要来自 MBP 长历史不足与纸盘 outcome 不足。

补充核心复核：2012-01-01 至 2026-04-27 的 US RTH 长样本、8 个均值回归核心候选、365 日训练 / 10 日 purge / 90 日测试 walk-forward 中，同一结构 `bar_best_mean_reversion_lb30_thr1_hold30_us_rth` 仍排第一：

| 指标 | 数值 |
| --- | ---: |
| 特征行数 | 5,383,225 |
| 入选测试折 | 5 |
| 正收益测试折比例 | 100.00% |
| 测试净点数 | 9,544.00 |
| 测试最大回撤点数 | 3,905.125 |
| 测试净点数/最大回撤 | 2.4440 |
| 平均测试 PF | 1.1152 |
| 平均测试胜率 | 51.58% |
| 最差入选测试折净点数 | 277.50 |

这进一步支持“长历史 NQ 中存在 US RTH 均值回归正收益结构”。但该验证仍是 bar-only、低 PF、高回撤的辅助证据；它不能替代 MBP/order-book 策略的长历史 MBP 复核，也不能清除 paper outcome 和 live-readiness 阻塞。

欧洲时段边界复核：2012-01-01 至 2026-04-27 的 Europe bar-only 短持仓均值回归 micro 网格没有找到稳定候选。最优入选项 `bar_best_mean_reversion_lb10_thr0.6_hold10_europe` 只有 1 个入选测试折，测试净点数 -2,640.00、PF 0.8168、正收益折比例 0%。这说明当前 MBP 最佳策略的欧洲时段优势不能被解释为简单 bar-only 价格均值回归；它更依赖 MBP/order-book 特征，例如盘口失衡、价差和深度过滤。该负证据提高了对“必须补足长历史 MBP/order-book 数据”的要求。

## 工程产物

- 排名脚本：`scripts/rank_mbp_best_strategy.py`
- 局部 walk-forward 搜索脚本：`scripts/search_mbp_best_strategy_walkforward.py`
- 长历史 bar-only 搜索脚本：`scripts/search_nq_bar_best_strategy_walkforward.py`
- 逐笔导出脚本：`scripts/export_mbp_best_strategy_trades.py`
- 排名报告：`reports/NQM6-best-strategy-ranking.md`
- 局部 walk-forward 搜索报告：`reports/NQM6-best-strategy-walkforward-neighbors.md`
- 长历史 bar-only 搜索报告：`reports/NQ-bar-best-strategy-walkforward-us-rth-mr-2020.md`
- 最终选择报告：`reports/NQM6-best-strategy-final-selection.md`
- 逐笔交易样本：`.tmp/mbp-best-strategy-trades.csv`
- Gate 汇总：`.tmp/mbp-best-strategy-gate-summary.csv`
- Walk-forward 汇总：`.tmp/mbp-best-strategy-walk-forward-summary.csv`

## 实盘边界

该策略已经是当前候选集合中收益、回撤、稳定性综合最优的研究候选，但还不能称为“可直接实盘”。缺口仍然是：

- 需要纸盘逐笔验证真实成交、滑点、拒单和交易时段行为。
- 需要确认 NQM6 合约月份、交易所时间、夏令时和数据源时间戳对齐。
- 需要在实盘执行层设置单日亏损、单日最大交易数、连续亏损冷却和最大持仓时间。
- 需要至少一个未参与挖掘的新数据窗口或连续纸盘窗口，验证边际没有消失。
