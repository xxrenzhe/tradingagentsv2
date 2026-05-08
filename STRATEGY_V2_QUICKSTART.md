# Lightglow Strategy V2 - Quick Start Guide

## 📋 概述

Lightglow Strategy V2 是原始策略的优化版本，通过添加Kill Zone时段过滤器来提升风险调整后收益。

### 核心改进

```
指标                  V1 (原始)      V2 (非KZ)      改进
====================================================================
净利润               $2,205,060     $2,124,958     -3.6%
盈利因子             1.91           2.45           +28.2% ✅
平均每笔             $52.85         $66.49         +25.8% ✅
最大回撤             $46,470        $33,580        -27.7% ✅
利润/回撤比          47.45          63.28          +33.4% ✅
```

**结论**: 牺牲3.6%的利润，换来28%的盈利因子提升和更低的风险。

---

## 🚀 快速开始

### 1. 生成V2策略交易文件

```bash
# 从原始交易中过滤掉Kill Zone交易
python scripts/export_lightglow_v2_strategy_trades.py
```

这会创建 `.tmp/nq-lightglow-v2-strategy-trades.csv`，包含31,959笔非Kill Zone交易。

---

### 2. 运行Paper Trading (Dry-Run)

```bash
# 持续监控模式（推荐）
python scripts/run_lightglow_v2_paper_trader.py --daemon --max-iterations 0

# 单次运行
python scripts/run_lightglow_v2_paper_trader.py
```

---

### 3. 启用实盘提交（谨慎）

```bash
# 需要添加 --allow-entry-only-submit 标志
python scripts/run_lightglow_v2_paper_trader.py \
    --daemon \
    --submit \
    --allow-entry-only-submit \
    --max-iterations 0
```

⚠️ **警告**: 当前版本只支持入场，不支持自动2分钟出场。需要手动管理出场。

---

## 📊 V2策略详细说明

### Kill Zone过滤器

**禁止交易时段** (EST):
- NY AM Kill Zone: 8:30 - 11:30
- NY PM Kill Zone: 13:30 - 16:00

**允许交易时段** (EST):
- 亚洲时段: 18:00 - 02:00 (最佳)
- 伦敦时段: 02:00 - 08:30 (良好)
- 午休时段: 11:30 - 13:30 (可交易)
- 盘后时段: 16:00 - 18:00 (可交易)

### 为什么避免Kill Zone？

```
Kill Zone表现:
- 盈利因子: 1.08 (vs 2.45 非KZ)
- 平均每笔: $8.21 (vs $66.49 非KZ)
- 贡献利润: 仅3.6%

原因:
❌ 高波动导致假反转信号
❌ 强趋势不利于反转策略
❌ 机构订单方向性强
❌ 交易质量低
```

---

## 📁 文件结构

### 核心文件

```
tradingagents/execution/
├── kill_zone_filter.py              # Kill Zone过滤器工具
└── (其他执行文件)

scripts/
├── export_lightglow_v2_strategy_trades.py   # 生成V2交易文件
└── run_lightglow_v2_paper_trader.py         # V2 Paper Trading脚本

.tmp/
├── signals_trades.csv                       # 原始策略交易 (V1)
└── nq-lightglow-v2-strategy-trades.csv     # V2策略交易

文档/
├── STRATEGY_EXPLAINED.md            # V1策略说明
├── STRATEGY_V2_EXPLAINED.md         # V2策略详细说明
└── STRATEGY_V2_QUICKSTART.md        # 本文件
```

---

## 🔧 Kill Zone过滤器API

### Python使用示例

```python
from datetime import datetime
import pytz
from tradingagents.execution.kill_zone_filter import (
    is_kill_zone,
    should_trade,
    get_session_name,
)

# 创建时间戳
ny_tz = pytz.timezone('America/New_York')
timestamp = ny_tz.localize(datetime(2026, 5, 8, 10, 0))

# 检查是否在Kill Zone
if is_kill_zone(timestamp):
    print("在Kill Zone，不交易")
else:
    print("不在Kill Zone，可以交易")

# 或者直接使用
if should_trade(timestamp):
    print("允许交易")

# 获取时段名称
session = get_session_name(timestamp)
print(f"当前时段: {session}")
```

### 主要函数

```python
is_kill_zone(timestamp: datetime) -> bool
    # 检查是否在Kill Zone
    # 返回: True=在KZ, False=不在KZ

should_trade(timestamp: datetime, *, allow_kill_zone: bool = False) -> bool
    # 判断是否应该交易
    # allow_kill_zone=True 可以覆盖过滤器

get_session_name(timestamp: datetime) -> str
    # 获取时段名称
    # 返回: 'Asian', 'London', 'NY_AM_Kill_Zone', 等

get_kill_zone_stats(timestamps: list[datetime]) -> dict
    # 计算Kill Zone统计信息
    # 返回: 包含统计数据的字典
```

---

## 📈 监控指标

### 每日检查

```bash
# 检查今日交易
grep "$(date +%Y-%m-%d)" .tmp/nq-lightglow-v2-paper-runner-state.json

# 关键指标:
✅ 是否有Kill Zone交易？（应该为0）
✅ 盈利因子是否 > 2.0？
✅ 当日盈亏是否正常？
```

### 每周检查

```python
# 分析一周的交易
import pandas as pd

trades = pd.read_csv('.tmp/nq-lightglow-v2-strategy-trades.csv')
trades['entry_ts'] = pd.to_datetime(trades['entry_ts'])

# 最近一周
recent = trades[trades['entry_ts'] > pd.Timestamp.now() - pd.Timedelta(days=7)]

# 计算指标
wins = recent[recent['net_dollars'] > 0]['net_dollars'].sum()
losses = abs(recent[recent['net_dollars'] < 0]['net_dollars'].sum())
pf = wins / losses if losses > 0 else 0

print(f"周度盈利因子: {pf:.2f}")
print(f"周度交易数: {len(recent)}")
print(f"周度净利润: ${recent['net_dollars'].sum():,.0f}")
```

---

## ⚠️ 重要注意事项

### 1. 时间出场未实现

当前版本**不支持自动2分钟时间出场**。如果使用 `--submit`，需要：
- 手动监控持仓
- 在2分钟后手动平仓
- 或者等待自动出场功能实现

### 2. Paper账户数据延迟

Paper账户数据延迟10-15分钟，实盘表现可能不同：
- 滑点可能更大
- 执行速度可能不同
- 需要在实盘前充分测试

### 3. 参数优化

V2策略使用V1的优化参数。如果市场条件改变，可能需要：
- 重新优化参数
- 调整ATR阈值
- 调整Premium/Discount百分位数

### 4. 回测vs实盘

回测表现不代表未来：
- 市场条件可能改变
- 执行成本可能不同
- 需要持续监控和调整

---

## 🔄 从V1迁移到V2

### 如果你正在运行V1

```bash
# 1. 停止V1 Paper Trading
# (Ctrl+C 停止运行中的脚本)

# 2. 生成V2交易文件
python scripts/export_lightglow_v2_strategy_trades.py

# 3. 启动V2 Paper Trading
python scripts/run_lightglow_v2_paper_trader.py --daemon --max-iterations 0

# 4. 监控对比
# 比较V1和V2的实际表现
```

### 如果你想回退到V1

```bash
# 使用 --disable-kill-zone-filter 标志
python scripts/run_lightglow_v2_paper_trader.py \
    --daemon \
    --disable-kill-zone-filter \
    --max-iterations 0
```

---

## 📚 更多文档

- **V1策略说明**: `STRATEGY_EXPLAINED.md`
- **V2策略详细说明**: `STRATEGY_V2_EXPLAINED.md`
- **完整探索历程**: `FINAL_EXPLORATION_SUMMARY.md`
- **组合策略测试**: `COMBINED_STRATEGY_TEST.md`

---

## 🆘 故障排除

### 问题: 没有生成交易

**检查**:
1. 是否在Kill Zone时段？
2. ATR是否 > 8.0？
3. 价格是否在Premium/Discount区域？
4. 是否已有持仓？

### 问题: 盈利因子低于预期

**可能原因**:
1. 市场条件改变
2. 执行滑点过大
3. 数据延迟影响
4. 需要重新优化参数

### 问题: Kill Zone仍有交易

**检查**:
1. 是否使用了V2脚本？
2. 是否禁用了过滤器？
3. 时区设置是否正确？
4. 查看日志确认过滤器状态

---

## 📞 支持

如有问题，请查看：
1. 策略文档 (`STRATEGY_V2_EXPLAINED.md`)
2. 代码注释
3. 测试脚本输出

---

**祝交易顺利！** 🚀

记住：V2策略的目标不是最高利润，而是最佳风险调整后收益！
