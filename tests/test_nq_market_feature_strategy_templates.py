from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "backtest_nq_market_feature_strategy_templates.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("backtest_nq_market_feature_strategy_templates", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["backtest_nq_market_feature_strategy_templates"] = script
SPEC.loader.exec_module(script)


def test_confirm_break_entry_ignores_events_too_close_to_end() -> None:
    event_indexes = np.asarray([2, 8])
    open_prices = np.arange(10, dtype=float) + 100.0
    high = open_prices + 1.0
    low = open_prices - 1.0
    close = open_prices.copy()
    close[3] = high[2] + 1.0
    atr = np.full(10, 2.0)

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="confirm_break",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 4
    assert np.isnan(entries[1])


def test_build_template_trades_hits_target_for_long_setup() -> None:
    frame = _trade_frame()
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_next_open_atr",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=1.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="bracket",
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["entry_index"] == 3
    assert row["exit_reason"] == "take_profit"
    assert row["gross_points"] == 2.0


def test_fast_fail_exit_cuts_trade_before_full_horizon() -> None:
    frame = _trade_frame()
    frame.loc[4, "Close"] = 99.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_fast_fail",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="fast_fail",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "fast_fail"
    assert row["exit_index"] == 4


def test_bracket_fast_fail_cuts_trade_before_full_stop() -> None:
    frame = _trade_frame()
    frame.loc[4, "Close"] = 99.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_bracket_fast_fail",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="bracket_fast_fail",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "fast_fail"
    assert row["exit_index"] == 4


def test_staged_exit_books_half_at_one_r_then_time_exit() -> None:
    frame = _trade_frame()
    frame.loc[5:, "Close"] = 102.5
    frame.loc[5:, "High"] = 103.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_staged",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="staged",
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "partial_time"
    assert row["gross_points"] == 1.75


def test_staged_exit_uses_reward_risk_for_second_target() -> None:
    frame = _trade_frame()
    frame.loc[5:, "High"] = 105.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    rr1_template = script.StrategyTemplate(
        name="synthetic_long_staged_rr1",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=1.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="staged",
        fast_fail_bars=0,
    )
    rr2_template = script.StrategyTemplate(
        name="synthetic_long_staged_rr2",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="staged",
        fast_fail_bars=0,
    )

    rr1 = script.build_template_trades(frame, feature, rr1_template, min_gap_minutes=1, min_stop_points=1.0)
    rr2 = script.build_template_trades(frame, feature, rr2_template, min_gap_minutes=1, min_stop_points=1.0)

    assert rr1.iloc[0]["exit_reason"] == "partial_target"
    assert rr2.iloc[0]["exit_reason"] == "partial_target"
    assert rr1.iloc[0]["gross_points"] == 2.0
    assert rr2.iloc[0]["gross_points"] == 3.0


def test_staged_exit_can_fast_fail_before_scale_out() -> None:
    frame = _trade_frame()
    frame.loc[4, "Close"] = 99.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_staged_fast_fail",
        feature_id="synthetic_long",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="staged",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "fast_fail"
    assert row["exit_index"] == 4


def test_quality_reclaim_requires_strong_close_through_prior_bar() -> None:
    event_indexes = np.asarray([2, 5])
    open_prices = np.full(12, 100.0)
    high = np.full(12, 101.0)
    low = np.full(12, 99.0)
    close = np.full(12, 100.0)
    atr = np.full(12, 2.0)
    high[3] = 101.0
    low[3] = 98.5
    close[3] = 101.6
    high[6] = 101.0
    low[6] = 98.5
    close[6] = 100.8

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="quality_reclaim",
        confirm_bars=2,
        pullback_atr=0.25,
    )

    assert entries[0] == 4
    assert np.isnan(entries[1])


def test_hybrid_event_atr_caps_structural_stop_distance() -> None:
    template = script.StrategyTemplate(
        name="hybrid",
        feature_id="feature",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="hybrid_event_atr",
        reward_risk=1.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.5,
    )

    distances = script.stop_distances_for_template(
        template=template,
        event_indexes=np.asarray([0]),
        entry_prices=np.asarray([100.0]),
        high=np.asarray([101.0]),
        low=np.asarray([80.0]),
        atr=np.asarray([4.0]),
        min_stop_points=1.0,
        stop_buffer_atr=0.1,
        min_buffer_points=0.25,
    )

    assert distances[0] == 6.0


def test_reclaim_hold_requires_second_hold_bar() -> None:
    event_indexes = np.asarray([2])
    open_prices = np.arange(10, dtype=float) + 100.0
    high = open_prices + 1.0
    low = open_prices - 1.0
    close = open_prices.copy()
    low[3] = 99.0
    close[3] = 102.5
    close[4] = 103.0
    atr = np.full(10, 2.0)

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="reclaim_hold",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 5


def test_aggregate_walk_forward_dedupes_overlapping_selected_trades() -> None:
    folds = pd.DataFrame(
        [
            {
                "fold": 0,
                "template": "template_a",
                "feature_id": "feature_a",
                "family": "trend_start",
                "entry_mode": "next_open",
                "stop_mode": "atr",
                "reward_risk": 1.0,
                "horizon_minutes": 5,
                "test_net_points": 1.0,
                "train_research_score": 2.0,
            },
            {
                "fold": 1,
                "template": "template_a",
                "feature_id": "feature_a",
                "family": "trend_start",
                "entry_mode": "next_open",
                "stop_mode": "atr",
                "reward_risk": 1.0,
                "horizon_minutes": 5,
                "test_net_points": 1.0,
                "train_research_score": 2.0,
            },
        ]
    )
    selected = pd.DataFrame(
        [
            _selected_trade(fold=0, entry_index=10, net_points=3.0),
            _selected_trade(fold=1, entry_index=10, net_points=3.0),
            _selected_trade(fold=1, entry_index=20, net_points=-1.0),
        ]
    )

    aggregate = script.aggregate_walk_forward(folds, selected)

    assert len(aggregate) == 1
    row = aggregate.iloc[0]
    assert row["test_trades"] == 2.0
    assert row["test_net_points"] == 2.0
    assert row["selected_folds"] == 2


def test_template_pool_respects_explicit_feature_direction() -> None:
    market_features = {
        "feature_short": script.MarketFeature(
            feature_id="feature_short",
            family="trend_start",
            direction_hint="short",
            description="Synthetic short feature.",
            signal=pd.Series([False]),
        )
    }

    templates = script.template_pool(
        market_features,
        ["feature_short"],
        entry_modes=["next_open"],
        stop_modes=["atr"],
        reward_risks=[1.0],
        horizons=[5],
        confirm_bars=[1],
        pullback_atr=[0.25, 0.5],
        stop_atr_mult=[1.0, 2.0],
        exit_modes=["bracket"],
        fast_fail_bars=[5],
    )

    assert len(templates) == 2
    assert {template.direction for template in templates} == {-1}
    assert {template.stop_atr_mult for template in templates} == {1.0, 2.0}


def test_walk_forward_validate_selects_positive_train_template() -> None:
    trades_by_template = {
        "template_a": pd.DataFrame(
            [
                _trade_row("template_a", "2021-01-10", 5, 1.0),
                _trade_row("template_a", "2021-06-10", 6, 1.0),
                _trade_row("template_a", "2022-01-10", 7, 1.0),
            ]
        ),
        "template_b": pd.DataFrame(
            [
                _trade_row("template_b", "2021-01-10", 5, -1.0),
                _trade_row("template_b", "2021-06-10", 6, -1.0),
                _trade_row("template_b", "2022-01-10", 7, 1.0),
            ]
        ),
    }
    templates = [
        _template("template_a"),
        _template("template_b"),
    ]
    args = argparse.Namespace(
        walk_start_date="2022-01-01",
        end_date="2022-04-01",
        train_days=365,
        purge_days=0,
        test_days=30,
        step_days=30,
        min_train_trades=2,
        min_train_net_points=0.0,
        max_fold_candidates=1,
    )

    folds, aggregate, selected = script.walk_forward_validate(trades_by_template, templates, args)

    assert not folds.empty
    assert folds.iloc[0]["template"] == "template_a"
    assert not aggregate.empty
    assert not selected.empty


def _trade_frame() -> pd.DataFrame:
    close = np.asarray([100.0, 100.5, 101.0, 101.0, 102.0, 103.2, 103.5, 103.5, 103.5])
    open_price = np.r_[100.0, close[:-1]]
    high = np.maximum(open_price, close) + 0.25
    low = np.minimum(open_price, close) - 0.25
    high[5] = 103.5
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=len(close), freq="min", tz="UTC"),
            "symbol": ["NQH6"] * len(close),
            "Open": open_price,
            "High": high,
            "Low": low,
            "Close": close,
            "atr_30": np.full(len(close), 2.0),
        }
    )


def _selected_trade(*, fold: int, entry_index: int, net_points: float) -> dict[str, object]:
    return {
        "template": "template_a",
        "fold": fold,
        "fold_rank": 1,
        "entry_index": entry_index,
        "entry_ts": f"2022-01-01 00:{entry_index:02d}:00+00:00",
        "net_points": net_points,
        "exit_reason": "time",
    }


def _trade_row(template: str, entry_ts: str, entry_index: int, net_points: float) -> dict[str, object]:
    return {
        "template": template,
        "entry_ts": entry_ts,
        "entry_index": entry_index,
        "net_points": net_points,
        "exit_reason": "time",
    }


def _template(name: str) -> script.StrategyTemplate:
    return script.StrategyTemplate(
        name=name,
        feature_id="feature_a",
        family="trend_start",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=1.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="bracket",
    )
