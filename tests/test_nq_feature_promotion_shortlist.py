from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "build_nq_feature_promotion_shortlist.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("build_nq_feature_promotion_shortlist", SCRIPT_PATH)
shortlist_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["build_nq_feature_promotion_shortlist"] = shortlist_script
SPEC.loader.exec_module(shortlist_script)


def test_build_shortlist_promotes_stable_directional_and_flags_past_fold_watchlist() -> None:
    directional = pd.DataFrame(
        [
            {
                "candidate": "stable_base",
                "full_trades": 100,
                "full_net_points": 4000.0,
                "full_profit_factor": 1.6,
                "positive_fold_rate": 1.0,
                "stress_net_points": 100.0,
                "selected_folds": 2,
                "live_ready": False,
            }
        ]
    )
    state_filters = pd.DataFrame(
        [
            {
                "candidate": "stable_base",
                "filter": "vwap_below",
                "trades": 90,
                "net_points": 2000.0,
                "profit_factor": 1.4,
                "positive_fold_rate": 0.5,
                "min_fold_net_points": -100.0,
                "baseline_net_points": 2500.0,
                "net_improvement": -500.0,
                "folds": 2,
            }
        ]
    )
    past_fold = pd.DataFrame(
        [
            {
                "candidate": "stable_base",
                "filter": "z_30_negative",
                "test_trades": 80,
                "test_net_points": 1200.0,
                "fold_net_profit_factor": 2.0,
                "positive_selected_fold_rate": 0.5,
                "min_test_fold_net_points": -100.0,
                "test_baseline_net_points": 1000.0,
                "test_net_improvement": 200.0,
                "selected_folds": 2,
            }
        ]
    )

    shortlist = shortlist_script.build_shortlist(directional, state_filters, past_fold)

    assert shortlist.iloc[0]["tier"] == "promote_to_strict_gate"
    assert "paper_watchlist" in set(shortlist["tier"])
    assert "reject_for_now" in set(shortlist["tier"])
