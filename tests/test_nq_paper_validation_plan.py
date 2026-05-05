from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "build_nq_paper_validation_plan.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("build_nq_paper_validation_plan", SCRIPT_PATH)
plan_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["build_nq_paper_validation_plan"] = plan_script
SPEC.loader.exec_module(plan_script)


def test_build_plan_includes_only_recent_oos_passes() -> None:
    recent = pd.DataFrame(
        [
            {
                "recent_verdict": "passes_recent_oos",
                "candidate": "strategy_a",
                "filter": "none",
                "tier": "promote_to_strict_gate",
                "trades": 30,
                "net_points": 100.0,
                "profit_factor": 1.5,
                "positive_month_rate": 0.75,
                "min_month_net_points": -5.0,
            },
            {
                "recent_verdict": "watch_recent_oos",
                "candidate": "strategy_b",
                "filter": "z_30_negative",
                "tier": "paper_watchlist",
                "trades": 30,
                "net_points": 90.0,
                "profit_factor": 1.4,
                "positive_month_rate": 0.5,
                "min_month_net_points": -10.0,
            },
        ]
    )

    plan = plan_script.build_plan(recent, symbol="MNQ", contract_month="202606", max_candidates=3)

    assert plan["strategy_id"].tolist() == ["strategy_a"]
    assert plan.iloc[0]["implementation_status"] == "needs_nq_bar_live_signal_adapter"
    assert "--submit" not in plan.iloc[0]["dry_run_command_after_adapter"]
    assert "--submit" in plan.iloc[0]["submit_command_after_adapter"]
    assert plan.iloc[0]["max_consecutive_losses"] == 3
