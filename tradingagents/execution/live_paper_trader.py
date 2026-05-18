from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .agent_gate import AgentStrategyGate
from .ibkr import IBKRContractSpec, IBKRPaperBroker, IBKRPaperTradingSession
from .live_signal import LiveSignalConfig, build_live_signal_row, write_live_signal
from .live_strategy import (
    BEST_MEAN_REVERSION_STRATEGY_ID,
    BEST_MEAN_REVERSION_ALIAS,
    LiveStrategySignalConfig,
    LiveStrategySpec,
    build_strategy_live_signal_row,
)
from .paper_runner import PaperRunnerConfig, run_adaptive_portfolio_paper_once
from .paper_report import PaperValidationGateConfig, summarize_paper_audits
from .tick_recorder import IBKRTickRecorderConfig
from .trade_log import append_execution_fill_log, append_realtime_execution_fill_ledger, append_realtime_trade_ledger
from .trade_outcome_inference import infer_outcomes, record_outcomes

DEFAULT_LIVE_STRATEGY_ID = BEST_MEAN_REVERSION_STRATEGY_ID
DEFAULT_LIVE_SELECTED_ALIAS = BEST_MEAN_REVERSION_ALIAS


@dataclass(frozen=True)
class LivePaperTraderConfig:
    live_signal_path: Path = Path(".tmp/mbp-live-signal.csv")
    state_path: Path = Path(".tmp/mbp-live-paper-trader-state.json")
    strategy_id: str = DEFAULT_LIVE_STRATEGY_ID
    selected_alias: str = DEFAULT_LIVE_SELECTED_ALIAS
    direction: int = 0
    signal_mode: str = "strategy"
    strategy_spec: LiveStrategySpec = field(default_factory=LiveStrategySpec)
    strategy_signal: LiveStrategySignalConfig = field(default_factory=LiveStrategySignalConfig)
    contract: IBKRContractSpec = IBKRContractSpec()
    account: str | None = None
    quantity: int = 1
    stop_loss_points: float = 16.0
    take_profit_points: float = 24.0
    max_hold_minutes: int = 6
    submit: bool = False
    require_agent_gate: bool = False
    skip_preflight: bool = False
    snapshot_attempts: int = 3
    snapshot_retry_seconds: float = 1.0
    skip_when_position_open: bool = True
    trade_log_dir: Path = Path("docs/Strategy/tradelogs")
    realtime_ledger_path: Path = Path(".tmp/ibkr-paper-realtime-trades.jsonl")
    realtime_ledger_csv_path: Path | None = Path(".tmp/ibkr-paper-realtime-trades.csv")
    sync_execution_logs: bool = True
    sync_paper_outcomes: bool = True
    agent_audit_path: Path = Path(".tmp/agent-gate-audit.jsonl")
    ibkr_audit_path: Path = Path(".tmp/ibkr-paper-audit.jsonl")
    paper_validation_gate_enabled: bool = True
    paper_validation_accrual_mode: bool = False
    paper_validation_gate: PaperValidationGateConfig = field(default_factory=PaperValidationGateConfig)
    update_memory_from_outcomes: bool = False
    tick_recorder: IBKRTickRecorderConfig = field(default_factory=IBKRTickRecorderConfig)


@dataclass(frozen=True)
class LivePaperTraderDaemonConfig:
    trader: LivePaperTraderConfig = field(default_factory=LivePaperTraderConfig)
    interval_seconds: float = 30.0
    max_iterations: int | None = None
    preflight_attempts: int = 3
    preflight_retry_seconds: float = 1.0
    require_preflight_ready: bool = True
    status_path: Path = Path(".tmp/mbp-live-paper-trader-status.json")


def run_live_paper_trader_daemon(
    *,
    config: LivePaperTraderDaemonConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    gate: AgentStrategyGate | None = None,
) -> dict[str, Any]:
    config = config or LivePaperTraderDaemonConfig()
    active_broker = broker or IBKRPaperBroker()
    if config.require_preflight_ready:
        while True:
            preflight = live_paper_preflight(
                broker=active_broker,
                contract=config.trader.contract,
                attempts=config.preflight_attempts,
                retry_seconds=config.preflight_retry_seconds,
            )
            if preflight.get("readiness", {}).get("status") == "ready":
                _write_live_status(
                    config.status_path,
                    {
                        "status": "running",
                        "iterations": 0,
                        "events": [],
                        "mode": "submit" if config.trader.submit else "dry_run",
                        "preflight": _compact_preflight(preflight),
                    },
                )
                break
            result = {
                "status": "preflight_blocked",
                "submitted": False,
                "iterations": 0,
                "events": [],
                "mode": "submit" if config.trader.submit else "dry_run",
                "preflight": preflight,
                "state_path": str(config.trader.state_path),
            }
            _write_live_status(config.status_path, result)
            _append_live_audit(config.trader.state_path, result)
            if config.max_iterations is not None:
                return result
            time.sleep(max(1.0, float(config.interval_seconds)))
    iteration = 0
    events: list[dict[str, Any]] = []
    next_started_at = time.monotonic()
    while config.max_iterations is None or iteration < config.max_iterations:
        now = time.monotonic()
        if now < next_started_at:
            time.sleep(next_started_at - now)
        started_at = time.monotonic()
        iteration += 1
        result = run_live_paper_trader_once(config=config.trader, broker=active_broker, gate=gate)
        execution_sync = _sync_execution_logs(active_broker, config.trader)
        next_started_at = started_at + max(0.0, float(config.interval_seconds))
        event = {
            "iteration": iteration,
            "status": result.get("status"),
            "submitted": result.get("submitted"),
            "reason": result.get("reason"),
            "candidate_key": result.get("candidate_key"),
            "intent_id": result.get("intent", {}).get("intent_id") if isinstance(result.get("intent"), dict) else None,
            "execution_log_sync": execution_sync,
            "started_at_monotonic": started_at,
            "next_started_at_monotonic": next_started_at,
        }
        _append_live_audit(config.trader.state_path, {"status": "daemon_iteration", **event})
        events.append(event)
        _write_live_status(
            config.status_path,
            {
                "status": "running",
                "iterations": iteration,
                "events": events[-20:],
                "mode": "submit" if config.trader.submit else "dry_run",
                "last_event": event,
            },
        )
        if config.max_iterations is not None and iteration >= config.max_iterations:
            break
    result = {"status": "completed", "iterations": iteration, "events": events, "state_path": str(config.trader.state_path)}
    _write_live_status(config.status_path, result)
    return result


def live_paper_preflight(
    *,
    broker: IBKRPaperBroker,
    contract: IBKRContractSpec,
    attempts: int,
    retry_seconds: float,
) -> dict[str, Any]:
    session = IBKRPaperTradingSession(broker=broker, contract=contract)
    last_preflight: dict[str, Any] = {}
    for attempt in range(max(1, int(attempts))):
        try:
            last_preflight = session.preflight()
        except Exception as exc:
            last_preflight = {
                "event_type": "ibkr_paper_preflight",
                "created_at": time.time(),
                "socket_ready": False,
                "connection": {
                    "status": "blocked",
                    "connected": False,
                    "reason": str(exc) or exc.__class__.__name__,
                    "error_type": exc.__class__.__name__,
                    "connection": asdict(broker.connection),
                },
                "account": {},
                "contract": {},
                "market_data": {},
                "readiness": {
                    "status": "blocked",
                    "missing_requirements": ["preflight_error"],
                },
            }
            broker._audit(last_preflight)
        if last_preflight.get("readiness", {}).get("status") == "ready":
            return last_preflight
        if attempt + 1 < attempts:
            time.sleep(max(0.0, float(retry_seconds)))
    return last_preflight


def run_live_paper_trader_once(
    *,
    config: LivePaperTraderConfig | None = None,
    broker: IBKRPaperBroker | None = None,
    gate: AgentStrategyGate | None = None,
) -> dict[str, Any]:
    config = config or LivePaperTraderConfig()
    active_broker = broker or IBKRPaperBroker()
    try:
        live_signal_config = LiveSignalConfig(
            output=config.live_signal_path,
            strategy_id=config.strategy_id,
            selected_alias=config.selected_alias,
            direction=config.direction,
            max_hold_minutes=config.max_hold_minutes,
            signal_source="ibkr_live_paper_trader",
            contract=config.contract,
            snapshot_attempts=config.snapshot_attempts,
            snapshot_retry_seconds=config.snapshot_retry_seconds,
        )
        if config.signal_mode == "strategy":
            row = build_strategy_live_signal_row(
                signal_config=live_signal_config,
                strategy_spec=config.strategy_spec,
                strategy_config=config.strategy_signal,
                broker=active_broker,
            )
        elif config.signal_mode == "manual":
            row = build_live_signal_row(config=live_signal_config, broker=active_broker)
        else:
            raise ValueError(f"unsupported signal_mode: {config.signal_mode}")
    except Exception as exc:
        result = {
            "status": "signal_blocked",
            "submitted": False,
            "reason": str(exc) or exc.__class__.__name__,
        }
        result["realtime_ledger"] = _append_realtime_ledger_safely(result, config=config)
        _append_live_audit(config.state_path, result)
        return result

    write_live_signal(row, config.live_signal_path)
    if config.skip_when_position_open:
        exposure = _current_exposure(active_broker, config.contract.symbol)
        if exposure["blocked"]:
            result = {
                "status": "exposure_blocked",
                "submitted": False,
                "reason": exposure["reason"],
                "exposure": exposure,
                "live_signal": row,
            }
            result["realtime_ledger"] = _append_realtime_ledger_safely(result, config=config)
            _append_live_audit(config.state_path, result)
            return result

    paper_gate = _paper_validation_gate(config) if config.submit and config.paper_validation_gate_enabled else None
    if paper_gate is not None and not _paper_gate_allows_submit(paper_gate, accrual_mode=config.paper_validation_accrual_mode):
        result = {
            "status": "paper_validation_blocked",
            "submitted": False,
            "reason": ",".join(paper_gate.get("blockers", [])) or "paper_validation_blocked",
            "paper_validation_gate": paper_gate,
            "live_signal": row,
        }
        result["realtime_ledger"] = _append_realtime_ledger_safely(result, config=config)
        _append_live_audit(config.state_path, result)
        return result

    runner_config = PaperRunnerConfig(
        trades_path=config.live_signal_path,
        state_path=config.state_path,
        contract_month=config.contract.last_trade_date_or_contract_month,
        account=config.account,
        quantity=config.quantity,
        stop_loss_points=config.stop_loss_points,
        take_profit_points=config.take_profit_points,
        submit=config.submit,
        skip_preflight=config.skip_preflight,
        require_agent_gate=config.require_agent_gate,
        max_signal_age_minutes=10.0,
        trade_log_dir=config.trade_log_dir,
        tick_recorder=config.tick_recorder,
    )
    result = run_adaptive_once(runner_config, active_broker, gate)
    result["live_signal"] = row
    result["realtime_ledger"] = _append_realtime_ledger_safely(result, config=config)
    _append_live_audit(config.state_path, {"status": "live_iteration", **_audit_result(result)})
    return result


def run_adaptive_once(
    runner_config: PaperRunnerConfig,
    broker: IBKRPaperBroker,
    gate: AgentStrategyGate | None,
) -> dict[str, Any]:
    return run_adaptive_portfolio_paper_once(config=runner_config, broker=broker, gate=gate)


def _current_exposure(broker: IBKRPaperBroker, symbol: str) -> dict[str, Any]:
    try:
        connection = broker.connect()
        if not connection.get("connected"):
            return {
                "blocked": True,
                "reason": connection.get("reason") or connection.get("status") or "connect_failed",
                "connection": connection,
            }
        snapshot = broker.status_snapshot(symbol)
    except Exception as exc:
        return {"blocked": True, "reason": str(exc) or exc.__class__.__name__}
    current_position = int(snapshot.get("current_position") or 0)
    open_trades = snapshot.get("open_trades") or []
    blocked = current_position != 0 or bool(open_trades)
    return {
        "blocked": blocked,
        "reason": "position_or_open_orders_present" if blocked else None,
        "current_position": current_position,
        "open_trades": open_trades,
    }


def _append_realtime_ledger_safely(result: dict[str, Any], *, config: LivePaperTraderConfig) -> dict[str, Any]:
    try:
        return append_realtime_trade_ledger(
            result,
            ledger_path=config.realtime_ledger_path,
            csv_path=config.realtime_ledger_csv_path,
        )
    except Exception as exc:
        return {"status": "error", "reason": str(exc) or exc.__class__.__name__}


def _append_live_audit(state_path: Path, event: dict[str, Any]) -> None:
    audit_path = state_path.with_suffix(".jsonl")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event_type": "ibkr_live_paper_trader", **event}, sort_keys=True, default=str) + "\n")


def _write_live_status(path: Path, status: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(status, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)
    return path


def _compact_preflight(preflight: dict[str, Any]) -> dict[str, Any]:
    readiness = preflight.get("readiness", {}) if isinstance(preflight.get("readiness"), dict) else {}
    connection = preflight.get("connection", {}) if isinstance(preflight.get("connection"), dict) else {}
    market_data = preflight.get("market_data", {}) if isinstance(preflight.get("market_data"), dict) else {}
    return {
        "status": readiness.get("status"),
        "missing_requirements": readiness.get("missing_requirements", []),
        "connected": connection.get("connected"),
        "connection_reason": connection.get("reason"),
        "market_data": {
            "order_ready": market_data.get("order_ready"),
            "bid": market_data.get("bid"),
            "ask": market_data.get("ask"),
            "last": market_data.get("last"),
            "spread": market_data.get("spread"),
            "market_data_type": market_data.get("market_data_type"),
        },
    }


def _paper_validation_gate(config: LivePaperTraderConfig) -> dict[str, Any]:
    summary = summarize_paper_audits(
        agent_audit_path=config.agent_audit_path,
        ibkr_audit_path=config.ibkr_audit_path,
        gate_config=config.paper_validation_gate,
        strategy_id=config.strategy_id,
    )
    return summary["validation_gate"]


def _paper_gate_allows_submit(gate: dict[str, Any], *, accrual_mode: bool) -> bool:
    if gate.get("status") == "pass":
        return True
    if not accrual_mode:
        return False
    blockers = list(gate.get("blockers", []))
    return bool(blockers) and all(str(blocker).startswith("paper_outcomes_below_min:") for blocker in blockers)


def _sync_execution_logs(broker: IBKRPaperBroker, config: LivePaperTraderConfig) -> dict[str, Any]:
    if not config.sync_execution_logs:
        return {"status": "disabled", "fills": 0}
    try:
        fills = broker.execution_fills(symbol=config.contract.symbol)
        paths = []
        fill_ledgers = []
        for fill in fills:
            path = append_execution_fill_log(fill, log_dir=config.trade_log_dir)
            if path is not None:
                paths.append(str(path))
            fill_ledgers.append(
                append_realtime_execution_fill_ledger(
                    fill,
                    ledger_path=config.realtime_ledger_path,
                    csv_path=config.realtime_ledger_csv_path,
                )
            )
        outcome_sync = _sync_paper_outcomes(config) if paths else {"status": "skipped", "recorded": 0, "reason": "no_trade_log_paths"}
        return {
            "status": "synced",
            "fills": len(fills),
            "paths": sorted(set(paths)),
            "realtime_fill_ledgers": fill_ledgers,
            "paper_outcomes": outcome_sync,
        }
    except Exception as exc:
        return {"status": "error", "fills": 0, "reason": str(exc) or exc.__class__.__name__}


def _sync_paper_outcomes(config: LivePaperTraderConfig) -> dict[str, Any]:
    if not config.sync_paper_outcomes:
        return {"status": "disabled", "recorded": 0}
    outcomes = infer_outcomes(config.trade_log_dir, strategy_id=config.strategy_id)
    high_confidence = [outcome for outcome in outcomes if outcome.confidence == "target_or_stop_hit"]
    recorded = record_outcomes(
        outcomes,
        audit_path=config.agent_audit_path,
        update_memory=config.update_memory_from_outcomes,
    )
    return {
        "status": "synced",
        "outcomes": len(outcomes),
        "high_confidence": len(high_confidence),
        "recorded": recorded,
        "audit_path": str(config.agent_audit_path),
    }


def _audit_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "status": result.get("status"),
        "submitted": result.get("submitted"),
        "candidate_key": result.get("candidate_key"),
        "intent": result.get("intent"),
        "agent_gate": result.get("agent_gate"),
        "tick_recording": result.get("tick_recording"),
        "trade_log_path": result.get("trade_log_path"),
        "trade_log_error": result.get("trade_log_error"),
        "realtime_ledger": result.get("realtime_ledger"),
    }
    selected_trade = result.get("selected_trade")
    if selected_trade:
        compact["selected_trade"] = selected_trade
    return compact


__all__ = [
    "BEST_MEAN_REVERSION_STRATEGY_ID",
    "BEST_MEAN_REVERSION_ALIAS",
    "LivePaperTraderConfig",
    "LivePaperTraderDaemonConfig",
    "live_paper_preflight",
    "run_live_paper_trader_daemon",
    "run_live_paper_trader_once",
]
