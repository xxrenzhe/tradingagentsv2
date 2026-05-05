from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
MINE_SCRIPT_PATH = SCRIPTS_DIR / "mine_nq_state_filtered_features.py"
VALIDATE_SCRIPT_PATH = SCRIPTS_DIR / "validate_nq_state_filters_walkforward.py"
sys.path.insert(0, str(SCRIPTS_DIR))

MINE_SPEC = importlib.util.spec_from_file_location("mine_nq_state_filtered_features", MINE_SCRIPT_PATH)
mine_script = importlib.util.module_from_spec(MINE_SPEC)
assert MINE_SPEC.loader is not None
sys.modules["mine_nq_state_filtered_features"] = mine_script
MINE_SPEC.loader.exec_module(mine_script)

VALIDATE_SPEC = importlib.util.spec_from_file_location("validate_nq_state_filters_walkforward", VALIDATE_SCRIPT_PATH)
validate_script = importlib.util.module_from_spec(VALIDATE_SPEC)
assert VALIDATE_SPEC.loader is not None
sys.modules["validate_nq_state_filters_walkforward"] = validate_script
VALIDATE_SPEC.loader.exec_module(validate_script)


def _trade_rows() -> pd.DataFrame:
    rows = []
    for fold in range(4):
        for index in range(80):
            in_edge = index < 50
            rows.append(
                {
                    "entry_ts": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=fold * 100 + index),
                    "candidate": "candidate_a",
                    "direction": 1,
                    "net_points": 10.0 if in_edge else -2.0,
                    "fold": fold,
                    "vwap_side": "above" if in_edge else "below",
                    "trend_side_120": "up" if in_edge else "down",
                    "momentum_60": 1.0 if in_edge else -1.0,
                    "z_30": -1.0 if in_edge else 1.0,
                    "vol_120_rank": 0.2 if in_edge else 0.9,
                    "range_30_rank": 0.2 if in_edge else 0.9,
                    "volume_z_60": 1.5 if in_edge else -1.5,
                    "return_1m_side": "positive" if in_edge else "negative",
                    "entry_body_rank": 0.2 if in_edge else 0.9,
                    "entry_body_to_range": 0.2 if in_edge else 0.9,
                    "entry_candle_side": "up" if in_edge else "down",
                    "entry_close_zone": "high" if in_edge else "low",
                    "vwap_distance_abs_rank": 0.2 if in_edge else 0.9,
                    "vwap_stretch_side": "neutral",
                    "minute_bucket_30": 30,
                }
            )
    return pd.DataFrame(rows)


def test_past_fold_validation_selects_on_prior_folds_only() -> None:
    results, selections = validate_script.validate_past_fold_selection(
        _trade_rows(),
        min_train_folds=2,
        min_train_trades=80,
        min_train_net_points=500.0,
        min_train_profit_factor=1.2,
        min_train_win_rate=0.5,
        min_train_positive_fold_rate=1.0,
        min_train_min_fold_net_points=1.0,
        max_fold_candidates=3,
    )

    assert not results.empty
    assert set(results["fold"]) == {2, 3}
    assert selections["fold"].min() == 2
    assert "vwap_above" in set(results["filter"])

    aggregate = validate_script.aggregate_results(results)

    assert not aggregate.empty
    top = aggregate.iloc[0]
    assert top["selected_folds"] == 2
    assert top["test_net_points"] > 0
