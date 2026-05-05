from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "mine_nq_state_filtered_features.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("mine_nq_state_filtered_features", SCRIPT_PATH)
mine_script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["mine_nq_state_filtered_features"] = mine_script
SPEC.loader.exec_module(mine_script)


def test_enrich_state_features_resets_vwap_by_trade_date() -> None:
    features = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=4, freq="min", tz="UTC"),
            "Open": [99.0, 101.0, 199.0, 203.0],
            "High": [101.0, 103.0, 201.0, 203.0],
            "Low": [99.0, 101.0, 199.0, 201.0],
            "Close": [100.0, 102.0, 200.0, 202.0],
            "Volume": [1.0, 1.0, 1.0, 1.0],
            "trade_date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "minute_of_day": [900, 901, 900, 901],
            "vol_120": [1.0, 2.0, 3.0, 4.0],
            "range_mean_30": [1.0, 2.0, 3.0, 4.0],
            "return_1m": [0.1, 0.2, -0.1, -0.2],
        }
    )

    enriched = mine_script.enrich_state_features(features)

    assert enriched["vwap"].round(2).tolist() == [100.0, 101.0, 200.0, 201.0]
    assert enriched["minute_bucket_30"].tolist() == [30, 30, 30, 30]
    assert enriched["entry_close_zone"].tolist() == ["middle", "middle", "middle", "middle"]
    assert enriched["return_1m_side"].tolist() == ["positive", "positive", "negative", "negative"]


def test_mine_filters_finds_profitable_composite_state_edge() -> None:
    rows = []
    entry_ts = pd.date_range("2026-01-01", periods=220, freq="min", tz="UTC")
    for index, ts in enumerate(entry_ts):
        in_edge = index < 100
        rows.append(
            {
                "entry_ts": ts,
                "candidate": "candidate_a",
                "direction": 1,
                "net_points": 20.0 if in_edge else -5.0,
                "fold": index // 50,
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
    trades = pd.DataFrame(rows)

    mined = mine_script.mine_filters(
        trades,
        min_trades=80,
        min_folds=2,
        min_net_points=1500.0,
        min_profit_factor=1.2,
        min_win_rate=0.48,
    )

    assert not mined.empty
    composite = mined[mined["filter"] == "vwap_above_and_trend_120_up"].iloc[0]
    assert composite["net_points"] == 2000.0
    assert composite["positive_fold_rate"] == 1.0
