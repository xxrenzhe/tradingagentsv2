from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_nq_pine_indicator_combinations.py"
SPEC = importlib.util.spec_from_file_location("search_nq_pine_indicator_combinations", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_macd_hist_repair_enters_before_line_cross() -> None:
    frame = pd.DataFrame(
        {
            "mtf60_macd_hist": [-3.0, -2.0, -1.0],
            "mtf60_hist_delta": [pd.NA, 1.0, 1.0],
            "mtf60_macd_above_signal": [False, False, False],
            "mtf60_macd_below_signal": [True, True, True],
        }
    )

    mask = MODULE._macd_filter_mask(frame, 1, timeframe=60, filter_name="hist_repair")

    assert mask.tolist() == [False, True, True]
    assert not frame["mtf60_macd_above_signal"].any()


def test_score_penalizes_tiny_samples_below_robust_candidate() -> None:
    tiny = {
        "trades": 5,
        "net_points": 135.0,
        "profit_factor": 6.5,
        "win_rate": 0.8,
        "avg_points": 27.0,
        "max_drawdown_points": 24.0,
        "worst_trade_points": -24.0,
    }
    robust = {
        "trades": 218,
        "net_points": 1732.0,
        "profit_factor": 2.05,
        "win_rate": 0.55,
        "avg_points": 7.94,
        "max_drawdown_points": 133.5,
        "worst_trade_points": -109.0,
    }

    assert MODULE.score_summary(robust) > MODULE.score_summary(tiny)


def test_build_combo_specs_includes_screenshot_fast_reversal_and_hist_repair() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [60],
            "macd_filters": ["hist_repair"],
            "stop_atr_buffers": [0.8],
            "target_rs": [1.2],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    names = {spec.name for spec in specs}

    assert any("screenshot_reversal_macd60_hist_repair" in name for name in names)
    assert any("fast_boundary_reversal_macd60_hist_repair" in name for name in names)


def test_phase_trend_families_are_bidirectional() -> None:
    assert MODULE.FAMILY_DIRECTIONS["phase_up_breakout_long"] == 1
    assert MODULE.FAMILY_DIRECTIONS["phase_up_pullback_long"] == 1
    assert MODULE.FAMILY_DIRECTIONS["phase_down_breakdown_short"] == -1
    assert MODULE.FAMILY_DIRECTIONS["phase_down_pullback_short"] == -1
    assert MODULE.FAMILY_DIRECTIONS["trend_pullback_short_asia_europe"] == -1
    assert MODULE.FAMILY_DIRECTIONS["trend_transition_short_asia_rth"] == -1
    assert MODULE.FAMILY_DIRECTIONS["trend_transition_short_asia"] == -1
    assert MODULE.FAMILY_TARGET_BASE["trend_pullback_short_asia_europe"] == "trend_pullback_short"
    assert MODULE.FAMILY_TARGET_BASE["trend_transition_short_asia_rth"] == "trend_transition_short"
    assert MODULE.FAMILY_TARGET_BASE["trend_transition_short_asia"] == "trend_transition_short"


def test_build_combo_specs_includes_bidirectional_phase_trend() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [60],
            "macd_filters": ["hist_deceleration"],
            "stop_atr_buffers": [0.8],
            "target_rs": [1.8],
            "max_hold_bars_grid": [60],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    phase_specs = [spec for spec in specs if spec.name.startswith("phase_trend_macd60_hist_deceleration")]

    assert len(phase_specs) == 1
    assert phase_specs[0].families == (
        "phase_up_breakout_long",
        "phase_up_pullback_long",
        "phase_down_breakdown_short",
        "phase_down_pullback_short",
    )


def test_build_combo_specs_includes_selective_bidirectional_families() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [1],
            "macd_filters": ["cross_recent_5"],
            "stop_atr_buffers": [1.25],
            "target_rs": [2.5],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    spec_by_name = {spec.name: spec for spec in specs}
    selective = spec_by_name["selective_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]
    core = spec_by_name["selective_bidirectional_core_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]

    assert "top_reject_short" not in selective.families
    assert "reversal_impulse_short" not in selective.families
    assert {
        "top_breakout_long",
        "trend_ignition_long",
        "trend_pullback_long",
        "trend_transition_long",
        "reversal_impulse_long",
        "bottom_breakdown_short",
        "trend_pullback_short",
        "trend_transition_short",
    }.issubset(selective.families)
    assert "trend_ignition_long" not in core.families
    assert "reversal_impulse_long" not in core.families


def test_build_combo_specs_includes_session_gated_selective_bidirectional() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [1],
            "macd_filters": ["cross_recent_5"],
            "stop_atr_buffers": [1.25],
            "target_rs": [2.5],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    spec_by_name = {spec.name: spec for spec in specs}
    selective = spec_by_name["selective_bidirectional_session_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]

    assert "trend_pullback_short" not in selective.families
    assert "trend_transition_short" not in selective.families
    assert "trend_pullback_short_asia_europe" in selective.families
    assert "trend_transition_short_asia_rth" in selective.families

    strict = spec_by_name["selective_bidirectional_strict_short_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]
    assert "trend_transition_short_asia" in strict.families
    assert "trend_transition_short_asia_rth" not in strict.families

    reversal_long = spec_by_name["selective_bidirectional_strict_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]
    assert "bottom_reclaim_long" in reversal_long.families
    assert "fast_reversal_long" in reversal_long.families
    assert "smc_discount_choch_long" in reversal_long.families
    assert "top_reject_short" not in reversal_long.families
    assert "fast_reversal_short" not in reversal_long.families


def test_all_lightglow_excludes_session_gated_aliases() -> None:
    assert "trend_pullback_short_asia_europe" not in MODULE.ALL_LIGHTGLOW_BASE_FAMILIES
    assert "trend_transition_short_asia_rth" not in MODULE.ALL_LIGHTGLOW_BASE_FAMILIES
    assert "trend_transition_short_asia" not in MODULE.ALL_LIGHTGLOW_BASE_FAMILIES


def test_build_combo_specs_includes_smc_filtered_families() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [1],
            "macd_filters": ["cross_recent_5"],
            "stop_atr_buffers": [1.25],
            "target_rs": [2.5],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    spec_by_name = {spec.name: spec for spec in specs}
    smc = spec_by_name["smc_strict_bidirectional_macd1_cross_recent_5_stop1.25_r2.5_h30_norisk"]

    assert MODULE.FAMILY_DIRECTIONS["smc_discount_choch_long"] == 1
    assert MODULE.FAMILY_DIRECTIONS["smc_premium_choch_short"] == -1
    assert MODULE.FAMILY_TARGET_BASE["smc_ob_retest_long"] == "trend_pullback_long"
    assert MODULE.FAMILY_TARGET_BASE["smc_bos_fvg_short"] == "trend_transition_short"
    assert "smc_trend_transition_long" in smc.families
    assert "smc_trend_transition_short" in smc.families


def test_build_combo_specs_includes_structure_rr_entry_modes() -> None:
    args = type(
        "Args",
        (),
        {
            "macd_timeframes": [1],
            "macd_filters": ["cross_recent_5"],
            "stop_atr_buffers": [1.25],
            "target_rs": [2.5],
            "max_hold_bars_grid": [30],
            "risk_control_modes": [False],
        },
    )()

    specs = MODULE.build_combo_specs(args)
    spec_by_name = {spec.name: spec for spec in specs}
    structure = spec_by_name["structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk"]

    assert structure.entry_mode == "structure_rr"
    assert structure.min_structure_rr == 2.0
    assert structure.entry_wait_bars == 8
    assert "trend_pullback_short_asia_europe" in structure.families
    assert "trend_transition_short_asia" in structure.families

    filtered = spec_by_name["structure_filter_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1.5_norisk"]
    assert filtered.entry_mode == "structure_filter"
    assert filtered.min_structure_rr == 1.5
    assert filtered.entry_wait_bars == 0
    assert "trend_pullback_short_asia_europe" in filtered.families
    assert "trend_transition_short_asia" in filtered.families

    adaptive = spec_by_name["structure_adaptive_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1.7_wait3_norisk"]
    assert adaptive.entry_mode == "structure_adaptive"
    assert adaptive.min_structure_rr == 1.7
    assert adaptive.entry_wait_bars == 3
    assert "trend_pullback_short_asia_europe" in adaptive.families
    assert "trend_transition_short_asia" in adaptive.families

    micro = spec_by_name["structure_micro_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1.25_wait3_norisk"]
    assert micro.entry_mode == "structure_micro_rr"
    assert micro.min_structure_rr == 1.25
    assert micro.entry_wait_bars == 3
    assert "trend_pullback_short_asia_europe" in micro.families
    assert "trend_transition_short_asia" in micro.families

    risk_cap = spec_by_name["structure_risk_cap_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_cap2.5atr_norisk"]
    assert risk_cap.entry_mode == "structure_risk_cap"
    assert risk_cap.risk_cap_atr == 2.5
    assert risk_cap.entry_wait_bars == 0
    assert "trend_pullback_short_asia_europe" in risk_cap.families
    assert "trend_transition_short_asia" in risk_cap.families

    risk_cap_reversal = spec_by_name["structure_risk_cap_selective_strict_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h30_cap3.5atr_norisk"]
    assert risk_cap_reversal.entry_mode == "structure_risk_cap"
    assert risk_cap_reversal.risk_cap_atr == 3.5
    assert "bottom_reclaim_long" in risk_cap_reversal.families
    assert "fast_reversal_long" in risk_cap_reversal.families
    assert "smc_discount_choch_long" in risk_cap_reversal.families
    assert "fast_reversal_short" not in risk_cap_reversal.families

    balanced = spec_by_name["selective_yield_balanced_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h30_maxr4_trail1.2x2_be1.5_norisk"]
    assert balanced.entry_mode == "next_open"
    assert balanced.max_target_r == 4.0
    assert balanced.trail_start_r == 1.2
    assert balanced.trail_atr_mult == 2.0
    assert balanced.breakeven_trigger_r == 1.5
    assert "smc_discount_choch_long" in balanced.families

    growth = spec_by_name["selective_yield_growth_reversal_long_macd1_cross_recent_5_stop1.25_r2.75_h40_maxr3_trail1.2x3_be1.5_norisk"]
    assert growth.target_r == 2.75
    assert growth.max_hold_bars == 40
    assert growth.trail_atr_mult == 3.0

    cap_growth = spec_by_name["structure_risk_cap_yield_growth_reversal_long_macd1_cross_recent_5_stop1.25_r2.75_h45_maxr3_trail2x3_be1.5_cap3.5atr_norisk"]
    assert cap_growth.entry_mode == "structure_risk_cap"
    assert cap_growth.risk_cap_atr == 3.5
    assert cap_growth.max_hold_bars == 45

    exit_lock = spec_by_name["selective_exit_lock_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h30_maxr4_trail1.2x2_be1.5_lock1.5to1r_norisk"]
    assert exit_lock.giveback_start_r == 1.5
    assert exit_lock.giveback_keep_r == 1.0
    assert exit_lock.time_stop_bars == 0
    assert not exit_lock.avoid_loss_clusters

    cluster_filter = spec_by_name["selective_exit_lock_cluster_filter_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h30_maxr4_trail1.2x2_be1.5_lock1.5to1r_norisk"]
    assert cluster_filter.giveback_start_r == 1.5
    assert cluster_filter.giveback_keep_r == 1.0
    assert cluster_filter.avoid_loss_clusters

    adverse_guard = spec_by_name["selective_adverse_guard_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h35_maxr4_trail1.2x2_be1.5_lock1.5to1r_adverse_exit0.25r_norisk"]
    assert not adverse_guard.target_runner
    assert adverse_guard.adverse_reversal_exit
    assert adverse_guard.adverse_exit_max_r == 0.25

    runner_exit = spec_by_name["selective_runner_reversal_exit_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h45_maxr4_trail1.2x2_be1.5_lock1.5to1r_runner_adverse_exit0.25r_norisk"]
    assert runner_exit.target_runner
    assert runner_exit.adverse_reversal_exit
    assert runner_exit.adverse_exit_max_r == 0.25

    long_runner = spec_by_name["selective_long_runner_adverse_guard_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h35_maxr4_trail1.2x2_be1.5_lock1.5to1r_runner_adverse_exit0.25r_norisk"]
    assert long_runner.target_runner
    assert long_runner.target_runner_families == ("trend_transition_long", "trend_pullback_long")

    quality = spec_by_name["selective_adverse_guard_smc_volume_guard_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h35_maxr4_trail1.2x2_be1.5_lock1.5to1r_adverse_exit0.25r_norisk"]
    assert quality.entry_quality_filter == "smc_volume_guard"
    assert quality.adverse_reversal_exit

    time_stop = spec_by_name["structure_risk_cap_exit_time_reversal_long_macd1_cross_recent_5_stop1.25_r2.75_h45_maxr3_trail2x3_be1.5_cap3.5atr_tstop20b0.5r_lock2to0.5r_adverse_exit0.25r_norisk"]
    assert time_stop.entry_mode == "structure_risk_cap"
    assert time_stop.time_stop_bars == 20
    assert time_stop.time_stop_min_r == 0.5
    assert time_stop.giveback_start_r == 2.0
    assert time_stop.giveback_keep_r == 0.5
    assert time_stop.adverse_reversal_exit


def test_adaptive_structure_plan_uses_historical_structure_only() -> None:
    frame = pd.DataFrame(
        {
            "Low": [100.0, 101.0, 102.0, 103.0, 150.0],
            "High": [110.0, 111.0, 112.0, 113.0, 170.0],
        }
    )

    plan = MODULE._adaptive_structure_plan(
        frame,
        signal_index=3,
        direction=1,
        family="trend_pullback_long",
        entry_price=104.0,
        active_atr=4.0,
        min_structure_rr=1.4,
        wait_bars=0,
    )

    assert plan is not None
    assert plan["structure_stop"] < 100.0
    assert plan["structure_target"] < 130.0


def test_micro_structure_plan_uses_signal_bar_structure_only() -> None:
    frame = pd.DataFrame(
        {
            "Low": [100.0, 101.0, 102.0, 103.0, 150.0],
            "High": [106.0, 107.0, 108.0, 109.0, 180.0],
            "range_high": [120.0, 120.0, 120.0, 120.0, 300.0],
            "range_low": [98.0, 98.0, 98.0, 98.0, 90.0],
        }
    )
    config = MODULE.BoundaryLightglowConfig(target_r=2.5, max_target_r=3.0)

    plan = MODULE._micro_structure_plan(
        frame,
        config,
        signal_index=3,
        direction=1,
        family="trend_pullback_long",
        entry_price=105.0,
        active_atr=4.0,
        min_structure_rr=1.0,
        wait_bars=0,
    )

    assert plan is not None
    assert plan["structure_stop"] < 100.0
    assert plan["structure_target"] < 200.0


def _minimal_combo_frame(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=rows, freq="min", tz="UTC"),
            "symbol": ["NQH6"] * rows,
            "Open": [100.0] * rows,
            "High": [101.0] * rows,
            "Low": [99.0] * rows,
            "Close": [100.0] * rows,
            "atr": [4.0] * rows,
            "range_high": [float("nan")] * rows,
            "range_low": [float("nan")] * rows,
            "session": ["asia"] * rows,
            "trade_date": [pd.Timestamp("2026-01-01").date()] * rows,
            "lg_trend_transition_long": [False] * rows,
            "lg_trend_transition_short_asia": [False] * rows,
            "strong_trend_continuation_long": [False] * rows,
            "strong_trend_continuation_short": [False] * rows,
            "adverse_reversal_long": [False] * rows,
            "adverse_reversal_short": [False] * rows,
        }
    )


def test_target_runner_skips_fixed_target_after_prior_strong_trend_confirmation() -> None:
    frame = _minimal_combo_frame(7)
    frame.loc[0, "lg_trend_transition_long"] = True
    frame.loc[0, ["Low", "High", "Close"]] = [99.0, 101.0, 100.5]
    frame.loc[1, ["Open", "High", "Low", "Close"]] = [100.0, 101.0, 99.5, 100.5]
    frame.loc[2, ["Open", "High", "Low", "Close", "strong_trend_continuation_long"]] = [104.0, 110.0, 103.5, 109.5, True]
    frame.loc[3, ["Open", "High", "Low", "Close"]] = [110.0, 116.0, 107.0, 115.0]
    frame.loc[4, ["Open", "High", "Low", "Close"]] = [115.0, 124.0, 116.0, 123.0]
    frame.loc[5, ["Open", "High", "Low", "Close"]] = [118.0, 118.5, 115.0, 117.0]
    frame.loc[6, ["Open", "High", "Low", "Close"]] = [117.0, 119.0, 116.0, 118.0]

    spec = MODULE.ComboSpec(
        name="runner",
        families=("trend_transition_long",),
        macd_filter="none",
        macd_timeframe=1,
        stop_atr_buffer=1.25,
        target_r=2.5,
        max_hold_bars=6,
        use_risk_controls=False,
        target_runner=True,
        giveback_start_r=1.5,
        giveback_keep_r=1.0,
    )
    config = MODULE.BoundaryLightglowConfig(stop_atr_buffer=1.25, target_r=2.5, max_hold_bars=6)

    trades = MODULE.backtest_combo_fast(frame, spec, config, MODULE.pine_default_costs())

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "protective_stop"
    assert trades.iloc[0]["gross_points"] > 15.0


def test_adverse_reversal_exit_cuts_short_before_original_stop() -> None:
    frame = _minimal_combo_frame(6)
    frame.loc[0, "lg_trend_transition_short_asia"] = True
    frame.loc[0, ["High", "Low", "Close"]] = [101.0, 99.0, 99.5]
    frame.loc[1, ["Open", "High", "Low", "Close"]] = [100.0, 100.5, 99.0, 99.5]
    frame.loc[2, ["Open", "High", "Low", "Close"]] = [99.0, 99.5, 93.0, 94.0]
    frame.loc[3, ["Open", "High", "Low", "Close", "adverse_reversal_short"]] = [94.0, 103.5, 93.5, 102.0, True]

    spec = MODULE.ComboSpec(
        name="adverse",
        families=("trend_transition_short_asia",),
        macd_filter="none",
        macd_timeframe=1,
        stop_atr_buffer=1.25,
        target_r=2.5,
        max_hold_bars=5,
        use_risk_controls=False,
        adverse_reversal_exit=True,
    )
    config = MODULE.BoundaryLightglowConfig(stop_atr_buffer=1.25, target_r=2.5, max_hold_bars=5)

    trades = MODULE.backtest_combo_fast(frame, spec, config, MODULE.pine_default_costs())

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "adverse_reversal"
    assert trades.iloc[0]["exit_price"] == 102.0


def test_entry_quality_filter_uses_signal_bar_features() -> None:
    frame = pd.DataFrame(
        {
            "range_pos": [0.2, 0.8, 0.1],
            "volume_z": [-0.1, 1.0, 0.5],
            "body_atr": [0.5, 0.5, 0.5],
            "compression_width_atr": [3.0, 3.0, 3.0],
            "momentum": [1.0, 1.0, 1.0],
            "ts": pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC"),
            "session": ["asia", "us_rth", "europe"],
            "ema60": [100.0, 100.0, 100.0],
            "ema200": [101.0, 99.0, 99.0],
        }
    )

    assert not MODULE._passes_entry_quality_filter(frame, 0, "smc_discount_choch_long", "smc_volume_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "smc_discount_choch_long", "weak_hour_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 1, "bottom_reclaim_long", "reversal_quality_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 1, "bottom_reclaim_long", "reversal_loose_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 1, "trend_pullback_long", "pullback_quality_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 1, "trend_transition_long", "weak_ttl_session_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 2, "trend_pullback_long", "weak_family_session_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 2, "smc_discount_choch_long", "weak_combo2_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 2, "trend_pullback_long", "weak_hour_family_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "smc_discount_choch_long", "weak_loss_cluster_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "trend_transition_long", "weak_loss_cluster_ttl_asia_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "trend_transition_short_asia", "weak_loss_cluster_broad_hour_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 2, "bottom_reclaim_long", "weak_loss_cluster_strict_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "trend_transition_long", "weak_loss_cluster_ultra_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "bottom_reclaim_long", "weak_loss_cluster_ultra_plus_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "trend_pullback_long", "ultra_plus_trend_regime_guard")
    assert not MODULE._passes_entry_quality_filter(frame, 0, "trend_transition_long", "ultra_plus_selective_regime_guard")
    assert MODULE._passes_entry_quality_filter(frame, 2, "bottom_reclaim_long", "reversal_quality_guard")
