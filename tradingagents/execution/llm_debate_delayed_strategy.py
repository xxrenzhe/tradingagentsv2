from __future__ import annotations

import json
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
        return audit_and_return(
            config.audit_path,
            {
                "status": "no_trade_after_recheck",
                "submitted": False,
                "trigger_key": trigger_key,
                "reason": route["reason"],
                "trigger": asdict(trigger),
                "plan": asdict(plan),
                "recheck_price": price,
                "snapshots": {"initial": first_snapshots, "recheck": recheck_snapshots},
            },
        )
    if not config.allow_existing_exposure:
        exposure = active_broker.status_snapshot(config.contract.symbol)
        if int(exposure.get("current_position") or 0) != 0 or exposure.get("open_trades"):
            return audit_and_return(
                config.audit_path,
                {
                    "status": "exposure_blocked",
                    "submitted": False,
                    "trigger_key": trigger_key,
                    "exposure": exposure,
                    "trigger": asdict(trigger),
                    "plan": asdict(plan),
                },
            )
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
