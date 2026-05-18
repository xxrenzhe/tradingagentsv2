from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_exit_rules import replay_with_rule, ExitRule
from optimize_nq_sum_pos_market_feature_filters import add_market_features, attach_entry_features, summarize
from optimize_nq_sum_pos_runner_meta_allocation import MetaRule, apply_meta_rule
from optimize_nq_sum_pos_calibrated_runner_allocation import _to_utc
from search_nq_pine_indicator_combinations import (
    ComboSpec,
    MacdConfig,
    add_all_lightglow_signal_columns,
    add_features,
    add_macd_features,
    backtest_combo_fast,
)
from backtest_nq_boundary_lightglow_strategy import BoundaryLightglowConfig, pine_default_costs
from search_nq_bar_2r_walkforward import load_continuous_nq_bars
from backtest_lightglow_trend_optimized import resample_ohlcv


ROOT_DIR = Path(__file__).resolve().parents[1]


REVERSAL_LONG_FAMILIES = (
    "top_breakout_long",
    "trend_ignition_long",
    "trend_pullback_long",
    "trend_transition_long",
    "reversal_impulse_long",
    "bottom_reclaim_long",
    "fast_reversal_long",
    "smc_discount_choch_long",
    "trend_pullback_short_asia_europe",
    "trend_transition_short_asia",
)


def load_features(start_date: str, end_date: str, cache: Path, chunk_size: int, min_volume: float, timeframe_minutes: int) -> pd.DataFrame:
    args = SimpleNamespace(
        start_date=start_date,
        end_date=end_date,
        cache=str(cache),
        chunk_size=chunk_size,
        min_volume=min_volume,
    )
    bars = load_continuous_nq_bars(args).sort_values("ts").reset_index(drop=True)
    if timeframe_minutes > 1:
        bars = resample_ohlcv(bars, timeframe_minutes)
        bars["range_points"] = bars["High"].astype(float) - bars["Low"].astype(float)
        bars["range_mean_30"] = bars["range_points"].rolling(30, min_periods=30).mean()
        volume = bars["Volume"].astype(float)
        bars["volume_z_60"] = (volume - volume.rolling(60, min_periods=60).mean()) / volume.rolling(60, min_periods=60).std().replace(0, np.nan)
    config = BoundaryLightglowConfig()
    features = add_all_lightglow_signal_columns(add_features(bars, config), config)
    features = add_macd_features(features, MacdConfig(timeframe_minutes=timeframe_minutes))
    return features


def fixed_component_specs(timeframe_minutes: int = 1) -> list[tuple[ComboSpec, str]]:
    specs: list[tuple[ComboSpec, str]] = [
        (
            ComboSpec(
                name="selective_adverse_guard_ultra_plus_selective_regime_guard_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h35_maxr4_trail1.2x2_be1.5_lock1.5to1r_adverse_exit0.25r_norisk",
                families=REVERSAL_LONG_FAMILIES,
                macd_filter="cross_recent_5",
                macd_timeframe=timeframe_minutes,
                stop_atr_buffer=1.25,
                target_r=2.5,
                max_hold_bars=35,
                use_risk_controls=False,
                max_target_r=4.0,
                trail_start_r=1.2,
                trail_atr_mult=2.0,
                breakeven_trigger_r=1.5,
                min_target_r=1.0,
                giveback_start_r=1.5,
                giveback_keep_r=1.0,
                adverse_reversal_exit=True,
                adverse_exit_max_r=0.25,
                entry_quality_filter="ultra_plus_selective_regime_guard",
            ),
            "selective_adverse_guard_ultra_plus_selective_regime_guard_reversal_long_macd1_cross_recent_5_stop1.25_r2.5_h35_maxr4_trail1.2x2_be1.5_lock1.5to1r_adverse_exit0.25r_norisk",
        ),
        (
            ComboSpec(
                name="structure_micro_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1_wait3_norisk",
                families=(
                    "top_breakout_long",
                    "trend_ignition_long",
                    "trend_pullback_long",
                    "trend_transition_long",
                    "reversal_impulse_long",
                    "trend_pullback_short_asia_europe",
                    "trend_transition_short_asia",
                ),
                macd_filter="cross_recent_5",
                macd_timeframe=timeframe_minutes,
                stop_atr_buffer=1.25,
                target_r=2.5,
                max_hold_bars=30,
                use_risk_controls=False,
                entry_mode="structure_micro_rr",
                min_structure_rr=1.0,
                entry_wait_bars=3,
            ),
            "structure_micro_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1_wait3_norisk",
        ),
        (
            ComboSpec(
                name="structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk",
                families=(
                    "top_breakout_long",
                    "trend_ignition_long",
                    "trend_pullback_long",
                    "trend_transition_long",
                    "reversal_impulse_long",
                    "trend_pullback_short_asia_europe",
                    "trend_transition_short_asia",
                ),
                macd_filter="cross_recent_5",
                macd_timeframe=timeframe_minutes,
                stop_atr_buffer=1.25,
                target_r=2.5,
                max_hold_bars=30,
                use_risk_controls=False,
                entry_mode="structure_rr",
                min_structure_rr=2.0,
                entry_wait_bars=8,
            ),
            "structure_rr_selective_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr2_wait8_norisk",
        ),
        (
            ComboSpec(
                name="structure_adaptive_smc_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1.7_wait3_norisk",
                families=(
                    "smc_discount_choch_long",
                    "smc_bos_fvg_long",
                    "smc_ob_retest_long",
                    "smc_trend_transition_long",
                    "smc_trend_pullback_long",
                    "smc_premium_choch_short",
                    "smc_bos_fvg_short",
                    "smc_ob_retest_short",
                    "smc_trend_transition_short",
                    "smc_trend_pullback_short",
                ),
                macd_filter="cross_recent_5",
                macd_timeframe=timeframe_minutes,
                stop_atr_buffer=1.25,
                target_r=2.5,
                max_hold_bars=30,
                use_risk_controls=False,
                entry_mode="structure_adaptive",
                min_structure_rr=1.7,
                entry_wait_bars=3,
            ),
            "structure_adaptive_smc_strict_macd1_cross_recent_5_stop1.25_r2.5_h30_rr1.7_wait3_norisk",
        ),
    ]
    high_yield_families = (
        "top_breakout_long",
        "smc_discount_choch_long",
        "smc_ob_retest_long",
        "smc_premium_choch_short",
        "smc_ob_retest_short",
    )
    for min_rr in (1.4, 1.7, 2.0):
        for wait_bars in (3, 5):
            specs.append(
                (
                    ComboSpec(
                        name=f"twelve_month_high_yield_core_rr{min_rr:g}_wait{wait_bars}",
                families=high_yield_families,
                macd_filter="cross_recent_5",
                macd_timeframe=timeframe_minutes,
                        stop_atr_buffer=1.25,
                        target_r=2.5,
                        max_hold_bars=30,
                        use_risk_controls=False,
                        entry_mode="structure_adaptive",
                        min_structure_rr=min_rr,
                        entry_wait_bars=wait_bars,
                        entry_quality_filter="twelve_month_high_yield_guard",
                    ),
                    "twelve_month_high_yield_core",
                )
            )
    return specs


def fixed_cell_set(train_trades_path: Path) -> set[str]:
    train = pd.read_csv(train_trades_path)
    if "cell" not in train.columns:
        raise ValueError(f"training trades must include cell: {train_trades_path}")
    return set(train["cell"].astype(str))


def generate_component_trades(features: pd.DataFrame, timeframe_minutes: int = 1) -> pd.DataFrame:
    costs = pine_default_costs()
    base_config = BoundaryLightglowConfig()
    rows: list[pd.DataFrame] = []
    for spec, component_name in fixed_component_specs(timeframe_minutes):
        config = replace(
            base_config,
            stop_atr_buffer=spec.stop_atr_buffer,
            target_r=spec.target_r,
            max_hold_bars=spec.max_hold_bars,
            max_target_r=spec.max_target_r if spec.max_target_r > 0 else BoundaryLightglowConfig.max_target_r,
            trail_start_r=spec.trail_start_r if spec.trail_start_r > 0 else BoundaryLightglowConfig.trail_start_r,
            trail_atr_mult=spec.trail_atr_mult if spec.trail_atr_mult > 0 else BoundaryLightglowConfig.trail_atr_mult,
            breakeven_trigger_r=spec.breakeven_trigger_r if spec.breakeven_trigger_r > 0 else BoundaryLightglowConfig.breakeven_trigger_r,
            min_target_r=spec.min_target_r if spec.min_target_r > 0 else BoundaryLightglowConfig.min_target_r,
        )
        trades = backtest_combo_fast(features, spec, config, costs)
        if trades.empty:
            continue
        trades = trades.copy()
        trades["component_strategy"] = component_name
        trades["hour"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.hour
        trades["month"] = pd.to_datetime(trades["entry_ts"], utc=True).dt.to_period("M").astype(str)
        rows.append(trades)
    if not rows:
        return pd.DataFrame()
    output = pd.concat(rows, ignore_index=True)
    output["cell"] = [
        str((row.component_strategy, row.signal_family, row.session, int(row.direction), int(row.hour)))
        for row in output.itertuples(index=False)
    ]
    output["key"] = (
        output["entry_ts"].astype(str)
        + "|"
        + output["exit_ts"].astype(str)
        + "|"
        + output["signal_family"].astype(str)
        + "|"
        + output["session"].astype(str)
        + "|"
        + output["direction"].astype(str)
        + "|"
        + output["entry_price"].round(8).astype(str)
        + "|"
        + output["exit_price"].round(8).astype(str)
    )
    return output.sort_values(["entry_ts", "component_strategy"]).reset_index(drop=True)


def select_fixed_cells(trades: pd.DataFrame, cells: set[str], max_open: int) -> pd.DataFrame:
    selected = trades.loc[trades["cell"].astype(str).isin(cells)].copy()
    if selected.empty:
        return selected
    selected = selected.sort_values(["entry_ts", "exit_ts", "net_points"], ascending=[True, True, False]).reset_index(drop=True)
    accepted: list[dict[str, object]] = []
    open_exits: list[pd.Timestamp] = []
    seen_keys: set[str] = set()
    for row in selected.itertuples(index=False):
        key = str(row.key)
        if key in seen_keys:
            continue
        entry_ts = pd.Timestamp(row.entry_ts)
        open_exits = [ts for ts in open_exits if ts > entry_ts]
        if len(open_exits) >= max_open:
            continue
        accepted.append(row._asdict())
        open_exits.append(pd.Timestamp(row.exit_ts))
        seen_keys.add(key)
    if not accepted:
        return pd.DataFrame(columns=selected.columns)
    return pd.DataFrame(accepted).sort_values("entry_ts").reset_index(drop=True)


def apply_market_feature_filters(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    keep = pd.Series(True, index=df.index)
    direction = df["direction"].astype(int)
    family = df["signal_family"].astype(str)
    session = df["session"].astype(str)
    target_plan = df["target_plan"].astype(str)
    entry_mode = df["entry_mode"].astype(str)
    keep &= ~(
        family.eq("trend_transition_long")
        & session.eq("us_rth")
        & pd.to_numeric(df["dir_mom_60"], errors="coerce").lt(0)
    )
    keep &= ~(
        family.eq("trend_transition_short_asia")
        & pd.to_numeric(df["dir_ema20_dist"], errors="coerce").lt(0)
    )
    keep &= ~(
        entry_mode.eq("structure_rr")
        & pd.to_numeric(df["directional_range_pos_120"], errors="coerce").ge(0.85)
    )
    keep &= ~(
        target_plan.eq("fixed_r")
        & pd.to_numeric(df["atr14_rank_240"], errors="coerce").lt(0.30)
    )
    keep &= ~(
        target_plan.eq("micro_fixed_r")
        & pd.to_numeric(df["dir_mom_30"], errors="coerce").lt(1.0)
    )
    keep &= ~(
        family.eq("smc_discount_choch_long")
        & pd.to_numeric(df["directional_range_pos_60"], errors="coerce").le(0.05)
    )
    return df.loc[keep].sort_values("entry_ts").reset_index(drop=True)


def apply_second_pass_filters(trades: pd.DataFrame) -> pd.DataFrame:
    df = trades.copy()
    keep = pd.Series(True, index=df.index)
    family = df["signal_family"].astype(str)
    session = df["session"].astype(str)
    target_plan = df["target_plan"].astype(str)
    entry_mode = df["entry_mode"].astype(str)
    keep &= ~(
        target_plan.eq("trend_range_target")
        & pd.to_numeric(df["dir_ema20_dist"], errors="coerce").gt(2.0)
    )
    keep &= ~(
        family.eq("trend_transition_long")
        & session.eq("europe")
        & ~pd.to_numeric(df["atr14_rank_240"], errors="coerce").between(0.5, 1.0)
    )
    keep &= ~(
        target_plan.eq("micro_trend_range_target")
        & pd.to_numeric(df["dir_mom_15"], errors="coerce").lt(1.0)
    )
    keep &= ~(
        entry_mode.eq("structure_micro_rr")
        & family.eq("trend_transition_short_asia")
        & pd.to_numeric(df["dir_mom_30"], errors="coerce").lt(2.5)
    )
    return df.loc[keep].sort_values("entry_ts").reset_index(drop=True)


def apply_smc_discount_time_stop(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    rule = ExitRule(
        "smc_discount_tstop16_min-0.25r",
        lambda row: str(row.get("signal_family")) == "smc_discount_choch_long",
        time_bars=16,
        time_min_r=-0.25,
    )
    replay = replay_with_rule(trades, bars, rule)
    replay["exit_ts"] = replay["rule_exit_ts"]
    replay["exit_price"] = replay["rule_exit_price"]
    replay["net_points"] = replay["rule_net_points"]
    replay["gross_points"] = (replay["exit_price"].astype(float) - replay["entry_price"].astype(float)) * replay["direction"].astype(int)
    replay["bars_held"] = replay["rule_bars_held"]
    replay["exit_reason"] = "rule_" + replay["exit_rule"].astype(str)
    return replay.sort_values("entry_ts").reset_index(drop=True)


def apply_third_pass_giveback(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    ts_values = pd.to_datetime(bars["ts"], utc=True).astype("int64").to_numpy()
    rows: list[dict[str, object]] = []
    for _, row in trades.iterrows():
        output = row.to_dict()
        is_segment = (
            str(row.get("signal_family")) == "trend_transition_long"
            and str(row.get("session")) == "us_rth"
            and str(row.get("entry_mode")) == "structure_micro_rr"
        )
        if not is_segment:
            rows.append(output)
            continue
        entry_key = pd.DatetimeIndex([pd.Timestamp(row["entry_ts"])]).astype("int64")[0]
        exit_key = pd.DatetimeIndex([pd.Timestamp(row["exit_ts"])]).astype("int64")[0]
        entry_pos = int(np.searchsorted(ts_values, entry_key, side="left"))
        exit_pos = int(np.searchsorted(ts_values, exit_key, side="right") - 1)
        if entry_pos < 0 or exit_pos <= entry_pos:
            rows.append(output)
            continue
        direction = int(row["direction"])
        entry = float(row["entry_price"])
        risk = max(abs(entry - float(row["initial_stop"])), 0.25)
        best_r = -np.inf
        for pos in range(entry_pos + 1, exit_pos + 1):
            bar = bars.iloc[pos]
            high = float(bar["High"])
            low = float(bar["Low"])
            close = float(bar["Close"])
            progress_r = ((high - entry) if direction > 0 else (entry - low)) / risk
            best_r = max(best_r, progress_r)
            close_r = (close - entry) * direction / risk
            if best_r >= 0.75 and close_r <= 0.0:
                gross = (close - entry) * direction
                output.update(
                    {
                        "exit_ts": pd.Timestamp(bar["ts"]),
                        "exit_price": close,
                        "gross_points": gross,
                        "net_points": gross - 1.5,
                        "net_dollars": (gross - 1.5) * 20.0,
                        "bars_held": int(pos - entry_pos),
                        "exit_reason": "early_ttl_us_rth_micro_giveback",
                    }
                )
                break
        rows.append(output)
    return pd.DataFrame(rows).sort_values("entry_ts").reset_index(drop=True)


def apply_scaleout_runner(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    from optimize_nq_sum_pos_runner_variants import RunnerConfig, replay_runner_config

    config = RunnerConfig(
        name="fixed_scaleout_runner_f0.5_x30_trail1.5_lock1.5",
        target_fraction=0.5,
        extra_bars=30,
        trail_atr_mult=1.5,
        lock_r=1.5,
    )
    return replay_runner_config(trades, bars, config).sort_values("entry_ts").reset_index(drop=True)


def apply_fixed_meta_allocation(third_pass: pd.DataFrame, scaleout: pd.DataFrame) -> pd.DataFrame:
    base = third_pass.copy()
    scale = scaleout.copy()
    for frame in (base, scale):
        frame["entry_ts"] = _to_utc(frame["entry_ts"])
        frame["exit_ts"] = _to_utc(frame["exit_ts"])
    eligible = scale.loc[
        scale.get("runner_rule", pd.Series("original", index=scale.index)).astype(str).ne("original")
        | scale["exit_reason"].astype(str).str.startswith("scaleout")
        | scale["exit_reason"].astype(str).str.startswith("target_scaleout")
    ].copy()
    if eligible.empty:
        raise ValueError("fixed meta allocation requires at least one runner-eligible row")
    merged = base.merge(
        eligible.loc[:, ["trade_id", "gross_points", "exit_ts", "exit_price", "bars_held"]],
        on="trade_id",
        how="inner",
        suffixes=("_base", "_scaleout"),
    )
    direction = merged["direction"].astype(int)
    target_gross = (merged["target"].astype(float) - merged["entry_price"].astype(float)) * direction
    runner_gross = 2.0 * merged["gross_points_scaleout"].astype(float) - target_gross
    runner_legs = pd.DataFrame(
        {
            "trade_id": merged["trade_id"].astype(str),
            "target_gross": target_gross.astype(float),
            "runner_gross": runner_gross.astype(float),
            "scaleout_exit_ts": merged["exit_ts_scaleout"],
            "scaleout_exit_price": merged["exit_price_scaleout"].astype(float),
            "scaleout_bars_held": merged["bars_held_scaleout"].astype(int),
        }
    )
    rule = MetaRule(
        "fixed_weak_runner_family_set_or_short_positive_mom_to_target",
        lambda df: df["signal_family"].astype(str).isin(
            [
                "trend_transition_short_asia",
                "trend_pullback_long",
                "trend_pullback_short_asia_europe",
                "smc_ob_retest_long",
            ]
        )
        | (df["direction"].astype(int).lt(0) & pd.to_numeric(df["dir_mom_30"], errors="coerce").ge(1.5)),
        target_fraction=1.0,
    )
    return apply_meta_rule(base, runner_legs, base.merge(runner_legs, on="trade_id", how="inner"), rule)


def period_rows(label: str, trades: pd.DataFrame) -> dict[str, object]:
    row = {"stage": label, **summarize(trades)}
    months = pd.to_datetime(trades["entry_ts"], utc=True).dt.to_period("M")
    monthly = trades.assign(month=months.astype(str)).groupby("month")["net_points"].sum()
    row["months"] = int(len(monthly))
    row["positive_months"] = int((monthly > 0).sum())
    row["worst_month_points"] = float(monthly.min()) if len(monthly) else 0.0
    return row


def yearly_breakdown(trades: pd.DataFrame, stage: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    years = pd.to_datetime(trades["entry_ts"], utc=True).dt.year
    rows = []
    for year, group in trades.assign(year=years).groupby("year"):
        rows.append({"stage": stage, "year": int(year), **summarize(group)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate fixed sum_pos_open2 meta runner allocation outside its 12m mining window.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--train-trades", default="reports/NQ-pine-12m-high-return-sum_pos-open2-dirNone-trades.csv")
    parser.add_argument("--cache", default=".tmp/nq-sum-pos-meta-oos-bars.pkl")
    parser.add_argument("--timeframe-minutes", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--output-prefix", default="reports/NQ-pine-sum_pos-open2-fixed-meta-oos")
    args = parser.parse_args()

    features = load_features(args.start_date, args.end_date, ROOT_DIR / args.cache, args.chunk_size, args.min_volume, args.timeframe_minutes)
    bars = add_market_features(features)
    cells = fixed_cell_set(ROOT_DIR / args.train_trades)
    raw_components = generate_component_trades(features, args.timeframe_minutes)
    raw = select_fixed_cells(raw_components, cells, max_open=2)
    featured = attach_entry_features(raw, bars)
    first = apply_market_feature_filters(featured)
    second = apply_second_pass_filters(first)
    second_exit = apply_smc_discount_time_stop(second, bars)
    third = apply_third_pass_giveback(second_exit, bars)
    scaleout = apply_scaleout_runner(third, bars)
    meta = apply_fixed_meta_allocation(third, scaleout)

    prefix = ROOT_DIR / args.output_prefix
    outputs = {
        "raw_fixed_cells": raw,
        "market_feature": first,
        "second_pass": second_exit,
        "third_pass": third,
        "scaleout_50_50": scaleout,
        "fixed_meta": meta,
    }
    for name, frame in outputs.items():
        frame.to_csv(prefix.with_name(f"{prefix.name}-{name}-trades.csv"), index=False)
    summary = pd.DataFrame([period_rows(name, frame) for name, frame in outputs.items()])
    yearly = pd.concat([yearly_breakdown(frame, name) for name, frame in outputs.items()], ignore_index=True)
    summary.to_csv(prefix.with_name(f"{prefix.name}-summary.csv"), index=False)
    yearly.to_csv(prefix.with_name(f"{prefix.name}-yearly.csv"), index=False)
    print(summary.to_string(index=False))
    print(f"wrote {prefix.name}-*.csv")


if __name__ == "__main__":
    main()
