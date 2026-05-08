# NQ 1m/3m Short-Timeframe Trend System Summary

## 结论

继续研究后，不是“没有找到可以盈利的策略”。更准确的结论是：找到了一个比 ICT/lightglow 图形特征更稳、回测为正且跨年度为正的短线趋势候选：

`trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time`

它不是“可以直接实盘”的最终系统，但已经满足更接近稳定盈利的研究级标准：

- 3m bar，US RTH。
- ADX(30) >= 28 表示趋势强度足够。
- +DI > -DI 且当前 close 上涨时做多；-DI > +DI 且当前 close 下跌时做空。
- 信号下一根 3m bar 开盘入场。
- 固定持有 30 分钟出场。
- 成本已扣：NQ round trip 0.625 点。

## 行业候选来源

本轮把常见短线趋势策略机械化验证：

- Opening Range Breakout
- Donchian / channel breakout
- VWAP trend pullback
- EMA trend / pullback
- ADX / DI trend following

行业资料只用于生成候选族，结论以本地 Databento 1m/3m 回测为准。

## 数据与验证

- 数据源：`data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`
- 时间：2021-04-28 到 2026-04-27
- 数据：连续 NQ 1m bars，另聚合 3m bars
- Walk-forward：365d train / 5d purge / 90d OOS / 90d step
- 代表性搜索：432 个 time-exit 趋势候选
- 聚焦搜索：648 个 ADX/VWAP/Donchian 候选，含 time 与 bracket exit

## 最佳候选审计

### 3m ADX(30)/DI RTH both hold30m

候选：`trend_adx_di_trend_3m_us_rth_lb30_adx30_thr28_hold30m_both_time`

全样本：

| 指标 | 数值 |
| --- | ---: |
| trades | 2,516 |
| net points | 6,696.75 |
| profit factor | 1.171 |
| win rate | 50.83% |
| max drawdown points | 1,077.75 |
| first half points | 2,555.25 |
| second half points | 4,141.50 |
| stability | 0.617 |

固定 90 天窗口：

| 指标 | 数值 |
| --- | ---: |
| windows | 16 |
| positive windows | 11 |
| positive rate | 68.75% |
| window net points | 5,996.50 |
| worst 90d window | -537.125 |
| mean PF | 1.194 |
| max 90d drawdown | 873.125 |

年度净点数：

| 年份 | net points |
| --- | ---: |
| 2021 | 749.625 |
| 2022 | 792.125 |
| 2023 | 748.750 |
| 2024 | 2,186.000 |
| 2025 | 1,678.125 |
| 2026 YTD | 542.125 |

这比单个 OOS fold 优胜的候选更可信，因为它全样本、分半、年度都为正。

成本敏感性：

| slippage ticks / side | round-trip cost points | net points | PF | max DD points | first half | second half |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 | 0.625 | 6,696.75 | 1.171 | 1,077.75 | 2,555.25 | 4,141.50 |
| 2.0 | 1.125 | 5,438.75 | 1.137 | 1,248.625 | 1,926.25 | 3,512.50 |
| 3.0 | 1.625 | 4,180.75 | 1.103 | 1,448.125 | 1,297.25 | 2,883.50 |

近端样本：

| 成本 | 样本 | trades | net points | PF | max DD points | first half | second half |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 tick/side | 2025-01-01 至 2026-04-28 | 592 | 2,220.25 | 1.180 | 813.00 | 723.75 | 1,496.50 |
| 1 tick/side | 2025-04-28 至 2026-04-28 | 442 | 1,056.00 | 1.126 | 657.375 | -462.625 | 1,518.625 |
| 2 tick/side | 2025-01-01 至 2026-04-28 | 592 | 1,924.25 | 1.154 | 828.00 | 575.75 | 1,348.50 |
| 2 tick/side | 2025-04-28 至 2026-04-28 | 442 | 835.00 | 1.098 | 736.375 | -573.125 | 1,408.125 |
| 3 tick/side | 2025-01-01 至 2026-04-28 | 592 | 1,628.25 | 1.129 | 942.625 | 427.75 | 1,200.50 |
| 3 tick/side | 2025-04-28 至 2026-04-28 | 442 | 614.00 | 1.071 | 836.875 | -683.625 | 1,297.625 |

近端样本仍为正，但最近 12 个月内部不均衡：前半段亏损、后半段盈利。这说明它有真实研究价值，但还不能按“稳定到可直接上线”处理。

## 不采纳的表面稳定候选

聚焦 walk-forward 中有两个 VWAP bracket 候选通过了初始 stable gate：

- `trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold15m_long_sl12_tp24`
- `trend_vwap_trend_pullback_1m_us_rth_lb60_thr0_hold30m_long_sl12_tp24`

但全样本 sanity check 均为负：

| candidate | full net points | PF |
| --- | ---: | ---: |
| hold15m sl12_tp24 | -404.625 | 0.931 |
| hold30m sl12_tp24 | -592.000 | 0.907 |

所以它们不应作为稳定策略候选。

## 其他候选

| candidate | 全样本 net | PF | 90d positive rate | 年度问题 |
| --- | ---: | ---: | ---: | --- |
| `3m ADX14 thr26 both hold30m` | 7,083.00 | 1.058 | 68.75% | 2022/2023 为负 |
| `1m ADX30 thr24 both hold30m` | 4,814.00 | 1.071 | 62.50% | 2025 明显负 |
| `1m VWAP pullback lb50 short hold30m` | 3,607.625 | 1.222 | 62.50% | 2023 为负 |
| `1m VWAP pullback lb50 both hold30m` | 3,469.00 | 1.111 | 56.25% | 2025 为负 |

这些可作为组合候选，但不如 `3m ADX30 thr28` 稳。

## 当前判断

找到的是一个“研究级稳定候选”，不是最终生产系统。它可以被定义为“有统计研究价值的盈利短线趋势系统候选”，但不能被定义为“已完成验证、可直接实盘的稳定套利系统”。

可以继续推进它，但下一步必须做：

- 更严格的实盘成本模型：不同手续费、滑点随波动和成交量变化。
- bracket/dynamic exit：当前最佳仍是 time exit，固定 bracket 没有普遍改善。
- 合约 roll 与实盘撮合一致性检查。
- paper validation 至少 2-4 周。

## 产物

- 搜索脚本：`scripts/search_nq_short_trend_systems.py`
- 代表性搜索报告：`reports/NQ-short-timeframe-trend-system-representative.md`
- 聚焦搜索报告：`reports/NQ-short-timeframe-trend-system-focused.md`
- 候选审计 CSV：
  - `.tmp/nq-short-trend-candidate-validation-summary.csv`
  - `.tmp/nq-short-trend-candidate-validation-90d.csv`
  - `.tmp/nq-short-trend-candidate-validation-yearly.csv`
  - `.tmp/nq-short-trend-best-cost-sensitivity.csv`
  - `.tmp/nq-short-trend-best-recent-periods.csv`
