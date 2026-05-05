from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts, StrategySpec, build_trades


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
RANK_SCRIPT_PATH = SCRIPTS_DIR / "rank_nq_bar_best_strategy.py"
SEARCH_SCRIPT_PATH = SCRIPTS_DIR / "search_nq_bar_best_strategy_walkforward.py"
sys.path.insert(0, str(SCRIPTS_DIR))
RANK_SPEC = importlib.util.spec_from_file_location("rank_nq_bar_best_strategy", RANK_SCRIPT_PATH)
rank_script = importlib.util.module_from_spec(RANK_SPEC)
assert RANK_SPEC.loader is not None
RANK_SPEC.loader.exec_module(rank_script)
SEARCH_SPEC = importlib.util.spec_from_file_location("search_nq_bar_best_strategy_walkforward", SEARCH_SCRIPT_PATH)
search_script = importlib.util.module_from_spec(SEARCH_SPEC)
assert SEARCH_SPEC.loader is not None
sys.modules["search_nq_bar_best_strategy_walkforward"] = search_script
SEARCH_SPEC.loader.exec_module(search_script)


def _frame(closes: list[float], lows: list[float], highs: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=len(closes), freq="min", tz="UTC"),
            "Open": closes,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": [1_000] * len(closes),
            "vwap": [100.0] * len(closes),
        }
    )


def test_support_reclaim_triggers_after_sweep_and_reclaim() -> None:
    frame = _frame(
        closes=[100.0, 100.2, 100.1, 100.0, 100.4, 100.6],
        lows=[99.8, 100.0, 99.9, 98.8, 100.2, 100.4],
        highs=[100.3, 100.4, 100.35, 100.1, 100.7, 100.9],
    )
    spec = StrategySpec("support_reclaim_lb3_thr0.0002_hold1", "support_reclaim", 3, 0.0002, 1)

    trades = build_trades(frame, spec, BacktestCosts(slippage_ticks_per_side=0.0, commission_per_contract=0.0))

    assert not trades.empty
    assert int(trades.iloc[0]["direction"]) == 1


def test_breakout_retest_triggers_after_break_and_hold() -> None:
    frame = _frame(
        closes=[100.0, 100.1, 100.2, 101.0, 100.9, 101.2],
        lows=[99.8, 99.9, 100.0, 100.7, 100.15, 101.0],
        highs=[100.3, 100.4, 100.5, 101.2, 101.1, 101.5],
    )
    spec = StrategySpec("breakout_retest_lb3_thr0.0002_hold1", "breakout_retest", 3, 0.0002, 1)

    trades = build_trades(frame, spec, BacktestCosts(slippage_ticks_per_side=0.0, commission_per_contract=0.0))

    assert not trades.empty
    assert int(trades.iloc[0]["direction"]) == 1


def test_direction_filter_keeps_only_requested_side() -> None:
    frame = _frame(
        closes=[100.0, 100.2, 100.1, 100.0, 100.4, 100.6],
        lows=[99.8, 100.0, 99.9, 98.8, 100.2, 100.4],
        highs=[100.3, 100.4, 100.35, 100.1, 100.7, 100.9],
    )
    spec = StrategySpec(
        "support_reclaim_lb3_thr0.0002_hold1_short",
        "support_reclaim",
        3,
        0.0002,
        1,
        direction_filter="short",
    )

    trades = build_trades(frame, spec, BacktestCosts(slippage_ticks_per_side=0.0, commission_per_contract=0.0))

    assert trades.empty


def test_nq_candidate_pool_and_debate_text_include_price_action_setups() -> None:
    args = type(
        "Args",
        (),
        {
            "sessions": ["us_rth"],
            "families": ["support_reclaim", "breakout_retest"],
            "lookbacks": [30],
            "holding_minutes": [30],
            "direction_filters": ["long", "short"],
            "support_reclaim_thresholds": [0.0002],
            "breakout_retest_thresholds": [0.0005],
        },
    )()

    candidates = search_script.candidate_pool(args)
    families = {candidate.spec.family for candidate in candidates}

    assert families == {"support_reclaim", "breakout_retest"}
    assert {candidate.spec.direction_filter for candidate in candidates} == {"long", "short"}
    assert any(candidate.spec.name.endswith("_long") for candidate in candidates)
    assert any(candidate.spec.name.endswith("_short") for candidate in candidates)
    assert "Only take long signals" in rank_script.signal_rule(
        pd.Series({"family": "support_reclaim", "lookback": 30, "threshold": 0.0002, "direction_filter": "long"})
    )
    assert "Only take short signals" in rank_script.signal_rule(
        pd.Series({"family": "breakout_retest", "lookback": 30, "threshold": 0.0005, "direction_filter": "short"})
    )
