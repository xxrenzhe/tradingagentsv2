# NQ 1m/3m Short-Timeframe Trend System Summary

## 结论

继续研究后，不是“没有找到可以盈利的策略”。更准确的结论是：找到了一个比 ICT/lightglow 图形特征更稳、回测为正且跨年度为正的短线趋势候选：

`trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_both_time`

它不是“可以直接实盘”的最终系统，但已经满足更接近稳定盈利的研究级标准：

- 3m bar，US RTH。
- ADX(30) >= 26 表示趋势强度足够。
- +DI > -DI 且当前 close 上涨时做多；-DI > +DI 且当前 close 下跌时做空。
- 信号下一根 3m bar 开盘入场。
- 固定持有 60 分钟出场。
- 成本已扣：NQ round trip 0.625 点。

## 行业候选来源

本轮把常见短线趋势策略机械化验证：

- Opening Range Breakout
- Donchian / channel breakout
- VWAP trend pullback
- EMA trend / pullback
- ADX / DI trend following

行业资料只用于生成候选族，结论以本地 Databento 1m/3m 回测为准。

外部资料核验：

- Time-series momentum 在期货、指数、外汇、商品、债券等资产中有长期文献基础，见 Moskowitz/Ooi/Pedersen 的 SSRN 论文：https://ssrn.com/abstract=2089463
- Opening Range Breakout 是明确的日内动量候选，Zarattini/Barbon/Aziz 在 2024 SSRN 论文中专门研究 5-minute ORB：https://ssrn.com/abstract=4729284
- ADX/+DI/-DI 的用途是同时判断趋势强度和方向，StockCharts ChartSchool 对 Wilder Directional Movement System 有机械定义：https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx
- VWAP 适合日内分析，并可用当前价格相对 VWAP 判断日内方向和相对价值：https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/volume-weighted-average-price-vwap
- Donchian / Price Channel 用 x-period high/low 描述突破和趋势启动，可用于日内、日线、周线等周期：https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/price-channels
- Moving average crossover 是基础趋势跟随候选，作为 EMA trend / pullback 的来源之一：https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/how-to-trade-price-to-moving-average-crossovers

## 数据与验证

- 数据源：`data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`
- 时间：2021-04-28 到 2026-04-27
- 数据：连续 NQ 1m bars，另聚合 3m bars
- Walk-forward：365d train / 5d purge / 90d OOS / 90d step
- 代表性搜索：432 个 time-exit 趋势候选
- 聚焦搜索：648 个 ADX/VWAP/Donchian 候选，含 time 与 bracket exit

## 最佳候选审计

### 3m ADX(30)/DI RTH both hold60m

候选：`trend_adx_di_trend_3m_us_rth_lb30_adx30_thr26_hold60m_both_time`

全样本：

| 指标 | 数值 |
| --- | ---: |
| trades | 1,950 |
| net points | 7,763.25 |
| profit factor | 1.177 |
| win rate | 47.79% |
| max drawdown points | 1,184.75 |
| first half points | 2,778.125 |
| second half points | 4,985.125 |
| stability | 0.557 |

固定 90 天窗口：

| 指标 | 数值 |
| --- | ---: |
| windows | 16 |
| positive windows | 12 |
| positive rate | 75.00% |
| window net points | 6,669.875 |
| worst 90d window | -403.50 |
| mean PF | 1.191 |
| max 90d drawdown | 856.50 |

年度净点数：

| 年份 | net points |
| --- | ---: |
| 2021 | 1,031.625 |
| 2022 | 1,032.000 |
| 2023 | 557.250 |
| 2024 | 3,171.375 |
| 2025 | 814.000 |
| 2026 YTD | 1,157.000 |

这比单个 OOS fold 优胜的候选更可信，因为它全样本、分半、年度都为正。

成本敏感性：

| slippage ticks / side | round-trip cost points | net points | PF | max DD points | first half | second half |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.0 | 0.625 | 7,763.25 | 1.177 | 1,184.75 | 2,778.125 | 4,985.125 |
| 2.0 | 1.125 | 6,788.25 | 1.153 | 1,250.75 | 2,290.625 | 4,497.625 |
| 3.0 | 1.625 | 5,813.25 | 1.129 | 1,316.75 | 1,803.125 | 4,010.125 |

近端样本：

| 成本 | 样本 | trades | net points | PF | max DD points | first half | second half |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 tick/side | 2025-01-01 至 2026-04-28 | 484 | 1,971.00 | 1.139 | 1,135.375 | -32.50 | 2,003.50 |
| 1 tick/side | 2025-04-28 至 2026-04-28 | 364 | 1,869.50 | 1.202 | 849.50 | 626.00 | 1,243.50 |
| 2 tick/side | 2025-01-01 至 2026-04-28 | 484 | 1,729.00 | 1.121 | 1,162.875 | -153.50 | 1,882.50 |
| 2 tick/side | 2025-04-28 至 2026-04-28 | 364 | 1,687.50 | 1.180 | 899.875 | 535.00 | 1,152.50 |
| 3 tick/side | 2025-01-01 至 2026-04-28 | 484 | 1,487.00 | 1.103 | 1,191.375 | -274.50 | 1,761.50 |
| 3 tick/side | 2025-04-28 至 2026-04-28 | 364 | 1,505.50 | 1.159 | 960.375 | 444.00 | 1,061.50 |

近端样本仍为正。2025-2026 样本内部仍不均衡，2025-01-01 至 2026-04-28 的前半段小幅亏损、后半段盈利；但最近 12 个月在 1/2/3 tick per side 成本下前后半段都为正。这说明它有真实研究价值，但还不能按“稳定到可直接上线”处理。

## 参数邻域验证

为了避免只挑中一个偶然参数点，额外补测了 84 个 ADX/DI 周边组合：

- 范围：3m、US RTH、both、time exit。
- ADX period：14、30。
- ADX threshold：18-32 的离散值。
- 持有时间：18、24、30、36、45、60 分钟。

结果：

| 指标 | 数值 |
| --- | ---: |
| tested candidates | 84 |
| positive full-sample candidates | 72 |
| PF >= 1.05 candidates | 40 |
| all-years-positive candidates | 18 |
| ADX30 positive candidates | 42 |
| ADX30 all-years-positive candidates | 15 |

邻域内多个参数都为正，最佳候选不是孤立点。排名靠前的候选包括：

| candidate sketch | net points | PF | max DD | positive years | min year net |
| --- | ---: | ---: | ---: | ---: | ---: |
| ADX14 thr28 hold60m | 8,076.00 | 1.088 | 2,272.75 | 6 | 413.25 |
| ADX30 thr26 hold60m | 7,763.25 | 1.177 | 1,184.75 | 6 | 557.25 |
| ADX14 thr26 hold60m | 7,626.875 | 1.072 | 2,365.375 | 6 | 659.125 |
| ADX30 thr22 hold60m | 7,503.00 | 1.107 | 1,810.00 | 6 | 778.75 |
| ADX30 thr28 hold30m | 6,696.75 | 1.171 | 1,077.75 | 6 | 542.125 |

因此最终优先选 `ADX30 threshold26 hold60m`，原因不是净利润最高，而是 PF、回撤、年度一致性和参数邻域稳定性的综合平衡更好。

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
| `3m ADX30 thr28 both hold30m` | 6,696.75 | 1.171 | 68.75% | 无，原最佳候选 |
| `3m ADX14 thr26 both hold30m` | 7,083.00 | 1.058 | 68.75% | 2022/2023 为负 |
| `1m ADX30 thr24 both hold30m` | 4,814.00 | 1.071 | 62.50% | 2025 明显负 |
| `1m VWAP pullback lb50 short hold30m` | 3,607.625 | 1.222 | 62.50% | 2023 为负 |
| `1m VWAP pullback lb50 both hold30m` | 3,469.00 | 1.111 | 56.25% | 2025 为负 |

这些可作为组合候选，但不如 `3m ADX30 thr26 hold60m` 综合稳。

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
  - `.tmp/nq-short-trend-adx-neighborhood.csv`
  - `.tmp/nq-short-trend-best2-cost-sensitivity.csv`
  - `.tmp/nq-short-trend-best2-recent-periods.csv`
  - `.tmp/nq-short-trend-best2-90d.csv`
  - `.tmp/nq-short-trend-best2-yearly.csv`
