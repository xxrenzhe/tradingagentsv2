import importlib.util
import json
from pathlib import Path

import pandas as pd

from tradingagents.execution.agent_gate import AgentGateConfig
from tradingagents.execution.paper_report import PaperValidationGateConfig, evaluate_paper_validation_gate, summarize_paper_audits
from tradingagents.execution.walk_forward import WalkForwardConfig, walk_forward_gate_replay


def _trade_rows(days=8):
    rows = []
    for day in range(days):
        for trade_index, points in enumerate([10.0, -4.0]):
            rows.append(
                {
                    "entry_ts": f"2026-05-{day + 1:02d} 10:{trade_index:02d}:00+00:00",
                    "exit_ts": f"2026-05-{day + 1:02d} 10:{trade_index + 1:02d}:00+00:00",
                    "trade_date": f"2026-05-{day + 1:02d}",
                    "direction": 1,
                    "entry_price": 18000.0,
                    "exit_price": 18000.0 + points,
                    "net_points": points,
                    "portfolio_rule": "adaptive_defensive_mr",
                    "selected_alias": "stable_mr",
                    "exit_reason": "time",
                    "entry_index": day * 2 + trade_index,
                }
            )
    return pd.DataFrame(rows)


def _load_script(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_walk_forward_gate_replay_outputs_folds(tmp_path):
    decisions, summary = walk_forward_gate_replay(
        _trade_rows(8),
        config=WalkForwardConfig(train_days=3, test_days=2, step_days=2, audit_dir=tmp_path / "wf"),
        gate_config=AgentGateConfig(performance_min_trades=3),
    )

    assert not decisions.empty
    assert len(summary) == 3
    assert {"raw_net_points", "gate_net_points", "drawdown_delta_points"}.issubset(summary.columns)


def test_walk_forward_script_outputs_files(tmp_path, monkeypatch, capsys):
    trades_path = tmp_path / "trades.csv"
    decisions_path = tmp_path / "decisions.csv"
    summary_path = tmp_path / "summary.csv"
    _trade_rows(6).to_csv(trades_path, index=False)
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "walk_forward_agent_gate_on_mbp_trades.py"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "walk_forward_agent_gate_on_mbp_trades.py",
            "--trades",
            str(trades_path),
            "--train-days",
            "2",
            "--test-days",
            "2",
            "--step-days",
            "2",
            "--decisions-output",
            str(decisions_path),
            "--summary-output",
            str(summary_path),
            "--audit-dir",
            str(tmp_path / "wf"),
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"folds"' in output
    assert decisions_path.exists()
    assert summary_path.exists()


def test_summarize_paper_audits(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text(
        "\n".join(
            [
                json.dumps({"event_type": "agent_strategy_gate", "passed": True, "reasons": []}),
                json.dumps({"event_type": "agent_strategy_gate", "passed": False, "reasons": ["agent_vetoed_candidate"]}),
                json.dumps({"event_type": "agent_gate_paper_outcome", "points": 5.0}),
                json.dumps({"event_type": "agent_gate_paper_outcome", "points": -2.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ibkr_audit.write_text(
        "\n".join(
            [
                json.dumps({"event_type": "ibkr_paper_preflight", "readiness": {"status": "ready", "missing_requirements": []}}),
                json.dumps({"event_type": "ibkr_paper_preflight", "readiness": {"status": "blocked", "missing_requirements": ["market_data_not_ready"]}}),
                json.dumps({"status": "submitted"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_paper_audits(agent_audit_path=agent_audit, ibkr_audit_path=ibkr_audit)

    assert summary["agent_reviews"] == 2
    assert summary["agent_rejected"] == 1
    assert summary["paper_outcomes"]["net_points"] == 3.0
    assert summary["ibkr_ready"] == 1
    assert summary["ibkr_current_ready"] == 0
    assert "market_data_not_ready=1" in summary["ibkr_readiness_reasons"]
    assert "market_data_not_ready=1" in summary["ibkr_current_readiness_reasons"]
    assert summary["ibkr_current_account"] is None
    assert not summary["ibkr_current_account_paper"]
    assert summary["validation_gate"]["status"] == "blocked"
    assert any(reason.startswith("paper_outcomes_below_min") for reason in summary["validation_gate"]["blockers"])


def test_summarize_paper_audits_filters_by_strategy_id(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text(
        "\n".join(
            [
                json.dumps({"event_type": "agent_strategy_gate", "intent": {"strategy_id": "best"}, "passed": True}),
                json.dumps({"event_type": "agent_strategy_gate", "intent": {"strategy_id": "other"}, "passed": False}),
                json.dumps({"event_type": "agent_gate_paper_outcome", "strategy_id": "best", "points": 5.0}),
                json.dumps({"event_type": "agent_gate_paper_outcome", "strategy_id": "other", "points": -20.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ibkr_audit.write_text(
        "\n".join(
            [
                json.dumps({"event_type": "ibkr_paper_preflight", "readiness": {"status": "ready", "missing_requirements": []}}),
                json.dumps({"status": "submitted", "intent": {"strategy_id": "best"}}),
                json.dumps({"status": "submitted", "intent": {"strategy_id": "other"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_paper_audits(
        agent_audit_path=agent_audit,
        ibkr_audit_path=ibkr_audit,
        strategy_id="best",
        gate_config=PaperValidationGateConfig(min_paper_outcomes=1),
    )

    assert summary["strategy_id_filter"] == "best"
    assert summary["agent_reviews"] == 1
    assert summary["agent_approved"] == 1
    assert summary["agent_rejected"] == 0
    assert summary["paper_outcomes"]["trades"] == 1
    assert summary["paper_outcomes"]["net_points"] == 5.0
    assert summary["ibkr_submitted"] == 1


def test_evaluate_paper_validation_gate_passes_when_thresholds_met():
    summary = {
        "paper_outcomes": {"trades": 25, "net_points": 12.5, "win_rate": 52.0, "consecutive_losses": 2},
        "ibkr_ready": 2,
        "ibkr_current_ready": 1,
        "ibkr_submitted": 25,
        "ibkr_readiness_reasons": "",
        "ibkr_current_readiness_reasons": "",
    }

    gate = evaluate_paper_validation_gate(summary, config=PaperValidationGateConfig(min_paper_outcomes=20))

    assert gate["status"] == "pass"
    assert gate["blockers"] == []


def test_paper_validation_gate_uses_latest_preflight_for_current_readiness(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "ibkr_paper_preflight",
                        "readiness": {"status": "blocked", "missing_requirements": ["not_connected"]},
                    }
                ),
                json.dumps({"event_type": "ibkr_paper_preflight", "readiness": {"status": "ready", "missing_requirements": []}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_paper_audits(
        agent_audit_path=agent_audit,
        ibkr_audit_path=ibkr_audit,
        gate_config=PaperValidationGateConfig(min_ibkr_submitted=0, min_paper_outcomes=0),
    )

    assert summary["ibkr_ready"] == 1
    assert summary["ibkr_current_ready"] == 1
    assert "not_connected=1" in summary["ibkr_readiness_reasons"]
    assert summary["ibkr_current_readiness_reasons"] == ""
    assert not any(reason.startswith("readiness_blockers_above_max") for reason in summary["validation_gate"]["blockers"])


def test_paper_summary_preserves_latest_paper_account_when_market_data_blocked(tmp_path):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text(
        json.dumps(
            {
                "event_type": "ibkr_paper_preflight",
                "account": {"account": "DU002", "paper": True},
                "readiness": {"status": "blocked", "missing_requirements": ["market_data_not_ready"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = summarize_paper_audits(agent_audit_path=agent_audit, ibkr_audit_path=ibkr_audit)

    assert summary["ibkr_current_ready"] == 0
    assert summary["ibkr_current_account"] == "DU002"
    assert summary["ibkr_current_account_paper"]


def test_summarize_paper_validation_script_outputs_file(tmp_path, monkeypatch, capsys):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    output_path = tmp_path / "summary.csv"
    agent_audit.write_text(json.dumps({"event_type": "agent_strategy_gate", "passed": True}) + "\n", encoding="utf-8")
    ibkr_audit.write_text(json.dumps({"event_type": "ibkr_paper_preflight", "readiness": {"status": "ready", "missing_requirements": []}}) + "\n", encoding="utf-8")
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "summarize_paper_validation.py"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "summarize_paper_validation.py",
            "--agent-audit",
            str(agent_audit),
            "--ibkr-audit",
            str(ibkr_audit),
            "--output",
            str(output_path),
        ],
    )

    assert script.main() == 0
    assert '"agent_reviews": 1' in capsys.readouterr().out
    assert output_path.exists()


def test_generate_walk_forward_paper_validation_report_outputs_html(tmp_path, monkeypatch, capsys):
    decisions_path = tmp_path / "decisions.csv"
    summary_path = tmp_path / "summary.csv"
    paper_path = tmp_path / "paper.csv"
    output_path = tmp_path / "report.html"
    pd.DataFrame(
        [
            {
                "entry_ts": "2026-05-01 10:00:00+00:00",
                "net_points": 10.0,
                "gate_net_points": 10.0,
                "allowed": True,
            },
            {
                "entry_ts": "2026-05-02 10:00:00+00:00",
                "net_points": -4.0,
                "gate_net_points": 0.0,
                "allowed": False,
            },
        ]
    ).to_csv(decisions_path, index=False)
    pd.DataFrame(
        [
            {
                "fold": 0,
                "train_start": "2026-04-01",
                "train_end": "2026-04-15",
                "test_start": "2026-04-16",
                "test_end": "2026-04-20",
                "train_trades": 10,
                "test_trades": 2,
                "allowed": 1,
                "blocked": 1,
                "raw_net_points": 6.0,
                "gate_net_points": 10.0,
                "raw_max_drawdown_points": 4.0,
                "gate_max_drawdown_points": 0.0,
                "raw_profit_factor": 2.5,
                "gate_profit_factor": 99.0,
                "net_delta_points": 4.0,
                "drawdown_delta_points": 4.0,
            }
        ]
    ).to_csv(summary_path, index=False)
    pd.DataFrame(
        [
            {
                "agent_reviews": 1,
                "agent_approved": 1,
                "agent_rejected": 0,
                "paper_outcomes_trades": 0,
                "paper_outcomes_net_points": 0.0,
                "ibkr_preflights": 1,
                "ibkr_ready": 0,
                "ibkr_blocked": 1,
                "ibkr_submitted": 0,
                "ibkr_readiness_reasons": "market_data_not_ready=1",
                "validation_gate_status": "blocked",
                "validation_gate_blockers": "ibkr_submitted_below_min:0<1, paper_outcomes_below_min:0<20",
            }
        ]
    ).to_csv(paper_path, index=False)
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "generate_walk_forward_paper_validation_report.py"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "generate_walk_forward_paper_validation_report.py",
            "--walk-forward-summary",
            str(summary_path),
            "--walk-forward-decisions",
            str(decisions_path),
            "--paper-summary",
            str(paper_path),
            "--output",
            str(output_path),
        ],
    )

    assert script.main() == 0
    assert str(output_path) in capsys.readouterr().out
    html = output_path.read_text(encoding="utf-8")
    assert "NQM6 MBP 验证闭环报告" in html
    assert "Walk-forward equity by trading date" in html
    assert "market_data_not_ready=1" in html
    assert "BLOCKED: 尚未达到 paper 验证门槛" in html


def test_check_paper_validation_gate_script_blocks_without_outcomes(tmp_path, monkeypatch, capsys):
    agent_audit = tmp_path / "agent.jsonl"
    ibkr_audit = tmp_path / "ibkr.jsonl"
    agent_audit.write_text("", encoding="utf-8")
    ibkr_audit.write_text(
        json.dumps(
            {
                "event_type": "ibkr_paper_preflight",
                "readiness": {"status": "blocked", "missing_requirements": ["market_data_not_ready"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "check_paper_validation_gate.py"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_paper_validation_gate.py",
            "--agent-audit",
            str(agent_audit),
            "--ibkr-audit",
            str(ibkr_audit),
        ],
    )

    assert script.main() == 2
    output = capsys.readouterr().out
    assert '"status": "blocked"' in output
    assert "market_data_not_ready" in output


def test_run_daily_paper_validation_stops_on_failure(tmp_path, monkeypatch, capsys):
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "run_daily_paper_validation.py"))
    calls = []

    class Completed:
        def __init__(self, returncode):
            self.returncode = returncode
            self.stdout = "out"
            self.stderr = "err"

    def fake_run(command, cwd, text, capture_output, check):
        calls.append(command)
        return Completed(1)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["run_daily_paper_validation.py"])

    assert script.main() == 1
    assert len(calls) == 1
    assert '"ok": false' in capsys.readouterr().out


def test_check_nq_realtime_debate_status_reports_recent_decision(tmp_path, monkeypatch, capsys):
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "check_nq_realtime_debate_status.py"))
    status_path = tmp_path / "status.json"
    audit_path = tmp_path / "audit.jsonl"
    trade_log_dir = tmp_path / "tradelogs"
    trade_log_dir.mkdir()
    status_path.write_text(
        json.dumps(
            {
                "updated_at": "2026-05-06T00:00:00+00:00",
                "status": "completed",
                "mode": "dry_run",
                "iterations": 1,
                "events": [
                    {
                        "status": "dry_run",
                        "submitted": False,
                        "trigger": {"feature_set": "support_reclaim + entry_candle_up"},
                        "route": {"action": "BUY"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    audit_path.write_text(
        json.dumps(
            {
                "event_type": "nq_llm_debate_delayed_strategy",
                "status": "dry_run",
                "submitted": False,
                "trigger": {"feature_set": "support_reclaim + entry_candle_up"},
                "plan": {"decision_id": "decision-1"},
                "route": {"action": "BUY"},
                "recheck_price": 100.5,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (trade_log_dir / "2026-05-06.md").write_text(
        "# 交易记录 2026-05-06\n\n## 2026-05-06T00:00:00+00:00 - NQ LLM辩论策略 做多\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "daemon_status", lambda pattern: {"running": True, "submit_enabled": False, "dry_run_enabled": True, "pids": ["123"], "processes": []})
    monkeypatch.setattr(
        script,
        "ready_preflight",
        lambda **kwargs: {"readiness": {"status": "ready", "missing_requirements": []}, "connection": {"connected": True}, "market_data": {"order_ready": True}},
    )
    monkeypatch.setattr(script.time, "time", lambda: 1778025600.0)
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_nq_realtime_debate_status.py",
            "--status-path",
            str(status_path),
            "--audit-path",
            str(audit_path),
            "--trade-log-dir",
            str(trade_log_dir),
            "--max-status-age-seconds",
            "999999999",
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"status": "ready"' in output
    assert "support_reclaim + entry_candle_up" in output
    assert "NQ LLM辩论策略 做多" in output


def test_build_ibkr_tick_replay_dataset_script_outputs_files(tmp_path, monkeypatch, capsys):
    input_dir = tmp_path / "ticks"
    input_dir.mkdir()
    (input_dir / "NQ-202606-intent.jsonl").write_text(
        json.dumps(
            {
                "event_type": "ibkr_paper_tick",
                "intent_id": "intent-1",
                "candidate_key": "candidate-1",
                "strategy_id": "strategy-1",
                "tick_index": 0,
                "tick_event_index": 0,
                "source_event_type": "ibkr_tick_snapshot",
                "snapshot_time": "2026-05-01T10:30:00Z",
                "bid": 18000.0,
                "ask": 18000.25,
                "last": 18000.25,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "replay.csv"
    summary = tmp_path / "summary.csv"
    script = _load_script(str(Path(__file__).resolve().parents[1] / "scripts" / "build_ibkr_tick_replay_dataset.py"))
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_ibkr_tick_replay_dataset.py",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output),
            "--summary-output",
            str(summary),
        ],
    )

    assert script.main() == 0
    text = capsys.readouterr().out
    assert '"ticks": 1' in text
    assert output.exists()
    assert summary.exists()
