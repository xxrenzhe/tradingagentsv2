from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import pandas as pd

from tradingagents.llm_clients.factory import create_llm_client

from .ibkr import IBKRContractSpec, IBKROrderIntent, IBKRPaperBroker, IBKRPaperTradingSession
from .trade_log import DEFAULT_TRADE_LOG_DIR


@dataclass(frozen=True)
class FeatureTrigger:
    feature_set: str
    candidate: str
    direction: str
    trigger_price: float
    trigger_time: str
    win_rate: float
    payoff_ratio_r: float
    net_points: float = 0.0
    filter_name: str = "none"
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_series(cls, row: pd.Series, *, trigger_price: float, trigger_time: str | None = None) -> "FeatureTrigger":
        return cls(
            feature_set=str(row.get("feature_set", row.get("candidate", ""))),
            candidate=str(row.get("candidate", "")),
            direction=str(row.get("direction", "unknown")),
            trigger_price=float(trigger_price),
            trigger_time=trigger_time or datetime.now(UTC).isoformat(),
            win_rate=float(row.get("win_rate", row.get("test_win_rate", 0.0))),
            payoff_ratio_r=float(row.get("payoff_ratio_r", row.get("test_payoff_ratio_r", 0.0))),
            net_points=float(row.get("net_points", row.get("test_net_points", 0.0))),
            filter_name=str(row.get("filter", "none")),
            context={key: normalize_json_value(value) for key, value in row.to_dict().items()},
        )


@dataclass(frozen=True)
class DebateExecutionPlan:
    decision_id: str
    feature_set: str
    stance: str
    recheck_after_seconds: int
    long_trigger: float | None = None
    short_trigger: float | None = None
    no_trade_low: float | None = None
    no_trade_high: float | None = None
    long_stop: float | None = None
    long_target: float | None = None
    short_stop: float | None = None
    short_target: float | None = None
    max_chase_points: float = 6.0
    order_type: str = "MKT"
    limit_offset_points: float = 0.0
    confidence: float = 0.0
    debate_summary: dict[str, str] = field(default_factory=dict)
    raw_response: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DebateExecutionPlan":
        return cls(
            decision_id=str(payload.get("decision_id") or f"debate_{uuid4().hex}"),
            feature_set=str(payload.get("feature_set") or payload.get("feature_id") or ""),
            stance=str(payload.get("stance") or payload.get("final_instruction") or "conditional"),
            recheck_after_seconds=int(float(payload.get("recheck_after_seconds", 120))),
            long_trigger=optional_float(payload.get("long_trigger")),
            short_trigger=optional_float(payload.get("short_trigger")),
            no_trade_low=optional_float(payload.get("no_trade_low")),
            no_trade_high=optional_float(payload.get("no_trade_high")),
            long_stop=optional_float(payload.get("long_stop")),
            long_target=optional_float(payload.get("long_target")),
            short_stop=optional_float(payload.get("short_stop")),
            short_target=optional_float(payload.get("short_target")),
            max_chase_points=float(payload.get("max_chase_points", 6.0)),
            order_type=str(payload.get("order_type", "MKT")).upper(),
            limit_offset_points=float(payload.get("limit_offset_points", 0.0)),
            confidence=float(payload.get("confidence", 0.0)),
            debate_summary=dict(payload.get("debate_summary") or {}),
            raw_response=str(payload.get("raw_response", "")),
        )


class DebatePlanner(Protocol):
    def build_plan(self, trigger: FeatureTrigger, snapshots: list[dict[str, Any]]) -> DebateExecutionPlan:
        ...


@dataclass(frozen=True)
class StaticDebatePlanner:
    plan: DebateExecutionPlan

    def build_plan(self, trigger: FeatureTrigger, snapshots: list[dict[str, Any]]) -> DebateExecutionPlan:
        return self.plan


@dataclass(frozen=True)
class RuleDebatePlanner:
    recheck_after_seconds: int = 120
    stop_points: float = 16.0
    target_points: float = 24.0
    buffer_points: float = 2.0
    max_chase_points: float = 6.0

    def build_plan(self, trigger: FeatureTrigger, snapshots: list[dict[str, Any]]) -> DebateExecutionPlan:
        price = trigger.trigger_price
        long_bias = trigger.direction.lower() == "long"
        short_bias = trigger.direction.lower() == "short"
        long_trigger = price + self.buffer_points if long_bias else price + self.stop_points * 0.5
        short_trigger = price - self.stop_points * 0.5 if long_bias else price - self.buffer_points
        return DebateExecutionPlan(
            decision_id=f"rule_debate_{uuid4().hex}",
            feature_set=trigger.feature_set,
            stance="conditional",
            recheck_after_seconds=self.recheck_after_seconds,
            long_trigger=round_to_tick(long_trigger),
            short_trigger=round_to_tick(short_trigger),
            no_trade_low=round_to_tick(short_trigger),
            no_trade_high=round_to_tick(long_trigger),
            long_stop=round_to_tick(price - self.stop_points),
            long_target=round_to_tick(price + self.target_points),
            short_stop=round_to_tick(price + self.stop_points),
            short_target=round_to_tick(price - self.target_points),
            max_chase_points=self.max_chase_points,
            confidence=0.55 if long_bias or short_bias else 0.0,
            debate_summary={
                "long_case": "If price holds above the trigger zone after the delay, the flush failed and reversal/continuation can be bought.",
                "short_case": "If price breaks below the invalidation zone after the delay, the setup failed and breakdown continuation is favored.",
                "risk_case": "Skip if price remains inside the no-trade zone or has already moved beyond the chase budget.",
            },
        )


@dataclass(frozen=True)
class LLMDebatePlanner:
    provider: str
    model: str
    base_url: str | None = None
    timeout: float = 60.0
    fallback: DebatePlanner = field(default_factory=RuleDebatePlanner)

    def build_plan(self, trigger: FeatureTrigger, snapshots: list[dict[str, Any]]) -> DebateExecutionPlan:
        prompt = build_debate_prompt(trigger, snapshots)
        try:
            llm = create_llm_client(
                self.provider,
                self.model,
                base_url=self.base_url,
                timeout=self.timeout,
            ).get_llm()
            response = llm.invoke(prompt)
            content = getattr(response, "content", response)
            payload = extract_json_object(str(content))
            payload["raw_response"] = str(content)
            return DebateExecutionPlan.from_dict(payload)
        except Exception as exc:
            fallback_plan = self.fallback.build_plan(trigger, snapshots)
            return DebateExecutionPlan(
                **(
                    asdict(fallback_plan)
                    | {
                        "debate_summary": fallback_plan.debate_summary
                        | {"fallback_reason": str(exc) or exc.__class__.__name__},
                        "raw_response": f"llm_fallback:{exc}",
                    }
                )
            )


@dataclass(frozen=True)
class DebateDelayedStrategyConfig:
    feature_sets_path: Path = Path("reports/NQ-5y-high-win-payoff-past-fold-validation.csv")
    audit_path: Path = Path(".tmp/nq-llm-debate-paper-audit.jsonl")
    state_path: Path = Path(".tmp/nq-llm-debate-paper-state.json")
    contract: IBKRContractSpec = IBKRContractSpec()
    account: str | None = None
    quantity: int = 1
    submit: bool = False
    skip_preflight: bool = False
    min_win_rate: float = 0.53
    min_payoff_ratio: float = 1.0
    min_net_points: float = 0.0
    max_signal_age_seconds: float = 300.0
    snapshot_attempts: int = 3
    snapshot_retry_seconds: float = 1.0
    allow_existing_exposure: bool = False
    enforce_delay: bool = True
    trade_log_dir: Path = DEFAULT_TRADE_LOG_DIR


@dataclass(frozen=True)
class FeatureScannerConfig:
    history_path: Path = Path(".tmp/nq-llm-debate-scanner-history.jsonl")
    state_path: Path = Path(".tmp/nq-llm-debate-scanner-state.json")
    feature_set: str | None = None
    min_history_points: int = 7
    max_history_points: int = 180
    cooldown_seconds: float = 120.0
    support_reclaim_points: float = 1.0
    max_support_reclaim_points: float = 12.0
    vwap_distance_z_threshold: float = 0.67
    require_order_ready: bool = True


@dataclass(frozen=True)
class RealtimeDebateTraderConfig:
    strategy: DebateDelayedStrategyConfig = DebateDelayedStrategyConfig()
    scanner: FeatureScannerConfig = FeatureScannerConfig()
    interval_seconds: float = 30.0
    max_iterations: int | None = 1
    preflight_attempts: int = 3
    preflight_retry_seconds: float = 1.0
    require_preflight_ready: bool = True
    status_path: Path = Path(".tmp/nq-llm-debate-realtime-status.json")


def load_tradeable_feature_sets(
    path: Path | str,
    *,
    min_win_rate: float = 0.53,
    min_payoff_ratio: float = 1.0,
    min_net_points: float = 0.0,
) -> pd.DataFrame:
    frame = pd.read_csv(path)
    win_column = "test_win_rate" if "test_win_rate" in frame.columns else "win_rate"
    payoff_column = "test_payoff_ratio_r" if "test_payoff_ratio_r" in frame.columns else "payoff_ratio_r"
    net_column = "test_net_points" if "test_net_points" in frame.columns else "net_points"
    selected = frame[
        (pd.to_numeric(frame[win_column], errors="coerce") > min_win_rate)
        & (pd.to_numeric(frame[payoff_column], errors="coerce") > min_payoff_ratio)
        & (pd.to_numeric(frame[net_column], errors="coerce") > min_net_points)
    ].copy()
    selected["win_rate"] = pd.to_numeric(selected[win_column], errors="coerce")
    selected["payoff_ratio_r"] = pd.to_numeric(selected[payoff_column], errors="coerce")
    selected["net_points"] = pd.to_numeric(selected[net_column], errors="coerce")
    return selected.reset_index(drop=True)


def run_realtime_debate_trader(
    *,
    feature_sets: pd.DataFrame,
    planner: DebatePlanner,
    config: RealtimeDebateTraderConfig | None = None,
    broker: IBKRPaperBroker | None = None,
) -> dict[str, Any]:
    config = config or RealtimeDebateTraderConfig()
    active_broker = broker or IBKRPaperBroker(audit_path=config.strategy.audit_path)
    preflight = realtime_preflight(
        broker=active_broker,
        contract=config.strategy.contract,
        attempts=config.preflight_attempts,
        retry_seconds=config.preflight_retry_seconds,
    )
    if config.require_preflight_ready and preflight["readiness"].get("status") != "ready":
        result = {
            "status": "preflight_blocked",
            "submitted": False,
            "preflight": preflight,
            "events": [],
        }
        write_realtime_status(config.status_path, result)
        return audit_and_return(config.strategy.audit_path, result)
    result = run_debate_delayed_scanner_daemon(
        feature_sets=feature_sets,
        planner=planner,
        strategy_config=config.strategy,
        scanner_config=config.scanner,
        broker=active_broker,
        interval_seconds=config.interval_seconds,
        max_iterations=config.max_iterations,
    )
    result = {
        **result,
        "preflight": {
            "status": preflight["readiness"].get("status"),
            "missing_requirements": preflight["readiness"].get("missing_requirements", []),
            "market_data": preflight.get("market_data", {}),
        },
        "mode": "submit" if config.strategy.submit else "dry_run",
    }
    write_realtime_status(config.status_path, result)
    return audit_and_return(config.strategy.audit_path, result)


def realtime_preflight(
    *,
    broker: IBKRPaperBroker,
    contract: IBKRContractSpec,
    attempts: int,
    retry_seconds: float,
) -> dict[str, Any]:
    session = IBKRPaperTradingSession(broker=broker, contract=contract)
    last_preflight: dict[str, Any] = {}
    for attempt in range(max(1, int(attempts))):
        last_preflight = session.preflight()
        readiness = last_preflight.get("readiness", {})
        if isinstance(readiness, dict) and readiness.get("status") == "ready":
            return last_preflight
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_seconds)))
    return last_preflight


def write_realtime_status(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": datetime.now(UTC).isoformat(), **event}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def append_debate_trade_log_safely(result: dict[str, Any], *, log_dir: Path | str = DEFAULT_TRADE_LOG_DIR) -> Path | None:
    try:
        return append_debate_trade_log(result, log_dir=log_dir)
    except Exception as exc:
        result["trade_log_error"] = str(exc) or exc.__class__.__name__
        return None


def append_debate_trade_log(result: dict[str, Any], *, log_dir: Path | str = DEFAULT_TRADE_LOG_DIR) -> Path:
    timestamp = debate_log_timestamp(result)
    output = Path(log_dir) / f"{timestamp.date().isoformat()}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        output.write_text(f"# 交易记录 {timestamp.date().isoformat()}\n\n", encoding="utf-8")
    decision_id = str((result.get("plan") if isinstance(result.get("plan"), dict) else {}).get("decision_id") or "")
    trigger_key = str(result.get("trigger_key") or "")
    existing = output.read_text(encoding="utf-8")
    marker = f"- 决策ID：`{decision_id}`"
    if decision_id and trigger_key and marker in existing and f"- 触发Key：`{trigger_key}`" in existing:
        return output
    with output.open("a", encoding="utf-8") as handle:
        handle.write(format_debate_trade_log_entry(result, timestamp))
    return output


def debate_log_timestamp(result: dict[str, Any]) -> datetime:
    trigger = result.get("trigger") if isinstance(result.get("trigger"), dict) else {}
    for value in [trigger.get("trigger_time"), result.get("created_at")]:
        timestamp = parse_timestamp(str(value)) if value else None
        if timestamp is not None:
            return timestamp
    return datetime.now(UTC)


def format_debate_trade_log_entry(result: dict[str, Any], timestamp: datetime) -> str:
    trigger = result.get("trigger") if isinstance(result.get("trigger"), dict) else {}
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    route = result.get("route") if isinstance(result.get("route"), dict) else {}
    intent = result.get("intent") if isinstance(result.get("intent"), dict) else {}
    broker_result = result.get("result") if isinstance(result.get("result"), dict) else {}
    snapshots = result.get("snapshots") if isinstance(result.get("snapshots"), dict) else {}
    initial = last_snapshot(snapshots.get("initial"))
    recheck = last_snapshot(snapshots.get("recheck"))
    debate_summary = plan.get("debate_summary") if isinstance(plan.get("debate_summary"), dict) else {}
    action = str(route.get("action") or intent.get("action") or "NO_TRADE").upper()
    action_label = {"BUY": "做多", "SELL": "做空", "NO_TRADE": "不交易"}.get(action, action)
    lines = [
        f"## {timestamp.isoformat()} - NQ LLM辩论策略 {action_label}",
        "",
        f"- 状态：`{result.get('status', '')}`；是否提交IBKR：`{result.get('submitted', False)}`",
        f"- 触发Key：`{result.get('trigger_key', '')}`",
        f"- 特征：`{trigger.get('feature_set', '')}`",
        f"- 候选：`{trigger.get('candidate', '')}`；过滤：`{trigger.get('filter_name', '')}`",
        f"- 回测证据：胜率 `{format_percent(trigger.get('win_rate'))}`；盈亏比 `{format_number(trigger.get('payoff_ratio_r'))}R`；净点数 `{format_number(trigger.get('net_points'))}`",
        f"- 行情触发：价格 `{format_number(trigger.get('trigger_price'))}`；初始 bid/ask/last=`{format_number(initial.get('bid'))}`/`{format_number(initial.get('ask'))}`/`{format_number(initial.get('last'))}`",
        f"- LLM辩论结论：stance=`{plan.get('stance', '')}`；confidence=`{format_number(plan.get('confidence'))}`；等待复查 `{plan.get('recheck_after_seconds', '')}` 秒",
        f"- 多头方案：触发 `{format_number(plan.get('long_trigger'))}`；止损 `{format_number(plan.get('long_stop'))}`；止盈 `{format_number(plan.get('long_target'))}`",
        f"- 空头方案：触发 `{format_number(plan.get('short_trigger'))}`；止损 `{format_number(plan.get('short_stop'))}`；止盈 `{format_number(plan.get('short_target'))}`",
        f"- 不交易区：`{format_number(plan.get('no_trade_low'))}` - `{format_number(plan.get('no_trade_high'))}`；最大追价 `{format_number(plan.get('max_chase_points'))}` 点",
        f"- 复查行情：价格 `{format_number(result.get('recheck_price'))}`；bid/ask/last=`{format_number(recheck.get('bid'))}`/`{format_number(recheck.get('ask'))}`/`{format_number(recheck.get('last'))}`",
        f"- 执行路由：action=`{action}`；reason=`{route.get('reason', result.get('reason', ''))}`；side=`{route.get('side', '')}`",
        f"- IBKR结果：status=`{broker_result.get('status', '')}`；intent=`{intent.get('intent_id', '')}`；order_type=`{intent.get('order_type', '')}`",
        f"- 决策ID：`{plan.get('decision_id', '')}`",
    ]
    for key in ["long_case", "short_case", "risk_case", "fallback_reason"]:
        if debate_summary.get(key):
            lines.append(f"- 辩论摘要/{key}：{debate_summary[key]}")
    lines.append("")
    return "\n".join(lines)


def last_snapshot(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value:
        snapshot = value[-1]
        return snapshot if isinstance(snapshot, dict) else {}
    return value if isinstance(value, dict) else {}


def format_number(value: Any) -> str:
    number = optional_float(value)
    if number is None:
        return ""
    return f"{number:.4f}".rstrip("0").rstrip(".")


def format_percent(value: Any) -> str:
    number = optional_float(value)
    if number is None:
        return ""
    return f"{number * 100:.2f}%"


def run_debate_delayed_scanner_once(
    *,
    feature_sets: pd.DataFrame,
    planner: DebatePlanner,
    strategy_config: DebateDelayedStrategyConfig | None = None,
    scanner_config: FeatureScannerConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    strategy_config = strategy_config or DebateDelayedStrategyConfig()
    scanner_config = scanner_config or FeatureScannerConfig()
    active_broker = broker or IBKRPaperBroker(audit_path=strategy_config.audit_path)
    scan = scan_feature_trigger_once(
        feature_sets,
        scanner_config=scanner_config,
        strategy_config=strategy_config,
        broker=active_broker,
        now=now,
    )
    if scan["status"] != "triggered":
        return audit_and_return(strategy_config.audit_path, {"submitted": False, **scan})
    return run_debate_delayed_strategy_once(
        trigger=scan["trigger"],
        planner=planner,
        config=strategy_config,
        broker=active_broker,
        now=now,
    )


def run_debate_delayed_scanner_daemon(
    *,
    feature_sets: pd.DataFrame,
    planner: DebatePlanner,
    strategy_config: DebateDelayedStrategyConfig | None = None,
    scanner_config: FeatureScannerConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    interval_seconds: float = 30.0,
    max_iterations: int | None = 1,
) -> dict[str, Any]:
    events = []
    iteration = 0
    while max_iterations is None or iteration < max_iterations:
        iteration += 1
        event = run_debate_delayed_scanner_once(
            feature_sets=feature_sets,
            planner=planner,
            strategy_config=strategy_config,
            scanner_config=scanner_config,
            broker=broker,
        )
        events.append(event)
        if event.get("status") in {"dry_run", "submitted"}:
            break
        if max_iterations is None or iteration < max_iterations:
            time.sleep(max(0.0, float(interval_seconds)))
    return {"status": "completed", "iterations": iteration, "events": events}


def scan_feature_trigger_once(
    feature_sets: pd.DataFrame,
    *,
    scanner_config: FeatureScannerConfig | None = None,
    strategy_config: DebateDelayedStrategyConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    scanner_config = scanner_config or FeatureScannerConfig()
    strategy_config = strategy_config or DebateDelayedStrategyConfig()
    if feature_sets.empty:
        return {"status": "scanner_blocked", "reason": "no_tradeable_feature_sets"}
    active_broker = broker or IBKRPaperBroker(audit_path=strategy_config.audit_path)
    snapshots = collect_snapshots(active_broker, strategy_config)
    snapshot = snapshots[-1] if snapshots else {}
    if scanner_config.require_order_ready and not snapshot.get("order_ready"):
        return {"status": "scanner_blocked", "reason": "market_snapshot_not_order_ready", "snapshot": snapshot}
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    event = scanner_market_event(timestamp, snapshot)
    append_scanner_history(scanner_config.history_path, event)
    history = load_scanner_history(scanner_config.history_path, scanner_config.max_history_points)
    if len(history) < scanner_config.min_history_points:
        return {
            "status": "no_feature_trigger",
            "reason": "insufficient_scanner_history",
            "history_points": len(history),
            "required_points": scanner_config.min_history_points,
            "snapshot": snapshot,
        }
    state = load_strategy_state(scanner_config.state_path)
    candidates = rank_scanner_feature_sets(feature_sets, scanner_config.feature_set)
    for _, row in candidates.iterrows():
        evaluation = evaluate_scanner_feature(row, history, scanner_config)
        if not evaluation["triggered"]:
            continue
        trigger = FeatureTrigger.from_series(
            row,
            trigger_price=float(evaluation["trigger_price"]),
            trigger_time=timestamp.isoformat(),
        )
        trigger = FeatureTrigger(
            **(
                asdict(trigger)
                | {
                    "direction": evaluation["direction"],
                    "context": trigger.context
                    | {
                        "scanner": {
                            key: normalize_json_value(value)
                            for key, value in evaluation.items()
                            if key not in {"triggered", "trigger_price", "direction"}
                        }
                    },
                }
            )
        )
        cooldown = scanner_cooldown_status(trigger, state, timestamp, scanner_config.cooldown_seconds)
        if not cooldown["passed"]:
            return {"status": "no_feature_trigger", "reason": "scanner_cooldown", "cooldown": cooldown, "trigger": trigger}
        save_strategy_state(
            scanner_config.state_path,
            {
                "last_scanner_trigger_key": build_trigger_key(trigger),
                "last_scanner_feature_set": trigger.feature_set,
                "last_scanner_trigger_at": trigger.trigger_time,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        return {
            "status": "triggered",
            "reason": evaluation["reason"],
            "trigger": trigger,
            "evaluation": evaluation,
            "snapshot": snapshot,
            "history_points": len(history),
        }
    return {"status": "no_feature_trigger", "reason": "no_scanner_rule_matched", "snapshot": snapshot, "history_points": len(history)}


def select_feature_trigger(
    feature_sets: pd.DataFrame,
    *,
    feature_set: str | None,
    trigger_price: float,
    trigger_time: str | None = None,
) -> FeatureTrigger:
    if feature_sets.empty:
        raise ValueError("No tradeable feature sets passed win_rate > 53% and payoff_ratio_r > 1R")
    selected = feature_sets
    if feature_set:
        selected = feature_sets[feature_sets["feature_set"].astype(str).eq(feature_set)]
        if selected.empty:
            raise ValueError(f"Feature set not found or not tradeable: {feature_set}")
    row = selected.iloc[0]
    return FeatureTrigger.from_series(row, trigger_price=trigger_price, trigger_time=trigger_time)


def run_debate_delayed_strategy_once(
    *,
    trigger: FeatureTrigger,
    planner: DebatePlanner,
    config: DebateDelayedStrategyConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    config = config or DebateDelayedStrategyConfig()
    active_broker = broker or IBKRPaperBroker(audit_path=config.audit_path)
    trigger_key = build_trigger_key(trigger)
    state = load_strategy_state(config.state_path)
    previous_trigger_key = state.get("last_trigger_key")
    if previous_trigger_key == trigger_key:
        return audit_and_return(
            config.audit_path,
            {
                "status": "duplicate_skipped",
                "submitted": False,
                "trigger_key": trigger_key,
                "previous_trigger_key": previous_trigger_key,
                "trigger": asdict(trigger),
            },
        )
    trigger_time = parse_timestamp(trigger.trigger_time) or (now or datetime.now(UTC))
    checked_at = now or datetime.now(UTC)
    freshness = (checked_at - trigger_time).total_seconds()
    if freshness > config.max_signal_age_seconds:
        return audit_and_return(
            config.audit_path,
            {
                "status": "stale_trigger_blocked",
                "submitted": False,
                "trigger_key": trigger_key,
                "age_seconds": freshness,
                "trigger": asdict(trigger),
            },
        )
    first_snapshots = collect_snapshots(active_broker, config)
    plan = planner.build_plan(trigger, first_snapshots)
    if config.enforce_delay and plan.recheck_after_seconds > 0:
        time.sleep(plan.recheck_after_seconds)
    recheck_snapshots = collect_snapshots(active_broker, config)
    recheck = recheck_snapshots[-1] if recheck_snapshots else {}
    price = market_price(recheck, fallback=trigger.trigger_price)
    route = route_plan(plan, price)
    if route["action"] == "NO_TRADE":
        save_strategy_state(
            config.state_path,
            {
                "last_trigger_key": trigger_key,
                "last_decision_id": plan.decision_id,
                "last_intent_id": None,
                "last_status": "no_trade_after_recheck",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        result = {
            "status": "no_trade_after_recheck",
            "submitted": False,
            "trigger_key": trigger_key,
            "reason": route["reason"],
            "trigger": asdict(trigger),
            "plan": asdict(plan),
            "route": route,
            "recheck_price": price,
            "snapshots": {"initial": first_snapshots, "recheck": recheck_snapshots},
        }
        append_debate_trade_log_safely(result, log_dir=config.trade_log_dir)
        return audit_and_return(config.audit_path, result)
    if not config.allow_existing_exposure:
        exposure = active_broker.status_snapshot(config.contract.symbol)
        if int(exposure.get("current_position") or 0) != 0 or exposure.get("open_trades"):
            result = {
                "status": "exposure_blocked",
                "submitted": False,
                "trigger_key": trigger_key,
                "exposure": exposure,
                "trigger": asdict(trigger),
                "plan": asdict(plan),
                "route": route,
                "recheck_price": price,
                "snapshots": {"initial": first_snapshots, "recheck": recheck_snapshots},
            }
            append_debate_trade_log_safely(result, log_dir=config.trade_log_dir)
            return audit_and_return(config.audit_path, result)
    intent = build_intent_from_route(
        trigger,
        plan,
        route,
        price,
        contract=config.contract,
        account=config.account,
        quantity=config.quantity,
    ).normalized()
    session = IBKRPaperTradingSession(broker=active_broker, contract=config.contract)
    response = session.submit_intent(intent, dry_run=not config.submit, skip_preflight=config.skip_preflight)
    result = {
        "status": response.get("status", "unknown"),
        "submitted": bool(response.get("submitted")),
        "trigger_key": trigger_key,
        "trigger": asdict(trigger),
        "plan": asdict(plan),
        "route": route,
        "recheck_price": price,
        "intent": response.get("intent", asdict(intent)),
        "result": response,
        "snapshots": {"initial": first_snapshots, "recheck": recheck_snapshots},
    }
    append_debate_trade_log_safely(result, log_dir=config.trade_log_dir)
    if result["status"] in {"dry_run", "submitted"}:
        save_strategy_state(
            config.state_path,
            {
                "last_trigger_key": trigger_key,
                "last_decision_id": plan.decision_id,
                "last_intent_id": result["intent"].get("intent_id"),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
    return audit_and_return(config.audit_path, result)


def collect_snapshots(broker: IBKRPaperBroker, config: DebateDelayedStrategyConfig) -> list[dict[str, Any]]:
    snapshots = []
    for attempt in range(max(1, config.snapshot_attempts)):
        snapshot = broker.tick_snapshot(config.contract)
        snapshots.append(snapshot)
        if snapshot.get("order_ready"):
            break
        if attempt + 1 < config.snapshot_attempts:
            time.sleep(max(0.0, config.snapshot_retry_seconds))
    return snapshots


def scanner_market_event(timestamp: datetime, snapshot: dict[str, Any]) -> dict[str, Any]:
    bid = optional_float(snapshot.get("bid"))
    ask = optional_float(snapshot.get("ask"))
    last = optional_float(snapshot.get("last"))
    mid = (bid + ask) / 2 if bid is not None and ask is not None else last
    return {
        "event_type": "nq_llm_debate_scanner_market_event",
        "ts": timestamp.isoformat(),
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid": mid,
        "spread": optional_float(snapshot.get("spread")),
        "market_data_type": snapshot.get("market_data_type"),
        "order_ready": bool(snapshot.get("order_ready")),
        "snapshot_time": snapshot.get("snapshot_time"),
    }


def append_scanner_history(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


def load_scanner_history(path: Path, max_points: int) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "nq_llm_debate_scanner_market_event":
            continue
        event_ts = parse_timestamp(str(event.get("ts", "")))
        price = optional_float(event.get("last")) or optional_float(event.get("mid"))
        if event_ts is None or price is None:
            continue
        event["ts"] = event_ts
        event["price"] = price
        rows.append(event)
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).sort_values("ts").drop_duplicates("ts")
    return frame.tail(max(1, int(max_points))).reset_index(drop=True)


def rank_scanner_feature_sets(feature_sets: pd.DataFrame, feature_set: str | None) -> pd.DataFrame:
    selected = feature_sets
    if feature_set:
        selected = selected[selected["feature_set"].astype(str).eq(feature_set)]
    if selected.empty:
        return selected
    sort_columns = [column for column in ["future_pass", "selected_folds", "net_points", "win_rate", "payoff_ratio_r"] if column in selected.columns]
    if not sort_columns:
        return selected
    ascending = [False] * len(sort_columns)
    return selected.sort_values(sort_columns, ascending=ascending).reset_index(drop=True)


def evaluate_scanner_feature(row: pd.Series, history: pd.DataFrame, config: FeatureScannerConfig) -> dict[str, Any]:
    prices = pd.to_numeric(history["price"], errors="coerce").dropna().reset_index(drop=True)
    if len(prices) < config.min_history_points:
        return {"triggered": False, "reason": "insufficient_scanner_history", "history_points": int(len(prices))}
    candidate = str(row.get("candidate", row.get("feature_set", ""))).lower()
    filter_name = str(row.get("filter", "")).lower()
    direction = inferred_direction(candidate)
    base = evaluate_base_candidate(candidate, prices, config)
    if not base["triggered"]:
        return base | {"direction": direction}
    filter_result = evaluate_feature_filter(filter_name, prices, config)
    if not filter_result["triggered"]:
        return filter_result | {"direction": direction}
    return {
        "triggered": True,
        "reason": f"{base['reason']}+{filter_result['reason']}",
        "direction": direction,
        "trigger_price": float(prices.iloc[-1]),
        "base": base,
        "filter": filter_result,
        "last_price": float(prices.iloc[-1]),
        "return_1m": one_period_return(prices),
        "momentum_60": momentum_points(prices, min(60, len(prices) - 1)),
        "z_30": z_score(prices, min(30, len(prices))),
        "vwap_distance_z": distance_z_score(prices),
    }


def evaluate_base_candidate(candidate: str, prices: pd.Series, config: FeatureScannerConfig) -> dict[str, Any]:
    if "mean_reversion" in candidate:
        lookback = extract_int(candidate, "lb", default=30)
        threshold = extract_float(candidate, "thr", default=1.4)
        active_lookback = min(lookback, len(prices))
        current_z = z_score(prices, active_lookback)
        triggered = current_z is not None and current_z <= -abs(threshold)
        return {
            "triggered": bool(triggered),
            "reason": "mean_reversion_z_flush" if triggered else "mean_reversion_z_not_extreme",
            "z_score": current_z,
            "lookback": active_lookback,
            "threshold": -abs(threshold),
        }
    if "support_reclaim" in candidate:
        lookback = extract_int(candidate, "lb", default=60)
        active_lookback = min(lookback, len(prices))
        support = float(prices.tail(active_lookback).min())
        current = float(prices.iloc[-1])
        previous = float(prices.iloc[-2])
        reclaimed = previous <= support + config.support_reclaim_points and current > support + config.support_reclaim_points
        not_extended = current <= support + config.max_support_reclaim_points
        return {
            "triggered": bool(reclaimed and not_extended),
            "reason": "support_reclaim" if reclaimed and not_extended else "support_not_reclaimed",
            "support": support,
            "previous_price": previous,
            "last_price": current,
        }
    if "momentum" in candidate:
        lookback = extract_int(candidate, "lb", default=60)
        threshold = extract_float(candidate, "thr", default=0.0006)
        active_lookback = min(lookback, len(prices) - 1)
        momentum = normalized_momentum(prices, active_lookback)
        triggered = momentum is not None and momentum >= threshold
        return {
            "triggered": bool(triggered),
            "reason": "momentum_breakout" if triggered else "momentum_below_threshold",
            "momentum": momentum,
            "lookback": active_lookback,
            "threshold": threshold,
        }
    return {"triggered": False, "reason": "unsupported_scanner_candidate"}


def evaluate_feature_filter(filter_name: str, prices: pd.Series, config: FeatureScannerConfig) -> dict[str, Any]:
    if not filter_name or filter_name == "none":
        return {"triggered": True, "reason": "no_filter"}
    return_1m = one_period_return(prices)
    if filter_name == "entry_candle_up" or filter_name == "return_1m_positive":
        return {"triggered": return_1m is not None and return_1m > 0, "reason": "return_1m_positive", "return_1m": return_1m}
    if filter_name == "entry_candle_down" or filter_name == "return_1m_negative":
        return {"triggered": return_1m is not None and return_1m < 0, "reason": "return_1m_negative", "return_1m": return_1m}
    if filter_name == "momentum_60_positive":
        momentum = momentum_points(prices, min(60, len(prices) - 1))
        return {"triggered": momentum is not None and momentum > 0, "reason": "momentum_60_positive", "momentum_60": momentum}
    if filter_name == "z_30_negative":
        current_z = z_score(prices, min(30, len(prices)))
        return {"triggered": current_z is not None and current_z < 0, "reason": "z_30_negative", "z_30": current_z}
    if filter_name == "vwap_distance_high":
        distance = distance_z_score(prices)
        return {
            "triggered": distance is not None and abs(distance) >= config.vwap_distance_z_threshold,
            "reason": "vwap_distance_high",
            "vwap_distance_z": distance,
            "threshold": config.vwap_distance_z_threshold,
        }
    return {"triggered": False, "reason": f"unsupported_filter:{filter_name}"}


def scanner_cooldown_status(trigger: FeatureTrigger, state: dict[str, Any], timestamp: datetime, cooldown_seconds: float) -> dict[str, Any]:
    previous_key = state.get("last_scanner_trigger_key")
    previous_time = parse_timestamp(str(state.get("last_scanner_trigger_at", "")))
    if previous_key != build_trigger_key(trigger) or previous_time is None:
        return {"passed": True}
    elapsed = (timestamp - previous_time).total_seconds()
    return {"passed": elapsed >= cooldown_seconds, "elapsed_seconds": elapsed, "cooldown_seconds": cooldown_seconds}


def inferred_direction(candidate: str) -> str:
    if "_short_" in candidate or candidate.endswith("_short"):
        return "short"
    if "_long_" in candidate or candidate.endswith("_long"):
        return "long"
    return "unknown"


def extract_int(text: str, prefix: str, *, default: int) -> int:
    match = re.search(rf"{re.escape(prefix)}(\d+)", text)
    return int(match.group(1)) if match else default


def extract_float(text: str, prefix: str, *, default: float) -> float:
    match = re.search(rf"{re.escape(prefix)}(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else default


def one_period_return(prices: pd.Series) -> float | None:
    if len(prices) < 2:
        return None
    previous = float(prices.iloc[-2])
    current = float(prices.iloc[-1])
    if previous == 0:
        return None
    return current / previous - 1.0


def momentum_points(prices: pd.Series, lookback: int) -> float | None:
    if lookback <= 0 or len(prices) <= lookback:
        return None
    return float(prices.iloc[-1] - prices.iloc[-lookback - 1])


def normalized_momentum(prices: pd.Series, lookback: int) -> float | None:
    points = momentum_points(prices, lookback)
    reference = float(prices.iloc[-lookback - 1]) if lookback > 0 and len(prices) > lookback else 0.0
    if points is None or reference == 0:
        return None
    return points / reference


def z_score(prices: pd.Series, lookback: int) -> float | None:
    if lookback < 2 or len(prices) < lookback:
        return None
    window = prices.tail(lookback)
    mean = float(window.mean())
    std = float(window.std())
    if std == 0 or math.isnan(std):
        return None
    return (float(prices.iloc[-1]) - mean) / std


def distance_z_score(prices: pd.Series) -> float | None:
    current_z = z_score(prices, min(30, len(prices)))
    return current_z


def build_trigger_key(trigger: FeatureTrigger) -> str:
    parts = [
        trigger.feature_set,
        trigger.candidate,
        trigger.direction,
        f"{trigger.trigger_price:.2f}",
        trigger.trigger_time,
    ]
    return "|".join(str(part) for part in parts)


def route_plan(plan: DebateExecutionPlan, price: float) -> dict[str, Any]:
    if plan.long_trigger is not None and price >= plan.long_trigger:
        if price > plan.long_trigger + plan.max_chase_points:
            return {"action": "NO_TRADE", "reason": "long_chase_exceeded", "side": "long"}
        return {"action": "BUY", "side": "long", "trigger": plan.long_trigger}
    if plan.short_trigger is not None and price <= plan.short_trigger:
        if price < plan.short_trigger - plan.max_chase_points:
            return {"action": "NO_TRADE", "reason": "short_chase_exceeded", "side": "short"}
        return {"action": "SELL", "side": "short", "trigger": plan.short_trigger}
    if plan.no_trade_low is not None and plan.no_trade_high is not None and plan.no_trade_low < price < plan.no_trade_high:
        return {"action": "NO_TRADE", "reason": "price_inside_no_trade_zone"}
    return {"action": "NO_TRADE", "reason": "no_conditional_level_matched"}


def build_intent_from_route(
    trigger: FeatureTrigger,
    plan: DebateExecutionPlan,
    route: dict[str, Any],
    price: float,
    *,
    contract: IBKRContractSpec,
    account: str | None,
    quantity: int,
) -> IBKROrderIntent:
    action = str(route["action"]).upper()
    if action == "BUY":
        stop = plan.long_stop if plan.long_stop is not None else price - 16.0
        target = plan.long_target if plan.long_target is not None else price + 24.0
        limit_price = price - plan.limit_offset_points if plan.order_type == "LMT" else None
    elif action == "SELL":
        stop = plan.short_stop if plan.short_stop is not None else price + 16.0
        target = plan.short_target if plan.short_target is not None else price - 24.0
        limit_price = price + plan.limit_offset_points if plan.order_type == "LMT" else None
    else:
        raise ValueError(f"Cannot build intent for action={action}")
    reason = (
        f"llm_debate_delayed_nq | feature_set={trigger.feature_set} | decision_id={plan.decision_id} "
        f"| recheck_price={price:.2f} | stop_loss_points={abs(price - stop):.4f} "
        f"| take_profit_points={abs(target - price):.4f}"
    )
    return IBKROrderIntent(
        action=action,
        quantity=quantity,
        order_type=plan.order_type if plan.order_type in {"MKT", "LMT"} else "MKT",
        limit_price=round_to_tick(limit_price) if limit_price is not None else None,
        stop_loss_price=round_to_tick(stop),
        take_profit_price=round_to_tick(target),
        account=account,
        strategy_id="nq_llm_debate_delayed",
        reason=reason,
        **contract.to_intent_fields(),
    )


def build_debate_prompt(trigger: FeatureTrigger, snapshots: list[dict[str, Any]]) -> str:
    return (
        "You are generating an executable NQ paper-trading plan. "
        "A script found a feature with win_rate > 53% and payoff_ratio_r > 1R. "
        "Debate long and short scenarios and return ONLY JSON with keys: "
        "decision_id, feature_set, stance, recheck_after_seconds, long_trigger, short_trigger, "
        "no_trade_low, no_trade_high, long_stop, long_target, short_stop, short_target, "
        "max_chase_points, order_type, limit_offset_points, confidence, debate_summary. "
        "Use conditional levels: buy only if price still holds/starts above long_trigger after recheck; "
        "sell only if price breaks below short_trigger after recheck; otherwise no trade.\n\n"
        f"FEATURE_TRIGGER:\n{json.dumps(asdict(trigger), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"IBKR_SNAPSHOTS:\n{json.dumps(snapshots, ensure_ascii=False, sort_keys=True, default=str)}"
    )


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        payload = json.loads(stripped[start : end + 1])
        if isinstance(payload, dict):
            return payload
    raise ValueError("LLM response did not contain a JSON object")


def parse_timestamp(value: str) -> datetime | None:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def market_price(snapshot: dict[str, Any], *, fallback: float) -> float:
    for key in ["last", "ask", "bid"]:
        value = optional_float(snapshot.get(key))
        if value is not None:
            return value
    return float(fallback)


def optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def normalize_json_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, float) and value != value:
        return None
    return value


def load_strategy_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def save_strategy_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")


def round_to_tick(value: float | None, tick_size: float = 0.25) -> float | None:
    if value is None:
        return None
    return round(round(float(value) / tick_size) * tick_size, 2)


def audit_and_return(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event_type": "nq_llm_debate_delayed_strategy", **event}, sort_keys=True, default=str) + "\n")
    return event


def planner_from_env_or_args(
    *,
    decision_json: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
) -> DebatePlanner:
    if decision_json:
        return StaticDebatePlanner(DebateExecutionPlan.from_dict(json.loads(decision_json)))
    active_provider = provider or os.getenv("TRADINGAGENTS_NQ_DEBATE_LLM_PROVIDER")
    active_model = model or os.getenv("TRADINGAGENTS_NQ_DEBATE_LLM_MODEL")
    if active_provider and active_model:
        return LLMDebatePlanner(
            provider=active_provider,
            model=active_model,
            base_url=base_url or os.getenv("TRADINGAGENTS_NQ_DEBATE_LLM_BASE_URL") or None,
        )
    return RuleDebatePlanner()
