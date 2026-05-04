import importlib.util
from pathlib import Path

import pandas as pd

from tradingagents.execution.agent_gate import AgentGateConfig
from tradingagents.execution.gate_backtest import GateReplayConfig, replay_gate_on_trades


def _trades(points):
    rows = []
    for index, value in enumerate(points):
        rows.append(
            {
                "entry_ts": f"2026-05-01 10:{index:02d}:00+00:00",
                "exit_ts": f"2026-05-01 10:{index + 1:02d}:00+00:00",
                "trade_date": "2026-05-01",
                "direction": 1,
                "entry_price": 18000.0 + index,
                "exit_price": 18000.0 + index + value,
                "net_points": float(value),
                "portfolio_rule": "adaptive_defensive_mr",
                "selected_alias": "stable_mr",
                "exit_reason": "time",
                "entry_index": index,
            }
        )
    return pd.DataFrame(rows)


def test_offline_gate_replay_blocks_after_performance_guard(tmp_path):
    replay_config = GateReplayConfig(
        audit_path=tmp_path / "gate.jsonl",
        max_trades=None,
        sizing_mode="block",
    )
    gate_config = AgentGateConfig(
        performance_min_trades=3,
        performance_recent_trades=3,
        performance_min_net_points=-10,
        performance_min_win_rate=30,
        performance_max_consecutive_losses=3,
    )

    decisions, summary = replay_gate_on_trades(
        _trades([-5, -6, -7, 20]),
        replay_config=replay_config,
        gate_config=gate_config,
    )

    assert decisions["allowed"].tolist() == [True, True, True, False]
    assert decisions.iloc[-1]["gate_status"] == "offline_rejected"
    assert "paper_consecutive_losses_guard" in decisions.iloc[-1]["gate_reasons"]
    assert summary.loc[summary["label"].eq("raw"), "net_points"].iloc[0] == 2.0
    assert summary.loc[summary["label"].eq("gate"), "net_points"].iloc[0] == -18.0


def test_offline_gate_replay_shadow_outcomes_allow_recovery(tmp_path):
    replay_config = GateReplayConfig(audit_path=tmp_path / "gate.jsonl", sizing_mode="block")
    gate_config = AgentGateConfig(
        performance_min_trades=3,
        performance_recent_trades=3,
        performance_min_net_points=-10,
        performance_min_win_rate=30,
        performance_max_consecutive_losses=3,
    )

    decisions, _ = replay_gate_on_trades(
        _trades([-5, -6, -7, 20, 20]),
        replay_config=replay_config,
        gate_config=gate_config,
    )

    assert decisions["allowed"].tolist() == [True, True, True, False, True]


def test_offline_gate_replay_scales_watch_mode_instead_of_blocking(tmp_path):
    replay_config = GateReplayConfig(audit_path=tmp_path / "gate.jsonl", sizing_mode="scale")
    gate_config = AgentGateConfig(
        performance_min_trades=3,
        performance_recent_trades=3,
        performance_min_net_points=-100,
        performance_min_win_rate=80,
        performance_max_consecutive_losses=9,
        performance_watch_scale=0.25,
        performance_hard_block=False,
    )

    decisions, summary = replay_gate_on_trades(
        _trades([10, -1, -1, 20]),
        replay_config=replay_config,
        gate_config=gate_config,
    )

    assert decisions["position_scale"].tolist() == [1.0, 1.0, 1.0, 0.25]
    assert decisions["allowed"].tolist() == [True, True, True, True]
    assert decisions.iloc[-1]["gate_severity"] == "watch"
    assert summary.loc[summary["label"].eq("gate"), "net_points"].iloc[0] == 13.0


def test_backtest_agent_gate_script_outputs_files(tmp_path, monkeypatch, capsys):
    trades_path = tmp_path / "trades.csv"
    _trades([1, -2]).to_csv(trades_path, index=False)
    decisions_path = tmp_path / "decisions.csv"
    summary_path = tmp_path / "summary.csv"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "backtest_agent_gate_on_mbp_trades.py"
    spec = importlib.util.spec_from_file_location("backtest_agent_gate_on_mbp_trades", script_path)
    script = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(script)
    monkeypatch.setattr(
        "sys.argv",
        [
            "backtest_agent_gate_on_mbp_trades.py",
            "--trades",
            str(trades_path),
            "--decisions-output",
            str(decisions_path),
            "--summary-output",
            str(summary_path),
            "--audit-path",
            str(tmp_path / "audit.jsonl"),
        ],
    )

    assert script.main() == 0
    output = capsys.readouterr().out
    assert '"allowed": 2' in output
    assert decisions_path.exists()
    assert summary_path.exists()
