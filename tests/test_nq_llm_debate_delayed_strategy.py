from __future__ import annotations

import importlib.util
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from tradingagents.execution import (
    DebateDelayedStrategyConfig,
    DebateExecutionPlan,
    FeatureScannerConfig,
    FeatureTrigger,
    IBKRConnectionConfig,
    IBKRContractSpec,
    RealtimeDebateTraderConfig,
    StaticDebatePlanner,
    build_intent_from_route,
    load_tradeable_feature_sets,
    route_plan,
    run_debate_delayed_scanner_once,
    run_realtime_debate_trader,
    run_debate_delayed_strategy_once,
    scan_feature_trigger_once,
)


def test_load_tradeable_feature_sets_requires_win_rate_above_53_percent_and_payoff_above_1r(tmp_path):
    path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {"feature_set": "exact_53_rejected", "test_win_rate": 0.53, "test_payoff_ratio_r": 1.2, "test_net_points": 10},
            {"feature_set": "low_payoff_rejected", "test_win_rate": 0.54, "test_payoff_ratio_r": 1.0, "test_net_points": 10},
            {"feature_set": "negative_net_rejected", "test_win_rate": 0.56, "test_payoff_ratio_r": 1.2, "test_net_points": -1},
            {"feature_set": "qualified", "test_win_rate": 0.531, "test_payoff_ratio_r": 1.01, "test_net_points": 1},
        ]
    ).to_csv(path, index=False)

    selected = load_tradeable_feature_sets(path)

    assert selected["feature_set"].tolist() == ["qualified"]
    assert selected.iloc[0]["win_rate"] > 0.53
    assert selected.iloc[0]["payoff_ratio_r"] > 1.0


def test_route_plan_maps_recheck_price_to_conditional_action():
    plan = DebateExecutionPlan(
        decision_id="decision-1",
        feature_set="flush_hold",
        stance="conditional",
        recheck_after_seconds=120,
        long_trigger=100.0,
        short_trigger=90.0,
        no_trade_low=90.0,
        no_trade_high=100.0,
        max_chase_points=6.0,
    )

    assert route_plan(plan, 101.0)["action"] == "BUY"
    assert route_plan(plan, 89.0)["action"] == "SELL"
    assert route_plan(plan, 95.0)["reason"] == "price_inside_no_trade_zone"
    assert route_plan(plan, 107.0)["reason"] == "long_chase_exceeded"
    assert route_plan(plan, 83.0)["reason"] == "short_chase_exceeded"


def test_build_intent_from_route_creates_bracketed_buy_and_sell_orders():
    trigger = FeatureTrigger(
        feature_set="flush_hold",
        candidate="bar_best",
        direction="long",
        trigger_price=25000.0,
        trigger_time="2026-05-06T00:00:00+00:00",
        win_rate=0.55,
        payoff_ratio_r=1.2,
    )
    plan = DebateExecutionPlan(
        decision_id="decision-1",
        feature_set="flush_hold",
        stance="conditional",
        recheck_after_seconds=120,
        long_stop=24984.0,
        long_target=25024.0,
        short_stop=25016.0,
        short_target=24976.0,
    )
    contract = IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606")

    buy = build_intent_from_route(trigger, plan, {"action": "BUY"}, 25002.0, contract=contract, account="DU123", quantity=1)
    sell = build_intent_from_route(trigger, plan, {"action": "SELL"}, 24998.0, contract=contract, account="DU123", quantity=1)

    assert buy.action == "BUY"
    assert buy.stop_loss_price == 24984.0
    assert buy.take_profit_price == 25024.0
    assert buy.strategy_id == "nq_llm_debate_delayed"
    assert sell.action == "SELL"
    assert sell.stop_loss_price == 25016.0
    assert sell.take_profit_price == 24976.0
    assert sell.account == "DU123"


class FakeBroker:
    def __init__(self, snapshots):
        self.connection = IBKRConnectionConfig(port=7497, account="DU123")
        self.snapshots = list(snapshots)
        self.submitted = []

    def tick_snapshot(self, spec):
        return self.snapshots.pop(0)

    def status_snapshot(self, symbol):
        return {"positions": [], "current_position": 0, "open_trades": [], "fills": []}

    def connect(self):
        return {"status": "connected", "connected": True}

    def account_summary(self):
        return {"account": "DU123", "account_type": "paper", "paper": True}

    def contract_details(self, spec):
        return {
            "symbol": spec.symbol,
            "exchange": spec.exchange,
            "currency": spec.currency,
            "tick_size": spec.expected_tick_size,
            "point_value": spec.expected_point_value,
        }

    def market_snapshot(self, spec):
        snapshot = self.tick_snapshot(spec)
        from tradingagents.execution.ibkr import IBKRMarketSnapshot

        return IBKRMarketSnapshot(
            symbol=spec.symbol,
            bid=snapshot.get("bid"),
            ask=snapshot.get("ask"),
            last=snapshot.get("last"),
            market_data_type=str(snapshot.get("market_data_type", "1")),
            snapshot_time=str(snapshot.get("snapshot_time", "")),
        )

    def submit(self, intent, *, dry_run=True, current_position=0):
        self.submitted.append(intent)
        return {
            "status": "dry_run" if dry_run else "submitted",
            "submitted": not dry_run,
            "dry_run": dry_run,
            "intent": asdict(intent),
            "orders": [],
            "trades": [],
        }

    def _audit(self, event):
        pass


def _scanner_feature_sets() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "feature_set": "support_reclaim + entry_candle_up",
                "candidate": "bar_best_support_reclaim_lb60_thr0.0002_hold30_long_us_late",
                "filter": "entry_candle_up",
                "direction": "long",
                "win_rate": 0.63,
                "payoff_ratio_r": 1.08,
                "net_points": 160.0,
                "future_pass": True,
                "selected_folds": 1,
            }
        ]
    )


def test_scan_feature_trigger_once_detects_support_reclaim_feature(tmp_path):
    history_path = tmp_path / "scanner-history.jsonl"
    state_path = tmp_path / "scanner-state.json"
    snapshots = [
        {"last": 100.0, "bid": 99.75, "ask": 100.25, "order_ready": True},
        {"last": 98.0, "bid": 97.75, "ask": 98.25, "order_ready": True},
        {"last": 97.0, "bid": 96.75, "ask": 97.25, "order_ready": True},
        {"last": 96.0, "bid": 95.75, "ask": 96.25, "order_ready": True},
        {"last": 96.5, "bid": 96.25, "ask": 96.75, "order_ready": True},
        {"last": 96.75, "bid": 96.5, "ask": 97.0, "order_ready": True},
        {"last": 98.0, "bid": 97.75, "ask": 98.25, "order_ready": True},
    ]
    broker = FakeBroker(snapshots)
    strategy_config = DebateDelayedStrategyConfig(
        audit_path=tmp_path / "audit.jsonl",
        contract=IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606"),
        snapshot_attempts=1,
    )
    scanner_config = FeatureScannerConfig(
        history_path=history_path,
        state_path=state_path,
        min_history_points=7,
        support_reclaim_points=1.0,
    )
    result = {}
    for _ in range(7):
        result = scan_feature_trigger_once(
            _scanner_feature_sets(),
            scanner_config=scanner_config,
            strategy_config=strategy_config,
            broker=broker,
        )

    assert result["status"] == "triggered"
    assert result["trigger"].direction == "long"
    assert result["trigger"].feature_set == "support_reclaim + entry_candle_up"
    assert result["evaluation"]["reason"].startswith("support_reclaim")
    assert state_path.exists()


def test_run_debate_delayed_scanner_once_executes_after_scanner_trigger(tmp_path):
    snapshots = [
        {"last": 100.0, "bid": 99.75, "ask": 100.25, "order_ready": True},
        {"last": 98.0, "bid": 97.75, "ask": 98.25, "order_ready": True},
        {"last": 97.0, "bid": 96.75, "ask": 97.25, "order_ready": True},
        {"last": 96.0, "bid": 95.75, "ask": 96.25, "order_ready": True},
        {"last": 96.5, "bid": 96.25, "ask": 96.75, "order_ready": True},
        {"last": 96.75, "bid": 96.5, "ask": 97.0, "order_ready": True},
        {"last": 98.0, "bid": 97.75, "ask": 98.25, "order_ready": True},
        {"last": 98.25, "bid": 98.0, "ask": 98.5, "order_ready": True},
        {"last": 100.5, "bid": 100.25, "ask": 100.75, "order_ready": True},
    ]
    broker = FakeBroker(snapshots)
    plan = DebateExecutionPlan(
        decision_id="decision-1",
        feature_set="support_reclaim + entry_candle_up",
        stance="conditional",
        recheck_after_seconds=120,
        long_trigger=100.0,
        long_stop=84.0,
        long_target=124.0,
    )
    strategy_config = DebateDelayedStrategyConfig(
        audit_path=tmp_path / "audit.jsonl",
        state_path=tmp_path / "strategy-state.json",
        contract=IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606"),
        submit=False,
        skip_preflight=True,
        enforce_delay=False,
        snapshot_attempts=1,
        max_signal_age_seconds=999999,
    )
    scanner_config = FeatureScannerConfig(
        history_path=tmp_path / "scanner-history.jsonl",
        state_path=tmp_path / "scanner-state.json",
        min_history_points=7,
        support_reclaim_points=1.0,
    )
    result = {}
    for _ in range(6):
        result = run_debate_delayed_scanner_once(
            feature_sets=_scanner_feature_sets(),
            planner=StaticDebatePlanner(plan),
            strategy_config=strategy_config,
            scanner_config=scanner_config,
            broker=broker,
        )
        assert result["status"] == "no_feature_trigger"
    result = run_debate_delayed_scanner_once(
        feature_sets=_scanner_feature_sets(),
        planner=StaticDebatePlanner(plan),
        strategy_config=strategy_config,
        scanner_config=scanner_config,
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["route"]["action"] == "BUY"
    assert broker.submitted[0].strategy_id == "nq_llm_debate_delayed"


def test_run_realtime_debate_trader_blocks_when_preflight_not_ready(tmp_path):
    broker = FakeBroker([])
    broker.connect = lambda: {"status": "blocked", "connected": False, "reason": "socket_not_listening"}
    result = run_realtime_debate_trader(
        feature_sets=_scanner_feature_sets(),
        planner=StaticDebatePlanner(
            DebateExecutionPlan(
                decision_id="decision-1",
                feature_set="support_reclaim + entry_candle_up",
                stance="conditional",
                recheck_after_seconds=120,
            )
        ),
        config=RealtimeDebateTraderConfig(
            strategy=DebateDelayedStrategyConfig(
                audit_path=tmp_path / "audit.jsonl",
                contract=IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606"),
            ),
            scanner=FeatureScannerConfig(history_path=tmp_path / "history.jsonl", state_path=tmp_path / "scanner-state.json"),
            preflight_attempts=1,
            status_path=tmp_path / "status.json",
        ),
        broker=broker,
    )

    assert result["status"] == "preflight_blocked"
    assert result["submitted"] is False
    assert (tmp_path / "status.json").exists()


def test_run_debate_delayed_strategy_once_dry_runs_after_delay_recheck(tmp_path):
    trigger = FeatureTrigger(
        feature_set="flush_hold",
        candidate="bar_best",
        direction="long",
        trigger_price=25000.0,
        trigger_time="2026-05-06T00:00:00+00:00",
        win_rate=0.55,
        payoff_ratio_r=1.2,
    )
    plan = DebateExecutionPlan(
        decision_id="decision-1",
        feature_set="flush_hold",
        stance="conditional",
        recheck_after_seconds=120,
        long_trigger=25001.0,
        short_trigger=24990.0,
        no_trade_low=24990.0,
        no_trade_high=25001.0,
        long_stop=24984.0,
        long_target=25024.0,
    )
    broker = FakeBroker(
        [
            {"last": 25000.0, "bid": 24999.75, "ask": 25000.25, "order_ready": True},
            {"last": 25002.0, "bid": 25001.75, "ask": 25002.25, "order_ready": True},
        ]
    )
    config = DebateDelayedStrategyConfig(
        audit_path=tmp_path / "audit.jsonl",
        state_path=tmp_path / "state.json",
        contract=IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606"),
        submit=False,
        skip_preflight=True,
        enforce_delay=False,
        snapshot_attempts=1,
        max_signal_age_seconds=999999,
    )

    result = run_debate_delayed_strategy_once(
        trigger=trigger,
        planner=StaticDebatePlanner(plan),
        config=config,
        broker=broker,
    )

    assert result["status"] == "dry_run"
    assert result["route"]["action"] == "BUY"
    assert result["recheck_price"] == 25002.0
    assert broker.submitted[0].action == "BUY"
    assert (tmp_path / "state.json").exists()
    assert "nq_llm_debate_delayed_strategy" in (tmp_path / "audit.jsonl").read_text()


def test_run_debate_delayed_strategy_once_skips_duplicate_trigger(tmp_path):
    trigger = FeatureTrigger(
        feature_set="flush_hold",
        candidate="bar_best",
        direction="long",
        trigger_price=25000.0,
        trigger_time="2026-05-06T00:00:00+00:00",
        win_rate=0.55,
        payoff_ratio_r=1.2,
    )
    plan = DebateExecutionPlan(
        decision_id="decision-1",
        feature_set="flush_hold",
        stance="conditional",
        recheck_after_seconds=120,
        long_trigger=25001.0,
        long_stop=24984.0,
        long_target=25024.0,
    )
    config = DebateDelayedStrategyConfig(
        audit_path=tmp_path / "audit.jsonl",
        state_path=tmp_path / "state.json",
        contract=IBKRContractSpec(symbol="MNQ", last_trade_date_or_contract_month="202606"),
        submit=False,
        skip_preflight=True,
        enforce_delay=False,
        snapshot_attempts=1,
        max_signal_age_seconds=999999,
    )
    first_broker = FakeBroker(
        [
            {"last": 25000.0, "bid": 24999.75, "ask": 25000.25, "order_ready": True},
            {"last": 25002.0, "bid": 25001.75, "ask": 25002.25, "order_ready": True},
        ]
    )
    first = run_debate_delayed_strategy_once(
        trigger=trigger,
        planner=StaticDebatePlanner(plan),
        config=config,
        broker=first_broker,
    )
    second_broker = FakeBroker(
        [
            {"last": 25000.0, "bid": 24999.75, "ask": 25000.25, "order_ready": True},
            {"last": 25002.0, "bid": 25001.75, "ask": 25002.25, "order_ready": True},
        ]
    )
    second = run_debate_delayed_strategy_once(
        trigger=trigger,
        planner=StaticDebatePlanner(plan),
        config=config,
        broker=second_broker,
    )

    assert first["status"] == "dry_run"
    assert second["status"] == "duplicate_skipped"
    assert second_broker.submitted == []


def test_run_nq_llm_debate_paper_trader_script_wires_arguments(tmp_path, monkeypatch, capsys):
    feature_path = tmp_path / "features.csv"
    pd.DataFrame(
        [
            {
                "feature_set": "qualified",
                "candidate": "bar_best",
                "direction": "long",
                "test_win_rate": 0.54,
                "test_payoff_ratio_r": 1.1,
                "test_net_points": 10,
            }
        ]
    ).to_csv(feature_path, index=False)
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_nq_llm_debate_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_nq_llm_debate_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_run_once(*, trigger, planner, config, broker=None):
        captured["trigger"] = trigger
        captured["config"] = config
        captured["broker"] = broker
        return {"status": "dry_run", "submitted": False, "feature_set": trigger.feature_set}

    monkeypatch.setattr(script, "run_debate_delayed_strategy_once", fake_run_once)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_nq_llm_debate_paper_trader.py",
            "--feature-sets",
            str(feature_path),
            "--feature-set",
            "qualified",
            "--trigger-price",
            "25000",
            "--trigger-time",
            "2026-05-06T00:00:00+00:00",
            "--account",
            "DU123",
            "--quantity",
            "1",
            "--submit",
            "--skip-preflight",
            "--no-enforce-delay",
        ],
    )

    assert script.main() == 0
    assert captured["trigger"].feature_set == "qualified"
    assert captured["trigger"].win_rate > 0.53
    assert captured["config"].submit is True
    assert captured["config"].skip_preflight is True
    assert captured["config"].enforce_delay is False
    assert '"status": "dry_run"' in capsys.readouterr().out


def test_run_nq_llm_debate_paper_trader_script_wires_scan_mode(tmp_path, monkeypatch, capsys):
    feature_path = tmp_path / "features.csv"
    _scanner_feature_sets().to_csv(feature_path, index=False)
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_nq_llm_debate_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_nq_llm_debate_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_scan_once(*, feature_sets, planner, strategy_config, scanner_config, broker=None):
        captured["feature_sets"] = feature_sets
        captured["strategy_config"] = strategy_config
        captured["scanner_config"] = scanner_config
        return {"status": "no_feature_trigger", "reason": "no_scanner_rule_matched"}

    monkeypatch.setattr(script, "run_debate_delayed_scanner_once", fake_scan_once)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_nq_llm_debate_paper_trader.py",
            "--scan",
            "--feature-sets",
            str(feature_path),
            "--feature-set",
            "support_reclaim + entry_candle_up",
            "--scanner-history",
            str(tmp_path / "history.jsonl"),
            "--scanner-state",
            str(tmp_path / "scanner-state.json"),
            "--no-enforce-delay",
        ],
    )

    assert script.main() == 0
    assert captured["feature_sets"].iloc[0]["win_rate"] > 0.53
    assert captured["scanner_config"].feature_set == "support_reclaim + entry_candle_up"
    assert captured["strategy_config"].enforce_delay is False
    assert '"status": "no_feature_trigger"' in capsys.readouterr().out


def test_run_nq_llm_debate_paper_trader_script_wires_realtime_mode(tmp_path, monkeypatch, capsys):
    feature_path = tmp_path / "features.csv"
    _scanner_feature_sets().to_csv(feature_path, index=False)
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_nq_llm_debate_paper_trader.py"
    spec = importlib.util.spec_from_file_location("run_nq_llm_debate_paper_trader", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    captured = {}

    def fake_realtime(*, feature_sets, planner, config, broker=None):
        captured["feature_sets"] = feature_sets
        captured["config"] = config
        captured["broker"] = broker
        return {"status": "completed", "iterations": 1, "events": []}

    monkeypatch.setattr(script, "run_realtime_debate_trader", fake_realtime)
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_nq_llm_debate_paper_trader.py",
            "--realtime",
            "--feature-sets",
            str(feature_path),
            "--status-path",
            str(tmp_path / "status.json"),
            "--max-iterations",
            "1",
            "--no-enforce-delay",
        ],
    )

    assert script.main() == 0
    assert captured["config"].max_iterations == 1
    assert captured["config"].require_preflight_ready is True
    assert captured["config"].status_path == tmp_path / "status.json"
    assert captured["config"].strategy.enforce_delay is False
    assert '"status": "completed"' in capsys.readouterr().out
