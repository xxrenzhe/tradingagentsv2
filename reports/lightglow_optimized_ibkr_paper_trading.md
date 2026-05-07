# Lightglow优化策略 - IBKR Paper Trading集成指南

## 📋 概述

本指南介绍如何将Lightglow优化策略接入IBKR Paper Trading进行实时验证。

**策略参数**:
- 品种: NQ期货 (Nasdaq 100 E-mini)
- 周期: 1分钟
- 信号: Premium/Discount反转
- 出场: 2根K线
- 过滤器: ATR > 8.0, NY Kill Zone

**回测表现 (2020-2026)**:
- 净利润: $5,996,565
- 盈利因子: 4.73
- 胜率: 58.0%
- 最大回撤: $39,695
- 夏普比率: 5.00

---

## 🚀 快速开始

### 步骤1: 导出交易信号

```bash
# 导出最近的交易信号
python scripts/export_lightglow_optimized_strategy_trades.py \
    --start-date 2026-04-01 \
    --end-date 2026-05-07 \
    --output .tmp/nq-lightglow-optimized-strategy-trades.csv
```

**输出**:
```json
{
  "status": "written",
  "strategy_id": "lightglow_premium_discount_optimized_1m_killzone_atr8",
  "selected_alias": "lightglow_optimized_1m_premium_discount",
  "rows": 1234,
  "output": ".tmp/nq-lightglow-optimized-strategy-trades.csv",
  "timeframe": "1m",
  "session": "killzone",
  "atr_threshold": 8.0
}
```

### 步骤2: 运行Paper Trading (Dry Run)

```bash
# 干跑模式 - 不提交订单，只监控信号
python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --trades .tmp/nq-lightglow-optimized-strategy-trades.csv \
    --symbol MNQ \
    --contract-month 202606 \
    --quantity 1
```

### 步骤3: 守护进程模式 (持续监控)

```bash
# 每60秒检查一次新信号
python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --trades .tmp/nq-lightglow-optimized-strategy-trades.csv \
    --symbol MNQ \
    --contract-month 202606 \
    --quantity 1 \
    --daemon \
    --interval-seconds 60 \
    --max-iterations 0
```

### 步骤4: 实际提交 (需要确认)

```bash
# ⚠️ 警告: 这会实际提交订单到IBKR Paper账户
python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --trades .tmp/nq-lightglow-optimized-strategy-trades.csv \
    --symbol MNQ \
    --contract-month 202606 \
    --quantity 1 \
    --submit \
    --allow-entry-only-submit \
    --daemon \
    --interval-seconds 60
```

---

## 📊 命令行参数

### 导出脚本参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--start-date` | 2021-04-28 | 开始日期 |
| `--end-date` | 2026-04-28 | 结束日期 |
| `--cache` | .tmp/nq-lightglow-optimized-features-cache.pkl | 缓存文件 |
| `--output` | .tmp/nq-lightglow-optimized-strategy-trades.csv | 输出文件 |
| `--chunk-size` | 500000 | 数据块大小 |
| `--min-volume` | 1.0 | 最小成交量 |

### Paper Trading参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--trades` | .tmp/nq-lightglow-optimized-strategy-trades.csv | 交易信号文件 |
| `--symbol` | MNQ | 交易品种 |
| `--contract-month` | 202606 | 合约月份 |
| `--quantity` | 1 | 交易数量 |
| `--submit` | False | 是否提交订单 |
| `--allow-entry-only-submit` | False | 允许只入场提交 |
| `--daemon` | False | 守护进程模式 |
| `--interval-seconds` | 60.0 | 检查间隔（秒） |
| `--max-iterations` | 1 | 最大迭代次数（0=无限） |
| `--max-signal-age-minutes` | 10.0 | 最大信号年龄（分钟） |
| `--record-ticks` | False | 记录tick数据 |
| `--agent-gate` | False | 需要多代理审核 |

---

## 🔧 工作流程

### 1. 信号生成流程

```
Databento数据 
    ↓
加载1分钟K线
    ↓
计算Premium/Discount区域
    ↓
应用ATR过滤器 (> 8.0)
    ↓
应用时间过滤器 (Kill Zone)
    ↓
生成入场信号
    ↓
导出到CSV
```

### 2. Paper Trading流程

```
加载交易信号CSV
    ↓
连接IBKR TWS/Gateway
    ↓
检查当前时间是否有信号
    ↓
验证信号年龄 (< 10分钟)
    ↓
执行预检查
    ↓
提交订单 (如果--submit)
    ↓
记录结果
    ↓
等待下一个周期
```

---

## ⚠️ 重要注意事项

### 1. 时间出场问题

**当前限制**:
```
策略需要在2根K线后平仓（2分钟）
但当前脚本不支持自动时间出场
```

**解决方案**:
```
选项A: 手动监控并平仓
选项B: 使用--allow-entry-only-submit + 手动出场
选项C: 等待时间出场管理器开发完成
```

### 2. Kill Zone时间

**NY Kill Zone (EST)**:
```
上午: 8:30 - 11:30
下午: 13:30 - 16:00
```

**UTC时间**:
```
上午: 13:30 - 16:30
下午: 18:30 - 21:00
```

### 3. ATR过滤器

```
只在ATR > 8.0时交易
低波动期可能没有信号
这是正常的，不要强制交易
```

### 4. 信号年龄

```
默认: 信号必须在10分钟内
过期信号会被跳过
使用--allow-stale-signal-submit可以覆盖
```

---

## 📈 监控和日志

### 状态快照

```bash
# 查看当前状态
cat .tmp/nq-lightglow-optimized-paper-runner-state.json
```

**示例输出**:
```json
{
  "last_processed_date": "2026-05-07",
  "last_processed_row": 123,
  "total_signals": 456,
  "submitted_trades": 10,
  "dry_runs": 446,
  "last_update": "2026-05-07T14:30:00Z"
}
```

### Tick数据记录

```bash
# 启用tick记录
python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --record-ticks \
    --tick-output-dir .tmp/ibkr-paper-ticks \
    --tick-interval-seconds 1.0 \
    --max-ticks 120
```

**输出**:
```
.tmp/ibkr-paper-ticks/
├── MNQ_202606_20260507_143000.csv
├── MNQ_202606_20260507_143200.csv
└── ...
```

---

## 🎯 使用场景

### 场景1: 每日信号导出

```bash
#!/bin/bash
# daily_export.sh

TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

python scripts/export_lightglow_optimized_strategy_trades.py \
    --start-date $YESTERDAY \
    --end-date $TODAY \
    --output .tmp/nq-lightglow-optimized-today.csv

echo "Exported signals for $TODAY"
```

### 场景2: 实时监控（不提交）

```bash
#!/bin/bash
# monitor.sh

python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --trades .tmp/nq-lightglow-optimized-strategy-trades.csv \
    --symbol MNQ \
    --daemon \
    --interval-seconds 60 \
    --max-iterations 0 \
    --record-ticks \
    2>&1 | tee logs/lightglow_monitor_$(date +%Y%m%d).log
```

### 场景3: Paper Trading（提交订单）

```bash
#!/bin/bash
# paper_trade.sh

# 确认IBKR TWS已连接
if ! nc -z localhost 7497; then
    echo "Error: IBKR TWS not connected"
    exit 1
fi

python scripts/run_lightglow_optimized_strategy_paper_trader.py \
    --trades .tmp/nq-lightglow-optimized-strategy-trades.csv \
    --symbol MNQ \
    --contract-month 202606 \
    --quantity 1 \
    --submit \
    --allow-entry-only-submit \
    --daemon \
    --interval-seconds 60 \
    --max-iterations 0 \
    --record-ticks \
    --agent-gate \
    2>&1 | tee logs/lightglow_paper_$(date +%Y%m%d).log
```

---

## 🔍 故障排查

### 问题1: 没有信号生成

**可能原因**:
```
1. ATR < 8.0 (波动率太低)
2. 不在Kill Zone时间
3. 价格没有触及Premium/Discount区域
4. 数据缺失
```

**解决方案**:
```bash
# 检查最近的K线数据
python -c "
from scripts.search_nq_bar_2r_walkforward import load_continuous_nq_bars
import argparse
args = argparse.Namespace(
    start_date='2026-05-07',
    end_date='2026-05-07',
    cache='.tmp/test.pkl',
    chunk_size=100000,
    min_volume=1.0
)
bars = load_continuous_nq_bars(args)
print(f'Loaded {len(bars)} bars')
print(bars.tail())
"
```

### 问题2: IBKR连接失败

**检查清单**:
```
□ TWS/Gateway是否运行？
□ API端口是否正确？(7497 for TWS, 4001 for Gateway)
□ API设置是否启用？
□ 防火墙是否允许？
□ Paper账户是否激活？
```

### 问题3: 信号过期

**原因**:
```
信号生成时间 > 10分钟前
```

**解决方案**:
```bash
# 选项1: 增加最大年龄
--max-signal-age-minutes 30

# 选项2: 允许过期信号
--allow-stale-signal-submit

# 选项3: 更频繁地导出信号
# 每小时运行一次导出脚本
```

---

## 📊 性能预期

### 正常市场条件

```
每日信号: 10-20个
每周交易: 50-100笔
月度盈利: $30K-$80K (基于回测)
胜率: 50-60%
```

### 高波动期（类似2022年）

```
每日信号: 30-50个
每周交易: 150-250笔
月度盈利: $100K-$500K (基于回测)
胜率: 60-65%
```

### 低波动期

```
每日信号: 2-5个
每周交易: 10-25笔
月度盈利: $10K-$30K (基于回测)
胜率: 45-50%
```

---

## 🎓 最佳实践

### 1. 渐进式部署

```
第1周: 只监控，不提交
第2周: 手动执行部分信号
第3-4周: 小仓位自动提交（1手）
第5-8周: 正常仓位（根据资金）
```

### 2. 风险管理

```
□ 设置每日最大交易数（50笔）
□ 设置每日最大亏损（400点）
□ 监控滑点和执行质量
□ 记录所有交易
□ 每周回顾表现
```

### 3. 监控指标

```
□ 信号生成频率
□ 信号执行率
□ 实际滑点 vs 回测
□ 实际盈亏 vs 回测
□ ATR分布
□ Kill Zone覆盖率
```

---

## 📁 文件结构

```
TradingAgentsV2/
├── scripts/
│   ├── export_lightglow_optimized_strategy_trades.py  # 导出信号
│   ├── run_lightglow_optimized_strategy_paper_trader.py  # Paper Trading
│   └── backtest_lightglow_nq_bars.py  # 回测引擎
├── .tmp/
│   ├── nq-lightglow-optimized-strategy-trades.csv  # 交易信号
│   ├── nq-lightglow-optimized-paper-runner-state.json  # 状态
│   └── ibkr-paper-ticks/  # Tick数据
├── logs/
│   ├── lightglow_monitor_20260507.log  # 监控日志
│   └── lightglow_paper_20260507.log  # 交易日志
└── reports/
    ├── backtest_report_1k.html  # 回测报告
    └── 2022_profit_surge_analysis.md  # 分析报告
```

---

## 🚦 下一步

1. **测试导出脚本**
   ```bash
   python scripts/export_lightglow_optimized_strategy_trades.py \
       --start-date 2026-05-01 \
       --end-date 2026-05-07
   ```

2. **验证信号质量**
   ```bash
   # 检查导出的信号
   head -20 .tmp/nq-lightglow-optimized-strategy-trades.csv
   ```

3. **启动监控模式**
   ```bash
   python scripts/run_lightglow_optimized_strategy_paper_trader.py \
       --daemon \
       --interval-seconds 60
   ```

4. **观察1-2周后决定是否提交**

---

## 📞 支持

如有问题，请查看：
- 回测报告: `reports/backtest_report_1k.html`
- 策略分析: `reports/2022_profit_surge_analysis.md`
- Pine脚本: `pine_scripts/lightglow_optimized_strategy.pine`

---

**最后更新**: 2026-05-07  
**版本**: 1.0  
**状态**: 准备就绪 ✅
