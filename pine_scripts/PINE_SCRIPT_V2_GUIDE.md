# Lightglow V2 Pine Script - 使用指南

## 📋 概述

`lightglow_v2_non_kill_zone.pine` 是Lightglow Strategy V2的TradingView Pine Script实现，包含Kill Zone过滤器。

---

## 🚀 快速开始

### 1. 导入到TradingView

1. 打开TradingView
2. 点击 "Pine Editor"
3. 创建新脚本
4. 复制 `pine_scripts/lightglow_v2_non_kill_zone.pine` 的内容
5. 粘贴到编辑器
6. 点击 "Add to Chart"

---

### 2. 推荐设置

```
图表设置:
- 交易品种: NQ (Nasdaq 100 Futures) 或 MNQ (Micro)
- 时间周期: 1分钟
- 时区: UTC (脚本会自动转换)

策略设置:
- Initial Capital: $25,000
- Order Size: 1 contract
- Commission: $5 per contract
- Slippage: 2 ticks
```

---

## ⚙️ 参数说明

### Premium/Discount参数

```
Lookback Length: 100
- 用于计算Premium/Discount区域的回溯周期
- 默认: 100根K线
- 范围: 10-500

Premium Threshold: 0.95
- Premium区域阈值（95%分位数）
- 价格高于此水平 → 做空信号
- 默认: 0.95 (95%)

Discount Threshold: 0.05
- Discount区域阈值（5%分位数）
- 价格低于此水平 → 做多信号
- 默认: 0.05 (5%)
```

---

### 出场参数

```
Exit After N Bars: 2
- 持仓N根K线后平仓
- 默认: 2根K线（2分钟）
- 范围: 1-10
```

---

### ATR过滤器

```
ATR Length: 14
- ATR计算周期
- 默认: 14根K线

ATR Threshold: 8.0
- 只在ATR大于此值时交易
- 避免低波动环境
- 默认: 8.0点
```

---

### 时间过滤器（V2核心）

```
Avoid Kill Zone (V2): ✅ 启用
- V2策略的核心改进
- 避开Kill Zone时段
- 只在非Kill Zone交易

Kill Zone时段（EST）:
- NY AM: 8:30 - 11:30
- NY PM: 13:30 - 16:00

允许交易时段:
- Asian: 18:00 - 02:00
- London: 02:00 - 08:30
- Lunch: 11:30 - 13:30
- After Hours: 16:00 - 18:00
```

---

### V1模式（对比用）

```
Enable V1 Mode: ❌ 禁用
- 启用后切换到V1模式
- 在Kill Zone交易（原始策略）
- 用于对比V1 vs V2表现
```

---

### 显示选项

```
Show Premium/Discount Zones: ✅
- 显示Premium/Discount区域
- 红色区域 = Premium（做空区）
- 绿色区域 = Discount（做多区）

Show Entry Signals: ✅
- 显示入场信号
- 绿色三角 = 做多信号
- 红色三角 = 做空信号

Show Statistics Table: ✅
- 显示统计表格
- 右上角显示关键指标

Show Session Backgrounds: ✅
- 显示时段背景色
- 红色 = Kill Zone（禁止交易）
- 蓝色 = Asian Session
- 橙色 = London Session
- 灰色 = Lunch Session
- 紫色 = After Hours
```

---

## 📊 图表解读

### 颜色说明

```
区域:
- 红色区域: Premium Zone（价格昂贵，做空区）
- 绿色区域: Discount Zone（价格便宜，做多区）
- 中间区域: Fair Value（公允价值，不交易）

信号:
- 绿色▲: 做多信号（在Discount区域）
- 红色▼: 做空信号（在Premium区域）

背景色（时段）:
- 红色背景: Kill Zone（V2禁止交易）
- 蓝色背景: Asian Session（最佳时段）
- 橙色背景: London Session（良好时段）
- 灰色背景: Lunch Session
- 紫色背景: After Hours
```

---

### 统计表格

```
右上角表格显示:
- Version: V2 (Non-KZ) 或 V1 (Kill Zone)
- Net Profit: 净利润
- Profit Factor: 盈利因子
- Win Rate: 胜率
- Total Trades: 总交易数
- Wins/Losses: 盈利/亏损次数
- Avg Win/Loss: 平均盈利/亏损
- Max Drawdown: 最大回撤
- Current ATR: 当前ATR值
```

---

## 🎯 使用场景

### 场景1: V2策略回测

```
设置:
✅ Avoid Kill Zone (V2): 启用
❌ Enable V1 Mode: 禁用

预期结果:
- 盈利因子: ~2.45
- 胜率: ~42%
- 交易数: 较少（过滤掉23%）
- 平均每笔: 较高
```

---

### 场景2: V1策略回测（对比）

```
设置:
✅ Avoid Kill Zone (V2): 启用
✅ Enable V1 Mode: 启用

预期结果:
- 盈利因子: ~1.91
- 胜率: ~43%
- 交易数: 较多
- 总利润: 略高（+3.6%）
```

---

### 场景3: 无过滤器（基准）

```
设置:
❌ Avoid Kill Zone (V2): 禁用
❌ Enable V1 Mode: 禁用

预期结果:
- 24小时交易
- 最多交易机会
- 用于理解过滤器效果
```

---

## 📈 回测建议

### 推荐回测设置

```
时间范围: 2022-10-25 至今
- 至少3年数据
- 包含不同市场条件

交易品种:
- NQ1! (Nasdaq 100 Futures Continuous)
- 或 MNQ1! (Micro)

时间周期: 1分钟
- 策略设计为1分钟K线
- 不要使用其他周期

初始资金: $25,000
- 足够交易1手MNQ
- 考虑保证金要求
```

---

### 关键指标监控

```
必须监控:
✅ Profit Factor > 2.0 (V2目标)
✅ Win Rate > 35%
✅ Max Drawdown < $50,000
✅ 交易数合理（~25笔/天）

警告信号:
❌ Profit Factor < 1.5
❌ Win Rate < 30%
❌ Max Drawdown > $100,000
❌ 交易数异常（<5或>100笔/天）
```

---

## 🔧 常见问题

### Q1: 为什么没有交易信号？

**检查清单**:
1. 是否在Kill Zone时段？（V2会跳过）
2. ATR是否 > 8.0？
3. 价格是否在Premium/Discount区域？
4. 是否已有持仓？

---

### Q2: V2和V1有什么区别？

**核心区别**:
```
V1: 在Kill Zone交易
V2: 避开Kill Zone交易

V2优势:
✅ 盈利因子更高 (+28%)
✅ 风险更低 (-28% 回撤)
✅ 交易质量更好 (+26% 平均每笔)

V2代价:
❌ 总利润略少 (-3.6%)
❌ 交易机会减少 (-23%)
```

---

### Q3: 如何对比V1和V2？

**方法1: 使用V1模式开关**
```
1. 回测V2: Avoid KZ=✅, V1 Mode=❌
2. 回测V1: Avoid KZ=✅, V1 Mode=✅
3. 对比结果
```

**方法2: 使用两个图表**
```
1. 图表1: 加载V2脚本
2. 图表2: 加载V1脚本（原始）
3. 同时回测对比
```

---

### Q4: 时区设置重要吗？

**是的，非常重要！**

```
脚本使用UTC时间:
- 自动转换Kill Zone时间
- NY AM: 13:30-16:30 UTC
- NY PM: 18:30-21:00 UTC

TradingView设置:
- 图表时区可以任意
- 脚本会自动处理转换
- 但建议使用UTC或EST
```

---

### Q5: 可以用于其他品种吗？

**理论上可以，但需要调整**:

```
适合的品种:
✅ NQ/MNQ (设计目标)
✅ ES/MES (类似特性)
✅ 其他股指期货

需要调整的参数:
- ATR Threshold（根据品种波动率）
- Premium/Discount Threshold
- Commission/Slippage

不推荐:
❌ 外汇（不同的时段特性）
❌ 加密货币（24/7交易）
❌ 个股（流动性差异大）
```

---

## 🎨 自定义建议

### 调整ATR阈值

```
如果交易太少:
- 降低ATR Threshold (8.0 → 6.0)
- 允许更多低波动交易

如果交易太多:
- 提高ATR Threshold (8.0 → 10.0)
- 只在高波动时交易
```

---

### 调整Premium/Discount阈值

```
更激进（更多信号）:
- Premium: 0.95 → 0.90
- Discount: 0.05 → 0.10

更保守（更少信号）:
- Premium: 0.95 → 0.98
- Discount: 0.05 → 0.02
```

---

### 调整持仓时间

```
更快出场:
- Exit Bars: 2 → 1
- 更快锁定利润
- 但可能错过大行情

更长持仓:
- Exit Bars: 2 → 3 或 4
- 捕捉更大行情
- 但风险增加
```

---

## 📱 告警设置

### 创建告警

```
1. 右键点击图表
2. 选择 "Add Alert"
3. 选择条件:
   - Long Entry: 做多信号
   - Short Entry: 做空信号
   - Time Exit: 时间出场

4. 设置通知方式:
   - App推送
   - Email
   - Webhook
```

---

### 推荐告警

```
必须设置:
✅ Long Entry (做多信号)
✅ Short Entry (做空信号)
✅ Time Exit (出场提醒)

可选设置:
- 每日开始/结束
- 进入/离开Kill Zone
- ATR突破阈值
```

---

## 📚 相关文档

```
策略文档:
- STRATEGY_V2_EXPLAINED.md (详细说明)
- STRATEGY_V2_QUICKSTART.md (快速指南)
- STRATEGY_EXPLAINED.md (V1原始策略)

代码文件:
- tradingagents/execution/kill_zone_filter.py (Python实现)
- scripts/run_lightglow_v2_paper_trader.py (Paper Trading)
```

---

## ⚠️ 重要提示

### 回测 ≠ 实盘

```
回测结果不代表未来:
- 市场条件会改变
- 滑点可能更大
- 执行延迟影响
- 需要持续监控
```

---

### 风险管理

```
建议:
✅ 从小仓位开始
✅ 设置每日亏损限制
✅ 监控实际vs回测表现
✅ 准备好调整参数

警告:
❌ 不要过度优化参数
❌ 不要忽视风险管理
❌ 不要盲目相信回测
```

---

## 🆘 支持

如有问题:
1. 查看策略文档
2. 检查参数设置
3. 验证时区配置
4. 对比V1和V2结果

---

**祝回测顺利！** 📈

记住：V2的目标是更好的风险调整后收益，不是最高利润！
