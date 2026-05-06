from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "mine_nq_5y_high_win_payoff_feature_sets.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("mine_nq_5y_high_win_payoff_feature_sets", SCRIPT_PATH)
mine_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["mine_nq_5y_high_win_payoff_feature_sets"] = mine_script
SPEC.loader.exec_module(mine_script)


def test_mine_feature_sets_requires_win_rate_and_payoff_ratio() -> None:
    rows = []
    for index in range(100):
        rows.append(
            {
                "candidate": "passes",
                "net_points": 1.2 if index < 56 else -1.0,
                "direction": 1,
                "fold": index // 25,
                "minute_bucket_30": 40,
            }
        )
        rows.append(
            {
                "candidate": "fails_payoff",
                "net_points": 0.8 if index < 60 else -1.0,
                "direction": 1,
                "fold": index // 25,
                "minute_bucket_30": 40,
            }
        )
    trades = pd.DataFrame(rows)

    mined = mine_script.mine_feature_sets(
        trades,
        min_trades=80,
        min_folds=2,
        min_win_rate=0.53,
        min_payoff_ratio=1.0,
        min_net_points=0.0,
    )

    assert set(mined["candidate"]) == {"passes"}
    base = mined[mined["filter"].eq("none")].iloc[0]
    assert base["win_rate"] > 0.53
    assert base["payoff_ratio_r"] > 1.0
