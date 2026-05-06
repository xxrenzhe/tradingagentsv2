from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "validate_nq_high_win_payoff_past_folds.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("validate_nq_high_win_payoff_past_folds", SCRIPT_PATH)
validate_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["validate_nq_high_win_payoff_past_folds"] = validate_script
SPEC.loader.exec_module(validate_script)


def test_validate_past_folds_selects_from_prior_folds_only() -> None:
    rows = []
    for fold in range(4):
        for index in range(40):
            in_edge = index < 25
            rows.append(
                {
                    "entry_ts": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=fold, minutes=index),
                    "candidate": "candidate_a",
                    "direction": 1,
                    "net_points": 3.0 if in_edge else -1.0,
                    "fold": fold,
                    "vwap_side": "above" if in_edge else "below",
                    "minute_bucket_30": 40,
                }
            )
    trades = pd.DataFrame(rows)

    fold_results, trade_results = validate_script.validate_past_folds(
        trades,
        {("candidate_a", "vwap_above")},
        min_train_folds=2,
        min_train_trades=40,
        min_train_win_rate=0.53,
        min_train_payoff_ratio=1.0,
        min_train_net_points=1.0,
        min_train_positive_fold_rate=1.0,
        max_fold_candidates=3,
    )
    aggregate = validate_script.aggregate_results(fold_results, trade_results)

    assert set(fold_results["fold"]) == {2, 3}
    assert (fold_results["train_folds"] >= 2).all()
    assert not aggregate.empty
    assert bool(aggregate.iloc[0]["future_pass"])
