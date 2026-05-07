# Lightglow策略回测对比报告

**日期**: 2026-05-07  
**回测期间**: 2020-01-01 至 2026-05-07 (6.35年)  
**初始资金**: $25,000  
**佣金**: $5/往返  
**滑点**: 2点  

---

## 执行摘要

本报告对比了两个Lightglow Premium/Discount策略版本：

1. **优化版本** - 使用时间和波动率过滤器的反转策略
2. **自适应版本** - 基于ADX的趋势/反转自动切换策略

---

## 性能对比

### 关键指标

| 指标 | 优化版本 | 自适应版本 | 变化 |
|------|---------|-----------|------|
| **净利润** | ${OPT_PROFIT} | ${ADP_PROFIT} | {PROFIT_CHANGE}% |
| **盈利因子** | {OPT_PF} | {ADP_PF} | {PF_CHANGE}% |
| **胜率** | {OPT_WR}% | {ADP_WR}% | {WR_CHANGE}% |
| **最大回撤** | ${OPT_DD} | ${ADP_DD} | {DD_CHANGE}% |
| **总交易数** | {OPT_TRADES} | {ADP_TRADES} | {TRADES_CHANGE}% |
| **夏普比率** | {OPT_SHARPE} | {ADP_SHARPE} | {SHARPE_CHANGE}% |
| **平均盈利** | ${OPT_AVG_WIN} | ${ADP_AVG_WIN} | {AVG_WIN_CHANGE}% |
| **平均亏损** | ${OPT_AVG_LOSS} | ${ADP_AVG_LOSS} | {AVG_LOSS_CHANGE}% |

---

## 详细分析

### 1. 盈利能力

**优化版本**:
- 净利润: ${OPT_PROFIT}
- 年化收益率: {OPT_ANNUAL_RETURN}%
- 盈利因子: {OPT_PF}

**自适应版本**:
- 净利润: ${ADP_PROFIT}
- 年化收益率: {ADP_ANNUAL_RETURN}%
- 盈利因子: {ADP_PF}

**结论**: {PROFIT_CONCLUSION}

---

### 2. 风险控制

**优化版本**:
- 最大回撤: ${OPT_DD} ({OPT_DD_PCT}%)
- 回撤/利润比: {OPT_DD_RATIO}

**自适应版本**:
- 最大回撤: ${ADP_DD} ({ADP_DD_PCT}%)
- 回撤/利润比: {ADP_DD_RATIO}

**结论**: {RISK_CONCLUSION}

---

### 3. 交易效率

**优化版本**:
- 总交易: {OPT_TRADES}
- 每天交易: {OPT_TRADES_PER_DAY}
- 胜率: {OPT_WR}%

**自适应版本**:
- 总交易: {ADP_TRADES}
- 每天交易: {ADP_TRADES_PER_DAY}
- 胜率: {ADP_WR}%

**结论**: {EFFICIENCY_CONCLUSION}

---

### 4. 风险调整收益

**优化版本**:
- 夏普比率: {OPT_SHARPE}
- 索提诺比率: {OPT_SORTINO}

**自适应版本**:
- 夏普比率: {ADP_SHARPE}
- 索提诺比率: {ADP_SORTINO}

**结论**: {SHARPE_CONCLUSION}

---

## 年度表现

### 逐年对比

| 年份 | 优化版本 | 自适应版本 | 差异 |
|------|---------|-----------|------|
| 2020 | ${OPT_2020} | ${ADP_2020} | {DIFF_2020}% |
| 2021 | ${OPT_2021} | ${ADP_2021} | {DIFF_2021}% |
| 2022 | ${OPT_2022} | ${ADP_2022} | {DIFF_2022}% |
| 2023 | ${OPT_2023} | ${ADP_2023} | {DIFF_2023}% |
| 2024 | ${OPT_2024} | ${ADP_2024} | {DIFF_2024}% |
| 2025 | ${OPT_2025} | ${ADP_2025} | {DIFF_2025}% |
| 2026 | ${OPT_2026} | ${ADP_2026} | {DIFF_2026}% |

---

## 趋势市场表现分析

### 识别的主要趋势时段

1. **2020年3月** - 疫情暴跌
2. **2020年11月** - 大选后上涨
3. **2022年1月-6月** - 加息预期下跌
4. **其他显著趋势时段**

### 趋势时段对比

{TREND_ANALYSIS}

**关键发现**: {TREND_CONCLUSION}

---

## 震荡市场表现分析

### 震荡时段对比

{RANGE_ANALYSIS}

**关键发现**: {RANGE_CONCLUSION}

---

## 数据质量说明

### 合约滚动处理

- 检测到 **634,987** 个合约滚动点
- 滚动期间跳过交易（前后6根K线）
- 避免了虚假利润（例如：单笔$27,755的虚假盈利）

### 数据覆盖

- 时间范围: 2020-01-01 至 2026-04-27
- 总K线数: 2,885,249根
- 合约: NQ期货所有月份合约
- 数据源: Databento GLBX.MDP3

---

## 结论

### 优势对比

**优化版本优势**:
{OPT_ADVANTAGES}

**自适应版本优势**:
{ADP_ADVANTAGES}

### 劣势对比

**优化版本劣势**:
{OPT_DISADVANTAGES}

**自适应版本劣势**:
{ADP_DISADVANTAGES}

---

## 最终建议

### 策略选择

{STRATEGY_RECOMMENDATION}

### 下一步行动

1. **如果自适应版本更优**:
   - [ ] 进入Paper Trading阶段（3个月）
   - [ ] 设置TradingView实时告警
   - [ ] 监控实际滑点和执行质量
   - [ ] 对比实盘与回测差异

2. **如果优化版本更优**:
   - [ ] 继续使用优化版本
   - [ ] 分析自适应版本失败原因
   - [ ] 考虑参数优化

3. **如果两者相近**:
   - [ ] 进行参数敏感性分析
   - [ ] 测试不同市场环境
   - [ ] 考虑组合使用

### 风险提示

⚠️ **重要提醒**:
- 回测结果不代表未来表现
- 实盘交易会有额外滑点和延迟
- 建议从小仓位开始（50%）
- 严格执行风险管理规则
- Paper Trading至少3个月

---

## 附录

### 回测参数

```
初始资金: $25,000
佣金: $5 per round-trip
滑点: 2 points
点值: $20 per point

策略参数:
- Lookback: 100
- Premium Threshold: 0.95
- Discount Threshold: 0.05
- Exit Bars: 2
- ATR Length: 14
- ATR Threshold: 8.0
- ADX Length: 14
- ADX Threshold: 25.0
- Stop Loss: 50 points
- Max Trades/Day: 50
- Daily Loss Limit: 400 points
```

### 文件位置

- 交易记录: `reports/backtest_results/trades_*.csv`
- 权益曲线: `reports/backtest_results/equity_*.csv`
- 指标数据: `reports/backtest_results/metrics_*.json`

---

**报告生成时间**: {REPORT_TIME}  
**回测引擎**: Python + Pandas  
**数据源**: Databento
