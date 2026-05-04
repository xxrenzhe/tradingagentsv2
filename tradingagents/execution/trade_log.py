from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_TRADE_LOG_DIR = Path("docs/Strategy/tradelogs")


def append_trade_log(
    result: dict[str, Any],
    *,
    log_dir: Path | str = DEFAULT_TRADE_LOG_DIR,
    created_at: datetime | None = None,
) -> Path | None:
    if not result.get("submitted"):
        return None
    intent = result.get("intent")
    if not isinstance(intent, dict):
        return None
    timestamp = _event_timestamp(result, created_at)
    output = Path(log_dir) / f"{timestamp.date().isoformat()}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        output.write_text(f"# 交易记录 {timestamp.date().isoformat()}\n\n", encoding="utf-8")
    intent_id = str(intent.get("intent_id") or "")
    existing_content = output.read_text(encoding="utf-8")
    if intent_id and (f"- 订单ID：`{intent_id}`" in existing_content or f"- Intent ID: `{intent_id}`" in existing_content):
        return output
    with output.open("a", encoding="utf-8") as handle:
        handle.write(_format_entry(result, timestamp))
    return output


def append_execution_fill_log(
    fill: dict[str, Any],
    *,
    log_dir: Path | str = DEFAULT_TRADE_LOG_DIR,
) -> Path | None:
    execution = fill.get("execution") if isinstance(fill.get("execution"), dict) else {}
    contract = fill.get("contract") if isinstance(fill.get("contract"), dict) else {}
    exec_id = str(execution.get("exec_id") or "")
    timestamp = _parse_timestamp(execution.get("time")) or datetime.now(UTC)
    output = Path(log_dir) / f"{timestamp.date().isoformat()}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        output.write_text(f"# 交易记录 {timestamp.date().isoformat()}\n\n", encoding="utf-8")
    existing_content = output.read_text(encoding="utf-8")
    if exec_id and f"- 成交ID：`{exec_id}`" in existing_content:
        return output
    with output.open("a", encoding="utf-8") as handle:
        handle.write(_format_execution_fill_entry(fill, timestamp, execution, contract))
    return output


def _event_timestamp(result: dict[str, Any], fallback: datetime | None) -> datetime:
    candidates = [
        result.get("result", {}).get("created_at") if isinstance(result.get("result"), dict) else None,
        result.get("created_at"),
        fallback,
    ]
    for candidate in candidates:
        timestamp = _parse_timestamp(candidate)
        if timestamp is not None:
            return timestamp
    return datetime.now(UTC)


def _format_entry(result: dict[str, Any], timestamp: datetime) -> str:
    intent = result.get("intent") if isinstance(result.get("intent"), dict) else {}
    broker_result = result.get("result") if isinstance(result.get("result"), dict) else {}
    selected_trade = result.get("selected_trade") if isinstance(result.get("selected_trade"), dict) else {}
    live_signal = result.get("live_signal") if isinstance(result.get("live_signal"), dict) else {}
    preflight = broker_result.get("preflight") if isinstance(broker_result.get("preflight"), dict) else {}
    market_data = preflight.get("market_data") if isinstance(preflight.get("market_data"), dict) else {}
    risk = broker_result.get("risk") if isinstance(broker_result.get("risk"), dict) else {}
    protection = broker_result.get("protection") if isinstance(broker_result.get("protection"), dict) else {}
    trades = broker_result.get("trades") if isinstance(broker_result.get("trades"), list) else []
    direction = _direction_label(intent.get("action"), selected_trade.get("direction") or live_signal.get("direction"))
    action = str(intent.get("action", "UNKNOWN")).upper()
    action_label = "买入开多" if action == "BUY" else "卖出开空" if action == "SELL" else action
    reference_source = _reason_value(intent.get("reason"), "reference_source")
    reference_price = _reason_value(intent.get("reason"), "reference_price")
    lines = [
        f"## {timestamp.isoformat()} - {action_label} {intent.get('quantity', '')} {intent.get('symbol', '')}",
        "",
        f"- 账户：`{intent.get('account', '')}`",
        f"- 策略：`{intent.get('strategy_id', selected_trade.get('strategy_name', ''))}`",
        f"- 方向：`{direction}`",
        f"- 入场：`{reference_source}` @ `{reference_price}`，盘口 bid/ask/last=`{market_data.get('bid', selected_trade.get('ibkr_bid', live_signal.get('ibkr_bid', '')))}`/`{market_data.get('ask', selected_trade.get('ibkr_ask', live_signal.get('ibkr_ask', '')))}`/`{market_data.get('last', selected_trade.get('ibkr_last', live_signal.get('ibkr_last', '')))}`",
        f"- 止损/止盈：`{intent.get('stop_loss_price', '')}` / `{intent.get('take_profit_price', '')}`",
        f"- 成交状态：{_trade_status_summary(trades)}；保护单：{_protection_summary(protection)}",
        f"- 下单理由：{_order_reason_cn(intent, selected_trade, live_signal, reference_source, reference_price)}",
        f"- 订单ID：`{intent.get('intent_id', '')}`",
        "",
    ]
    return "\n".join(lines)


def _format_execution_fill_entry(
    fill: dict[str, Any],
    timestamp: datetime,
    execution: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    side = str(execution.get("side") or "").upper()
    action = "BUY" if side in {"BOT", "BUY"} else "SELL" if side in {"SLD", "SELL"} else side
    action_label = "买入成交" if action == "BUY" else "卖出成交" if action == "SELL" else "成交"
    quantity = execution.get("shares", "")
    symbol = contract.get("symbol", "")
    price = execution.get("price", "")
    lines = [
        f"## {timestamp.isoformat()} - {action_label} {quantity} {symbol}",
        "",
        f"- 账户：`{execution.get('account', '')}`",
        f"- 合约：`{symbol}` `{contract.get('localSymbol', contract.get('local_symbol', ''))}`",
        f"- 方向：`{_direction_label(action, None)}`",
        f"- 成交价/数量：`{price}` / `{quantity}`",
        f"- 下单理由：IBKR 实际成交回填；该成交来自账户 execution，不一定由当前自动策略进程提交。",
        f"- 订单ID：`ibkr_order_{execution.get('order_id', '')}`",
        f"- 成交ID：`{execution.get('exec_id', '')}`",
        "",
    ]
    return "\n".join(lines)


def _direction_label(action: Any, direction: Any) -> str:
    if action:
        return "做空" if str(action).upper() == "SELL" else "做多"
    try:
        return "做多" if int(direction) > 0 else "做空"
    except (TypeError, ValueError):
        return "未知"


def _trade_status_summary(trades: list[Any]) -> str:
    statuses = []
    for trade in trades[:3]:
        if not isinstance(trade, dict):
            continue
        order = trade.get("order") if isinstance(trade.get("order"), dict) else {}
        order_status = trade.get("order_status") if isinstance(trade.get("order_status"), dict) else {}
        action = order.get("action", "")
        status = order_status.get("status", "")
        filled = order_status.get("filled", "")
        if action or status:
            statuses.append(f"{action} {status} filled={filled}")
    return "；".join(statuses) if statuses else "未返回成交明细"


def _protection_summary(protection: dict[str, Any]) -> str:
    if not protection:
        return "无保护单信息"
    active = "已挂出" if protection.get("active") else "未激活"
    order_types = protection.get("order_types")
    if isinstance(order_types, list) and order_types:
        return f"{active} {'+'.join(str(order_type) for order_type in order_types)}"
    exit_count = protection.get("exit_order_count", "")
    return f"{active}，退出单数量={exit_count}"


def _order_reason_cn(
    intent: dict[str, Any],
    selected_trade: dict[str, Any],
    live_signal: dict[str, Any],
    reference_source: str,
    reference_price: str,
) -> str:
    signal_source = str(selected_trade.get("signal_source", live_signal.get("signal_source", "")))
    direction = _direction_label(intent.get("action"), selected_trade.get("direction") or live_signal.get("direction"))
    strategy = intent.get("strategy_id", selected_trade.get("strategy_name", "当前策略"))
    session = selected_trade.get("session_bucket", live_signal.get("session_bucket", ""))
    imbalance = live_signal.get("strategy_imbalance", selected_trade.get("imbalance_last", ""))
    z_score = live_signal.get("strategy_z_score", selected_trade.get("strategy_z_score", ""))
    if "mean_reversion" in signal_source:
        signal_text = f"均值回归信号触发，方向为{direction}"
    else:
        signal_text = f"策略信号触发，方向为{direction}"
    details = [signal_text, f"策略={strategy}"]
    if session:
        details.append(f"交易时段={session}")
    if z_score != "":
        details.append(f"z_score={z_score}")
    if imbalance != "":
        details.append(f"imbalance={imbalance}")
    if reference_source or reference_price:
        details.append(f"以{reference_source or '当前市场价'} {reference_price} 作为入场参考")
    details.append(f"同步设置止损 {intent.get('stop_loss_price', '')}、止盈 {intent.get('take_profit_price', '')}")
    return "；".join(str(detail) for detail in details)


def _reason_value(reason: Any, key: str) -> str:
    text = str(reason or "")
    prefix = f"{key}="
    for part in text.split("|"):
        part = part.strip()
        if part.startswith(prefix):
            return part[len(prefix) :]
    return ""


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)
