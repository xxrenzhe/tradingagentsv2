from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .agent_gate import AgentGateConfig, AgentStrategyGate
from .ibkr import IBKRPaperBroker, IBKRPaperTradingSession
from .paper_validation import build_paper_intent_from_trade, load_trade_samples, select_trade_sample
from .tick_recorder import IBKRTickRecorderConfig, record_ibkr_ticks


@dataclass(frozen=True)
class PaperRunnerConfig:
    trades_path: Path = Path(".tmp/mbp-adaptive-portfolio-trades.csv")
    state_path: Path = Path(".tmp/mbp-paper-runner-state.json")
    contract_month: str = "202606"
    account: str | None = None
    quantity: int = 1
    stop_loss_points: float = 16.0
    take_profit_points: float = 24.0
    submit: bool = False
    skip_preflight: bool = False
    require_agent_gate: bool = False
    max_signal_age_minutes: float | None = 10.0
    audit_path: Path | None = None
    tick_recorder: IBKRTickRecorderConfig = field(default_factory=IBKRTickRecorderConfig)


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
    intent = build_paper_intent_from_trade(
        sample,
        contract_month=config.contract_month,
        account=config.account,
        quantity=config.quantity,
        stop_loss_points=config.stop_loss_points,
        take_profit_points=config.take_profit_points,
        symbol=config.tick_recorder.symbol,
    ).normalized()
    key = _candidate_key(sample, intent.strategy_id)
    state = _load_state(config.state_path)
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

    active_broker = broker or IBKRPaperBroker(audit_path=config.audit_path)
    if config.submit:
        response = IBKRPaperTradingSession.from_env(active_broker).submit_intent(
            intent,
            dry_run=False,
            skip_preflight=config.skip_preflight,
        )
    else:
        response = active_broker.submit(intent, dry_run=True)
    result = {
        "status": response.get("status", "unknown"),
        "submitted": bool(response.get("submitted")),
        "candidate_key": key,
        "agent_gate": gate_result,
        "selected_trade": sample.to_dict(),
        "intent": response.get("intent", asdict(intent)),
        "result": response,
    }
    if response.get("status") in {"dry_run", "submitted"}:
        _save_state(config.state_path, {"last_candidate_key": key, "last_intent_id": result["intent"].get("intent_id")})
    result["tick_recording"] = record_ibkr_ticks(
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
