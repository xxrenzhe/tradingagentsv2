from pathlib import Path
import importlib.util

import pandas as pd

from tradingagents.execution.ibkr import IBKRPaperBroker, IBKRPaperRiskConfig
from tradingagents.execution.live_paper_trader import (
    LivePaperTraderConfig,
    LivePaperTraderDaemonConfig,
    run_live_paper_trader_daemon,
    run_live_paper_trader_once,
)
from tradingagents.execution.live_signal import LiveSignalConfig, build_live_signal_row, write_live_signal
from tradingagents.execution.paper_runner import PaperDaemonConfig, PaperRunnerConfig, run_adaptive_portfolio_paper_daemon, run_adaptive_portfolio_paper_once
from tradingagents.execution.paper_validation import build_paper_intent_from_trade, select_trade_sample
from tradingagents.execution.tick_recorder import IBKRTickRecorderConfig


def test_build_paper_intent_from_long_trade():
    trade = pd.Series(
        {
            "direction": 1,
            "entry_price": 25000.0,
            "trade_date": "2026-05-01",
            "portfolio_rule": "adaptive_rule",
            "selected_alias": "stable_mr",
            "exit_reason": "time",
        }
    )

    intent = build_paper_intent_from_trade(
        trade,
        contract_month="202606",
        account="DU123",
        stop_loss_points=10.0,
        take_profit_points=20.0,
    )

    assert intent.action == "BUY"
    assert intent.stop_loss_price == 24990.0
    assert intent.take_profit_price == 25020.0
    assert intent.account == "DU123"


def test_build_paper_intent_can_target_mnq():
    trade = pd.Series(
        {
            "direction": 1,
            "entry_price": 25000.0,
            "portfolio_rule": "adaptive_rule",
            "selected_alias": "stable_mr",
        }
    )

    intent = build_paper_intent_from_trade(trade, contract_month="202606", symbol="MNQ")

    assert intent.symbol == "MNQ"
    assert intent.last_trade_date_or_contract_month == "202606"


def test_build_paper_intent_can_use_current_reference_price():
    trade = pd.Series(
        {
            "direction": 1,
            "entry_price": 25000.0,
            "trade_date": "2026-05-01",
            "portfolio_rule": "adaptive_rule",
            "selected_alias": "stable_mr",
            "exit_reason": "time",
        }
    )

    intent = build_paper_intent_from_trade(
        trade,
        contract_month="202606",
        stop_loss_points=10.0,
        take_profit_points=20.0,
        reference_price=25100.0,
        reference_source="current_market_ask",
    )

    assert intent.stop_loss_price == 25090.0
    assert intent.take_profit_price == 25120.0
    assert "reference_source=current_market_ask" in intent.reason


def test_build_paper_intent_from_short_trade():
    trade = pd.Series(
        {
            "direction": -1,
            "entry_price": 25000.0,
            "trade_date": "2026-05-01",
            "portfolio_rule": "adaptive_rule",
            "selected_alias": "defensive_mr",
            "exit_reason": "reverse",
        }
    )

    intent = build_paper_intent_from_trade(trade, contract_month="202606")

    assert intent.action == "SELL"
    assert intent.stop_loss_price == 25016.0
    assert intent.take_profit_price == 24976.0


def test_select_trade_sample_filters_and_row_index():
    trades = pd.DataFrame(
        [
            {"trade_date": "2026-05-01", "portfolio_rule": "rule_a", "selected_alias": "stable_mr", "direction": 1, "entry_price": 1},
            {"trade_date": "2026-05-02", "portfolio_rule": "rule_a", "selected_alias": "defensive_mr", "direction": -1, "entry_price": 2},
            {"trade_date": "2026-05-02", "portfolio_rule": "rule_b", "selected_alias": "trend_vwap", "direction": 1, "entry_price": 3},
        ]
    )

    sample = select_trade_sample(trades, trade_date="2026-05-02", portfolio_rule="rule_a")
    assert sample["selected_alias"] == "defensive_mr"

    sample = select_trade_sample(trades, trade_date="2026-05-02", row_index=0)
    assert sample["selected_alias"] == "defensive_mr"


def test_validate_script_agent_gate_rejection_blocks_broker(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "validate_mbp_adaptive_portfolio_paper.py"
    spec = importlib.util.spec_from_file_location("validate_mbp_adaptive_portfolio_paper", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)

    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)

    class RejectingGate:
        def __init__(self, config):
            self.config = config

        def review(self, intent, *, trade_date, selected_trade=None):
            return {
                "passed": False,
                "status": "agent_rejected",
                "reasons": ["agent_rating_not_aligned_with_buy"],
                "intent": intent.normalized().__dict__,
            }

    def broker_should_not_run(*args, **kwargs):
        raise AssertionError("IBKR broker should not run after agent gate rejection")

    monkeypatch.setattr(script, "AgentStrategyGate", RejectingGate)
    monkeypatch.setattr(script, "IBKRPaperBroker", broker_should_not_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "validate_mbp_adaptive_portfolio_paper.py",
            "--trades",
            str(trades_path),
            "--agent-gate",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "agent_gate_rejected"' in output
    assert "agent_rating_not_aligned_with_buy" in output


def test_paper_runner_dry_run_records_state_and_skips_duplicate(tmp_path):
    trades_path = tmp_path / "trades.csv"
    state_path = tmp_path / "runner-state.json"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    broker = IBKRPaperBroker(
            risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    config = PaperRunnerConfig(trades_path=trades_path, state_path=state_path, account="DU123")

    first = run_adaptive_portfolio_paper_once(config=config, broker=broker)
    second = run_adaptive_portfolio_paper_once(config=config, broker=broker)

    assert first["status"] == "dry_run"
    assert first["intent"]["strategy_id"] == "adaptive_rule"
    assert second["status"] == "duplicate_skipped"
    assert state_path.exists()
    assert state_path.with_suffix(".jsonl").exists()


def test_paper_runner_waits_when_live_signal_file_missing(tmp_path):
    config = PaperRunnerConfig(trades_path=tmp_path / "missing-live-signal.csv", state_path=tmp_path / "runner-state.json", submit=True)

    result = run_adaptive_portfolio_paper_once(config=config)

    assert result["status"] == "no_signal"
    assert result["submitted"] is False
    assert result["trades_path"].endswith("missing-live-signal.csv")


def test_paper_runner_records_ticks_when_enabled(tmp_path):
    trades_path = tmp_path / "trades.csv"
    state_path = tmp_path / "runner-state.json"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    broker = IBKRPaperBroker(
            risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    broker.tick_snapshot = lambda spec: {
        "event_type": "ibkr_tick_snapshot",
            "symbol": "MNQ",
        "bid": 18000.0,
        "ask": 18000.25,
        "last": 18000.25,
        "spread": 0.25,
        "order_ready": True,
        "market_data_type": "test",
        "snapshot_time": "now",
    }
    config = PaperRunnerConfig(
        trades_path=trades_path,
        state_path=state_path,
        account="DU123",
        tick_recorder=IBKRTickRecorderConfig(
            output_dir=tmp_path / "ticks",
            enabled=True,
            max_ticks=1,
            interval_seconds=0,
            prefer_tick_by_tick=False,
        ),
    )

    result = run_adaptive_portfolio_paper_once(config=config, broker=broker)

    assert result["status"] == "dry_run"
    assert result["tick_recording"]["status"] == "recorded"
    assert Path(result["tick_recording"]["output"]).exists()


def test_live_signal_row_uses_ibkr_side_price_and_writes_csv(tmp_path):
    broker = IBKRPaperBroker(
        risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    broker.tick_snapshot = lambda spec: {
        "event_type": "ibkr_tick_snapshot",
        "symbol": "MNQ",
        "bid": 18000.0,
        "ask": 18000.25,
        "last": 18000.25,
        "spread": 0.25,
        "order_ready": True,
        "market_data_type": "test",
        "snapshot_time": "now",
    }

    row = build_live_signal_row(
        config=LiveSignalConfig(
            output=tmp_path / "live.csv",
            strategy_id="manual_live_signal",
            selected_alias="manual",
            direction=1,
        ),
        broker=broker,
    )
    output = write_live_signal(row, tmp_path / "live.csv")

    assert row["entry_price"] == 18000.25
    assert row["direction"] == 1
    assert row["portfolio_rule"] == "manual_live_signal"
    assert row["ibkr_bid"] == 18000.0
    assert row["ibkr_ask"] == 18000.25
    assert row["ibkr_spread"] == 0.25
    assert row["ibkr_order_ready"] is True
    csv_row = pd.read_csv(output).iloc[0]
    assert csv_row["entry_price"] == 18000.25
    assert csv_row["ibkr_bid"] == 18000.0
    assert csv_row["ibkr_ask"] == 18000.25


def test_live_signal_row_retries_until_market_snapshot_ready(tmp_path):
    broker = IBKRPaperBroker(
        risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ")),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    snapshots = [
        {"event_type": "ibkr_tick_snapshot", "symbol": "MNQ", "order_ready": False, "bid": None, "ask": None, "last": None},
        {"event_type": "ibkr_tick_snapshot", "symbol": "MNQ", "order_ready": True, "bid": 18000.0, "ask": 18000.25, "last": 18000.0},
    ]
    broker.tick_snapshot = lambda spec: snapshots.pop(0)

    row = build_live_signal_row(
        config=LiveSignalConfig(direction=-1, snapshot_attempts=2, snapshot_retry_seconds=0),
        broker=broker,
    )

    assert row["entry_price"] == 18000.0
    assert row["signal_source"].endswith(":ibkr_bid")


def test_live_paper_trader_refreshes_signal_before_runner(tmp_path, monkeypatch):
    broker = IBKRPaperBroker(
        risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    broker.status_snapshot = lambda symbol: {"current_position": 0, "open_trades": [], "fills": []}
    broker.tick_snapshot = lambda spec: {
        "event_type": "ibkr_tick_snapshot",
        "symbol": "MNQ",
        "bid": 18000.0,
        "ask": 18000.25,
        "last": 18000.25,
        "spread": 0.25,
        "order_ready": True,
        "market_data_type": "test",
        "snapshot_time": "now",
    }

    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(
            live_signal_path=tmp_path / "live.csv",
            state_path=tmp_path / "state.json",
            strategy_id="best",
            selected_alias="best_strategy",
            account="DU123",
        ),
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["submitted"] is False
    assert result["live_signal"]["ibkr_ask"] == 18000.25
    assert pd.read_csv(tmp_path / "live.csv").iloc[0]["ibkr_ask"] == 18000.25


def test_live_paper_trader_blocks_existing_exposure(tmp_path):
    broker = IBKRPaperBroker(
        risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    broker.status_snapshot = lambda symbol: {"current_position": 1, "open_trades": [], "fills": []}
    broker.tick_snapshot = lambda spec: {
        "event_type": "ibkr_tick_snapshot",
        "symbol": "MNQ",
        "bid": 18000.0,
        "ask": 18000.25,
        "last": 18000.25,
        "spread": 0.25,
        "order_ready": True,
    }

    result = run_live_paper_trader_once(
        config=LivePaperTraderConfig(live_signal_path=tmp_path / "live.csv", state_path=tmp_path / "state.json"),
        broker=broker,
    )

    assert result["status"] == "exposure_blocked"
    assert result["live_signal"]["ibkr_order_ready"] is True
    assert pd.read_csv(tmp_path / "live.csv").iloc[0]["ibkr_ask"] == 18000.25


def test_live_paper_trader_daemon_runs_one_iteration(tmp_path):
    broker = IBKRPaperBroker(
            risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    broker.connect = lambda: {"status": "connected", "connected": True}
    broker.status_snapshot = lambda symbol: {"current_position": 0, "open_trades": [], "fills": []}
    broker.tick_snapshot = lambda spec: {
        "event_type": "ibkr_tick_snapshot",
            "symbol": "MNQ",
        "bid": 18000.0,
        "ask": 18000.25,
        "last": 18000.25,
        "spread": 0.25,
        "order_ready": True,
    }

    result = run_live_paper_trader_daemon(
        config=LivePaperTraderDaemonConfig(
            trader=LivePaperTraderConfig(
                live_signal_path=tmp_path / "live.csv",
                state_path=tmp_path / "state.json",
                account="DU123",
            ),
            interval_seconds=0,
            max_iterations=1,
        ),
        broker=broker,
    )

    assert result["status"] == "completed"
    assert result["iterations"] == 1
    assert result["events"][0]["status"] == "dry_run"


def test_live_paper_trader_daemon_uses_fixed_start_cadence(tmp_path, monkeypatch):
    monotonic_values = iter([100.0, 100.0, 100.0, 104.0, 130.0])
    sleeps = []

    monkeypatch.setattr("tradingagents.execution.live_paper_trader.time.monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr("tradingagents.execution.live_paper_trader.time.sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(
        "tradingagents.execution.live_paper_trader.run_live_paper_trader_once",
        lambda *, config, broker, gate: {"status": "dry_run", "submitted": False},
    )

    result = run_live_paper_trader_daemon(
        config=LivePaperTraderDaemonConfig(
            trader=LivePaperTraderConfig(live_signal_path=tmp_path / "live.csv", state_path=tmp_path / "state.json"),
            interval_seconds=30,
            max_iterations=2,
        ),
        broker=IBKRPaperBroker(),
    )

    assert result["iterations"] == 2
    assert sleeps == [26.0]
    assert result["events"][1]["started_at_monotonic"] == 130.0


def test_paper_runner_agent_gate_rejection_blocks_submit(tmp_path):
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": -1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "defensive_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)

    class RejectingGate:
        def review(self, intent, *, trade_date, selected_trade=None):
            return {
                "passed": False,
                "status": "agent_rejected",
                "reasons": ["agent_vetoed_candidate"],
                "intent": intent.normalized().__dict__,
            }

    config = PaperRunnerConfig(
        trades_path=trades_path,
        state_path=tmp_path / "runner-state.json",
        require_agent_gate=True,
    )

    result = run_adaptive_portfolio_paper_once(config=config, gate=RejectingGate())

    assert result["status"] == "agent_gate_rejected"
    assert result["submitted"] is False


def test_paper_runner_blocks_submit_for_stale_signal(tmp_path):
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00+00:00",
                "exit_ts": "2026-05-01 10:33:00+00:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    broker = IBKRPaperBroker(
            risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    config = PaperRunnerConfig(
        trades_path=trades_path,
        state_path=tmp_path / "runner-state.json",
        account="DU123",
        submit=True,
        max_signal_age_minutes=10,
    )

    result = run_adaptive_portfolio_paper_once(config=config, broker=broker)

    assert result["status"] == "stale_signal_blocked"
    assert result["submitted"] is False
    assert result["freshness"]["reason"] == "stale_signal"
    assert not (tmp_path / "ibkr.jsonl").exists()


def test_paper_daemon_runs_one_iteration_with_snapshot(tmp_path, monkeypatch):
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    broker = IBKRPaperBroker(
            risk=IBKRPaperRiskConfig(allowed_accounts=("DU123",), allowed_symbols=("MNQ",)),
        audit_path=tmp_path / "ibkr.jsonl",
    )
    monkeypatch.setattr(broker, "status_snapshot", lambda symbol: {"current_position": 0, "open_trades": [], "fills": []})
    config = PaperDaemonConfig(
        runner=PaperRunnerConfig(trades_path=trades_path, state_path=tmp_path / "state.json", account="DU123"),
        max_iterations=1,
        interval_seconds=0,
        refresh_report=False,
    )

    result = run_adaptive_portfolio_paper_daemon(config=config, broker=broker)

    assert result["status"] == "completed"
    assert result["iterations"] == 1
    assert result["events"][0]["status"] == "dry_run"
    assert result["events"][0]["before"]["current_position"] == 0


def test_adaptive_portfolio_paper_trader_script_outputs_dry_run(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_adaptive_portfolio_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_adaptive_portfolio_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU123")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", "DU123")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_adaptive_portfolio_paper_trader.py",
            "--trades",
            str(trades_path),
            "--state-path",
            str(tmp_path / "state.json"),
            "--account",
            "DU123",
            "--record-ticks",
            "--tick-output-dir",
            str(tmp_path / "ticks"),
            "--max-ticks",
            "1",
            "--tick-interval-seconds",
            "0",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "dry_run"' in output
    assert '"strategy_id": "adaptive_rule"' in output
    assert '"tick_recording"' in output


def test_best_strategy_paper_trader_script_locks_strategy_filters(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_mbp_best_strategy_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_mbp_best_strategy_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    trades_path = tmp_path / "trades.csv"
    best_strategy = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:36:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": best_strategy,
                "selected_alias": "best_strategy",
                "exit_reason": "time",
            },
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:40:00",
                "exit_ts": "2026-05-01 10:46:00",
                "direction": -1,
                "entry_price": 18030.25,
                "portfolio_rule": "other_strategy",
                "selected_alias": "best_strategy",
                "exit_reason": "time",
            },
        ]
    ).to_csv(trades_path, index=False)
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU123")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", "DU123")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_mbp_best_strategy_paper_trader.py",
            "--trades",
            str(trades_path),
            "--state-path",
            str(tmp_path / "state.json"),
            "--account",
            "DU123",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "dry_run"' in output
    assert f'"strategy_id": "{best_strategy}"' in output
    assert '"portfolio_rule": "other_strategy"' not in output


def test_best_strategy_automation_dry_run_executes_without_submit_gate(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "automate_mbp_best_strategy_paper_trading.py"
    spec = importlib.util.spec_from_file_location("automate_mbp_best_strategy_paper_trading", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    trades_path = tmp_path / "trades.csv"
    best_strategy = "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:36:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": best_strategy,
                "selected_alias": "best_strategy",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU123")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", "DU123")
    monkeypatch.setattr(
        "sys.argv",
        [
            "automate_mbp_best_strategy_paper_trading.py",
            "--trades",
            str(trades_path),
            "--state-path",
            str(tmp_path / "state.json"),
            "--account",
            "DU123",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "dry_run"' in output
    assert '"mode": "dry_run"' in output
    assert f'"strategy_id": "{best_strategy}"' in output


def test_best_strategy_automation_blocks_submit_when_supervisor_gate_fails(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "automate_mbp_best_strategy_paper_trading.py"
    spec = importlib.util.spec_from_file_location("automate_mbp_best_strategy_paper_trading", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)

    monkeypatch.setattr(
        script,
        "_ready_preflight",
        lambda **kwargs: {"readiness": {"status": "blocked", "missing_requirements": ["market_data_not_ready"]}},
    )
    monkeypatch.setattr(
        script,
        "summarize_paper_audits",
        lambda **kwargs: {
            "validation_gate": {
                "status": "blocked",
                "blockers": ["paper_outcomes_below_min:0<20"],
                "warnings": [],
                "metrics": {},
                "thresholds": {},
            }
        },
    )
    monkeypatch.setattr(
        script,
        "run_adaptive_portfolio_paper_once",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("runner should not execute when submit gate is blocked")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "automate_mbp_best_strategy_paper_trading.py",
            "--submit",
            "--trades",
            str(tmp_path / "trades.csv"),
        ],
    )

    assert script.main() == 2
    output = capsys.readouterr().out
    assert '"status": "blocked"' in output
    assert "market_data_not_ready" in output
    assert "paper_validation:paper_outcomes_below_min:0<20" in output


def test_adaptive_portfolio_paper_trader_script_daemon_mode(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_adaptive_portfolio_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_adaptive_portfolio_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    trades_path = tmp_path / "trades.csv"
    pd.DataFrame(
        [
            {
                "trade_date": "2026-05-01",
                "entry_ts": "2026-05-01 10:30:00",
                "exit_ts": "2026-05-01 10:33:00",
                "direction": 1,
                "entry_price": 18025.25,
                "portfolio_rule": "adaptive_rule",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
            }
        ]
    ).to_csv(trades_path, index=False)
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ACCOUNT", "DU123")
    monkeypatch.setenv("TRADINGAGENTS_IBKR_ALLOWED_ACCOUNTS", "DU123")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_adaptive_portfolio_paper_trader.py",
            "--daemon",
            "--max-iterations",
            "1",
            "--interval-seconds",
            "0",
            "--no-status-snapshot",
            "--trades",
            str(trades_path),
            "--state-path",
            str(tmp_path / "state.json"),
            "--account",
            "DU123",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "completed"' in output
    assert '"iterations": 1' in output


def test_adaptive_portfolio_paper_trader_script_zero_iterations_means_continuous(tmp_path, monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_adaptive_portfolio_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_adaptive_portfolio_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_daemon(*, config):
        captured["max_iterations"] = config.max_iterations
        return {"status": "completed", "iterations": 0, "events": [], "state_path": str(config.runner.state_path)}

    monkeypatch.setattr(script, "run_adaptive_portfolio_paper_daemon", fake_daemon)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_adaptive_portfolio_paper_trader.py",
            "--daemon",
            "--max-iterations",
            "0",
            "--trades",
            str(tmp_path / "trades.csv"),
            "--state-path",
            str(tmp_path / "state.json"),
        ],
    )

    assert script.main() == 0
    assert captured["max_iterations"] is None


def test_write_ibkr_live_signal_script_writes_file(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "write_ibkr_live_signal.py"
    spec = importlib.util.spec_from_file_location("write_ibkr_live_signal", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    monkeypatch.setattr(
        script,
        "build_live_signal_row",
        lambda *, config: {
            "entry_ts": "2026-05-04T05:00:00+00:00",
            "actual_entry_ts": "2026-05-04T05:00:00+00:00",
            "exit_ts": "2026-05-04T05:04:00+00:00",
            "direction": 1,
            "entry_price": 18000.25,
            "portfolio_rule": config.strategy_id,
            "selected_alias": config.selected_alias,
        },
    )
    output = tmp_path / "live.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "write_ibkr_live_signal.py",
            "--direction",
            "buy",
            "--output",
            str(output),
            "--strategy-id",
            "manual_live_signal",
            "--write",
        ],
    )

    assert script.main() == 0
    assert output.exists()
    assert '"status": "written"' in capsys.readouterr().out


def test_write_ibkr_live_signal_script_derives_best_strategy_from_trades(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "write_ibkr_live_signal.py"
    spec = importlib.util.spec_from_file_location("write_ibkr_live_signal", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_build_live_signal_row(*, config):
        captured["config"] = config
        return {
            "entry_ts": "2026-05-04T05:00:00+00:00",
            "actual_entry_ts": "2026-05-04T05:00:00+00:00",
            "exit_ts": "2026-05-04T05:06:00+00:00",
            "direction": config.direction,
            "entry_price": 18000.25,
            "portfolio_rule": config.strategy_id,
            "selected_alias": config.selected_alias,
        }

    monkeypatch.setattr(script, "build_live_signal_row", fake_build_live_signal_row)
    trades_path = tmp_path / "best-trades.csv"
    pd.DataFrame(
        [
            {
                "entry_ts": "2026-05-01T07:00:00+00:00",
                "exit_ts": "2026-05-01T07:06:00+00:00",
                "trade_date": "2026-05-01",
                "direction": -1,
                "entry_price": 18025.25,
                "portfolio_rule": "adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3",
                "selected_alias": "best_strategy",
                "holding_minutes": 6,
            }
        ]
    ).to_csv(trades_path, index=False)
    output = tmp_path / "live.csv"
    monkeypatch.setattr(
        "sys.argv",
        [
            "write_ibkr_live_signal.py",
            "--from-trades",
            str(trades_path),
            "--selected-alias",
            "best_strategy",
            "--row-index",
            "-1",
            "--output",
            str(output),
            "--write",
        ],
    )

    assert script.main() == 0
    assert output.exists()
    assert captured["config"].direction == -1
    assert captured["config"].max_hold_minutes == 6
    assert captured["config"].selected_alias == "best_strategy"
    assert captured["config"].strategy_id.startswith("adv_wf_best_mean_reversion")
    assert "best-trades.csv" in captured["config"].signal_source
    assert '"selected_trade"' in capsys.readouterr().out


def test_write_ibkr_live_signal_script_reports_blocked_json(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "write_ibkr_live_signal.py"
    spec = importlib.util.spec_from_file_location("write_ibkr_live_signal", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    monkeypatch.setattr(script, "build_live_signal_row", lambda *, config: (_ for _ in ()).throw(ValueError("market snapshot is not order-ready")))
    monkeypatch.setattr(
        "sys.argv",
        [
            "write_ibkr_live_signal.py",
            "--direction",
            "sell",
            "--output",
            str(tmp_path / "live.csv"),
        ],
    )

    assert script.main() == 2
    output = capsys.readouterr().out
    assert '"status": "blocked"' in output
    assert "market snapshot is not order-ready" in output


def test_run_ibkr_live_paper_trader_script_invokes_live_runner(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_ibkr_live_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_ibkr_live_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_run_once(*, config, broker=None):
        captured["config"] = config
        captured["broker"] = broker
        return {"status": "submitted", "submitted": True, "intent": {"intent_id": "intent-1"}}

    monkeypatch.setattr(script, "run_live_paper_trader_once", fake_run_once)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_ibkr_live_paper_trader.py",
            "--live-signal",
            str(tmp_path / "live.csv"),
            "--state-path",
            str(tmp_path / "state.json"),
            "--direction",
            "sell",
            "--account",
            "DU123",
            "--client-id",
            "31",
            "--submit",
            "--agent-gate",
        ],
    )

    assert script.main() == 0
    assert captured["config"].direction == -1
    assert captured["config"].contract.symbol == "MNQ"
    assert captured["config"].tick_recorder.symbol == "MNQ"
    assert captured["config"].submit is True
    assert captured["config"].require_agent_gate is True
    assert '"status": "submitted"' in capsys.readouterr().out


def test_check_paper_automation_status_reports_blockers(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_paper_automation_status.py"
    spec = importlib.util.spec_from_file_location("check_paper_automation_status", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)

    class FakeSession:
        @classmethod
        def from_env(cls):
            return cls()

        def preflight(self):
            return {
                "readiness": {"status": "blocked", "missing_requirements": ["market_data_not_ready"]},
                "connection": {"connected": True},
                "market_data": {"order_ready": False},
            }

    monkeypatch.setattr(script, "IBKRPaperTradingSession", FakeSession)
    monkeypatch.setattr(script, "_daemon_status", lambda pattern: {"running": True, "submit_enabled": True, "pids": ["123"], "submit_pids": ["123"]})
    monkeypatch.setattr(
        script,
        "summarize_paper_audits",
        lambda **kwargs: {"validation_gate": {"status": "blocked", "blockers": ["paper_outcomes_below_min:0<20"]}},
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_paper_automation_status.py",
            "--live-signal",
            str(tmp_path / "missing.csv"),
        ],
    )

    assert script.main() == 2
    output = capsys.readouterr().out
    assert '"status": "blocked"' in output
    assert '"paper_submit_status": "blocked"' in output
    assert "live_signal_missing" in output
    assert "market_data_not_ready" in output


def test_check_paper_automation_status_blocks_dry_run_daemon(tmp_path, monkeypatch, capsys):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_paper_automation_status.py"
    spec = importlib.util.spec_from_file_location("check_paper_automation_status", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)

    live_signal = tmp_path / "live.csv"
    pd.DataFrame(
        [
            {
                "entry_ts": pd.Timestamp.utcnow().isoformat(),
                "actual_entry_ts": pd.Timestamp.utcnow().isoformat(),
                "exit_ts": pd.Timestamp.utcnow().isoformat(),
                "direction": 1,
                "entry_price": 18000.25,
                "portfolio_rule": "best_strategy",
                "selected_alias": "best_strategy",
            }
        ]
    ).to_csv(live_signal, index=False)

    class FakeSession:
        @classmethod
        def from_env(cls):
            return cls()

        def preflight(self):
            return {
                "readiness": {"status": "ready", "missing_requirements": []},
                "connection": {"connected": True},
                "market_data": {"order_ready": True},
            }

    monkeypatch.setattr(script, "IBKRPaperTradingSession", FakeSession)
    monkeypatch.setattr(script, "_daemon_status", lambda pattern: {"running": True, "submit_enabled": False, "pids": ["123"], "dry_run_pids": ["123"]})
    monkeypatch.setattr(script, "summarize_paper_audits", lambda **kwargs: {"validation_gate": {"status": "pass", "blockers": []}})
    monkeypatch.setattr("sys.argv", ["check_paper_automation_status.py", "--live-signal", str(live_signal)])

    assert script.main() == 2
    output = capsys.readouterr().out
    assert '"paper_submit_status": "blocked"' in output
    assert "submit_daemon_not_running" in output
