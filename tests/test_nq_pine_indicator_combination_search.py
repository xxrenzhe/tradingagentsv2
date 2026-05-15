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
