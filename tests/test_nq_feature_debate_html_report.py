from __future__ import annotations

import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "generate_nq_feature_debate_backtest_report.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("generate_nq_feature_debate_backtest_report", SCRIPT_PATH)
report_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["generate_nq_feature_debate_backtest_report"] = report_script
SPEC.loader.exec_module(report_script)


def test_generate_html_report_includes_debate_and_adapter_gap(tmp_path: Path) -> None:
    directional = tmp_path / "directional.csv"
    shortlist = tmp_path / "shortlist.csv"
    state_filters = tmp_path / "state_filters.csv"
    past_fold = tmp_path / "past_fold.csv"
    recent_oos = tmp_path / "recent_oos.csv"
    recent_monthly = tmp_path / "recent_monthly.csv"
    paper_plan = tmp_path / "paper_plan.csv"
    debate = tmp_path / "debate.json"
    output = tmp_path / "report.html"

    candidate = "bar_best_mean_reversion_lb10_thr1_hold30_long_us_late"
    pd.DataFrame(
        [
            {
                "candidate": candidate,
                "family": "mean_reversion",
                "direction_filter": "long",
                "full_trades": 369,
                "full_net_points": 4483.875,
                "full_profit_factor": 1.5586,
                "positive_fold_rate": 1.0,
                "stress_net_points": 1157.625,
                "best_strategy_score": 6.4,
                "selection_tier": "promote_to_strict_gate",
            }
        ]
    ).to_csv(directional, index=False)
    pd.DataFrame(
        [
            {
                "tier": "promote_to_strict_gate",
                "candidate": candidate,
                "filter": "none",
                "evidence_type": "directional_walkforward",
                "trades": 369,
                "net_points": 4483.875,
                "profit_factor": 1.5586,
                "positive_fold_rate": 1.0,
                "stress_points": 1157.625,
                "selected_folds": 2,
                "next_action": "integrate_into_strict_gate_and_recent_oos",
            }
        ]
    ).to_csv(shortlist, index=False)
    pd.DataFrame(
        [
            {
                "candidate": candidate,
                "filter": "z_30_negative",
                "trades": 200,
                "net_points": 1200.0,
                "profit_factor": 1.5,
                "positive_fold_rate": 0.75,
                "min_fold_net_points": -10.0,
                "baseline_net_points": 1100.0,
                "net_improvement": 100.0,
                "retained_trade_rate": 0.8,
            }
        ]
    ).to_csv(state_filters, index=False)
    pd.DataFrame(
        [
            {
                "candidate": candidate,
                "filter": "z_30_negative",
                "selected_folds": 2,
                "test_trades": 100,
                "test_net_points": 250.0,
                "fold_net_profit_factor": 1.8,
                "positive_selected_fold_rate": 0.5,
                "min_test_fold_net_points": -20.0,
                "test_baseline_net_points": 200.0,
                "test_net_improvement": 50.0,
            }
        ]
    ).to_csv(past_fold, index=False)
    pd.DataFrame(
        [
            {
                "recent_verdict": "passes_recent_oos",
                "candidate": candidate,
                "filter": "none",
                "trades": 80,
                "net_points": 900.0,
                "profit_factor": 1.4,
                "win_rate": 0.55,
                "positive_month_rate": 0.75,
                "min_month_net_points": -50.0,
                "months_with_trades": 4,
                "next_action": "paper_trade_small_size",
            }
        ]
    ).to_csv(recent_oos, index=False)
    pd.DataFrame(
        [{"candidate": candidate, "filter": "none", "month": "2026-01", "trades": 20, "net_points": 300.0, "win_rate": 0.6}]
    ).to_csv(recent_monthly, index=False)
    pd.DataFrame(
        [
            {
                "priority": 1,
                "strategy_id": candidate,
                "filter": "none",
                "tier": "promote_to_strict_gate",
                "symbol": "MNQ",
                "quantity": 1,
                "submit_mode": "blocked_until_nq_bar_live_adapter_exists",
                "recent_net_points": 900.0,
                "recent_profit_factor": 1.4,
                "implementation_status": "needs_nq_bar_live_signal_adapter",
                "adapter_gap": "run_ibkr_live_paper_trader currently supports MBP live_strategy families, not these bar_best NQ strategy IDs",
            }
        ]
    ).to_csv(paper_plan, index=False)
    debate.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": candidate,
                        "selection_tier": "promote_to_strict_gate",
                        "signal_rule": "go long on mean reversion",
                        "entry_point": "enter next minute",
                        "exit_rule": "exit after 30 minutes",
                        "session_window_utc": "20:00-23:00",
                        "direction_filter": "long",
                        "bull_case": ["positive_fold_rate=1.0000"],
                        "bear_case": ["full_trades=369"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    args = Namespace(
        directional_ranking=str(directional),
        shortlist=str(shortlist),
        state_filters=str(state_filters),
        past_fold_validation=str(past_fold),
        recent_oos=str(recent_oos),
        recent_monthly=str(recent_monthly),
        paper_plan=str(paper_plan),
        debate=str(debate),
        output=str(output),
        generated_at="2026-05-06 00:00 UTC",
    )

    report_script.write_html_report(args)

    html = output.read_text(encoding="utf-8")
    assert "NQ 5年特征、可盈利方向与 LLM 辩论回测报告" in html
    assert candidate in html
    assert "go long on mean reversion" in html
    assert "blocked_until_nq_bar_live_adapter_exists" in html
    assert "状态过滤挖掘" in html
