from __future__ import annotations

import json
import os
import csv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from tradingagents.agents.utils.rating import parse_rating
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .ibkr import IBKROrderIntent


BULLISH_RATINGS = {"Buy", "Overweight"}
BEARISH_RATINGS = {"Sell", "Underweight"}
FUTURES_MONTH_CODES = {
    "01": "F",
    "02": "G",
    "03": "H",
    "04": "J",
    "05": "K",
    "06": "M",
    "07": "N",
    "08": "Q",
    "09": "U",
    "10": "V",
    "11": "X",
    "12": "Z",
}


@dataclass(frozen=True)
class AgentGateConfig:
    enabled: bool = False
    analysts: tuple[str, ...] = ("market", "news")
    provider: str | None = None
    quick_model: str | None = None
    deep_model: str | None = None
    backend_url: str | None = None
    fast_graph_mode: bool = True
    deterministic_decision_mode: bool = False
    require_direction_alignment: bool = True
    memory_log_enabled: bool = True
    learning_context_enabled: bool = True
    learning_lookback_events: int = 50
    performance_guard_enabled: bool = True
    performance_min_trades: int = 5
    performance_recent_trades: int = 15
    performance_min_win_rate: float = 25.0
    performance_min_net_points: float = -60.0
    performance_max_consecutive_losses: int = 4
    performance_watch_scale: float = 0.25
    performance_hard_block: bool = True
    ibkr_audit_path: Path = Path(".tmp/ibkr-paper-audit.jsonl")
    strategy_evidence_path: Path = Path(".tmp/mbp-best-strategy-ranking.csv")
    audit_path: Path = Path(".tmp/agent-gate-audit.jsonl")
    output_language: str = "Chinese"

    @classmethod
    def from_env(cls) -> "AgentGateConfig":
        analysts = tuple(
            item.strip().lower()
            for item in os.getenv("TRADINGAGENTS_AGENT_GATE_ANALYSTS", "market,news").split(",")
            if item.strip()
        )
        return cls(
            enabled=os.getenv("TRADINGAGENTS_AGENT_GATE_ENABLED", "false").lower() in {"1", "true", "yes"},
            analysts=analysts or ("market", "news"),
            provider=os.getenv("TRADINGAGENTS_AGENT_GATE_LLM_PROVIDER") or None,
            quick_model=os.getenv("TRADINGAGENTS_AGENT_GATE_QUICK_LLM") or None,
            deep_model=os.getenv("TRADINGAGENTS_AGENT_GATE_DEEP_LLM") or None,
            backend_url=os.getenv("TRADINGAGENTS_AGENT_GATE_BACKEND_URL") or None,
            fast_graph_mode=os.getenv("TRADINGAGENTS_AGENT_GATE_FAST_MODE", "true").lower() not in {"0", "false", "no"},
            deterministic_decision_mode=os.getenv("TRADINGAGENTS_AGENT_GATE_DETERMINISTIC", "false").lower() in {"1", "true", "yes"},
            require_direction_alignment=os.getenv("TRADINGAGENTS_AGENT_GATE_REQUIRE_ALIGNMENT", "true").lower() not in {"0", "false", "no"},
            memory_log_enabled=os.getenv("TRADINGAGENTS_AGENT_GATE_MEMORY_ENABLED", "true").lower() not in {"0", "false", "no"},
            learning_context_enabled=os.getenv("TRADINGAGENTS_AGENT_GATE_LEARNING_ENABLED", "true").lower() not in {"0", "false", "no"},
            learning_lookback_events=int(os.getenv("TRADINGAGENTS_AGENT_GATE_LEARNING_LOOKBACK", "50")),
            performance_guard_enabled=os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_GUARD_ENABLED", "true").lower() not in {"0", "false", "no"},
            performance_min_trades=int(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_MIN_TRADES", "5")),
            performance_recent_trades=int(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_RECENT_TRADES", "15")),
            performance_min_win_rate=float(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_MIN_WIN_RATE", "25")),
            performance_min_net_points=float(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_MIN_NET_POINTS", "-60")),
            performance_max_consecutive_losses=int(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_MAX_CONSECUTIVE_LOSSES", "4")),
            performance_watch_scale=float(os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_WATCH_SCALE", "0.25")),
            performance_hard_block=os.getenv("TRADINGAGENTS_AGENT_GATE_PERFORMANCE_HARD_BLOCK", "true").lower() not in {"0", "false", "no"},
            ibkr_audit_path=Path(os.getenv("TRADINGAGENTS_IBKR_AUDIT_PATH", ".tmp/ibkr-paper-audit.jsonl")),
            strategy_evidence_path=Path(os.getenv("TRADINGAGENTS_AGENT_GATE_STRATEGY_EVIDENCE_PATH", ".tmp/mbp-best-strategy-ranking.csv")),
            audit_path=Path(os.getenv("TRADINGAGENTS_AGENT_GATE_AUDIT_PATH", ".tmp/agent-gate-audit.jsonl")),
            output_language=os.getenv("TRADINGAGENTS_AGENT_GATE_OUTPUT_LANGUAGE", "Chinese"),
        )


class AgentStrategyGate:
    def __init__(
        self,
        config: AgentGateConfig | None = None,
        graph_factory: Callable[[list[str], dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config = config or AgentGateConfig.from_env()
        self.graph_factory = graph_factory or self._default_graph_factory

    def review(
        self,
        intent: IBKROrderIntent,
        *,
        trade_date: str,
        selected_trade: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = intent.normalized()
        learning_context = (
            build_learning_context(
                strategy_id=normalized.strategy_id,
                agent_audit_path=self.config.audit_path,
                ibkr_audit_path=self.config.ibkr_audit_path,
                lookback_events=self.config.learning_lookback_events,
            )
            if self.config.learning_context_enabled
            else ""
        )
        candidate_context = build_candidate_trade_context(
            normalized,
            selected_trade,
            learning_context=learning_context,
            strategy_evidence=load_strategy_evidence(
                normalized.strategy_id,
                self.config.strategy_evidence_path,
            ),
        )
        graph = self.graph_factory(list(self.config.analysts), self._graph_config())
        analysis_symbol = analysis_symbol_from_intent(normalized)
        final_state, signal = graph.propagate(
            analysis_symbol,
            trade_date,
            candidate_trade_context=candidate_context,
        )
        final_decision = str(final_state.get("final_trade_decision", ""))
        rating = parse_rating(final_decision, default=str(signal or "Hold"))
        reasons = self._rejection_reasons(normalized, rating, final_decision)
        performance_guard = self._performance_guard(normalized.strategy_id)
        reasons.extend(performance_guard["reasons"])
        result = {
            "event_type": "agent_strategy_gate",
            "created_at": _now(),
            "enabled": self.config.enabled,
            "status": "agent_approved" if not reasons else "agent_rejected",
            "passed": not reasons,
            "reasons": reasons,
            "signal": signal,
            "rating": rating,
            "analysis_symbol": analysis_symbol,
            "intent": asdict(normalized),
            "selected_trade": selected_trade or {},
            "learning_context": learning_context,
            "performance_guard": performance_guard,
            "candidate_trade_context": candidate_context,
            "final_trade_decision": final_decision,
        }
        self._audit(result)
        return result

    def _graph_config(self) -> dict[str, Any]:
        config = DEFAULT_CONFIG.copy()
        config["memory_log_enabled"] = self.config.memory_log_enabled
        config["fast_graph_mode"] = self.config.fast_graph_mode
        config["deterministic_decision_mode"] = self.config.deterministic_decision_mode
        config["output_language"] = self.config.output_language
        config["market_report_use_mbp"] = True
        config["data_vendors"] = dict(config.get("data_vendors", {}))
        config["data_vendors"]["core_stock_apis"] = "databento"
        config["data_vendors"]["technical_indicators"] = "databento"
        if self.config.provider:
            config["llm_provider"] = self.config.provider
        if self.config.quick_model:
            config["quick_think_llm"] = self.config.quick_model
        if self.config.deep_model:
            config["deep_think_llm"] = self.config.deep_model
        if self.config.backend_url:
            config["backend_url"] = self.config.backend_url
        return config

    def _rejection_reasons(self, intent: IBKROrderIntent, rating: str, final_decision: str) -> list[str]:
        reasons: list[str] = []
        lower_decision = final_decision.lower()
        veto_tokens = ["veto", "reject", "do not trade", "do not submit", "avoid entry", "否决", "拒绝", "不应下单"]
        if any(token in lower_decision for token in veto_tokens):
            reasons.append("agent_vetoed_candidate")
        if self.config.deterministic_decision_mode:
            reasons.append("agent_gate_deterministic_mode")
        if self.config.require_direction_alignment:
            if intent.action == "BUY" and rating not in BULLISH_RATINGS:
                reasons.append("agent_rating_not_aligned_with_buy")
            if intent.action == "SELL" and rating not in BEARISH_RATINGS:
                reasons.append("agent_rating_not_aligned_with_sell")
        return reasons

    def _default_graph_factory(self, analysts: list[str], config: dict[str, Any]) -> TradingAgentsGraph:
        return TradingAgentsGraph(analysts, config=config, debug=False)

    def _performance_guard(self, strategy_id: str) -> dict[str, Any]:
        if not self.config.performance_guard_enabled:
            return {"enabled": False, "passed": True, "reasons": [], "severity": "off", "position_scale": 1.0}
        events = [
            event
            for event in _read_jsonl_tail(self.config.audit_path, self.config.learning_lookback_events)
            if event.get("event_type") == "agent_gate_paper_outcome" and _event_strategy_id(event) == strategy_id
        ]
        metrics = outcome_metrics(events[-self.config.performance_recent_trades :])
        reasons: list[str] = []
        if metrics["trades"] >= self.config.performance_min_trades:
            if metrics["win_rate"] < self.config.performance_min_win_rate:
                reasons.append("paper_win_rate_below_guard")
            if metrics["net_points"] < self.config.performance_min_net_points:
                reasons.append("paper_net_points_below_guard")
            if metrics["consecutive_losses"] >= self.config.performance_max_consecutive_losses:
                reasons.append("paper_consecutive_losses_guard")
        severity = _guard_severity(reasons, self.config.performance_hard_block)
        position_scale = _guard_position_scale(severity, self.config.performance_watch_scale)
        return {
            "enabled": True,
            "passed": severity != "block",
            "reasons": reasons,
            "severity": severity,
            "position_scale": position_scale,
            "metrics": metrics,
            "thresholds": {
                "min_trades": self.config.performance_min_trades,
                "recent_trades": self.config.performance_recent_trades,
                "min_win_rate": self.config.performance_min_win_rate,
                "min_net_points": self.config.performance_min_net_points,
                "max_consecutive_losses": self.config.performance_max_consecutive_losses,
                "watch_scale": self.config.performance_watch_scale,
                "hard_block": self.config.performance_hard_block,
            },
        }

    def _audit(self, event: dict[str, Any]) -> None:
        self.config.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")


@dataclass(frozen=True)
class PaperTradeOutcome:
    strategy_id: str
    intent_id: str | None = None
    symbol: str = "MNQ"
    action: str = "BUY"
    quantity: int = 1
    entry_time: str | None = None
    exit_time: str | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    points: float | None = None
    commission: float | None = None
    slippage_points: float | None = None
    exit_reason: str | None = None
    source: str = "paper"
    notes: str = ""

    @property
    def normalized_points(self) -> float | None:
        if self.points is not None:
            return float(self.points)
        if self.entry_price is None or self.exit_price is None:
            return None
        direction = 1 if self.action.upper() == "BUY" else -1
        return (float(self.exit_price) - float(self.entry_price)) * direction


def record_agent_gate_outcome(
    outcome: PaperTradeOutcome,
    *,
    audit_path: Path | str | None = None,
) -> dict[str, Any]:
    event = {
        "event_type": "agent_gate_paper_outcome",
        "created_at": _now(),
        "strategy_id": outcome.strategy_id,
        "intent_id": outcome.intent_id,
        "symbol": outcome.symbol,
        "action": outcome.action.upper(),
        "quantity": outcome.quantity,
        "entry_time": outcome.entry_time,
        "exit_time": outcome.exit_time,
        "entry_price": outcome.entry_price,
        "exit_price": outcome.exit_price,
        "points": outcome.normalized_points,
        "commission": outcome.commission,
        "slippage_points": outcome.slippage_points,
        "exit_reason": outcome.exit_reason,
        "source": outcome.source,
        "notes": outcome.notes,
    }
    path = Path(audit_path or AgentGateConfig.from_env().audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    return event


def build_candidate_trade_context(
    intent: IBKROrderIntent,
    selected_trade: dict[str, Any] | None = None,
    learning_context: str = "",
    strategy_evidence: dict[str, Any] | None = None,
) -> str:
    trade = selected_trade or {}
    parts = [
        f"Strategy ID: {intent.strategy_id}",
        f"Candidate action: {intent.action} {intent.quantity} {intent.symbol} {intent.last_trade_date_or_contract_month}",
        f"Order type: {intent.order_type}",
        f"Stop loss: {intent.stop_loss_price}",
        f"Take profit: {intent.take_profit_price}",
        f"Reason: {intent.reason}",
    ]
    for key in [
        "trade_date",
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "points",
        "portfolio_rule",
        "selected_alias",
        "regime",
        "exit_reason",
        "setup_id",
        "setup_family",
        "setup_bias",
        "setup_confidence",
        "setup_htf_trend",
        "setup_mtf_reclaim",
        "setup_ltf_trigger",
        "setup_reason",
    ]:
        if key in trade:
            parts.append(f"{key}: {trade[key]}")
    live_market_lines = _live_market_context_lines(trade)
    if live_market_lines:
        parts.extend(["", "Current IBKR top-of-book evidence:", *live_market_lines])
    if strategy_evidence:
        parts.extend(["", "Historical strategy evidence:", *_strategy_evidence_lines(strategy_evidence)])
    if learning_context:
        parts.extend(["", "Historical gate and paper-trading lessons:", learning_context])
    return "\n".join(parts)


def build_learning_context(
    *,
    strategy_id: str,
    agent_audit_path: Path | str,
    ibkr_audit_path: Path | str,
    lookback_events: int = 50,
) -> str:
    agent_events = _read_jsonl_tail(Path(agent_audit_path), lookback_events)
    ibkr_events = _read_jsonl_tail(Path(ibkr_audit_path), lookback_events)
    strategy_events = [
        event
        for event in agent_events
        if _event_strategy_id(event) == strategy_id
    ]
    outcome_events = [
        event
        for event in agent_events
        if event.get("event_type") == "agent_gate_paper_outcome" and _event_strategy_id(event) == strategy_id
    ]
    approved = sum(1 for event in strategy_events if event.get("passed") is True)
    rejected = sum(1 for event in strategy_events if event.get("passed") is False)
    recent_reasons = _top_counts(
        reason
        for event in strategy_events
        for reason in event.get("reasons", [])
    )
    preflight_blocks = _top_counts(
        reason
        for event in ibkr_events
        for reason in event.get("readiness", {}).get("missing_requirements", [])
    )
    latest_preflight = _latest_preflight_event(ibkr_events)
    statuses = _top_counts(
        str(event.get("status"))
        for event in ibkr_events
        if event.get("status")
    )
    outcome_summary = _outcome_summary(outcome_events)
    lines = [
        f"- Same-strategy agent gate history: {approved} approved, {rejected} rejected in last {lookback_events} gate events.",
    ]
    if outcome_summary:
        lines.append(f"- Same-strategy paper outcome summary: {outcome_summary}.")
    if recent_reasons:
        lines.append(f"- Same-strategy rejection reasons: {recent_reasons}.")
    if latest_preflight:
        readiness = latest_preflight.get("readiness", {})
        market_data = latest_preflight.get("market_data", {})
        lines.append(
            "- Latest IBKR preflight: "
            f"status={readiness.get('status', 'unknown')}, "
            f"missing={readiness.get('missing_requirements', [])}, "
            f"bid={market_data.get('bid')}, ask={market_data.get('ask')}, last={market_data.get('last')}, "
            f"spread={market_data.get('spread')}, order_ready={market_data.get('order_ready')}."
        )
    if statuses:
        lines.append(f"- Recent IBKR paper statuses: {statuses}.")
    if preflight_blocks:
        lines.append(f"- Historical IBKR preflight blockers, not current state unless latest preflight is blocked: {preflight_blocks}.")
    if len(lines) == 1 and not strategy_events and not ibkr_events:
        lines.append("- No prior gate or paper-trading audit events found; treat this as first-run evidence.")
    lines.append("- Use this context as a robustness prior only; do not approve a trade solely because past approvals exist.")
    return "\n".join(lines)


def load_strategy_evidence(strategy_id: str, path: Path | str) -> dict[str, Any] | None:
    evidence_path = Path(path)
    if not strategy_id or not evidence_path.exists():
        return None
    try:
        with evidence_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("name") == strategy_id:
                    return row
    except OSError:
        return None
    return None


def _live_market_context_lines(trade: dict[str, Any]) -> list[str]:
    if not trade:
        return []
    fields = {
        "bid": trade.get("ibkr_bid"),
        "ask": trade.get("ibkr_ask"),
        "last": trade.get("ibkr_last"),
        "spread": trade.get("ibkr_spread"),
        "market_data_type": trade.get("ibkr_market_data_type"),
        "order_ready": trade.get("ibkr_order_ready"),
        "snapshot_time": trade.get("ibkr_snapshot_time"),
    }
    if not any(_has_value(value) for value in fields.values()):
        return []
    return [
        "- IBKR snapshot is top-of-book bid/ask/last evidence, not full MBP depth-derived features.",
        "- "
        + ", ".join(f"{key}={value}" for key, value in fields.items() if _has_value(value)),
    ]


def _strategy_evidence_lines(evidence: dict[str, Any]) -> list[str]:
    keys = [
        "candidate_universe",
        "selection_tier",
        "family",
        "full_trades",
        "full_net_points",
        "full_max_drawdown_points",
        "net_to_drawdown",
        "full_profit_factor",
        "full_win_rate",
        "full_stability",
        "positive_fold_rate",
        "positive_window_rate",
        "min_window_net_points",
        "stress_net_points",
        "best_strategy_score",
        "live_ready",
    ]
    lines = [
        "- These are backtest/walk-forward metrics for strategy robustness; current live order still requires current market readiness and risk checks."
    ]
    summary = ", ".join(f"{key}={evidence.get(key)}" for key in keys if _has_value(evidence.get(key)))
    if summary:
        lines.append(f"- {summary}")
    return lines


def _latest_preflight_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") == "ibkr_paper_preflight":
            return event
    return None


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "nan", "None"}
    return True


def analysis_symbol_from_intent(intent: IBKROrderIntent) -> str:
    symbol = intent.symbol.upper()
    contract_month = str(intent.last_trade_date_or_contract_month)
    if len(contract_month) >= 6 and contract_month[:4].isdigit():
        month_code = FUTURES_MONTH_CODES.get(contract_month[4:6])
        if month_code:
            return f"{symbol}{month_code}{contract_month[3]}"
    return symbol


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events[-limit:]


def _event_strategy_id(event: dict[str, Any]) -> str | None:
    strategy_id = event.get("strategy_id")
    if strategy_id:
        return str(strategy_id)
    intent = event.get("intent")
    if isinstance(intent, dict):
        strategy_id = intent.get("strategy_id")
        if strategy_id:
            return str(strategy_id)
    selected_trade = event.get("selected_trade")
    if isinstance(selected_trade, dict):
        portfolio_rule = selected_trade.get("portfolio_rule")
        if portfolio_rule:
            return str(portfolio_rule)
    return None


def _top_counts(values) -> str:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        if not key or key == "None":
            continue
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5])


def _outcome_summary(events: list[dict[str, Any]]) -> str:
    metrics = outcome_metrics(events)
    if not metrics["trades"]:
        return ""
    return (
        f"trades={metrics['trades']}, wins={metrics['wins']}, losses={metrics['losses']}, "
        f"win_rate={metrics['win_rate']:.1f}%, net_points={metrics['net_points']:.2f}, "
        f"avg_points={metrics['avg_points']:.2f}, best={metrics['best_points']:.2f}, "
        f"worst={metrics['worst_points']:.2f}, consecutive_losses={metrics['consecutive_losses']}"
    )


def outcome_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    points = _outcome_points(events)
    if not points:
        return {
            "trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_points": 0.0,
            "avg_points": 0.0,
            "best_points": 0.0,
            "worst_points": 0.0,
            "consecutive_losses": 0,
        }
    wins = sum(1 for value in points if value > 0)
    losses = sum(1 for value in points if value < 0)
    total = sum(points)
    average = total / len(points)
    win_rate = wins / len(points) * 100
    return {
        "trades": len(points),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "net_points": total,
        "avg_points": average,
        "best_points": max(points),
        "worst_points": min(points),
        "consecutive_losses": _trailing_losses(points),
    }


def _outcome_points(events: list[dict[str, Any]]) -> list[float]:
    points = []
    for event in events:
        value = event.get("points")
        if value is None:
            continue
        try:
            points.append(float(value))
        except (TypeError, ValueError):
            continue
    return points


def _trailing_losses(points: list[float]) -> int:
    count = 0
    for value in reversed(points):
        if value < 0:
            count += 1
        else:
            break
    return count


def _guard_severity(reasons: list[str], hard_block: bool) -> str:
    if not reasons:
        return "normal"
    if hard_block and (
        "paper_consecutive_losses_guard" in reasons
        or ("paper_win_rate_below_guard" in reasons and "paper_net_points_below_guard" in reasons)
    ):
        return "block"
    return "watch"


def _guard_position_scale(severity: str, watch_scale: float) -> float:
    if severity == "block":
        return 0.0
    if severity == "watch":
        return max(0.0, min(1.0, float(watch_scale)))
    return 1.0


def _now() -> str:
    return datetime.now(UTC).isoformat()
