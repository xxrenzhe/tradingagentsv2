from __future__ import annotations

import importlib.util
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from tradingagents.execution import (
    DebateDelayedStrategyConfig,
    DebateExecutionPlan,
    FeatureTrigger,
    IBKRContractSpec,
    StaticDebatePlanner,
    build_intent_from_route,
    load_tradeable_feature_sets,
    route_plan,
    run_debate_delayed_strategy_once,
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
    connection = None

    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.submitted = []

    def tick_snapshot(self, spec):
        return self.snapshots.pop(0)

    def status_snapshot(self, symbol):
        return {"positions": [], "current_position": 0, "open_trades": [], "fills": []}

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
