from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
MINE_SCRIPT_PATH = SCRIPTS_DIR / "mine_nq_state_filtered_features.py"
SCRIPT_PATH = SCRIPTS_DIR / "validate_nq_promotion_recent_oos.py"
sys.path.insert(0, str(SCRIPTS_DIR))

MINE_SPEC = importlib.util.spec_from_file_location("mine_nq_state_filtered_features", MINE_SCRIPT_PATH)
mine_script = importlib.util.module_from_spec(MINE_SPEC)
assert MINE_SPEC.loader is not None
sys.modules["mine_nq_state_filtered_features"] = mine_script
MINE_SPEC.loader.exec_module(mine_script)

SPEC = importlib.util.spec_from_file_location("validate_nq_promotion_recent_oos", SCRIPT_PATH)
recent_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["validate_nq_promotion_recent_oos"] = recent_script
SPEC.loader.exec_module(recent_script)


def test_evaluate_recent_marks_profitable_candidate_as_recent_pass() -> None:
    timestamps = pd.date_range("2026-01-01", periods=48, freq="7D", tz="UTC")
    trades = pd.DataFrame(
        {
            "entry_ts": timestamps,
            "candidate": ["candidate_a"] * len(timestamps),
            "filter": ["none"] * len(timestamps),
            "net_points": [10.0, 15.0, -3.0, 8.0] * 12,
            "fold": [0] * len(timestamps),
        }
    )
    shortlist = pd.DataFrame(
        [
            {
                "tier": "promote_to_strict_gate",
                "candidate": "candidate_a",
                "filter": "none",
                "evidence_type": "directional_walkforward",
                "next_action": "integrate",
            }
        ]
    )

    result, monthly = recent_script.evaluate_recent(trades, shortlist, months=12)

    assert result.iloc[0]["recent_verdict"] == "passes_recent_oos"
    assert result.iloc[0]["net_points"] > 0
    assert not monthly.empty


def test_filtered_candidate_must_beat_recent_baseline_to_pass() -> None:
    assert (
        recent_script.recent_verdict(
            {"trades": 30, "net_points": 100.0, "profit_factor": 1.4},
            {"months_with_trades": 4, "positive_month_rate": 0.75, "min_month_net_points": -10.0},
            net_improvement=-1.0,
            filter_name="z_30_negative",
        )
        == "watch_recent_oos"
    )
