from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent_gate import AgentGateConfig, AgentStrategyGate, outcome_metrics
from .ibkr import IBKROrderIntent, IBKRPaperBroker, IBKRPaperTradingSession
from .paper_validation import build_paper_intent_from_trade, load_trade_samples, select_trade_sample
from .trade_log import DEFAULT_TRADE_LOG_DIR, append_trade_log
from .tick_recorder import IBKRTickRecorderConfig, record_ibkr_ticks


@dataclass(frozen=True)
class PaperRunnerConfig:
    trades_path: Path = Path(".tmp/mbp-adaptive-portfolio-trades.csv")
    state_path: Path = Path(".tmp/mbp-paper-runner-state.json")
    contract_month: str = "202606"
    account: str | None = None
    quantity: int = 1
    stop_loss_points: float | None = 16.0
    take_profit_points: float | None = 24.0
    submit: bool = False
    skip_preflight: bool = False
    require_agent_gate: bool = False
    max_signal_age_minutes: float | None = 10.0
    audit_path: Path | None = None
    trade_log_dir: Path = DEFAULT_TRADE_LOG_DIR
    tick_recorder: IBKRTickRecorderConfig = field(default_factory=IBKRTickRecorderConfig)
    allow_time_exit_without_bracket_dry_run: bool = False
    allow_time_exit_submit: bool = False
    timed_exit_sleep_scale: float = 1.0
    agent_audit_path: Path = Path(".tmp/agent-gate-audit.jsonl")
    paper_consecutive_loss_halt: int | None = None
    paper_daily_loss_halt_points: float | None = None


@dataclass(frozen=True)
class PaperDaemonConfig:
    runner: PaperRunnerConfig = field(default_factory=PaperRunnerConfig)
    interval_seconds: float = 60.0
    max_iterations: int | None = None
    refresh_report: bool = True
    status_snapshot: bool = True
    trade_date: str | None = None
    portfolio_rule: str | None = None
    selected_alias: str | None = None
    row_index: int | None = None


def run_adaptive_portfolio_paper_daemon(
    *,
    config: PaperDaemonConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    gate: AgentStrategyGate | None = None,
) -> dict[str, Any]:
    config = config or PaperDaemonConfig()
    iteration = 0
    events = []
    active_broker = broker or IBKRPaperBroker(audit_path=config.runner.audit_path)
    while config.max_iterations is None or iteration < config.max_iterations:
        iteration += 1
        before = _status_snapshot(active_broker, config.runner.tick_recorder.symbol) if config.status_snapshot else {}
        result = run_adaptive_portfolio_paper_once(
            config=config.runner,
            trade_date=config.trade_date,
            portfolio_rule=config.portfolio_rule,
            selected_alias=config.selected_alias,
            row_index=config.row_index,
            broker=active_broker,
            gate=gate,
        )
        after = _status_snapshot(active_broker, config.runner.tick_recorder.symbol) if config.status_snapshot else {}
        event = {
            "iteration": iteration,
            "status": result.get("status"),
            "submitted": result.get("submitted"),
            "candidate_key": result.get("candidate_key"),
            "before": before,
            "after": after,
        }
        _append_runner_audit(config.runner.state_path, {"status": "daemon_iteration", **event})
        events.append(event)
        if config.refresh_report:
            events[-1]["refresh_report"] = refresh_validation_report()
        if config.max_iterations is not None and iteration >= config.max_iterations:
            break
        time.sleep(config.interval_seconds)
    return {
        "status": "completed",
        "iterations": iteration,
        "events": events,
        "state_path": str(config.runner.state_path),
    }


def run_adaptive_portfolio_paper_once(
    *,
    config: PaperRunnerConfig | None = None,
    trade_date: str | None = None,
    portfolio_rule: str | None = None,
    selected_alias: str | None = None,
    row_index: int | None = None,
    broker: IBKRPaperBroker | None = None,
    gate: AgentStrategyGate | None = None,
) -> dict[str, Any]:
    config = config or PaperRunnerConfig()
    state = _load_state(config.state_path)
    active_broker = broker or IBKRPaperBroker(audit_path=config.audit_path)
    pending_broker = _without_bracket_requirement(active_broker) if config.allow_time_exit_submit else active_broker
    pending_time_exit = _manage_pending_time_exit_close(
        state_path=config.state_path,
        state=state,
        broker=pending_broker,
        submit=config.submit,
        allow_submit=config.allow_time_exit_submit,
    )
    if pending_time_exit is not None:
        pending_time_exit["tick_recording"] = _record_ibkr_ticks_safely(
            broker=active_broker,
            config=config.tick_recorder,
            intent_id=pending_time_exit.get("intent", {}).get("intent_id"),
            candidate_key=str(pending_time_exit.get("candidate_key", "")),
            strategy_id=pending_time_exit.get("intent", {}).get("strategy_id"),
        )
        _append_runner_audit(config.state_path, pending_time_exit)
        return pending_time_exit

    try:
        trades = load_trade_samples(config.trades_path)
    except (FileNotFoundError, ValueError) as exc:
        result = {
            "status": "no_signal",
            "submitted": False,
            "reason": str(exc) or exc.__class__.__name__,
            "trades_path": str(config.trades_path),
        }
        _append_runner_audit(config.state_path, result)
        return result
    sample = select_trade_sample(
        trades,
        trade_date=trade_date,
        portfolio_rule=portfolio_rule,
        selected_alias=selected_alias,
        row_index=row_index,
    )
    stop_loss_points = _sample_optional_float(sample, "strategy_stop_points", config.stop_loss_points)
    take_profit_points = _sample_optional_float(sample, "strategy_target_points", config.take_profit_points)
    intent = build_paper_intent_from_trade(
        sample,
        contract_month=config.contract_month,
        account=config.account,
        quantity=config.quantity,
        stop_loss_points=stop_loss_points,
        take_profit_points=take_profit_points,
        symbol=config.tick_recorder.symbol,
    ).normalized()
    key = _candidate_key(sample, intent.strategy_id)
    previous = state.get("last_candidate_key")
    if previous == key:
        result = {
            "status": "duplicate_skipped",
            "submitted": False,
            "candidate_key": key,
            "previous_candidate_key": previous,
            "selected_trade": sample.to_dict(),
            "intent": asdict(intent),
        }
        _append_runner_audit(config.state_path, result)
        return result

    freshness = _signal_freshness(sample, max_age_minutes=config.max_signal_age_minutes)
    if config.submit and not freshness["passed"]:
        result = {
            "status": "stale_signal_blocked",
            "submitted": False,
            "candidate_key": key,
            "freshness": freshness,
            "selected_trade": sample.to_dict(),
            "intent": asdict(intent),
        }
        _append_runner_audit(config.state_path, result)
        return result

    risk_halt = _paper_risk_halt(
        strategy_id=intent.strategy_id,
        trade_date=str(sample.get("trade_date", "")),
        audit_path=config.agent_audit_path,
        consecutive_loss_halt=config.paper_consecutive_loss_halt,
        daily_loss_halt_points=config.paper_daily_loss_halt_points,
    )
    if config.submit and risk_halt["halted"]:
        result = {
            "status": "paper_risk_halted",
            "submitted": False,
            "candidate_key": key,
            "paper_risk_halt": risk_halt,
            "selected_trade": sample.to_dict(),
            "intent": asdict(intent),
        }
        _append_runner_audit(config.state_path, result)
        return result

    gate_config = AgentGateConfig.from_env()
    use_agent_gate = config.require_agent_gate or gate_config.enabled
    gate_result = None
    if use_agent_gate:
        gate_result = (gate or AgentStrategyGate(gate_config)).review(
            intent,
            trade_date=str(sample.get("trade_date", "")),
            selected_trade=sample.to_dict(),
        )
        if not gate_result["passed"]:
            result = {
                "status": "agent_gate_rejected",
                "submitted": False,
                "candidate_key": key,
                "agent_gate": gate_result,
                "selected_trade": sample.to_dict(),
                "intent": asdict(intent),
            }
            _append_runner_audit(config.state_path, result)
            return result

    time_exit_without_bracket = _time_exit_without_bracket_allowed(
        sample,
        stop_loss_points=stop_loss_points,
        take_profit_points=take_profit_points,
        submit=config.submit,
        allow_dry_run=config.allow_time_exit_without_bracket_dry_run,
        allow_submit=config.allow_time_exit_submit,
    )
    execution_broker = _without_bracket_requirement(active_broker) if time_exit_without_bracket else active_broker
    if config.submit:
        response = IBKRPaperTradingSession.from_env(execution_broker).submit_intent(
            intent,
            dry_run=False,
            skip_preflight=config.skip_preflight,
        )
    else:
        response = execution_broker.submit(intent, dry_run=True)
    if time_exit_without_bracket:
        response["time_exit_management"] = {
            "enabled": True,
            "mode": "submit_managed" if config.submit else "dry_run_only",
            "holding_minutes": _sample_optional_float(sample, "holding_minutes", None),
            "reason": "time_exit_strategy_without_bracket",
        }
    if time_exit_without_bracket and config.submit and response.get("status") == "submitted":
        response["time_exit_management"] = _submit_timed_exit_close(
            broker=execution_broker,
            entry_intent=intent,
            entry_response=response,
            sample=sample,
            sleep_scale=config.timed_exit_sleep_scale,
            state_path=config.state_path,
            candidate_key=key,
        )
    result = {
        "status": response.get("status", "unknown"),
        "submitted": bool(response.get("submitted")),
        "candidate_key": key,
        "agent_gate": gate_result,
        "selected_trade": sample.to_dict(),
        "intent": response.get("intent", asdict(intent)),
        "result": response,
    }
    if "time_exit_management" in response:
        result["time_exit_management"] = response["time_exit_management"]
    if response.get("status") in {"dry_run", "submitted"}:
        updated_state = _load_state(config.state_path)
        updated_state.update({"last_candidate_key": key, "last_intent_id": result["intent"].get("intent_id")})
        _save_state(config.state_path, updated_state)
    trade_log_path = _append_trade_log_safely(result, log_dir=config.trade_log_dir)
    if trade_log_path is not None:
        result["trade_log_path"] = str(trade_log_path)
    result["tick_recording"] = _record_ibkr_ticks_safely(
        broker=active_broker,
        config=config.tick_recorder,
        intent_id=result["intent"].get("intent_id"),
        candidate_key=key,
        strategy_id=result["intent"].get("strategy_id"),
    )
    _append_runner_audit(config.state_path, result)
    return result


def refresh_validation_report() -> dict[str, Any]:
    root_dir = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [sys.executable, "scripts/run_daily_paper_validation.py"],
        cwd=root_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _candidate_key(sample: Any, strategy_id: str) -> str:
    parts = [
        str(sample.get("portfolio_rule", strategy_id)),
        str(sample.get("selected_alias", "")),
        str(sample.get("entry_ts", "")),
        str(sample.get("exit_ts", "")),
        str(sample.get("direction", "")),
        str(sample.get("entry_price", "")),
    ]
    return "|".join(parts)


def _paper_risk_halt(
    *,
    strategy_id: str,
    trade_date: str,
    audit_path: Path,
    consecutive_loss_halt: int | None,
    daily_loss_halt_points: float | None,
) -> dict[str, Any]:
    if consecutive_loss_halt is None and daily_loss_halt_points is None:
        return {"enabled": False, "halted": False, "reasons": []}
    events = [
        event
        for event in _read_agent_outcomes(audit_path)
        if event.get("event_type") == "agent_gate_paper_outcome" and _event_strategy_id(event) == strategy_id
    ]
    metrics = outcome_metrics(events)
    day_events = [event for event in events if _event_trade_date(event) == trade_date]
    day_points = sum(_event_points(event) for event in day_events)
    reasons: list[str] = []
    if consecutive_loss_halt is not None and metrics["consecutive_losses"] >= int(consecutive_loss_halt):
        reasons.append(f"consecutive_loss_halt:{metrics['consecutive_losses']}>={int(consecutive_loss_halt)}")
    if daily_loss_halt_points is not None and day_points <= -abs(float(daily_loss_halt_points)):
        reasons.append(f"daily_loss_halt:{day_points:.2f}<=-{abs(float(daily_loss_halt_points)):.2f}")
    return {
        "enabled": True,
        "halted": bool(reasons),
        "reasons": reasons,
        "metrics": metrics,
        "trade_date": trade_date,
        "daily_points": day_points,
        "daily_trades": len(day_events),
        "thresholds": {
            "consecutive_loss_halt": consecutive_loss_halt,
            "daily_loss_halt_points": daily_loss_halt_points,
        },
    }


def _read_agent_outcomes(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events


def _event_strategy_id(event: dict[str, Any]) -> str | None:
    strategy_id = event.get("strategy_id")
    if strategy_id:
        return str(strategy_id)
    intent = event.get("intent")
    if isinstance(intent, dict) and intent.get("strategy_id"):
        return str(intent["strategy_id"])
    return None


def _event_trade_date(event: dict[str, Any]) -> str:
    raw = event.get("trade_date") or event.get("exit_time") or event.get("created_at")
    timestamp = _parse_utc_timestamp(raw)
    return timestamp.date().isoformat() if timestamp is not None else str(raw or "")


def _event_points(event: dict[str, Any]) -> float:
    try:
        return float(event.get("points") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _sample_optional_float(sample: Any, key: str, fallback: float | None) -> float | None:
    value = sample.get(key, None)
    if value is None or value == "":
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return number


def _time_exit_without_bracket_allowed(
    sample: Any,
    *,
    stop_loss_points: float | None,
    take_profit_points: float | None,
    submit: bool,
    allow_dry_run: bool,
    allow_submit: bool,
) -> bool:
    if submit and not allow_submit:
        return False
    if not submit and not allow_dry_run:
        return False
    if stop_loss_points is not None or take_profit_points is not None:
        return False
    exit_reason = str(sample.get("exit_reason", "") or "").lower()
    holding_minutes = _sample_optional_float(sample, "holding_minutes", None)
    strategy = str(sample.get("portfolio_rule", "") or "").lower()
    selected_alias = str(sample.get("selected_alias", "") or "").lower()
    is_lightglow = "lightglow" in strategy or "lightglow" in selected_alias
    return exit_reason == "time" and holding_minutes is not None and holding_minutes > 0 and is_lightglow


def _submit_timed_exit_close(
    *,
    broker: IBKRPaperBroker,
    entry_intent: Any,
    entry_response: dict[str, Any],
    sample: Any,
    sleep_scale: float,
    state_path: Path,
    candidate_key: str,
) -> dict[str, Any]:
    holding_minutes = _sample_optional_float(sample, "holding_minutes", None)
    if holding_minutes is None or holding_minutes <= 0:
        return {"enabled": True, "status": "close_skipped", "reason": "missing_holding_minutes"}
    entry_action = str(entry_intent.action).upper()
    close_action = "SELL" if entry_action == "BUY" else "BUY"
    close_intent = type(entry_intent)(
        action=close_action,
        quantity=entry_intent.quantity,
        symbol=entry_intent.symbol,
        exchange=entry_intent.exchange,
        currency=entry_intent.currency,
        last_trade_date_or_contract_month=entry_intent.last_trade_date_or_contract_month,
        order_type="MKT",
        account=entry_intent.account,
        strategy_id=entry_intent.strategy_id,
        reason=f"{entry_intent.reason} | timed_exit_close_after_minutes={holding_minutes:g}",
    ).normalized()
    signed_position = entry_intent.quantity if entry_action == "BUY" else -entry_intent.quantity
    wait_seconds = max(0.0, float(holding_minutes) * 60.0 * max(0.0, float(sleep_scale)))
    due_at = datetime.now(UTC).timestamp() + wait_seconds
    pending = {
        "status": "pending",
        "mode": "submit_managed",
        "candidate_key": candidate_key,
        "holding_minutes": holding_minutes,
        "wait_seconds": wait_seconds,
        "due_at": datetime.fromtimestamp(due_at, UTC).isoformat(),
        "entry_intent": asdict(entry_intent),
        "entry_status": entry_response.get("status"),
        "close_intent": asdict(close_intent),
        "signed_position": signed_position,
        "created_at": datetime.now(UTC).isoformat(),
        "attempts": 0,
    }
    state = _load_state(state_path)
    state["pending_time_exit_close"] = pending
    _save_state(state_path, state)
    if wait_seconds:
        time.sleep(wait_seconds)
    close_response = broker.submit(close_intent, dry_run=False, current_position=signed_position)
    _record_timed_exit_close_result(
        state_path=state_path,
        pending=pending,
        close_response=close_response,
    )
    return {
        "enabled": True,
        "mode": "submit_managed",
        "status": "close_submitted" if close_response.get("status") == "submitted" else close_response.get("status", "unknown"),
        "holding_minutes": holding_minutes,
        "wait_seconds": wait_seconds,
        "entry_status": entry_response.get("status"),
        "close_intent": close_response.get("intent"),
        "close_result": close_response,
        "reason": "time_exit_strategy_without_bracket",
    }


def _manage_pending_time_exit_close(
    *,
    state_path: Path,
    state: dict[str, Any],
    broker: IBKRPaperBroker,
    submit: bool,
    allow_submit: bool,
) -> dict[str, Any] | None:
    pending = state.get("pending_time_exit_close")
    if not isinstance(pending, dict):
        return None
    intent = pending.get("close_intent") if isinstance(pending.get("close_intent"), dict) else {}
    result_base = {
        "candidate_key": pending.get("candidate_key"),
        "intent": intent,
        "time_exit_management": {
            "enabled": True,
            "mode": pending.get("mode", "submit_managed"),
            "holding_minutes": pending.get("holding_minutes"),
            "due_at": pending.get("due_at"),
            "reason": "resume_pending_time_exit_close",
        },
    }
    if not submit or not allow_submit:
        return {
            **result_base,
            "status": "pending_time_exit_blocked",
            "submitted": False,
            "reason": "pending_time_exit_requires_submit_and_allow_time_exit_submit",
        }
    due_at = _parse_utc_timestamp(pending.get("due_at"))
    checked_at = datetime.now(UTC)
    if due_at is not None and checked_at < due_at:
        return {
            **result_base,
            "status": "time_exit_pending",
            "submitted": False,
            "time_exit_management": {
                **result_base["time_exit_management"],
                "status": "waiting_for_due_time",
                "seconds_until_due": (due_at - checked_at).total_seconds(),
            },
        }
    return _submit_pending_timed_exit_close(state_path=state_path, pending=pending, broker=broker)


def _submit_pending_timed_exit_close(
    *,
    state_path: Path,
    pending: dict[str, Any],
    broker: IBKRPaperBroker,
) -> dict[str, Any]:
    raw_intent = pending.get("close_intent") if isinstance(pending.get("close_intent"), dict) else {}
    close_intent = IBKROrderIntent(**{key: raw_intent[key] for key in IBKROrderIntent.__dataclass_fields__ if key in raw_intent}).normalized()
    signed_position = int(pending.get("signed_position") or (close_intent.quantity if close_intent.action == "SELL" else -close_intent.quantity))
    close_response = broker.submit(close_intent, dry_run=False, current_position=signed_position)
    _record_timed_exit_close_result(
        state_path=state_path,
        pending=pending,
        close_response=close_response,
    )
    return {
        "status": "submitted" if close_response.get("status") == "submitted" else close_response.get("status", "unknown"),
        "submitted": bool(close_response.get("submitted")),
        "candidate_key": pending.get("candidate_key"),
        "intent": close_response.get("intent", asdict(close_intent)),
        "result": close_response,
        "time_exit_management": {
            "enabled": True,
            "mode": "submit_managed",
            "status": "close_submitted" if close_response.get("status") == "submitted" else close_response.get("status", "unknown"),
            "holding_minutes": pending.get("holding_minutes"),
            "due_at": pending.get("due_at"),
            "close_intent": close_response.get("intent"),
            "close_result": close_response,
            "reason": "resumed_pending_time_exit_close",
        },
    }


def _record_timed_exit_close_result(
    *,
    state_path: Path,
    pending: dict[str, Any],
    close_response: dict[str, Any],
) -> None:
    state = _load_state(state_path)
    if close_response.get("status") == "submitted":
        state.pop("pending_time_exit_close", None)
        state["last_time_exit_close"] = {
            "candidate_key": pending.get("candidate_key"),
            "status": "submitted",
            "closed_at": datetime.now(UTC).isoformat(),
            "close_intent_id": close_response.get("intent", {}).get("intent_id"),
        }
    else:
        retry_pending = dict(pending)
        retry_pending["status"] = "close_retry_pending"
        retry_pending["attempts"] = int(retry_pending.get("attempts") or 0) + 1
        retry_pending["last_attempt_at"] = datetime.now(UTC).isoformat()
        retry_pending["last_close_status"] = close_response.get("status", "unknown")
        retry_pending["last_close_result"] = close_response
        state["pending_time_exit_close"] = retry_pending
    _save_state(state_path, state)


def _without_bracket_requirement(broker: IBKRPaperBroker) -> IBKRPaperBroker:
    return IBKRPaperBroker(
        connection=broker.connection,
        risk=replace(broker.risk, require_bracket=False),
        ib=broker.ib,
        audit_path=broker.audit_path,
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _signal_freshness(sample: Any, *, max_age_minutes: float | None) -> dict[str, Any]:
    raw_timestamp = sample.get("actual_entry_ts", None) or sample.get("entry_ts", None)
    if max_age_minutes is None:
        return {
            "passed": True,
            "max_age_minutes": None,
            "signal_ts": str(raw_timestamp),
            "checked_at": datetime.now(UTC).isoformat(),
        }
    signal_ts = _parse_utc_timestamp(raw_timestamp)
    checked_at = datetime.now(UTC)
    if signal_ts is None:
        return {
            "passed": False,
            "reason": "missing_or_invalid_signal_ts",
            "max_age_minutes": max_age_minutes,
            "signal_ts": str(raw_timestamp),
            "checked_at": checked_at.isoformat(),
        }
    age_seconds = (checked_at - signal_ts).total_seconds()
    passed = 0 <= age_seconds <= float(max_age_minutes) * 60
    return {
        "passed": passed,
        "reason": None if passed else "stale_signal",
        "max_age_minutes": max_age_minutes,
        "age_seconds": age_seconds,
        "signal_ts": signal_ts.isoformat(),
        "checked_at": checked_at.isoformat(),
    }


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
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


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _append_trade_log_safely(result: dict[str, Any], *, log_dir: Path) -> Path | None:
    try:
        return append_trade_log(result, log_dir=log_dir)
    except Exception as exc:
        result["trade_log_error"] = str(exc) or exc.__class__.__name__
        return None


def _record_ibkr_ticks_safely(
    *,
    broker: IBKRPaperBroker,
    config: IBKRTickRecorderConfig,
    intent_id: str | None,
    candidate_key: str,
    strategy_id: str | None,
) -> dict[str, Any]:
    try:
        return record_ibkr_ticks(
            broker=broker,
            config=config,
            intent_id=intent_id,
            candidate_key=candidate_key,
            strategy_id=strategy_id,
        )
    except Exception as exc:
        return {"status": "error", "ticks": 0, "errors": 1, "reason": str(exc) or exc.__class__.__name__}


def _append_runner_audit(state_path: Path, event: dict[str, Any]) -> None:
    audit_path = state_path.with_suffix(".jsonl")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event_type": "adaptive_portfolio_paper_runner", **event}, sort_keys=True, default=str) + "\n")


def _status_snapshot(broker: IBKRPaperBroker, symbol: str = "MNQ") -> dict[str, Any]:
    try:
        return broker.status_snapshot(symbol)
    except Exception as exc:
        return {"status": "snapshot_failed", "reason": str(exc) or exc.__class__.__name__}
