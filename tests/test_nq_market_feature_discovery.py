from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "discover_nq_tradeable_market_features.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("discover_nq_tradeable_market_features", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["discover_nq_tradeable_market_features"] = script
SPEC.loader.exec_module(script)


def test_event_path_summary_scores_directional_opportunity() -> None:
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=80, freq="min", tz="UTC"),
            "symbol": ["NQH6"] * 80,
            "Open": [100.0 + index for index in range(80)],
            "High": [101.0 + index for index in range(80)],
            "Low": [99.0 + index for index in range(80)],
            "Close": [100.0 + index for index in range(80)],
        }
    )
    feature = script.MarketFeature(
        feature_id="synthetic_trend_start",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long trend event.",
        signal=pd.Series([index in {5, 25, 45} for index in range(80)]),
    )

    events = script.event_path_rows(frame, [feature], horizons=[5, 15], min_gap_minutes=1)
    summary = script.summarize_events(events, horizons=[5, 15], min_events=1)

    assert len(events) == 3
    assert not summary.empty
    top = summary.iloc[0]
    assert top["feature_id"] == "synthetic_trend_start"
    assert top["events"] == 3
    assert top["favorable_close_rate_15m"] == 1.0
    assert top["median_mfe_15m"] > top["median_mae_15m"]


def test_fallback_feature_analysis_returns_strategy_principles() -> None:
    summary = pd.DataFrame(
        [
            {
                "feature_id": "volume_price_bullish_mismatch",
                "family": "volume_price_mismatch",
                "direction_hint": "long",
                "description": "Price weak while volume confirms accumulation.",
                "events": 120,
                "opportunity_score": 4.2,
            }
        ]
    )
    args = argparse.Namespace(llm_top_n=5)

    payload = script.fallback_feature_analysis(summary, args, memory_notes=[])

    assert payload["status"] == "fallback"
    assert payload["feature_rankings"][0]["feature_id"] == "volume_price_bullish_mismatch"
    assert "confirmation" in payload["feature_rankings"][0]
    assert payload["strategy_hypotheses"][0]["setup"] == "volume_price_bullish_mismatch"
    assert payload["risk_principles"]
