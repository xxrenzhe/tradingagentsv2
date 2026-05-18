from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backtest_nq_boundary_lightglow_strategy.py"
SPEC = importlib.util.spec_from_file_location("backtest_nq_boundary_lightglow_strategy", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _frame_with_manual_signals() -> pd.DataFrame:
    rows = []
    for index in range(20):
        price = 100.0 + index
        rows.append(
            {
                "ts": pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(minutes=index),
                "trade_date": pd.Timestamp("2020-01-01").date(),
                "symbol": "NQH0",
                "Open": price,
                "High": price + 4.0,
                "Low": price - 1.0,
                "Close": price + 2.0,
                "Volume": 10,
                "atr": 2.0,
                "range_high": price + 12.0,
                "range_low": price - 12.0,
                "session": "us_rth",
                "signal_family": "",
                "signal_direction": 0,
            }
        )
    frame = pd.DataFrame(rows)
    frame.loc[1, "signal_family"] = "trend_transition_long"
    frame.loc[1, "signal_direction"] = 1
    return frame


def test_backtest_uses_next_bar_open_and_records_signal_family() -> None:
    frame = _frame_with_manual_signals()
    config = MODULE.BoundaryLightglowConfig(
        cooldown_bars=0,
        max_hold_bars=5,
        min_hold_bars_before_target_exit=1,
        target_r=1.0,
        max_target_r=1.0,
        trail_start_r=5.0,
    )

    trades = MODULE.backtest_strategy(frame, config, BacktestCosts())

    assert len(trades) == 1
    assert trades["signal_family"].iloc[0] == "trend_transition_long"
    assert trades["entry_ts"].iloc[0] == frame["ts"].iloc[2]
    assert trades["entry_price"].iloc[0] == frame["Open"].iloc[2]
    assert trades["target_plan"].iloc[0] in {"trend_range_target", "fixed_r"}


def test_bracket_is_not_active_on_entry_fill_bar_like_pine_default() -> None:
    frame = _frame_with_manual_signals()
    frame.loc[2, "Low"] = 50.0
    frame.loc[2, "High"] = 150.0
    frame.loc[3, "Low"] = 103.0
    frame.loc[3, "High"] = 120.0
    config = MODULE.BoundaryLightglowConfig(
        cooldown_bars=0,
        max_hold_bars=5,
        min_hold_bars_before_target_exit=0,
        target_r=1.0,
        max_target_r=1.0,
        trail_start_r=5.0,
    )

    trades = MODULE.backtest_strategy(frame, config, BacktestCosts(slippage_ticks_per_side=0, commission_per_contract=0))

    assert len(trades) == 1
    assert trades["entry_ts"].iloc[0] == frame["ts"].iloc[2]
    assert trades["exit_ts"].iloc[0] != frame["ts"].iloc[2]


def test_atr_matches_tradingview_rma_definition() -> None:
    high = pd.Series([11.0, 13.0, 14.0, 15.0, 16.0])
    low = pd.Series([9.0, 10.0, 12.0, 13.0, 12.0])
    close = pd.Series([10.0, 12.0, 13.0, 14.0, 13.0])

    atr = MODULE._atr(high, low, close, length=3)

    true_ranges = pd.Series([2.0, 3.0, 2.0, 2.0, 4.0])
    expected = true_ranges.ewm(alpha=1 / 3, adjust=False, min_periods=3).mean()
    pd.testing.assert_series_equal(atr, expected)


def test_pine_default_costs_match_strategy_header() -> None:
    costs = MODULE.pine_default_costs()

    assert costs.slippage_ticks_per_side == 2.0
    assert costs.commission_per_contract == 10.0
    assert costs.round_trip_cost_points == 1.5


def test_boundary_config_uses_wider_top_breakout_stop_buffer_by_default() -> None:
    config = MODULE.BoundaryLightglowConfig()

    assert config.stop_atr_buffer == 1.25
    assert config.breakeven_trigger_r == 1.50
    assert config.trail_atr_mult == 2.00
    assert config.max_hold_bars == 120


def test_build_signals_defaults_to_core_databento_validated_cells() -> None:
    rows = []
    for index in range(140):
        ts = pd.Timestamp("2020-01-01", tz="UTC") + pd.Timedelta(minutes=index)
        session = "us_rth" if index == 100 else "us_late" if index == 110 else "europe"
        rows.append(
            {
                "ts": ts,
                "Open": 100 + index * 0.1,
                "High": 101 + index * 0.1,
                "Low": 99 + index * 0.1,
                "Close": 100.5 + index * 0.1,
                "Volume": 1000,
                "symbol": "NQH0",
                "trade_date": ts.date(),
                "session": session,
            }
        )
    frame = pd.DataFrame(rows)
    config = MODULE.BoundaryLightglowConfig()
    features = MODULE.build_signals(MODULE.add_features(frame, config), config)

    assert set(features.loc[features["signal_direction"].ne(0), "signal_family"].unique()) <= {
        "top_breakout_long",
        "trend_ignition_long",
    }


def test_parse_args_supports_skipping_python_only_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["backtest", "--skip-diagnostics"])

    args = MODULE.parse_args()

    assert args.skip_diagnostics is True


def test_select_enabled_families_requires_train_quality() -> None:
    trades = pd.DataFrame(
        [
            {"signal_family": "good", "net_points": 10.0},
            {"signal_family": "good", "net_points": -2.0},
            {"signal_family": "good", "net_points": 8.0},
            {"signal_family": "bad", "net_points": -5.0},
            {"signal_family": "bad", "net_points": 1.0},
            {"signal_family": "bad", "net_points": -1.0},
        ]
    )

    enabled = MODULE.select_enabled_families(trades, min_trades=3, min_pf=1.2, min_avg=0.0)

    assert enabled == {"good"}


def test_select_enabled_family_sessions_requires_cell_quality() -> None:
    trades = pd.DataFrame(
        [
            {"signal_family": "good", "session": "us_rth", "net_points": 10.0},
            {"signal_family": "good", "session": "us_rth", "net_points": -2.0},
            {"signal_family": "good", "session": "us_rth", "net_points": 8.0},
            {"signal_family": "good", "session": "asia", "net_points": -4.0},
            {"signal_family": "good", "session": "asia", "net_points": 1.0},
            {"signal_family": "good", "session": "asia", "net_points": -1.0},
        ]
    )

    enabled = MODULE.select_enabled_family_sessions(trades, min_trades=3, min_pf=1.2, min_avg=0.0)

    assert enabled == {("good", "us_rth")}


def test_group_summary_reports_drawdown_and_worst_trade() -> None:
    trades = pd.DataFrame(
        [
            {"signal_family": "x", "net_points": 5.0},
            {"signal_family": "x", "net_points": -7.0},
            {"signal_family": "x", "net_points": 3.0},
        ]
    )

    summary = MODULE.group_summary(trades, ["signal_family"])

    assert summary["trades"].iloc[0] == 3
    assert summary["worst_trade_points"].iloc[0] == -7.0
    assert summary["max_drawdown_points"].iloc[0] >= 7.0


def test_backtest_can_filter_by_family_session_without_family_allowlist() -> None:
    frame = _frame_with_manual_signals()
    frame.loc[1, "session"] = "us_rth"
    config = MODULE.BoundaryLightglowConfig(cooldown_bars=0, max_hold_bars=2, min_hold_bars_before_target_exit=1)

    trades = MODULE.backtest_strategy(
        frame,
        config,
        BacktestCosts(),
        enabled_family_sessions={("trend_transition_long", "us_rth")},
    )

    assert len(trades) == 1


def test_select_enabled_from_independent_cells_uses_train_rows_only() -> None:
    cells = pd.DataFrame(
        [
            {
                "signal_family": "trend_pullback_long",
                "session": "us_late",
                "period": "train",
                "trades": 30,
                "profit_factor": 1.3,
                "avg_points": 1.0,
                "net_points": 30.0,
            },
            {
                "signal_family": "bottom_reclaim_long",
                "session": "asia",
                "period": "oos",
                "trades": 30,
                "profit_factor": 2.0,
                "avg_points": 3.0,
                "net_points": 90.0,
            },
        ]
    )

    enabled = MODULE.select_enabled_from_independent_cells(cells, min_trades=20, min_pf=1.2, min_avg=0.5)

    assert enabled == {("trend_pullback_long", "us_late")}


def test_select_enabled_from_independent_cells_applies_stability_filter() -> None:
    cells = pd.DataFrame(
        [
            {
                "signal_family": "unstable",
                "session": "us_late",
                "period": "train",
                "trades": 50,
                "profit_factor": 1.5,
                "avg_points": 1.0,
                "net_points": 50.0,
            },
            {
                "signal_family": "stable",
                "session": "us_rth",
                "period": "train",
                "trades": 50,
                "profit_factor": 1.3,
                "avg_points": 0.8,
                "net_points": 40.0,
            },
        ]
    )
    stability = pd.DataFrame(
        [
            {
                "signal_family": "unstable",
                "session": "us_late",
                "positive_train_year_rate": 0.33,
                "worst_train_year_points": -200.0,
            },
            {
                "signal_family": "stable",
                "session": "us_rth",
                "positive_train_year_rate": 1.0,
                "worst_train_year_points": 5.0,
            },
        ]
    )

    enabled = MODULE.select_enabled_from_independent_cells(
        cells,
        min_trades=20,
        min_pf=1.2,
        min_avg=0.5,
        stability=stability,
        min_positive_year_rate=0.67,
        min_worst_year_points=-150.0,
    )

    assert enabled == {("stable", "us_rth")}


def test_run_walk_forward_uses_prior_year_window(monkeypatch) -> None:
    rows = []
    for year in [2020, 2021, 2022, 2023]:
        rows.append(
            {
                "ts": pd.Timestamp(f"{year}-01-02", tz="UTC"),
                "signal_direction": 0,
                "signal_family": "",
                "session": "us_rth",
            }
        )
    features = pd.DataFrame(rows)
    seen_train_ends: list[str] = []

    def fake_evaluate(features_arg, config, costs, *, train_end):
        seen_train_ends.append(train_end)
        return pd.DataFrame(
            [
                {
                    "signal_family": "stable",
                    "session": "us_rth",
                    "period": "train",
                    "trades": 10,
                    "profit_factor": 2.0,
                    "avg_points": 1.0,
                    "net_points": 10.0,
                }
            ]
        )

    def fake_stability(features_arg, config, costs, *, train_end):
        return pd.DataFrame(
            [
                {
                    "signal_family": "stable",
                    "session": "us_rth",
                    "positive_train_year_rate": 1.0,
                    "worst_train_year_points": 1.0,
                }
            ]
        )

    def fake_backtest(features_arg, config, costs, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(MODULE, "evaluate_independent_family_sessions", fake_evaluate)
    monkeypatch.setattr(MODULE, "cell_train_year_stability", fake_stability)
    monkeypatch.setattr(MODULE, "backtest_strategy", fake_backtest)
    args = type(
        "Args",
        (),
        {
            "min_cell_trades": 5,
            "min_cell_pf": 1.2,
            "min_cell_avg": 0.5,
            "min_positive_train_year_rate": 0.67,
            "min_worst_train_year_points": -10.0,
        },
    )()

    _, selections = MODULE.run_walk_forward(
        features,
        MODULE.BoundaryLightglowConfig(),
        BacktestCosts(),
        start_year=2023,
        end_year=2023,
        train_years=3,
        args=args,
    )

    assert seen_train_ends == ["2023-01-01"]
    assert selections["train_start"].iloc[0] == "2020-01-01"
    assert selections["train_end"].iloc[0] == "2023-01-01"
