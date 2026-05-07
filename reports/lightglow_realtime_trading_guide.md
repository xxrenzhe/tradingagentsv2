# Lightglow实时IBKR Paper Trading使用指南

## 📋 概述

本系统基于IBKR实时（或延迟）市场数据计算Premium/Discount信号，实现真正的自动化交易。

**与历史信号方式的区别**:
- ❌ 旧方式: 预先导出历史信号 → 检查是否匹配当前时间
- ✅ 新方式: 实时接收市场数据 → 实时计算指标 → 实时生成信号

---

## 🚀 快速开始

### 前提条件

1. **IBKR TWS或Gateway已运行**
   ```bash
   # 检查连接
   nc -z localhost 7497 && echo "✅ Connected" || echo "❌ Not connected"
   ```

2. **Paper账户已激活**
   - 登录IBKR TWS
   - 切换到Paper Trading模式
   - 确保API已启用

### 启动实时交易器

```bash
# 干跑模式（推荐先运行1-2周）
python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    --lookback 100 \
    --premium 0.95 \
    --discount 0.05 \
    --atr-threshold 8.0 \
    --exit-bars 2
```

**输出示例**:
```
============================================================
🚀 Starting Lightglow Real-time Trader
============================================================
Symbol: MNQ
Contract: 202606
Lookback: 100
Premium: 0.95
Discount: 0.05
ATR Threshold: 8.0
Exit Bars: 2
Dry Run: True
============================================================

✅ Connected to IBKR at 127.0.0.1:7497
✅ Requested delayed market data (free for paper accounts)
✅ Contract qualified: Future(conId=770561201, symbol='MNQ', ...)
📥 Loading historical bars for initialization...
✅ Loaded 114 historical bars
✅ Subscribed to real-time 1-minute bars
⏳ Monitoring for signals...

📊 New Bar: 2026-05-07 14:30:00 | O:27500.0 H:27502.5 L:27498.0 C:27501.0
   ATR: 12.45 (threshold: 8.0) ✅
   Kill Zone: ✅
   Premium: 27510.25 | In Premium: ❌
   Discount: 27490.50 | In Discount: ❌

📊 New Bar: 2026-05-07 14:31:00 | O:27501.0 H:27503.0 L:27499.5 C:27489.0
   ATR: 12.50 (threshold: 8.0) ✅
   Kill Zone: ✅
   Premium: 27510.25 | In Premium: ❌
   Discount: 27490.50 | In Discount: ✅
🟢 LONG SIGNAL at 27489.0

============================================================
🟢 ENTERING LONG
Time: 2026-05-07 14:31:00+00:00
Price: 27489.0
Action: BUY 1 MNQ
Dry Run: True
============================================================

📊 New Bar: 2026-05-07 14:32:00 | O:27489.0 H:27495.0 L:27488.0 C:27493.5
   Position: 1 | Bars in trade: 1/2

📊 New Bar: 2026-05-07 14:33:00 | O:27493.5 H:27496.0 L:27492.0 C:27495.0
   Position: 1 | Bars in trade: 2/2

============================================================
⚪ EXITING POSITION
Entry: 2026-05-07 14:31:00+00:00 @ 27489.0
Exit: 2026-05-07 14:33:00+00:00 @ 27495.0
Reason: time_exit
PnL: 6.00 points ($120.00)
Dry Run: True
============================================================
```

---

## 📊 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--symbol` | MNQ | 交易品种 |
| `--contract-month` | 202606 | 合约月份 |
| `--host` | 127.0.0.1 | IBKR主机 |
| `--port` | 7497 | IBKR端口（7497=TWS, 4001=Gateway） |
| `--client-id` | 1 | 客户端ID |
| `--lookback` | 100 | Premium/Discount回溯周期 |
| `--premium` | 0.95 | Premium阈值（95%） |
| `--discount` | 0.05 | Discount阈值（5%） |
| `--atr-length` | 14 | ATR计算周期 |
| `--atr-threshold` | 8.0 | ATR过滤阈值 |
| `--exit-bars` | 2 | 持仓N根K线后出场 |
| `--max-position` | 1 | 最大持仓 |
| `--submit` | False | 提交真实订单（默认干跑） |

---

## 🔧 工作原理

### 1. 初始化阶段

```
连接IBKR
    ↓
请求延迟市场数据（免费）
    ↓
加载历史100+根K线
    ↓
订阅实时1分钟K线
    ↓
准备就绪
```

### 2. 每根K线处理流程

```
接收新K线
    ↓
存入滚动窗口（保留最近100+根）
    ↓
计算ATR（最近14根）
    ↓
计算Premium/Discount（最近100根）
    ↓
检查Kill Zone时间
    ↓
检查是否有持仓
    ↓
如果有持仓 → 检查是否到达出场时间
如果无持仓 → 检查入场条件
    ↓
生成信号/执行订单
```

### 3. 入场逻辑

```python
# 多头入场条件
if (ATR > 8.0 
    and in_kill_zone 
    and price < discount_level 
    and position == 0):
    → BUY 1 MNQ

# 空头入场条件
if (ATR > 8.0 
    and in_kill_zone 
    and price > premium_level 
    and position == 0):
    → SELL 1 MNQ
```

### 4. 出场逻辑

```python
# 时间出场（2根K线后）
if bars_in_trade >= 2:
    → CLOSE POSITION
```

---

## 📈 实时监控

### 查看实时日志

```bash
# 启动并记录日志
python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    2>&1 | tee logs/lightglow_$(date +%Y%m%d).log
```

### 后台运行

```bash
# 使用nohup后台运行
nohup python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    > logs/lightglow_$(date +%Y%m%d).log 2>&1 &

# 记录PID
echo $! > logs/trader.pid

# 查看日志
tail -f logs/lightglow_$(date +%Y%m%d).log

# 停止
kill $(cat logs/trader.pid)
```

### 使用screen/tmux

```bash
# 使用screen
screen -S lightglow
python scripts/run_lightglow_realtime_trader.py
# Ctrl+A, D 分离
# screen -r lightglow 重新连接

# 使用tmux
tmux new -s lightglow
python scripts/run_lightglow_realtime_trader.py
# Ctrl+B, D 分离
# tmux attach -t lightglow 重新连接
```

---

## ⚠️ 重要注意事项

### 1. 市场数据类型

```
类型1: 实时数据（需要订阅，$$$）
类型2: 冻结数据（最后可用）
类型3: 延迟数据（15-20分钟延迟，免费）✅
类型4: 延迟冻结数据

Paper账户默认使用类型3（延迟数据）
```

**影响**:
- 延迟15-20分钟
- 信号会晚15-20分钟
- 适合测试逻辑，不适合实盘

**解决方案**:
- 测试阶段: 使用延迟数据（免费）
- 实盘阶段: 订阅实时数据

### 2. Kill Zone时间

```
NY Kill Zone (EST):
- 上午: 8:30 - 11:30
- 下午: 13:30 - 16:00

UTC时间:
- 上午: 13:30 - 16:30
- 下午: 18:30 - 21:00
```

**注意**:
- 脚本使用UTC时间
- 确保服务器时区正确
- 夏令时/冬令时切换时检查

### 3. 持仓管理

```
当前限制:
- 最大持仓: 1手
- 同时只能有1个方向
- 新信号会被忽略（直到平仓）
```

**改进方向**:
- 支持多个持仓
- 支持加仓/减仓
- 支持对冲

### 4. 风险控制

```
当前实现:
✅ ATR过滤器（波动率）
✅ 时间过滤器（Kill Zone）
✅ 2根K线强制出场
❌ 止损
❌ 止盈
❌ 每日最大交易数
❌ 每日最大亏损
```

**建议**:
- 添加止损（如50点）
- 添加止盈（如100点）
- 添加每日限制
- 监控滑点

---

## 🎯 使用场景

### 场景1: 策略验证（1-2周）

```bash
# 干跑模式，观察信号质量
python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    2>&1 | tee logs/validation_$(date +%Y%m%d).log
```

**检查项**:
- [ ] 信号频率是否合理？
- [ ] ATR过滤器是否有效？
- [ ] Kill Zone时间是否正确？
- [ ] Premium/Discount计算是否准确？
- [ ] 出场时机是否合适？

### 场景2: Paper Trading（1-2个月）

```bash
# 提交真实订单到Paper账户
python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    --submit \
    2>&1 | tee logs/paper_$(date +%Y%m%d).log
```

**监控项**:
- [ ] 订单执行质量
- [ ] 滑点大小
- [ ] 实际盈亏 vs 回测
- [ ] 系统稳定性
- [ ] 异常处理

### 场景3: 实盘准备

```bash
# 小仓位实盘测试
python scripts/run_lightglow_realtime_trader.py \
    --symbol MNQ \
    --contract-month 202606 \
    --max-position 1 \
    --submit \
    2>&1 | tee logs/live_$(date +%Y%m%d).log
```

**准备清单**:
- [ ] 订阅实时市场数据
- [ ] 设置止损/止盈
- [ ] 配置风险限制
- [ ] 准备应急预案
- [ ] 设置监控告警

---

## 🔍 故障排查

### 问题1: 无法连接IBKR

**症状**:
```
ConnectionRefusedError: [Errno 61] Connection refused
```

**解决方案**:
```bash
# 1. 检查TWS/Gateway是否运行
ps aux | grep -i tws

# 2. 检查端口
nc -z localhost 7497

# 3. 检查API设置
# TWS → File → Global Configuration → API → Settings
# ✅ Enable ActiveX and Socket Clients
# ✅ Socket port: 7497
# ✅ Allow connections from localhost
```

### 问题2: 市场数据订阅错误

**症状**:
```
Error 354: Requested market data is not subscribed
```

**解决方案**:
```
已修复！脚本现在使用延迟数据（免费）
如果仍有问题，检查:
1. TWS → Account → Market Data Subscriptions
2. 确保Paper账户已激活
3. 重启TWS
```

### 问题3: 没有信号生成

**可能原因**:
```
1. ATR < 8.0 (波动率太低)
2. 不在Kill Zone时间
3. 价格未触及Premium/Discount区域
4. 历史数据不足（需要100+根K线）
```

**调试**:
```bash
# 降低ATR阈值测试
python scripts/run_lightglow_realtime_trader.py \
    --atr-threshold 5.0

# 查看实时指标
# 脚本会打印每根K线的ATR、Premium/Discount等
```

### 问题4: 程序崩溃

**常见原因**:
```
1. IBKR连接断开
2. 网络问题
3. 内存不足
4. 异常K线数据
```

**解决方案**:
```bash
# 使用supervisor自动重启
# 或使用while循环
while true; do
    python scripts/run_lightglow_realtime_trader.py
    echo "Crashed, restarting in 10 seconds..."
    sleep 10
done
```

---

## 📊 性能预期

### 延迟数据模式（当前）

```
数据延迟: 15-20分钟
信号延迟: 15-20分钟
适用场景: 策略验证、逻辑测试
不适用: 实盘交易
```

### 实时数据模式（需订阅）

```
数据延迟: <1秒
信号延迟: <1秒
适用场景: Paper Trading、实盘交易
成本: $10-50/月（取决于交易所）
```

---

## 🎓 最佳实践

### 1. 渐进式部署

```
第1周: 干跑模式，观察信号
第2周: 继续干跑，验证逻辑
第3-4周: Paper Trading（提交订单）
第5-8周: 小仓位实盘（1手）
第9周+: 正常仓位
```

### 2. 监控指标

```
每日记录:
- 信号数量
- 入场次数
- 出场次数
- 盈亏点数
- ATR分布
- Kill Zone覆盖率
```

### 3. 风险管理

```
设置限制:
- 每日最大交易: 50笔
- 每日最大亏损: 400点
- 单笔最大亏损: 50点
- 最大持仓: 1手
```

---

## 📁 文件结构

```
TradingAgentsV2/
├── scripts/
│   ├── run_lightglow_realtime_trader.py  # 实时交易器 ✅
│   ├── export_lightglow_optimized_strategy_trades.py  # 历史信号导出
│   └── run_lightglow_optimized_strategy_paper_trader.py  # 历史信号交易
├── logs/
│   ├── lightglow_20260507.log  # 交易日志
│   └── trader.pid  # 进程ID
└── reports/
    ├── backtest_report_1k.html  # 回测报告
    └── 2022_profit_surge_analysis.md  # 策略分析
```

---

## 🚦 下一步

1. **启动干跑模式**
   ```bash
   python scripts/run_lightglow_realtime_trader.py
   ```

2. **观察1-2周**
   - 记录信号质量
   - 验证逻辑正确性
   - 检查时间过滤器

3. **启动Paper Trading**
   ```bash
   python scripts/run_lightglow_realtime_trader.py --submit
   ```

4. **评估实盘可行性**
   - 对比实际 vs 回测
   - 分析滑点影响
   - 评估执行质量

---

**最后更新**: 2026-05-07  
**版本**: 2.0 (实时版本)  
**状态**: 准备就绪 ✅
