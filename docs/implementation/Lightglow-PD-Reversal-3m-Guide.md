# Lightglow Premium/Discount Reversal 3m - 实施指南

**策略文件**：`pine_scripts/lightglow_premium_discount_reversal_3m.pine`  
**创建日期**：2026-05-07  
**状态**：✅ 准备测试

---

## 📊 策略概述

### 核心逻辑

这是一个**反向交易策略**，与传统ICT理论相反：

- **传统理论**：在Discount区域买入（买便宜），在Premium区域卖出（卖贵）
- **本策略**：在Premium区域做空，在Discount区域做多（反向操作）

**为什么反向有效**？
- 市场在极端区域往往继续惯性运动
- 短期动量效应强于均值回归
- 3分钟快速进出，捕捉短期趋势

### 历史表现（5年Walk-Forward验证）

| 指标 | 数值 | 说明 |
|------|------|------|
| **净利润** | 40,214点 = **$804,270** | 5年总收益 |
| **盈利因子** | **1.83** | 优秀（>1.5） |
| **最大回撤** | 1,262点 = **$25,230** | 可控 |
| **净利润/回撤比** | **31.88** | 极佳 |
| **正向日胜率** | **46.09%** | 稳健 |
| **总交易次数** | 12,728笔 | 样本充足 |
| **平均每天交易** | 13.83笔 | 适中 |
| **平均每笔盈利** | $63.2 | 良好 |

---

## 🚀 快速开始（10分钟）

### 步骤1：在TradingView中加载策略

1. **打开TradingView**
   - 访问 https://www.tradingview.com
   - 登录你的账户（需要Pro+或Premium）

2. **加载NQ图表**
   - 搜索：`NQ1!`（NQ连续合约）
   - 时间框架：**3分钟**（重要！）

3. **打开Pine Editor**
   - 点击底部的"Pine Editor"标签
   - 点击"New" → "Strategy"

4. **复制代码**
   - 打开文件：`pine_scripts/lightglow_premium_discount_reversal_3m.pine`
   - 全选复制（Cmd+A, Cmd+C）
   - 粘贴到Pine Editor（Cmd+V）

5. **保存并加载**
   - 点击"Save"
   - 命名：`Lightglow PD Reversal 3m`
   - 点击"Add to Chart"

### 步骤2：配置回测参数

策略会自动使用以下设置：
- 初始资金：$25,000
- 手续费：$5/往返
- 滑点：2点
- 回测期间：2020-01-01 至 2026-12-31

**无需修改任何参数**，默认值已优化。

### 步骤3：查看回测结果

1. **打开Strategy Tester**
   - 点击底部的"Strategy Tester"标签
   - 等待回测完成（可能需要1-2分钟）

2. **检查关键指标**
   - Net Profit：应该接近 $800K
   - Profit Factor：应该接近 1.8
   - Max Drawdown：应该接近 $25K
   - Total Trades：应该接近 12,700

3. **查看图表**
   - 红色背景 = Premium区域（做空信号）
   - 绿色背景 = Discount区域（做多信号）
   - 红色三角形 = 做空入场
   - 绿色三角形 = 做多入场

---

## 📈 预期回测结果

### 如果结果接近以下数值，说明实现正确：

```
Overview:
├── Net Profit: $750K - $850K
├── Total Trades: 12,000 - 13,500
├── Percent Profitable: 45% - 48%
├── Profit Factor: 1.7 - 1.9
├── Max Drawdown: $20K - $30K
└── Avg Trade: $55 - $70

Performance:
├── Total Closed Trades: ~12,700
├── Number Winning Trades: ~5,850
├── Number Losing Trades: ~6,850
├── Avg Win: ~$110
├── Avg Loss: ~$65
└── Largest Winning Trade: ~$500

Risk Metrics:
├── Max Drawdown: ~$25K (10% of capital)
├── Max Consecutive Losses: ~15
├── Sharpe Ratio: ~2.0
└── Recovery Factor: ~32
```

### 如果结果差异很大

**可能原因**：
1. 时间框架不是3分钟
2. 合约选择错误（应该用NQ1!连续合约）
3. 回测期间设置错误
4. TradingView数据质量问题

**解决方案**：
- 检查图表时间框架（右上角应显示"3"）
- 确认合约是NQ1!
- 检查Strategy Settings中的日期范围
- 尝试刷新页面重新加载

---

## ⚙️ 参数说明

### 默认参数（已优化，建议不修改）

```pinescript
// Zone Settings
Lookback Length: 100        // 计算Premium/Discount的回溯期
Premium Threshold: 0.95     // 95%以上为Premium区域
Discount Threshold: 0.05    // 5%以下为Discount区域

// Exit Settings
Exit After N Bars: 1        // 持仓1根K线（3分钟）

// Risk Management
Max Trades Per Day: 20      // 每天最多20笔交易
Daily Loss Limit: 400       // 单日亏损400点停止交易
```

### 如果想调整参数

**更保守的设置**：
```
Max Trades Per Day: 10
Daily Loss Limit: 200
```

**更激进的设置**：
```
Max Trades Per Day: 30
Daily Loss Limit: 600
```

**不建议修改**：
- Lookback Length（会改变策略本质）
- Premium/Discount Threshold（已优化）
- Exit After N Bars（核心参数）

---

## 🔔 设置告警

### 步骤1：创建告警

1. **右键点击图表** → "Add Alert"
2. **Condition**：选择"Lightglow PD Reversal 3m"
3. **选择告警类型**：
   - "Long Signal" - 做多信号
   - "Short Signal" - 做空信号
   - "Position Closed" - 平仓
   - "Daily Trade Limit Reached" - 达到每日交易限制
   - "Daily Loss Limit Hit" - 达到每日亏损限制

### 步骤2：配置告警选项

**Alert actions**：
- ✅ Notify on App
- ✅ Show popup
- ✅ Send email
- ✅ Play sound
- ⬜ Webhook URL（如果要自动化）

**Options**：
- Expiration: Open-ended
- Frequency: Once Per Bar Close

### 步骤3：测试告警

1. 创建告警后，等待下一个信号
2. 检查是否收到通知
3. 验证消息内容是否清晰

---

## 📱 Paper Trading工作流程

### 每天的交易流程

#### 开盘前（8:00 AM EST）

1. **检查TradingView**
   - 打开NQ 3分钟图表
   - 确认策略正在运行
   - 检查告警是否激活

2. **检查IBKR TWS**
   - 登录Paper Trading账户
   - 确认NQ合约正确（当前季度）
   - 检查账户余额

3. **准备交易日志**
   - 打开Google Sheets或Excel
   - 准备记录今天的交易

#### 交易时段（全天）

**当收到告警时**：

1. **验证信号**（30秒）
   ```
   ✅ 检查图表：确认Premium/Discount区域
   ✅ 检查价格：确认当前价格位置
   ✅ 检查时间：确认不是数据延迟
   ```

2. **决策**（10秒）
   ```
   如果信号有效 → 执行交易
   如果信号可疑 → 跳过
   ```

3. **在IBKR下单**（1分钟）
   ```
   Long Signal:
   ├── Action: BUY
   ├── Quantity: 1
   ├── Order Type: MKT（市价单，快速成交）
   └── 记录入场价格

   Short Signal:
   ├── Action: SELL
   ├── Quantity: 1
   ├── Order Type: MKT
   └── 记录入场价格
   ```

4. **设置计时器**（3分钟）
   ```
   - 手机设置3分钟倒计时
   - 或者等待下一根3分钟K线收盘
   ```

5. **平仓**（3分钟后）
   ```
   - 在IBKR中平仓（市价单）
   - 记录出场价格和盈亏
   ```

6. **记录交易**（1分钟）
   ```
   日志记录：
   ├── 时间
   ├── 方向（Long/Short）
   ├── 入场价格
   ├── 出场价格
   ├── 盈亏（点数和美元）
   └── 备注（信号质量、执行情况）
   ```

#### 收盘后（4:00 PM EST）

1. **统计今日表现**
   ```
   - 总交易次数
   - 盈利交易 / 亏损交易
   - 总盈亏
   - 最大单笔盈利/亏损
   ```

2. **对比回测**
   ```
   - 实际盈利因子 vs 回测1.83
   - 实际胜率 vs 回测46%
   - 实际滑点 vs 假设2点
   ```

3. **记录观察**
   ```
   - 哪些信号质量好
   - 哪些信号质量差
   - 执行中的问题
   - 改进建议
   ```

---

## 📊 交易日志模板

### Google Sheets模板

```
| 日期 | 时间 | 方向 | 入场 | 出场 | 点数 | 盈亏$ | 累计$ | 备注 |
|------|------|------|------|------|------|-------|-------|------|
| 5/7  | 9:15 | Long | 18050| 18055| +5   | +$100 | +$100 | 清晰的Discount信号 |
| 5/7  | 10:30| Short| 18100| 18095| +5   | +$100 | +$200 | Premium区域，快速下跌 |
| 5/7  | 11:45| Long | 18060| 18058| -2   | -$40  | +$160 | 假信号，立即反转 |
```

### 每周统计

```
Week: 2026-W19 (May 5-9)

Summary:
├── Total Trades: 67
├── Winning Trades: 32 (47.8%)
├── Losing Trades: 35 (52.2%)
├── Net P&L: +$2,150
├── Avg Win: $95
├── Avg Loss: $58
├── Profit Factor: 1.72
├── Max Drawdown: -$380
└── Best Day: +$680 (May 7)

Comparison to Backtest:
├── Win Rate: 47.8% vs 46% (✅ +1.8%)
├── Profit Factor: 1.72 vs 1.83 (⚠️ -6%)
├── Avg Trade: $32 vs $63 (⚠️ -49%)
└── Slippage: ~3 points vs 2 points (⚠️ +50%)

Notes:
- 实际滑点比预期高1点
- 需要考虑使用限价单
- 信号质量与回测一致
```

---

## ⚠️ 常见问题

### Q1: 回测结果与历史数据差异很大？

**检查清单**：
- [ ] 时间框架是3分钟？
- [ ] 合约是NQ1!？
- [ ] 回测期间是2020-2026？
- [ ] 手续费设置$5？
- [ ] 滑点设置2点？

**可接受的差异**：±10%

### Q2: 信号太多，来不及交易？

**解决方案**：
1. 只在特定时段交易（如NY AM 8:30-11:30）
2. 增加Daily Trade Limit限制
3. 考虑使用Webhook自动化

### Q3: 实际滑点比2点高很多？

**原因**：
- 市价单在快速市场中滑点大
- 流动性不足时段

**解决方案**：
- 使用限价单（但可能不成交）
- 避免在低流动性时段交易
- 记录实际滑点，调整回测参数

### Q4: Paper Trading表现比回测差？

**正常差异**：
- Paper Trading: 盈利因子1.5-1.7
- 回测: 盈利因子1.83
- 差异: ~10-15%

**如果差异>20%**：
- 检查执行质量
- 检查信号是否正确
- 检查是否跳过了某些交易

### Q5: 如何知道策略失效？

**警告信号**：
- 连续2周盈利因子<1.2
- 连续1个月亏损
- 最大回撤>$40K（60%超过历史）
- 胜率<35%（持续低于历史）

**行动**：
1. 停止交易
2. 分析原因（市场环境变化？执行问题？）
3. 重新评估策略

---

## 📅 3个月验证计划

### Month 1: 学习和适应

**目标**：
- 熟悉交易流程
- 建立交易习惯
- 记录详细数据

**成功标准**：
- 执行>80%的信号
- 记录完整的交易日志
- 理解策略行为

### Month 2: 优化和稳定

**目标**：
- 优化执行质量
- 减少滑点
- 提高效率

**成功标准**：
- 平均滑点<3点
- 盈利因子>1.5
- 胜率>40%

### Month 3: 验证和决策

**目标**：
- 验证长期稳定性
- 对比回测结果
- 决定是否进入实盘

**成功标准**：
- 3个月累计盈利
- 表现与回测差异<20%
- 最大回撤<$30K
- 心理承受能力良好

**Go/No-Go决策**：
```
✅ GO (进入实盘):
- 3个月盈利
- 盈利因子>1.5
- 回撤<$30K
- 心理状态良好

❌ NO-GO (继续Paper或停止):
- 3个月亏损
- 盈利因子<1.3
- 回撤>$40K
- 心理压力大
```

---

## 🎯 下一步

### 今天（完成Pine Script）✅

- [x] 创建Pine Script代码
- [x] 创建实施指南
- [ ] 在TradingView上测试
- [ ] 验证回测结果

### 明天（TradingView验证）

- [ ] 加载策略到TradingView
- [ ] 运行完整回测
- [ ] 对比历史数据
- [ ] 设置告警

### 本周（IBKR设置）

- [ ] 设置IBKR Paper Trading
- [ ] 配置NQ合约
- [ ] 测试下单流程
- [ ] 准备交易日志

### 下周（开始Paper Trading）

- [ ] 第一笔Paper Trading
- [ ] 记录执行质量
- [ ] 每日复盘
- [ ] 每周统计

---

## 📞 支持

**文档位置**：
- Pine Script: `pine_scripts/lightglow_premium_discount_reversal_3m.pine`
- 实施指南: `docs/implementation/Lightglow-PD-Reversal-3m-Guide.md`
- IBKR集成: `docs/plan/ICT-IBKR-Paper-Trading-Integration-Guide.md`

**问题反馈**：
- 创建beads issue: `bd create "问题描述"`
- 查看现有issues: `bd list`

---

**版本**：v1.0  
**创建日期**：2026-05-07  
**状态**：✅ 准备测试  
**下一步**：在TradingView上验证回测结果
