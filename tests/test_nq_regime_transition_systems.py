from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "search_nq_regime_transition_systems.py"
sys.path.insert(0, str(SCRIPTS_DIR))

SPEC = importlib.util.spec_from_file_location("search_nq_regime_transition_systems", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["search_nq_regime_transition_systems"] = script
SPEC.loader.exec_module(script)


def test_regime_transition_stability_gate_requires_win_pf_and_payoff() -> None:
    rows = pd.DataFrame(
        {
            "selected_folds": [4, 4],
            "test_trades": [100, 100],
            "positive_test_fold_rate": [1.0, 1.0],
            "test_net_points": [500.0, 500.0],
            "avg_test_expectancy_points": [2.0, 2.0],
            "avg_test_win_rate": [0.54, 0.52],
            "avg_test_profit_factor": [1.2, 1.2],
            "avg_test_payoff_ratio": [1.1, 1.1],
            "net_to_drawdown": [2.0, 2.0],
        }
    )

    result = script.apply_stability_gate(
        rows,
        min_selected_folds=3,
        min_test_trades=60,
        min_positive_test_fold_rate=0.60,
        min_test_win_rate=0.53,
        min_test_profit_factor=1.0,
        min_test_payoff_ratio=1.0,
        min_net_to_drawdown=1.0,
    )

    assert result.tolist() == [True, False]
