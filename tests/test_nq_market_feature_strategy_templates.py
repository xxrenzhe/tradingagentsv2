from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "backtest_nq_market_feature_strategy_templates.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("backtest_nq_market_feature_strategy_templates", SCRIPT_PATH)
script = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["backtest_nq_market_feature_strategy_templates"] = script
SPEC.loader.exec_module(script)

PRESSURE_SCRIPT_PATH = SCRIPTS_DIR / "pressure_test_nq_ofs_candidates.py"
PRESSURE_SPEC = importlib.util.spec_from_file_location("pressure_test_nq_ofs_candidates", PRESSURE_SCRIPT_PATH)
pressure_script = importlib.util.module_from_spec(PRESSURE_SPEC)
assert PRESSURE_SPEC.loader is not None
sys.modules["pressure_test_nq_ofs_candidates"] = pressure_script
PRESSURE_SPEC.loader.exec_module(pressure_script)

SCREENSHOT_PRESSURE_SCRIPT_PATH = SCRIPTS_DIR / "pressure_test_nq_screenshot_smc_candidates.py"
SCREENSHOT_PRESSURE_SPEC = importlib.util.spec_from_file_location(
    "pressure_test_nq_screenshot_smc_candidates",
    SCREENSHOT_PRESSURE_SCRIPT_PATH,
)
screenshot_pressure_script = importlib.util.module_from_spec(SCREENSHOT_PRESSURE_SPEC)
assert SCREENSHOT_PRESSURE_SPEC.loader is not None
sys.modules["pressure_test_nq_screenshot_smc_candidates"] = screenshot_pressure_script
SCREENSHOT_PRESSURE_SPEC.loader.exec_module(screenshot_pressure_script)

LONG_TERM_AUDIT_SCRIPT_PATH = SCRIPTS_DIR / "audit_nq_long_term_strategy_candidates.py"
LONG_TERM_AUDIT_SPEC = importlib.util.spec_from_file_location(
    "audit_nq_long_term_strategy_candidates",
    LONG_TERM_AUDIT_SCRIPT_PATH,
)
long_term_audit_script = importlib.util.module_from_spec(LONG_TERM_AUDIT_SPEC)
assert LONG_TERM_AUDIT_SPEC.loader is not None
sys.modules["audit_nq_long_term_strategy_candidates"] = long_term_audit_script
LONG_TERM_AUDIT_SPEC.loader.exec_module(long_term_audit_script)


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


def test_context_filter_mask_uses_directional_vwap_and_volume_state() -> None:
    frame = _trade_frame()
    frame["session_vwap_distance_atr"] = [-0.5, -0.1, 0.2, 0.4, -0.2, 0.5, 0.3, -0.3, 0.1]
    frame["cmf_20"] = [-0.1, 0.2, -0.2, 0.1, -0.3, 0.2, 0.2, -0.2, 0.1]
    frame["mfi_14"] = [40, 55, 45, 60, 40, 55, 55, 45, 60]
    frame["obv_slope_20"] = [-1, 1, -1, 1, -1, 1, 1, -1, 1]

    long_mask = script.context_filter_mask(frame, "vwap_volume", 1)
    short_mask = script.context_filter_mask(frame, "vwap_volume", -1)

    assert bool(long_mask.iloc[3])
    assert not bool(long_mask.iloc[0])
    assert bool(short_mask.iloc[0])
    assert not bool(short_mask.iloc[3])


def test_build_template_trades_applies_context_filter_at_entry_index() -> None:
    frame = _trade_frame()
    frame["session_vwap_distance_atr"] = [-0.5, -0.5, -0.5, -0.1, 0.3, 0.3, 0.3, 0.3, 0.3]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="trend_start",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    blocked_template = script.StrategyTemplate(
        name="synthetic_long_blocked_context",
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
        context_filter="vwap_aligned",
        exit_mode="bracket",
    )
    allowed_template = script.StrategyTemplate(
        **{**blocked_template.__dict__, "name": "synthetic_long_allowed_context", "context_filter": "vwap_support"}
    )

    blocked = script.build_template_trades(frame, feature, blocked_template, min_gap_minutes=1, min_stop_points=1.0)
    allowed = script.build_template_trades(frame, feature, allowed_template, min_gap_minutes=1, min_stop_points=1.0)

    assert blocked.empty
    assert len(allowed) == 1
    assert allowed.iloc[0]["context_filter"] == "vwap_support"


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


def test_light_partial_exit_books_configured_fraction_then_runner_target() -> None:
    frame = _trade_frame()
    frame.loc[5:, "High"] = 105.5
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_light_partial",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="light_partial",
        partial_fraction=0.25,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "partial_target"
    assert row["partial_fraction"] == 0.25
    assert row["gross_points"] == pytest.approx(3.5)


def test_light_partial_exit_uses_structure_invalidation_for_runner() -> None:
    frame = _trade_frame()
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [103.0, 103.5, 102.75, 103.25]
    frame.loc[6, ["Open", "High", "Low", "Close"]] = [103.25, 103.4, 100.9, 100.6]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_light_partial_structure",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="light_partial",
        partial_fraction=0.25,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "partial_structure_invalidation"
    assert row["exit_index"] == 6
    assert row["gross_points"] == pytest.approx(0.2)


def test_light_partial_exits_on_structure_before_scale_out() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 101.2, 100.2, 100.4]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_light_partial_structure_before_scale",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="light_partial",
        partial_fraction=0.25,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "structure_invalidation"
    assert row["exit_index"] == 4
    assert row["gross_points"] == pytest.approx(-0.6)


def test_adaptive_bracket_exits_on_structure_invalidation_before_stop() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 101.2, 99.2, 99.6]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_adaptive_bracket",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="adaptive_bracket",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "structure_invalidation"
    assert row["exit_index"] == 4
    assert row["gross_points"] == pytest.approx(-1.4)


def test_adaptive_staged_protects_runner_at_breakeven_after_scale_out() -> None:
    frame = _trade_frame()
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [103.0, 103.5, 102.75, 103.25]
    frame.loc[6, ["Open", "High", "Low", "Close"]] = [103.25, 103.4, 100.9, 101.5]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_adaptive",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="adaptive",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "partial_breakeven"
    assert row["exit_index"] == 6
    assert row["gross_points"] == 1.0


def test_staged_breakeven_protects_runner_after_scale_out() -> None:
    frame = _trade_frame()
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [103.0, 103.5, 102.75, 103.25]
    frame.loc[6, ["Open", "High", "Low", "Close"]] = [103.25, 103.4, 100.9, 101.5]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_staged_breakeven",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="staged_breakeven",
        fast_fail_bars=0,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "partial_breakeven"
    assert row["exit_index"] == 6
    assert row["gross_points"] == 1.0


def test_breakeven_bracket_moves_stop_to_entry_after_progress() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 102.7, 100.9, 102.2]
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [102.2, 102.5, 100.7, 101.2]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_breakeven_bracket",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="breakeven_bracket",
        fast_fail_bars=0,
        breakeven_trigger_r=0.75,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "breakeven"
    assert row["exit_index"] == 5
    assert row["gross_points"] == 0.0


def test_protective_bracket_moves_stop_to_entry_after_progress() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 102.7, 100.9, 102.2]
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [102.2, 102.5, 100.7, 101.2]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_protective_bracket",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="protective_bracket",
        fast_fail_bars=0,
        breakeven_trigger_r=0.75,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "protected_stop"
    assert row["exit_index"] == 5
    assert row["gross_points"] == 0.0


def test_progress_bracket_exits_when_trade_does_not_advance_by_deadline() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 101.8, 100.8, 101.1]
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [101.1, 101.7, 100.9, 101.3]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_progress_bracket",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="progress_bracket",
        fast_fail_bars=2,
        breakeven_trigger_r=0.5,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "no_progress_exit"
    assert row["exit_index"] == 5
    assert row["gross_points"] == pytest.approx(0.3)


def test_progress_protective_bracket_keeps_trade_if_progress_happens_before_deadline() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 103.2, 100.9, 102.8]
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [102.8, 102.9, 100.8, 101.4]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_progress_protective_bracket",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="progress_protective_bracket",
        fast_fail_bars=2,
        breakeven_trigger_r=0.5,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "protected_stop"
    assert row["exit_index"] == 5
    assert row["gross_points"] == 0.0


def test_adaptive_bracket_exits_when_no_progress_after_entry() -> None:
    frame = _trade_frame()
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [101.0, 101.8, 100.4, 100.7]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Synthetic long event.",
        signal=pd.Series([index == 2 for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_adaptive_no_progress",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="atr",
        reward_risk=2.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=2.0,
        exit_mode="adaptive_bracket",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    row = trades.iloc[0]
    assert row["exit_reason"] == "no_progress_exit"
    assert row["exit_index"] == 4
    assert row["gross_points"] == pytest.approx(-0.3)


def test_adaptive_exit_handles_rows_removed_by_stop_distance_filter() -> None:
    frame = _trade_frame()
    frame.loc[2, "Low"] = 98.25
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [103.0, 103.5, 102.75, 103.25]
    feature = script.MarketFeature(
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction_hint="long",
        description="Two events, first removed because stop is too small.",
        signal=pd.Series([index in {1, 2} for index in range(len(frame))]),
    )
    template = script.StrategyTemplate(
        name="synthetic_long_adaptive_filter",
        feature_id="synthetic_long",
        family="ict_order_flow_shift",
        direction=1,
        entry_mode="next_open",
        stop_mode="event_mid",
        reward_risk=1.0,
        horizon_minutes=5,
        confirm_bars=1,
        pullback_atr=0.25,
        stop_atr_mult=1.0,
        exit_mode="adaptive_bracket",
        fast_fail_bars=2,
    )

    trades = script.build_template_trades(frame, feature, template, min_gap_minutes=1, min_stop_points=1.0)

    assert len(trades) == 1
    assert trades.iloc[0]["event_index"] == 2


def test_summary_tracks_adaptive_exit_reason_rates() -> None:
    trades = pd.DataFrame(
        {
            "net_points": [1.0, -1.0, -0.25, 0.5, 0.0, -0.5, 0.25, 0.0],
            "exit_reason": [
                "partial_breakeven",
                "structure_invalidation",
                "no_progress_exit",
                "partial_target",
                "breakeven",
                "partial_stop_loss",
                "partial_structure_invalidation",
                "protected_stop",
            ],
        }
    )

    summary = script.summarize_trades(trades)

    assert summary["structure_invalidation_exit_rate"] == pytest.approx(2 / 8)
    assert summary["no_progress_exit_rate"] == pytest.approx(1 / 8)
    assert summary["partial_breakeven_exit_rate"] == pytest.approx(1 / 8)
    assert summary["breakeven_exit_rate"] == pytest.approx(1 / 8)
    assert summary["protected_stop_exit_rate"] == pytest.approx(1 / 8)
    assert summary["partial_stop_loss_exit_rate"] == pytest.approx(1 / 8)
    assert summary["partial_structure_invalidation_exit_rate"] == pytest.approx(1 / 8)
    assert summary["stop_exit_rate"] == pytest.approx(1 / 8)


def test_reclaim_followthrough_requires_next_bar_break_after_reclaim() -> None:
    event_indexes = np.asarray([2, 6])
    open_prices = np.full(12, 100.0)
    high = np.full(12, 101.0)
    low = np.full(12, 99.0)
    close = np.full(12, 100.0)
    atr = np.full(12, 2.0)
    low[3] = 98.5
    close[3] = 100.7
    high[3] = 101.0
    close[4] = 101.4
    high[4] = 101.6
    low[7] = 98.5
    close[7] = 100.7
    high[7] = 101.0
    close[8] = 100.8

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="reclaim_followthrough",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 5
    assert np.isnan(entries[1])


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


def test_reclaim_break_enters_after_reclaim_bar_breaks() -> None:
    event_indexes = np.asarray([2, 6])
    open_prices = np.full(12, 100.0)
    high = np.full(12, 101.0)
    low = np.full(12, 99.0)
    close = np.full(12, 100.0)
    atr = np.full(12, 2.0)
    low[3] = 98.5
    close[3] = 100.7
    high[3] = 101.0
    close[4] = 101.3
    high[4] = 101.5
    low[7] = 98.5
    close[7] = 100.7
    high[7] = 101.0
    close[8] = 101.0

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="reclaim_break",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 5
    assert np.isnan(entries[1])


def test_strong_reclaim_break_requires_buffered_high_close_and_midpoint_hold() -> None:
    event_indexes = np.asarray([2, 6])
    open_prices = np.full(12, 100.0)
    high = np.full(12, 101.0)
    low = np.full(12, 99.0)
    close = np.full(12, 100.0)
    atr = np.full(12, 2.0)
    low[3] = 98.5
    high[3] = 101.0
    close[3] = 100.8
    open_prices[4] = 100.8
    low[4] = 100.7
    high[4] = 101.7
    close[4] = 101.55
    low[7] = 98.5
    high[7] = 101.0
    close[7] = 100.8
    open_prices[8] = 100.8
    low[8] = 100.4
    high[8] = 101.7
    close[8] = 101.2

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=1,
        entry_mode="strong_reclaim_break",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 5
    assert np.isnan(entries[1])


def test_reclaim_break_supports_short_direction() -> None:
    event_indexes = np.asarray([2])
    open_prices = np.full(8, 100.0)
    high = np.full(8, 101.0)
    low = np.full(8, 99.0)
    close = np.full(8, 100.0)
    atr = np.full(8, 2.0)
    high[3] = 102.5
    low[3] = 99.0
    close[3] = 99.4
    low[4] = 98.6
    close[4] = 98.8

    entries = script.resolve_entry_indexes(
        event_indexes=event_indexes,
        open_prices=open_prices,
        high=high,
        low=low,
        close=close,
        atr=atr,
        direction=-1,
        entry_mode="reclaim_break",
        confirm_bars=3,
        pullback_atr=0.25,
    )

    assert entries[0] == 5


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


def test_template_pool_only_expands_breakeven_trigger_for_relevant_exit_modes() -> None:
    market_features = {
        "feature_long": script.MarketFeature(
            feature_id="feature_long",
            family="ict_order_flow_shift",
            direction_hint="long",
            description="Synthetic long feature.",
            signal=pd.Series([False]),
        )
    }

    templates = script.template_pool(
        market_features,
        ["feature_long"],
        entry_modes=["next_open"],
        stop_modes=["atr"],
        reward_risks=[1.0],
        horizons=[5],
        confirm_bars=[1],
        pullback_atr=[0.25],
        stop_atr_mult=[1.0],
        exit_modes=["bracket", "breakeven_bracket", "protective_bracket"],
        fast_fail_bars=[3],
        breakeven_trigger_r=[0.6, 0.75, 1.0],
    )

    bracket = [template for template in templates if template.exit_mode == "bracket"]
    breakeven = [template for template in templates if template.exit_mode == "breakeven_bracket"]
    protective = [template for template in templates if template.exit_mode == "protective_bracket"]
    assert len(bracket) == 1
    assert len(breakeven) == 3
    assert len(protective) == 3
    assert {template.breakeven_trigger_r for template in breakeven} == {0.6, 0.75, 1.0}
    assert {template.breakeven_trigger_r for template in protective} == {0.6, 0.75, 1.0}


def test_template_pool_only_expands_partial_fraction_for_light_partial() -> None:
    market_features = {
        "feature_long": script.MarketFeature(
            feature_id="feature_long",
            family="ict_order_flow_shift",
            direction_hint="long",
            description="Synthetic long feature.",
            signal=pd.Series([False]),
        )
    }

    templates = script.template_pool(
        market_features,
        ["feature_long"],
        entry_modes=["next_open"],
        stop_modes=["atr"],
        reward_risks=[1.0],
        horizons=[5],
        confirm_bars=[1],
        pullback_atr=[0.25],
        stop_atr_mult=[1.0],
        exit_modes=["bracket", "light_partial"],
        fast_fail_bars=[3],
        partial_fractions=[0.25, 0.33],
    )

    bracket = [template for template in templates if template.exit_mode == "bracket"]
    light_partial = [template for template in templates if template.exit_mode == "light_partial"]
    assert len(bracket) == 1
    assert len(light_partial) == 2
    assert {template.partial_fraction for template in light_partial} == {0.25, 0.33}


def test_template_pool_expands_context_filters() -> None:
    market_features = {
        "feature_long": script.MarketFeature(
            feature_id="feature_long",
            family="ict_order_flow_shift",
            direction_hint="long",
            description="Synthetic long feature.",
            signal=pd.Series([False]),
        )
    }

    templates = script.template_pool(
        market_features,
        ["feature_long"],
        entry_modes=["next_open"],
        stop_modes=["atr"],
        reward_risks=[1.0],
        horizons=[5],
        confirm_bars=[1],
        pullback_atr=[0.25],
        stop_atr_mult=[1.0],
        context_filters=["all", "vwap_volume"],
        exit_modes=["bracket"],
        fast_fail_bars=[3],
    )

    assert len(templates) == 2
    assert {template.context_filter for template in templates} == {"all", "vwap_volume"}
    assert any("_ctxvwap_volume" in template.name for template in templates)


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


def test_pressure_cost_stress_recomputes_net_from_gross_points() -> None:
    trades = pd.DataFrame({"gross_points": [2.0, -1.0, 3.0]})
    costs = script.BacktestCosts()

    stress = pressure_script.cost_stress_summary(trades, costs, [1.0, 2.0])

    assert stress["cost_1x_net_points"] == pytest.approx(sum(trades["gross_points"] - costs.round_trip_cost_points))
    assert stress["cost_2x_net_points"] == pytest.approx(sum(trades["gross_points"] - 2 * costs.round_trip_cost_points))
    assert stress["cost_2x_profit_factor"] < stress["cost_1x_profit_factor"]


def test_pressure_yearly_and_rolling_summaries_use_entry_ts() -> None:
    template = pressure_script.candidate_specs()[0]
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(
                [
                    "2020-01-10",
                    "2020-02-10",
                    "2020-03-10",
                    "2020-04-10",
                    "2020-05-10",
                    "2021-01-10",
                    "2021-03-10",
                ],
                utc=True,
            ),
            "net_points": [3.0, -1.0, 1.5, 0.5, -0.25, 2.0, -0.5],
            "gross_points": [3.625, -0.375, 2.125, 1.125, 0.375, 2.625, 0.125],
            "exit_reason": ["take_profit", "stop_loss", "take_profit", "time", "stop_loss", "take_profit", "time"],
        }
    )

    yearly = pressure_script.yearly_summary(template, trades, [1.0], script.BacktestCosts())
    rolling = pressure_script.rolling_summary(template, trades, 180, 90)

    assert set(yearly["year"]) == {2020, 2021}
    assert yearly.loc[yearly["year"] == 2020, "net_points"].iloc[0] == pytest.approx(3.75)
    assert not rolling.empty
    assert {"start", "end", "net_points"}.issubset(rolling.columns)


def test_screenshot_pressure_candidates_cover_smc_momentum_readouts() -> None:
    templates = screenshot_pressure_script.candidate_specs()
    feature_ids = {template.feature_id for template in templates}
    families = {template.family for template in templates}

    assert len(templates) == 8
    assert "eql_sweep_macd_reversal_long_us_rth" in feature_ids
    assert "eqh_sweep_macd_reversal_short_us_rth" in feature_ids
    assert "displacement_pullback_continuation_long_us_rth" in feature_ids
    assert "displacement_pullback_continuation_short_us_rth" in feature_ids
    assert "bos_stair_step_continuation_long_us_rth" in feature_ids
    assert "bos_stair_step_continuation_short_us_rth" in feature_ids
    assert {"smc_liquidity_macd_reversal", "smc_displacement_pullback", "smc_bos_continuation"}.issubset(families)
    assert {template.direction for template in templates} == {-1, 1}


def test_screenshot_pressure_summaries_and_cost_stress_are_reproducible() -> None:
    template = screenshot_pressure_script.candidate_specs()[0]
    costs = script.BacktestCosts()
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(
                [
                    "2020-01-10",
                    "2020-02-10",
                    "2020-03-10",
                    "2020-04-10",
                    "2020-05-10",
                    "2021-01-10",
                    "2021-03-10",
                ],
                utc=True,
            ),
            "net_points": [2.0, -1.0, 3.0, -0.5, 1.0, 4.0, -1.5],
            "gross_points": [2.625, -0.375, 3.625, 0.125, 1.625, 4.625, -0.875],
            "exit_reason": ["take_profit", "stop_loss", "take_profit", "time", "take_profit", "take_profit", "stop_loss"],
        }
    )

    stress = screenshot_pressure_script.cost_stress_summary(trades, costs, [1.0, 3.0])
    yearly = screenshot_pressure_script.yearly_summary(template, trades)
    rolling = screenshot_pressure_script.rolling_summary(template, trades, 180, 90)

    assert stress["cost_1x_net_points"] == pytest.approx(sum(trades["gross_points"] - costs.round_trip_cost_points))
    assert stress["cost_3x_profit_factor"] < stress["cost_1x_profit_factor"]
    assert set(yearly["year"]) == {2020, 2021}
    assert yearly.loc[yearly["year"] == 2020, "net_points"].iloc[0] == pytest.approx(4.5)
    assert not rolling.empty
    assert {"template", "start", "end", "net_points"}.issubset(rolling.columns)


def test_long_term_audit_includes_regime_ofs_and_screenshot_pools() -> None:
    years = list(range(2016, 2026))
    regime_summary = pd.DataFrame(
        {
            "label": ["regime_a"],
            "candidate": ["regime_breakout"],
            "years": [10],
            "trades": [500],
            "net_points": [2500.0],
            "net_dollars": [50000.0],
            "profit_factor": [1.5],
            "win_rate": [0.42],
            "payoff_ratio": [2.1],
            "expectancy_points": [5.0],
            "max_drawdown_points": [250.0],
            "net_to_drawdown": [10.0],
            "positive_year_rate": [0.8],
            "worst_year_points": [-50.0],
            "positive_90d_rate": [0.6],
            "worst_90d_points": [-75.0],
            "positive_180d_rate": [0.7],
            "worst_180d_points": [-100.0],
            "net_at_cost_2.125": [1700.0],
            "net_at_cost_3.125": [1200.0],
        }
    )
    regime_yearly = pd.DataFrame({"label": ["regime_a"] * 10, "year": years, "trades": [50] * 10, "net_points": [250.0] * 10})
    regime_rolling = pd.DataFrame(
        {
            "label": ["regime_a"] * 3,
            "start": ["2020-01-01", "2020-04-01", "2020-07-01"],
            "end": ["2020-03-31", "2020-06-30", "2020-09-30"],
            "trades": [20, 20, 20],
            "net_points": [100.0, -20.0, 120.0],
        }
    )
    ofs_summary = _template_summary("ofs_a", year_count=7, trades=350, net_points=1000.0, profit_factor=1.2)
    ofs_yearly = _template_yearly("ofs_a")
    ofs_rolling = _template_rolling("ofs_a")
    screenshot_summary = _template_summary(
        "screenshot_a",
        year_count=7,
        trades=370,
        net_points=650.0,
        profit_factor=1.14,
        family="smc_liquidity_macd_reversal",
    )
    screenshot_yearly = _template_yearly("screenshot_a")
    screenshot_rolling = _template_rolling("screenshot_a")

    audit, yearly, rolling = long_term_audit_script.build_candidate_audit(
        regime_summary=regime_summary,
        regime_yearly=regime_yearly,
        regime_rolling90=regime_rolling,
        regime_rolling180=regime_rolling,
        ofs_summary=ofs_summary,
        ofs_yearly=ofs_yearly,
        ofs_rolling=ofs_rolling,
        screenshot_summary=screenshot_summary,
        screenshot_yearly=screenshot_yearly,
        screenshot_rolling=screenshot_rolling,
        config=long_term_audit_script.AuditConfig(min_sample_years=10),
        base_cost_points=0.625,
    )

    assert set(audit["strategy_source"]) == {"regime_transition", "ict_order_flow_shift", "screenshot_smc_momentum"}
    assert set(yearly["strategy_source"]) == {"regime_transition", "ict_order_flow_shift", "screenshot_smc_momentum"}
    assert set(rolling["strategy_source"]) == {"regime_transition", "ict_order_flow_shift", "screenshot_smc_momentum"}
    regime = audit[audit["strategy_source"] == "regime_transition"].iloc[0]
    screenshot = audit[audit["strategy_source"] == "screenshot_smc_momentum"].iloc[0]
    assert bool(regime["long_term_research_pass"])
    assert not bool(screenshot["long_term_research_pass"])
    assert "sample_years" in screenshot["research_blockers"]


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


def _template_summary(
    template: str,
    *,
    year_count: int,
    trades: int,
    net_points: float,
    profit_factor: float,
    family: str = "ict_order_flow_shift",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "template": [template],
            "name": [template],
            "family": [family],
            "year_count": [year_count],
            "trades": [trades],
            "net_points": [net_points],
            "profit_factor": [profit_factor],
            "win_rate": [0.5],
            "payoff_ratio": [1.1],
            "expectancy_points": [net_points / trades],
            "max_drawdown_points": [300.0],
            "positive_year_rate": [0.8],
            "min_year_net_points": [-50.0],
            "positive_rolling_rate": [0.75],
            "min_rolling_net_points": [-100.0],
        }
    )


def _template_yearly(template: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "template": [template] * 7,
            "year": list(range(2020, 2027)),
            "trades": [50] * 7,
            "net_points": [100.0, 120.0, 80.0, -50.0, 160.0, 200.0, -20.0],
        }
    )


def _template_rolling(template: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "template": [template] * 4,
            "start": ["2020-01-01", "2020-07-01", "2021-01-01", "2021-07-01"],
            "end": ["2020-06-30", "2020-12-31", "2021-06-30", "2021-12-31"],
            "trades": [20, 20, 20, 20],
            "net_points": [120.0, -100.0, 140.0, 160.0],
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
