import json
from pathlib import Path

from tradingagents.execution.agent_gate import (
    AgentGateConfig,
    AgentStrategyGate,
    PaperTradeOutcome,
    analysis_symbol_from_intent,
    build_learning_context,
    build_candidate_trade_context,
    load_strategy_evidence,
    outcome_metrics,
    record_agent_gate_outcome,
)
from tradingagents.execution.ibkr import IBKROrderIntent


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


class FakeGraph:
    def __init__(self, final_decision, signal="Buy"):
        self.final_decision = final_decision
        self.signal = signal
        self.calls = []

    def propagate(self, symbol, trade_date, candidate_trade_context=""):
        self.calls.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "candidate_trade_context": candidate_trade_context,
            }
        )
        return {"final_trade_decision": self.final_decision}, self.signal


def _intent(**overrides):
    values = {
        "action": "BUY",
        "quantity": 1,
        "symbol": "NQ",
        "last_trade_date_or_contract_month": "202606",
        "stop_loss_price": 18000.0,
        "take_profit_price": 18100.0,
        "strategy_id": "adaptive_defensive_mr",
        "reason": "candidate from adaptive portfolio",
    }
    values.update(overrides)
    return IBKROrderIntent(**values)


def test_build_candidate_trade_context_includes_order_and_strategy_fields():
    context = build_candidate_trade_context(
        _intent(),
        {
            "trade_date": "2026-05-01",
            "entry_ts": "2026-05-01 10:30:00",
            "entry_price": 18025.25,
            "portfolio_rule": "adaptive_rule",
            "selected_alias": "stable_mr",
        },
    )

    assert "Candidate action: BUY 1 NQ 202606" in context
    assert "Strategy ID: adaptive_defensive_mr" in context
    assert "selected_alias: stable_mr" in context


def test_build_candidate_trade_context_includes_live_market_and_strategy_evidence():
    context = build_candidate_trade_context(
        _intent(strategy_id="best"),
        {
            "trade_date": "2026-05-04",
            "entry_price": 27898.5,
            "ibkr_bid": 27897.75,
            "ibkr_ask": 27898.5,
            "ibkr_last": 27898.25,
            "ibkr_spread": 0.75,
            "ibkr_order_ready": True,
        },
        strategy_evidence={
            "name": "best",
            "full_trades": "942",
            "full_net_points": "3318.0",
            "full_profit_factor": "1.6891",
            "full_stability": "0.8476",
            "positive_window_rate": "1.0",
            "live_ready": "True",
        },
    )

    assert "Current IBKR top-of-book evidence" in context
    assert "bid=27897.75" in context
    assert "order_ready=True" in context
    assert "Historical strategy evidence" in context
    assert "full_trades=942" in context
    assert "full_profit_factor=1.6891" in context


def test_analysis_symbol_from_ibkr_future_contract_month():
    assert analysis_symbol_from_intent(_intent(symbol="NQ", last_trade_date_or_contract_month="202606")) == "NQM6"
    assert analysis_symbol_from_intent(_intent(symbol="MNQ", last_trade_date_or_contract_month="202609")) == "MNQU6"


def test_agent_gate_approves_direction_aligned_candidate(tmp_path):
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Candidate allowed.")
    gate = AgentStrategyGate(
        AgentGateConfig(enabled=True, audit_path=tmp_path / "gate.jsonl"),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(), trade_date="2026-05-01", selected_trade={"entry_price": 18025.25})

    assert result["passed"]
    assert result["status"] == "agent_approved"
    assert result["rating"] == "Buy"
    assert fake_graph.calls[0]["symbol"] == "NQM6"
    assert fake_graph.calls[0]["candidate_trade_context"]
    assert (tmp_path / "gate.jsonl").exists()


def test_learning_context_summarizes_gate_and_ibkr_audits(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    _write_jsonl(
        agent_audit,
        [
            {"intent": {"strategy_id": "other"}, "passed": False, "reasons": ["agent_vetoed_candidate"]},
            {"intent": {"strategy_id": "adaptive_defensive_mr"}, "passed": True, "reasons": []},
            {"intent": {"strategy_id": "adaptive_defensive_mr"}, "passed": False, "reasons": ["agent_rating_not_aligned_with_buy"]},
        ],
    )
    _write_jsonl(
        ibkr_audit,
        [
            {"event_type": "ibkr_paper_preflight", "readiness": {"missing_requirements": ["market_data_not_ready"]}},
            {"status": "preflight_blocked", "readiness": {"missing_requirements": ["spread_too_wide"]}},
        ],
    )

    context = build_learning_context(
        strategy_id="adaptive_defensive_mr",
        agent_audit_path=agent_audit,
        ibkr_audit_path=ibkr_audit,
        lookback_events=10,
    )

    assert "1 approved, 1 rejected" in context
    assert "agent_rating_not_aligned_with_buy=1" in context
    assert "market_data_not_ready=1" in context
    assert "Historical IBKR preflight blockers" in context
    assert "preflight_blocked=1" in context


def test_learning_context_highlights_latest_preflight_ready(tmp_path):
    ibkr_audit = tmp_path / "ibkr.jsonl"
    _write_jsonl(
        ibkr_audit,
        [
            {"event_type": "ibkr_paper_preflight", "readiness": {"status": "blocked", "missing_requirements": ["not_connected"]}},
            {
                "event_type": "ibkr_paper_preflight",
                "readiness": {"status": "ready", "missing_requirements": []},
                "market_data": {"bid": 27897.75, "ask": 27898.5, "last": 27898.25, "spread": 0.75, "order_ready": True},
            },
        ],
    )

    context = build_learning_context(
        strategy_id="adaptive_defensive_mr",
        agent_audit_path=tmp_path / "agent.jsonl",
        ibkr_audit_path=ibkr_audit,
        lookback_events=10,
    )

    assert "Latest IBKR preflight: status=ready" in context
    assert "bid=27897.75" in context
    assert "Historical IBKR preflight blockers" in context
    assert "not_connected=1" in context


def test_load_strategy_evidence_finds_matching_strategy(tmp_path):
    ranking = tmp_path / "ranking.csv"
    ranking.write_text(
        "name,full_trades,full_net_points,full_profit_factor,live_ready\n"
        "other,1,2,3,False\n"
        "best,942,3318.0,1.6891,True\n",
        encoding="utf-8",
    )

    evidence = load_strategy_evidence("best", ranking)

    assert evidence is not None
    assert evidence["full_trades"] == "942"
    assert evidence["live_ready"] == "True"


def test_record_agent_gate_outcome_computes_points_and_updates_learning_context(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    event = record_agent_gate_outcome(
        PaperTradeOutcome(
            strategy_id="adaptive_defensive_mr",
            intent_id="intent-1",
            action="BUY",
            entry_price=18000.0,
            exit_price=18012.5,
            exit_reason="take_profit",
        ),
        audit_path=agent_audit,
    )
    record_agent_gate_outcome(
        PaperTradeOutcome(
            strategy_id="adaptive_defensive_mr",
            intent_id="intent-2",
            action="SELL",
            entry_price=18000.0,
            exit_price=18005.0,
            exit_reason="stop_loss",
        ),
        audit_path=agent_audit,
    )

    context = build_learning_context(
        strategy_id="adaptive_defensive_mr",
        agent_audit_path=agent_audit,
        ibkr_audit_path=tmp_path / "ibkr.jsonl",
        lookback_events=20,
    )

    assert event["points"] == 12.5
    assert "trades=2" in context
    assert "wins=1" in context
    assert "losses=1" in context
    assert "net_points=7.50" in context


def test_record_agent_gate_outcome_respects_explicit_points(tmp_path):
    event = record_agent_gate_outcome(
        PaperTradeOutcome(
            strategy_id="adaptive_defensive_mr",
            action="BUY",
            entry_price=18000.0,
            exit_price=17990.0,
            points=3.25,
        ),
        audit_path=tmp_path / "agent.jsonl",
    )

    assert event["points"] == 3.25


def test_outcome_metrics_tracks_trailing_losses():
    metrics = outcome_metrics(
        [
            {"points": 10},
            {"points": -2},
            {"points": 1},
            {"points": -3},
            {"points": -4},
        ]
    )

    assert metrics["trades"] == 5
    assert metrics["wins"] == 2
    assert metrics["losses"] == 3
    assert metrics["net_points"] == 2
    assert metrics["consecutive_losses"] == 2


def test_performance_guard_does_not_block_before_min_trades(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    for index in range(2):
        record_agent_gate_outcome(
            PaperTradeOutcome(strategy_id="adaptive_defensive_mr", action="BUY", points=-20 - index),
            audit_path=agent_audit,
        )
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Candidate allowed.")
    gate = AgentStrategyGate(
        AgentGateConfig(
            enabled=True,
            audit_path=agent_audit,
            performance_min_trades=3,
            performance_min_net_points=-1,
            performance_min_win_rate=80,
        ),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(), trade_date="2026-05-01")

    assert result["passed"]
    assert result["performance_guard"]["metrics"]["trades"] == 2


def test_performance_guard_rejects_degraded_paper_strategy(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    for points in [-8, -7, -6, -5]:
        record_agent_gate_outcome(
            PaperTradeOutcome(strategy_id="adaptive_defensive_mr", action="BUY", points=points),
            audit_path=agent_audit,
        )
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Candidate allowed.")
    gate = AgentStrategyGate(
        AgentGateConfig(
            enabled=True,
            audit_path=agent_audit,
            performance_min_trades=3,
            performance_recent_trades=4,
            performance_min_net_points=-10,
            performance_min_win_rate=35,
            performance_max_consecutive_losses=3,
        ),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(), trade_date="2026-05-01")

    assert not result["passed"]
    assert result["status"] == "agent_rejected"
    assert "paper_win_rate_below_guard" in result["reasons"]
    assert "paper_net_points_below_guard" in result["reasons"]
    assert "paper_consecutive_losses_guard" in result["reasons"]
    assert result["performance_guard"]["metrics"]["consecutive_losses"] == 4


def test_record_agent_gate_paper_outcome_script(tmp_path, monkeypatch, capsys):
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "record_agent_gate_paper_outcome.py"
    spec = importlib.util.spec_from_file_location("record_agent_gate_paper_outcome", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    audit_path = tmp_path / "agent.jsonl"
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_agent_gate_paper_outcome.py",
            "--strategy-id",
            "adaptive_defensive_mr",
            "--action",
            "BUY",
            "--entry-price",
            "18000",
            "--exit-price",
            "18010",
            "--audit-path",
            str(audit_path),
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"event_type": "agent_gate_paper_outcome"' in output
    assert '"points": 10.0' in output
    assert audit_path.exists()


def test_diagnose_agent_gate_veto_script_reports_primary_causes(tmp_path, monkeypatch, capsys):
    import importlib.util

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_agent_gate_veto.py"
    spec = importlib.util.spec_from_file_location("diagnose_agent_gate_veto", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    audit_path = tmp_path / "agent.jsonl"
    _write_jsonl(
        audit_path,
        [
            {
                "event_type": "agent_strategy_gate",
                "status": "agent_rejected",
                "passed": False,
                "rating": "Hold",
                "analysis_symbol": "NQM6",
                "intent": {"action": "BUY", "strategy_id": "strategy-1"},
                "reasons": ["agent_vetoed_candidate", "agent_rating_not_aligned_with_buy"],
                "candidate_trade_context": "Recent IBKR preflight blockers: market_data_not_ready=3.",
                "final_trade_decision": "Rating: Hold\nVetoed because evidence is too thin and execution risk is elevated.",
            }
        ],
    )
    monkeypatch.setattr("sys.argv", ["diagnose_agent_gate_veto.py", "--audit", str(audit_path)])

    assert script.main() == 2
    output = capsys.readouterr().out
    assert "explicit_veto" in output
    assert "rating_direction_mismatch" in output
    assert "execution_risk_context" in output
    assert "thin_market_evidence" in output


def test_agent_gate_injects_learning_context_into_candidate_review(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    _write_jsonl(
        agent_audit,
        [
            {"intent": {"strategy_id": "adaptive_defensive_mr"}, "passed": False, "reasons": ["agent_vetoed_candidate"]},
        ],
    )
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Candidate allowed.")
    gate = AgentStrategyGate(
        AgentGateConfig(
            enabled=True,
            audit_path=agent_audit,
            ibkr_audit_path=tmp_path / "ibkr.jsonl",
            learning_context_enabled=True,
        ),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(), trade_date="2026-05-01")

    context = fake_graph.calls[0]["candidate_trade_context"]
    assert result["passed"]
    assert "Historical gate and paper-trading lessons" in context
    assert "agent_vetoed_candidate=1" in context
    assert "Use this context as a robustness prior only" in context


def test_agent_gate_injects_strategy_evidence_into_candidate_review(tmp_path):
    ranking = tmp_path / "ranking.csv"
    ranking.write_text(
        "name,full_trades,full_net_points,full_profit_factor,full_stability,positive_window_rate,live_ready\n"
        "adaptive_defensive_mr,942,3318.0,1.6891,0.8476,1.0,True\n",
        encoding="utf-8",
    )
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Candidate allowed.")
    gate = AgentStrategyGate(
        AgentGateConfig(
            enabled=True,
            audit_path=tmp_path / "agent.jsonl",
            ibkr_audit_path=tmp_path / "ibkr.jsonl",
            strategy_evidence_path=ranking,
        ),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(), trade_date="2026-05-04")

    assert result["passed"]
    context = fake_graph.calls[0]["candidate_trade_context"]
    assert "Historical strategy evidence" in context
    assert "full_net_points=3318.0" in context
    assert "positive_window_rate=1.0" in context


def test_agent_gate_rejects_direction_mismatch(tmp_path):
    fake_graph = FakeGraph("**Rating**: Sell\n\n**Executive Summary**: Direction conflicts.", signal="Sell")
    gate = AgentStrategyGate(
        AgentGateConfig(enabled=True, audit_path=tmp_path / "gate.jsonl"),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(action="BUY"), trade_date="2026-05-01")

    assert not result["passed"]
    assert "agent_rating_not_aligned_with_buy" in result["reasons"]


def test_agent_gate_rejects_explicit_veto(tmp_path):
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Veto this candidate due to execution risk.")
    gate = AgentStrategyGate(
        AgentGateConfig(enabled=True, audit_path=tmp_path / "gate.jsonl"),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(action="BUY"), trade_date="2026-05-01")

    assert not result["passed"]
    assert "agent_vetoed_candidate" in result["reasons"]


def test_agent_gate_deterministic_mode_is_not_allowed_to_approve(tmp_path):
    fake_graph = FakeGraph("**Rating**: Buy\n\n**Executive Summary**: Deterministic hold.")
    gate = AgentStrategyGate(
        AgentGateConfig(enabled=True, deterministic_decision_mode=True, audit_path=tmp_path / "gate.jsonl"),
        graph_factory=lambda analysts, config: fake_graph,
    )

    result = gate.review(_intent(action="BUY"), trade_date="2026-05-01")

    assert not result["passed"]
    assert "agent_gate_deterministic_mode" in result["reasons"]
