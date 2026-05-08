# NQ 1m ICT/Lightglow Chart Feature Research Summary

## 结论

从截图、`docs/Strategy/ICT2022-2.md` 和 `docs/Strategy/lightglow.md` 可以机械化出 5 类可交易特征：

- P/D 极值延续：价格在 premium/discount 极端区域不反转，继续沿位移方向推进。
- P/D 极值反转：discount 买入、premium 卖出。
- 流动性 sweep/reclaim：扫前高/前低后收回。
- sweep + P/D POI：扫流动性同时发生在 matching premium/discount 区域。
- displacement BOS/FVG：长实体、较大 range、突破前结构高低点，或产生 FVG/imbalance。

回测后，真正有统计价值的是偏“延续”的特征，不是教科书式 P/D fade。最值得保留的是 `us_late` 的 displacement/BOS 与 P/D + displacement continuation。RTH 的 `sweep + P/D` 在单个 OOS fold 表现最好，但全样本为负，暂时只能当研究线索。

## 数据与方法

- 数据：`data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip` 中的连续 NQ 1m bars。
- 时间：2021-04-28 到 2026-04-27。
- 行数：1,769,740 1m bars，按同一分钟最高成交量构造连续 NQ。
- 成本：NQ round trip 0.625 点，来自 `BacktestCosts` 的单边 1 tick 滑点 + 手续费。
- Walk-forward：365 天训练、5 天 purge、90 天 OOS、90 天滚动。
- 交易：信号后一根开盘入场；先验证 2/3/5 分钟 time exit，再对强候选做 `sl8_tp12`、`sl8_tp16`、`sl12_tp24` 聚焦验证。

## 主要结果

完整 time-exit 搜索：

| 特征 | session | exit | OOS folds | OOS trades | OOS net pts | Avg PF | 全样本 net pts |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `sweep_pd_lb20_pd100` | US RTH | 5m time | 1 | 577 | 427.875 | 1.065 | -2471.125 |
| `displacement_bos_lb50` | US late | 5m time | 9 | 813 | 410.625 | 1.183 | 680.500 |
| `pd_displacement_continue_lb100_bos50` | US late | 2m time | 5 | 377 | 312.125 | 1.066 | 66.500 |
| `pd_displacement_continue_lb100_bos20` | US late | 2m time | 5 | 392 | 293.000 | 1.054 | 93.750 |
| `sweep_pd_lb50_pd50` | US late | 3m time | 3 | 399 | 103.625 | 1.078 | -1481.750 |

聚焦 bracket 验证：

- 固定 `sl8_tp12`、`sl8_tp16`、`sl12_tp24` 没有提升结果。
- 正向候选几乎都来自 `time` exit。
- `sl12_tp24` 对 displacement 与 sweep/P/D 候选多数为负，说明这些 1m 特征更像短暂 drift，而不是稳定 2R 扩展结构。

## 可交易特征排序

1. **US late displacement BOS continuation**
   - 信号：`displacement_bos_lb50_us_late_hold5m_time`
   - 逻辑：在美盘后段，强实体/大 range 收盘突破 50m prior high/low 后顺势持有 5 分钟。
   - 优点：全样本仍为正，OOS 净点数 410.625，Avg PF 1.183。
   - 风险：只 3/9 个 selected folds 为正，稳定性不足。

2. **US late P/D + displacement continuation**
   - 信号：`pd_displacement_continue_lb100_bos20/bos50`
   - 逻辑：价格已经在 100m premium/discount 极端区，并出现 20m/50m displacement BOS，顺势跟随 2-5 分钟。
   - 优点：和截图 #1 的阶梯式推进最接近；全样本小幅为正。
   - 风险：OOS 边际薄，部分 folds 亏损较大。

3. **Sweep + P/D POI**
   - 信号：`sweep_pd_lb20_pd100_us_rth_hold5m_time`、`sweep_pd_lb50_pd50_us_late_hold3m_time`
   - 逻辑：扫流动性只在 P/D POI 内交易。
   - 优点：OOS fold 内表现可观，符合 ICT 的“先扫再进 POI”。
   - 风险：RTH 版本全样本为负；late 版本全样本也为负，只能作为过滤器，不应独立上线。

4. **P/D + CHoCH confirmation**
   - 逻辑：进入 P/D 区后等待内部结构 CHoCH。
   - 结果：少量 OOS 正向，但全样本多数为负。
   - 用途：更适合作为二级确认或减少交易频率，不适合单独作为主策略。

## 实盘化建议

- 不要上线 RTH `sweep_pd_lb20_pd100`，尽管它是 OOS 排名第一；它只有一个 selected fold 且全样本亏损。
- 下一步优先研究 `us_late displacement_bos_lb50 hold5m time`，但要加 regime filter，例如只在 ATR/成交量状态、日内 VWAP 偏离、HTF 趋势一致时启用。
- 暂时不要使用固定 2R bracket；这些特征的优势集中在 2-5 分钟短漂移，硬套 8/12 或 12/24 点 bracket 会把优势打掉。
- 如果要结合截图 #2/#3 的入场线和 TP 线，应该先做动态退出/保本/部分止盈，而不是固定 TP/SL。

## 产物

- 脚本：`scripts/backtest_ict_chart_features_1m.py`
- 完整 time-exit 报告：`reports/NQ-chart-ict-lightglow-time-feature-backtest.md`
- 聚焦 bracket 报告：`reports/NQ-chart-ict-focused-bracket-backtest.md`
- 明细 CSV：
  - `.tmp/nq-chart-ict-1m-time-aggregate.csv`
  - `.tmp/nq-chart-ict-focused-bracket-aggregate.csv`
