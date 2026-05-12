from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from backtest_nq_market_feature_strategy_templates import (  # noqa: E402
    StrategyTemplate,
    build_template_trades,
    dedupe_selected_trades,
    full_sample_results,
    research_score,
    summarize_trades,
    walk_forward_validate,
)
from discover_nq_tradeable_market_features import (  # noqa: E402
    MarketFeature,
    build_market_features,
    event_path_rows,
    invalidation_for_family,
    load_or_prepare_features,
    summarize_events,
)
from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402
from tradingagents.config.env import load_project_env  # noqa: E402
from tradingagents.default_config import DEFAULT_CONFIG  # noqa: E402
from tradingagents.evolution.features import prepare_evolution_features  # noqa: E402
from tradingagents.evolution.memory import EvolutionMemory, utc_now  # noqa: E402
from tradingagents.execution.llm_debate_delayed_strategy import (  # noqa: E402
    extract_json_object,
    invoke_aicode_streaming_json,
)
from tradingagents.llm_clients.factory import create_llm_client  # noqa: E402


DEFAULT_RESEARCH_FEATURE_IDS = [
    "ict_bullish_order_flow_shift_setup_us_rth",
    "ict_bullish_ofs_fvg_retest_entry_us_rth",
    "ict_bullish_ofs_ob_retest_entry_us_rth",
    "ict_bullish_ofs_quality_pullback_reclaim_us_rth",
    "ict_bearish_order_flow_shift_setup_us_rth",
    "ict_bearish_ofs_fvg_retest_entry_us_rth",
    "ict_bearish_ofs_ob_retest_entry_us_rth",
    "w_bottom_reclaim_us_rth",
    "m_top_reject_us_rth",
    "demand_sweep_reclaim_long_us_rth",
    "supply_sweep_rejection_short_us_rth",
    "sell_pressure_absorbed_rebound_us_rth",
    "buy_pressure_absorbed_fade_us_rth",
    "volume_price_bullish_mismatch_us_rth",
    "volume_price_bearish_mismatch_us_rth",
    "trend_start_long_displacement_us_rth",
    "trend_start_short_displacement_us_rth",
    "range_compression_breakout_long_us_rth",
    "range_compression_breakdown_short_us_rth",
    "low_volume_pullback_trend_long_us_rth",
    "low_volume_pullback_trend_short_us_rth",
    "fast_selloff_rebound_us_rth",
    "fast_rally_fade_us_rth",
    "capitulation_v_reversal_long_us_rth",
    "vwap_reclaim_after_selloff_us_rth",
    "vwap_loss_after_rally_us_rth",
    "low_base_reclaim_long_us_rth",
    "high_base_reject_short_us_rth",
    "selloff_reversal_pullback_continuation_long_us_rth",
    "rally_fade_pullback_continuation_short_us_rth",
    "supply_retest_downtrend_continuation_short_us_rth",
    "selloff_liquidity_sweep_rebound_watch_long_us_rth",
    "trix_kst_momentum_reversal_long_us_rth",
    "trix_kst_momentum_reversal_short_us_rth",
    "williams_ultimate_oversold_reclaim_long_us_rth",
    "williams_ultimate_overbought_fade_short_us_rth",
    "chaikin_force_accumulation_reversal_long_us_rth",
    "chaikin_force_distribution_reversal_short_us_rth",
    "psar_vortex_trend_start_long_us_rth",
    "psar_vortex_trend_start_short_us_rth",
    "cloud_pullback_trend_long_us_rth",
    "cloud_pullback_trend_short_us_rth",
]

LEAKAGE_SOURCE_PATHS = [
    ROOT_DIR / "tradingagents/evolution/features.py",
    ROOT_DIR / "scripts/discover_nq_tradeable_market_features.py",
    ROOT_DIR / "scripts/backtest_nq_market_feature_strategy_templates.py",
    ROOT_DIR / "scripts/search_nq_tradingview_structure_strategies.py",
]

REQUIRED_LAB_FEATURE_COLUMNS = [
    "bullish_order_flow_shift_setup",
    "bearish_order_flow_shift_setup",
    "bullish_fvg_retest",
    "bearish_fvg_retest",
    "bullish_fvg_low",
    "bearish_fvg_high",
    "ofs_leg_position",
    "vfi_130",
    "chaikin_osc_3_10",
    "force_index_z_50",
]


@dataclass(frozen=True)
class EvolutionRound:
    name: str
    feature_ids: tuple[str, ...]
    entry_modes: tuple[str, ...]
    stop_modes: tuple[str, ...]
    reward_risks: tuple[float, ...]
    horizons: tuple[int, ...]
    confirm_bars: tuple[int, ...]
    pullback_atr: tuple[float, ...]
    stop_atr_mult: tuple[float, ...]
    context_filters: tuple[str, ...]
    exit_modes: tuple[str, ...]
    fast_fail_bars: tuple[int, ...] = (3,)
    breakeven_trigger_r: tuple[float, ...] = (0.75,)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a causal NQ 2020+ 1-minute strategy evolution lab: feature discovery, "
            "template combination, purged walk-forward validation, pressure testing, "
            "LLM review, memory recording, and leakage audit."
        )
    )
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--walk-start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--bars-cache", default=".tmp/nq-market-feature-bars-2020-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-2020-cache.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--rebuild-features", action="store_true")
    parser.add_argument("--feature-summary-output", default=".tmp/nq-2020-causal-evolution-feature-summary.csv")
    parser.add_argument("--event-output", default=".tmp/nq-2020-causal-evolution-events.csv")
    parser.add_argument("--rebuild-event-summary", action="store_true")
    parser.add_argument("--feature-ids", nargs="+")
    parser.add_argument("--max-feature-ids", type=int, default=24)
    parser.add_argument(
        "--include-summary-ranked-features",
        type=int,
        default=8,
        help=(
            "Add this many high-opportunity event features to the research pool. "
            "The report marks this as hypothesis-generation, not promotion evidence."
        ),
    )
    parser.add_argument("--max-template-count", type=int, default=1200)
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-stop-points", type=float, default=4.0)
    parser.add_argument("--max-stop-points", type=float, default=100.0)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.10)
    parser.add_argument("--min-buffer-points", type=float, default=0.25)
    parser.add_argument("--min-full-sample-trades", type=int, default=20)
    parser.add_argument("--train-days", type=int, default=730)
    parser.add_argument("--purge-days", type=int, default=5)
    parser.add_argument("--test-days", type=int, default=180)
    parser.add_argument("--step-days", type=int, default=90)
    parser.add_argument("--min-train-trades", type=int, default=20)
    parser.add_argument("--min-train-net-points", type=float, default=0.0)
    parser.add_argument("--max-fold-candidates", type=int, default=8)
    parser.add_argument("--min-selected-folds", type=int, default=3)
    parser.add_argument("--min-oos-trades", type=int, default=60)
    parser.add_argument("--min-positive-fold-rate", type=float, default=0.55)
    parser.add_argument("--rolling-days", type=int, default=180)
    parser.add_argument("--rolling-step-days", type=int, default=90)
    parser.add_argument("--cost-multipliers", type=float, nargs="+", default=[1.0, 2.0, 3.0])
    parser.add_argument("--full-output", default=".tmp/nq-2020-causal-evolution-full-sample.csv")
    parser.add_argument("--fold-output", default=".tmp/nq-2020-causal-evolution-folds.csv")
    parser.add_argument("--aggregate-output", default=".tmp/nq-2020-causal-evolution-aggregate.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-2020-causal-evolution-trades.csv")
    parser.add_argument("--pressure-output", default=".tmp/nq-2020-causal-evolution-pressure.csv")
    parser.add_argument("--leakage-output", default=".tmp/nq-2020-causal-evolution-leakage-audit.json")
    parser.add_argument("--llm-output", default=".tmp/nq-2020-causal-evolution-llm-review.json")
    parser.add_argument("--report", default="reports/NQ-2020-causal-strategy-evolution.html")
    parser.add_argument("--markdown-report", default="reports/NQ-2020-causal-strategy-evolution.md")
    parser.add_argument("--memory-db", default=".tmp/nq-trading-evolution.sqlite")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--memory-top-n", type=int, default=30)
    parser.add_argument("--memory-note-cap-per-key", type=int, default=3)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--backend-url")
    parser.add_argument("--llm-timeout", type=float, default=120.0)
    parser.add_argument("--llm-top-n", type=int, default=25)
    parser.add_argument("--top-n", type=int, default=60)
    parser.add_argument("--chart-count", type=int, default=6)
    parser.add_argument("--audit-rows", type=int, default=2500)
    parser.add_argument("--audit-cutoff-row", type=int, default=1200)
    parser.add_argument("--skip-leakage-audit", action="store_true")
    parser.add_argument("--review-only", action="store_true")
    args = parser.parse_args()

    summary = run_lab(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


def run_lab(args: argparse.Namespace) -> dict[str, Any]:
    if args.review_only:
        return run_review_only(args)

    features = load_features_for_lab(args)
    market_features = {feature.feature_id: feature for feature in build_market_features(features)}
    feature_summary = load_or_build_feature_summary(features, list(market_features.values()), args)
    selected_feature_ids = select_feature_ids(
        market_features=market_features,
        feature_summary=feature_summary,
        explicit=args.feature_ids,
        max_feature_ids=args.max_feature_ids,
        include_summary_ranked=args.include_summary_ranked_features,
    )
    templates = build_evolution_templates(
        market_features=market_features,
        feature_ids=selected_feature_ids,
        max_template_count=args.max_template_count,
    )
    if not templates:
        raise ValueError("No strategy templates were generated. Check feature ids and feature availability.")

    leakage = (
        {"skipped": True, "passed": None}
        if args.skip_leakage_audit
        else run_leakage_audit(features, market_features, selected_feature_ids, args)
    )
    write_json(Path(args.leakage_output), leakage)

    full_sample, trades_by_template = full_sample_results(features, market_features, templates, args)
    folds, aggregate, selected_trades = walk_forward_validate(trades_by_template, templates, args)
    selected_trades = dedupe_selected_trades(selected_trades)
    aggregate = annotate_candidate_readiness(aggregate, folds, selected_trades, args)
    pressure = build_pressure_frame(aggregate, selected_trades, folds, args)
    memory_notes = load_memory_notes(Path(args.memory_db), limit=20)
    llm_payload = invoke_llm_review(feature_summary, full_sample, aggregate, pressure, leakage, memory_notes, args)

    write_outputs(
        full_sample=full_sample,
        folds=folds,
        aggregate=aggregate,
        selected_trades=selected_trades,
        pressure=pressure,
        llm_payload=llm_payload,
        args=args,
    )
    write_html_report(
        Path(args.report),
        features=features,
        feature_summary=feature_summary,
        full_sample=full_sample,
        folds=folds,
        aggregate=aggregate,
        selected_trades=selected_trades,
        pressure=pressure,
        leakage=leakage,
        llm_payload=llm_payload,
        selected_feature_ids=selected_feature_ids,
        templates=templates,
        args=args,
    )
    write_markdown_report(
        Path(args.markdown_report),
        feature_summary=feature_summary,
        aggregate=aggregate,
        pressure=pressure,
        leakage=leakage,
        llm_payload=llm_payload,
        selected_feature_ids=selected_feature_ids,
        templates=templates,
        args=args,
    )
    if args.record_memory:
        record_lab_memory(Path(args.memory_db), feature_summary, aggregate, pressure, leakage, llm_payload, args)

    return {
        "feature_rows": int(len(features)),
        "market_feature_count": int(len(market_features)),
        "selected_feature_ids": selected_feature_ids,
        "template_count": int(len(templates)),
        "full_sample_rows": int(len(full_sample)),
        "fold_rows": int(len(folds)),
        "aggregate_rows": int(len(aggregate)),
        "selected_trade_rows": int(len(selected_trades)),
        "research_pass_count": int(aggregate["research_pass"].sum()) if "research_pass" in aggregate else 0,
        "leakage_passed": leakage.get("passed"),
        "llm_status": llm_payload.get("status", "unknown"),
        "top_candidate": aggregate.head(1).to_dict(orient="records")[0] if not aggregate.empty else {},
        "report": str(args.report),
        "markdown_report": str(args.markdown_report),
        "aggregate_output": str(args.aggregate_output),
        "pressure_output": str(args.pressure_output),
    }


def run_review_only(args: argparse.Namespace) -> dict[str, Any]:
    feature_summary = read_csv_if_exists(Path(args.feature_summary_output))
    full_sample = read_csv_if_exists(Path(args.full_output))
    folds = read_csv_if_exists(Path(args.fold_output))
    aggregate = read_csv_if_exists(Path(args.aggregate_output))
    selected_trades = read_csv_if_exists(Path(args.trades_output))
    pressure = read_csv_if_exists(Path(args.pressure_output))
    leakage = read_json_if_exists(Path(args.leakage_output), default={"skipped": True, "passed": None})
    memory_notes = load_memory_notes(Path(args.memory_db), limit=20)
    llm_payload = invoke_llm_review(feature_summary, full_sample, aggregate, pressure, leakage, memory_notes, args)
    write_json(Path(args.llm_output), llm_payload)
    write_markdown_report(
        Path(args.markdown_report),
        feature_summary=feature_summary,
        aggregate=aggregate,
        pressure=pressure,
        leakage=leakage,
        llm_payload=llm_payload,
        selected_feature_ids=[],
        templates=[],
        args=args,
    )
    if args.record_memory:
        record_lab_memory(Path(args.memory_db), feature_summary, aggregate, pressure, leakage, llm_payload, args)
    return {
        "review_only": True,
        "feature_summary_rows": int(len(feature_summary)),
        "aggregate_rows": int(len(aggregate)),
        "pressure_rows": int(len(pressure)),
        "llm_status": llm_payload.get("status", "unknown"),
        "markdown_report": str(args.markdown_report),
    }


def load_or_build_feature_summary(
    features: pd.DataFrame,
    market_features: list[MarketFeature],
    args: argparse.Namespace,
) -> pd.DataFrame:
    output = Path(args.feature_summary_output)
    if output.exists() and not args.rebuild_event_summary:
        frame = pd.read_csv(output)
        return frame.sort_values(["opportunity_score", "events"], ascending=[False, False]).reset_index(drop=True)

    events = event_path_rows(
        features,
        market_features,
        horizons=[5, 15, 30, 60, 120],
        min_gap_minutes=args.min_gap_minutes,
    )
    summary = summarize_events(events, horizons=[5, 15, 30, 60, 120], min_events=20)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output, index=False)
    event_output = Path(args.event_output)
    event_output.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(event_output, index=False)
    return summary


def load_features_for_lab(args: argparse.Namespace) -> pd.DataFrame:
    features = load_or_prepare_features(args)
    missing = [column for column in REQUIRED_LAB_FEATURE_COLUMNS if column not in features.columns]
    if missing and not getattr(args, "rebuild_features", False):
        print(
            "Feature cache is stale for the causal lab; rebuilding because columns are missing: "
            + ", ".join(missing),
            flush=True,
        )
        rebuild_args = Namespace(**vars(args))
        rebuild_args.rebuild_features = True
        features = load_or_prepare_features(rebuild_args)
        missing = [column for column in REQUIRED_LAB_FEATURE_COLUMNS if column not in features.columns]
    if missing:
        raise ValueError(f"Prepared features are missing required causal-lab columns: {missing}")
    return features


def select_feature_ids(
    *,
    market_features: dict[str, MarketFeature],
    feature_summary: pd.DataFrame,
    explicit: list[str] | None,
    max_feature_ids: int,
    include_summary_ranked: int,
) -> list[str]:
    available = set(market_features)
    if explicit:
        selected = [feature_id for feature_id in explicit if feature_id in available]
        missing = sorted(set(explicit) - available)
        if missing:
            raise ValueError(f"Feature ids not available: {missing}")
        return selected[:max_feature_ids] if max_feature_ids > 0 else selected

    selected: list[str] = []
    for feature_id in DEFAULT_RESEARCH_FEATURE_IDS:
        if feature_id in available and feature_id not in selected:
            selected.append(feature_id)
    if include_summary_ranked > 0 and not feature_summary.empty and "feature_id" in feature_summary:
        for feature_id in feature_summary["feature_id"].astype(str).head(include_summary_ranked):
            if feature_id in available and feature_id not in selected:
                selected.append(feature_id)
    if max_feature_ids > 0:
        selected = selected[:max_feature_ids]
    return selected


def build_evolution_templates(
    *,
    market_features: dict[str, MarketFeature],
    feature_ids: list[str],
    max_template_count: int,
) -> list[StrategyTemplate]:
    templates_by_feature: dict[str, list[StrategyTemplate]] = {}
    for feature_id in feature_ids:
        feature = market_features[feature_id]
        round_config = round_for_feature(feature)
        templates_by_feature[feature_id] = [
            template
            for template in templates_for_round(round_config, market_features)
            if template.feature_id == feature_id
        ]
    return round_robin_templates(templates_by_feature, max_template_count)


def round_for_feature(feature: MarketFeature) -> EvolutionRound:
    family = feature.family
    feature_ids = (feature.feature_id,)
    if "order_flow_shift" in family or family in {"ict_order_block_retest"}:
        return EvolutionRound(
            name="ict_ofs_retest",
            feature_ids=feature_ids,
            entry_modes=("pullback_reclaim", "reclaim_hold", "quality_reclaim"),
            stop_modes=("event_extreme", "hybrid_event_atr"),
            reward_risks=(1.5, 1.75, 2.0),
            horizons=(60, 120),
            confirm_bars=(2, 3, 4),
            pullback_atr=(0.25, 0.50),
            stop_atr_mult=(1.5,),
            context_filters=("all", "rth_open", "high_relative_volume", "open_trend_volume", "vwap_volume", "atr_expanding"),
            exit_modes=("bracket", "bracket_fast_fail", "progress_bracket"),
            fast_fail_bars=(3, 5),
            breakeven_trigger_r=(0.50, 0.75),
        )
    if family in {
        "trend_start",
        "range_breakout",
        "trend_pullback",
        "tradingview_trend",
        "tradingview_pullback",
        "smc_bos_continuation",
        "smc_failed_choch_continuation",
        "smc_displacement_pullback",
        "supply_retest_continuation",
    }:
        return EvolutionRound(
            name="trend_continuation",
            feature_ids=feature_ids,
            entry_modes=("next_open", "confirm_break", "midpoint_hold", "confirm_hold"),
            stop_modes=("event_extreme", "hybrid_event_atr", "atr"),
            reward_risks=(1.25, 1.5, 2.0),
            horizons=(30, 60, 120),
            confirm_bars=(2, 4),
            pullback_atr=(0.25,),
            stop_atr_mult=(1.5, 2.0),
            context_filters=("all", "trend_or_vwap", "trend_vwap_volume", "atr_trend_volume", "open_trend_volume"),
            exit_modes=("bracket", "bracket_fast_fail", "progress_bracket"),
            fast_fail_bars=(3, 5),
            breakeven_trigger_r=(0.75,),
        )
    if family in {
        "double_bottom",
        "double_top",
        "liquidity_reversal",
        "absorption",
        "exhaustion_reversal",
        "reclaim",
        "base_reclaim",
        "reversal_watch",
        "smc_liquidity_macd_reversal",
        "tradingview_momentum",
        "tradingview_oscillator",
        "volume_price_mismatch",
        "tradingview_volume_price",
        "smc_sequence",
    }:
        return EvolutionRound(
            name="reversal_reclaim",
            feature_ids=feature_ids,
            entry_modes=("next_open", "midpoint_hold", "confirm_hold", "confirm_break"),
            stop_modes=("event_extreme", "hybrid_event_atr", "event_mid"),
            reward_risks=(1.0, 1.25, 1.5),
            horizons=(30, 60, 120),
            confirm_bars=(2, 5),
            pullback_atr=(0.25,),
            stop_atr_mult=(1.25, 1.5),
            context_filters=("all", "vwap_support", "vwap_volume", "high_relative_volume", "rth_open"),
            exit_modes=("bracket", "bracket_fast_fail", "staged"),
            fast_fail_bars=(3, 5),
            breakeven_trigger_r=(0.75,),
        )
    return EvolutionRound(
        name="generic",
        feature_ids=feature_ids,
        entry_modes=("next_open", "confirm_break", "midpoint_hold"),
        stop_modes=("event_extreme", "atr"),
        reward_risks=(1.0, 1.5),
        horizons=(30, 60),
        confirm_bars=(2,),
        pullback_atr=(0.25,),
        stop_atr_mult=(1.5,),
        context_filters=("all", "vwap_volume"),
        exit_modes=("bracket",),
    )


def templates_for_round(round_config: EvolutionRound, market_features: dict[str, MarketFeature]) -> list[StrategyTemplate]:
    templates: list[StrategyTemplate] = []
    for feature_id in round_config.feature_ids:
        feature = market_features[feature_id]
        direction = 1 if feature.direction_hint == "long" else -1
        for entry_mode in round_config.entry_modes:
            for stop_mode in round_config.stop_modes:
                for reward_risk in round_config.reward_risks:
                    for horizon in round_config.horizons:
                        for confirm in round_config.confirm_bars:
                            for pullback in round_config.pullback_atr:
                                for atr_mult in round_config.stop_atr_mult:
                                    for context_filter in round_config.context_filters:
                                        for exit_mode in round_config.exit_modes:
                                            for fast_fail in round_config.fast_fail_bars:
                                                for trigger_r in round_config.breakeven_trigger_r:
                                                    if entry_mode not in {
                                                        "pullback_reclaim",
                                                        "reclaim_hold",
                                                        "quality_reclaim",
                                                        "reclaim_break",
                                                        "strong_reclaim_break",
                                                        "reclaim_followthrough",
                                                    } and pullback != round_config.pullback_atr[0]:
                                                        continue
                                                    if stop_mode not in {"atr", "hybrid_event_atr"} and atr_mult != round_config.stop_atr_mult[0]:
                                                        continue
                                                    if exit_mode not in {
                                                        "adaptive",
                                                        "adaptive_bracket",
                                                        "breakeven_bracket",
                                                        "bracket_fast_fail",
                                                        "fast_fail",
                                                        "progress_bracket",
                                                        "progress_protective_bracket",
                                                        "staged",
                                                        "staged_breakeven",
                                                    } and fast_fail != round_config.fast_fail_bars[0]:
                                                        continue
                                                    if exit_mode not in {
                                                        "adaptive",
                                                        "breakeven_bracket",
                                                        "progress_bracket",
                                                        "progress_protective_bracket",
                                                        "protective_bracket",
                                                        "staged_breakeven",
                                                    } and trigger_r != round_config.breakeven_trigger_r[0]:
                                                        continue
                                                    name = (
                                                        f"lab_{round_config.name}_{feature_id}_{entry_mode}_{stop_mode}_{exit_mode}"
                                                        f"_rr{reward_risk:g}_h{horizon}_c{confirm}_pb{pullback:g}"
                                                        f"_atr{atr_mult:g}_ctx{context_filter}_ff{fast_fail}_be{trigger_r:g}"
                                                    )
                                                    templates.append(
                                                        StrategyTemplate(
                                                            name=name,
                                                            feature_id=feature_id,
                                                            family=feature.family,
                                                            direction=direction,
                                                            entry_mode=entry_mode,
                                                            stop_mode=stop_mode,
                                                            reward_risk=float(reward_risk),
                                                            horizon_minutes=int(horizon),
                                                            confirm_bars=int(confirm),
                                                            pullback_atr=float(pullback),
                                                            stop_atr_mult=float(atr_mult),
                                                            context_filter=context_filter,
                                                            exit_mode=exit_mode,
                                                            fast_fail_bars=int(fast_fail),
                                                            breakeven_trigger_r=float(trigger_r),
                                                        )
                                                    )
    return templates


def round_robin_templates(templates_by_feature: dict[str, list[StrategyTemplate]], max_template_count: int) -> list[StrategyTemplate]:
    selected: list[StrategyTemplate] = []
    seen: set[str] = set()
    feature_ids = list(templates_by_feature)
    max_len = max((len(value) for value in templates_by_feature.values()), default=0)
    for index in range(max_len):
        for feature_id in feature_ids:
            templates = templates_by_feature[feature_id]
            if index >= len(templates):
                continue
            template = templates[index]
            if template.name in seen:
                continue
            selected.append(template)
            seen.add(template.name)
            if 0 < max_template_count <= len(selected):
                return selected
    return selected


def run_leakage_audit(
    features: pd.DataFrame,
    market_features: dict[str, MarketFeature],
    selected_feature_ids: list[str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    static = static_leakage_scan(LEAKAGE_SOURCE_PATHS)
    runtime = runtime_future_perturbation_audit(
        features,
        selected_feature_ids=selected_feature_ids,
        rows=args.audit_rows,
        cutoff_row=args.audit_cutoff_row,
    )
    passed = bool(runtime["passed"] and not static["high_risk_matches"])
    return {
        "passed": passed,
        "static_scan": static,
        "runtime_future_perturbation": runtime,
        "entry_policy": "Signals are evaluated after the signal/confirmation bar closes; entries use a later bar open.",
        "same_bar_ambiguity_policy": "If stop and target are both touched in a bar, stop-first or the existing conservative template logic is used.",
        "selected_feature_count": len(selected_feature_ids),
        "known_safe_feature_count": len(market_features),
    }


def static_leakage_scan(paths: Iterable[Path]) -> dict[str, Any]:
    high_risk_patterns = [
        re.compile(r"shift\s*\(\s*-\d+"),
        re.compile(r"rolling\s*\([^)]*center\s*=\s*True"),
        re.compile(r"\bcenter\s*=\s*True"),
    ]
    informational_patterns = [
        re.compile(r"\bfuture\b", re.IGNORECASE),
        re.compile(r"\blead\b", re.IGNORECASE),
        re.compile(r"lookahead|look-ahead", re.IGNORECASE),
    ]
    high_risk_matches: list[dict[str, Any]] = []
    informational_matches: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            for pattern in high_risk_patterns:
                if pattern.search(stripped):
                    high_risk_matches.append({"path": str(path.relative_to(ROOT_DIR)), "line": line_number, "text": stripped})
            for pattern in informational_patterns:
                if pattern.search(stripped):
                    informational_matches.append({"path": str(path.relative_to(ROOT_DIR)), "line": line_number, "text": stripped})
    return {
        "high_risk_matches": high_risk_matches,
        "informational_matches": informational_matches[:50],
        "scanned_files": [str(path.relative_to(ROOT_DIR)) for path in paths if path.exists()],
    }


def runtime_future_perturbation_audit(
    features: pd.DataFrame,
    *,
    selected_feature_ids: list[str],
    rows: int,
    cutoff_row: int,
) -> dict[str, Any]:
    source_columns = ["ts", "symbol", "Open", "High", "Low", "Close", "Volume"]
    sample = features[source_columns].head(max(rows, cutoff_row + 50)).copy().reset_index(drop=True)
    if len(sample) < cutoff_row + 10:
        cutoff_row = max(10, len(sample) // 2)
    mutated = sample.copy()
    future_mask = mutated.index >= cutoff_row
    for column, multiplier in [("Open", 1.03), ("High", 1.04), ("Low", 1.02), ("Close", 1.03), ("Volume", 4.0)]:
        mutated.loc[future_mask, column] = pd.to_numeric(mutated.loc[future_mask, column], errors="coerce") * multiplier
    mutated.loc[future_mask, "High"] = mutated.loc[future_mask, ["Open", "High", "Close"]].max(axis=1)
    mutated.loc[future_mask, "Low"] = mutated.loc[future_mask, ["Open", "Low", "Close"]].min(axis=1)

    base_features = prepare_evolution_features(sample)
    mutated_features = prepare_evolution_features(mutated)
    compare_end = max(0, cutoff_row - 1)
    changed_columns = compare_feature_frames(base_features.iloc[:compare_end], mutated_features.iloc[:compare_end])
    base_signals = {feature.feature_id: feature.signal.iloc[:compare_end].reset_index(drop=True) for feature in build_market_features(base_features)}
    changed_signals: list[str] = []
    for feature in build_market_features(mutated_features):
        if feature.feature_id not in selected_feature_ids:
            continue
        original = base_signals.get(feature.feature_id)
        if original is None:
            continue
        current = feature.signal.iloc[:compare_end].reset_index(drop=True).fillna(False).astype(bool)
        if not current.equals(original.fillna(False).astype(bool)):
            changed_signals.append(feature.feature_id)
    return {
        "passed": not changed_columns and not changed_signals,
        "rows": int(len(sample)),
        "cutoff_row": int(cutoff_row),
        "compared_rows_before_cutoff": int(compare_end),
        "changed_feature_columns_before_cutoff": changed_columns,
        "changed_selected_signals_before_cutoff": changed_signals,
    }


def compare_feature_frames(base: pd.DataFrame, mutated: pd.DataFrame) -> list[str]:
    changed: list[str] = []
    shared_columns = [column for column in base.columns if column in mutated.columns]
    for column in shared_columns:
        left = base[column].reset_index(drop=True)
        right = mutated[column].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(left) or pd.api.types.is_numeric_dtype(right):
            left_numeric = pd.to_numeric(left, errors="coerce").to_numpy(dtype=float)
            right_numeric = pd.to_numeric(right, errors="coerce").to_numpy(dtype=float)
            if not np.allclose(left_numeric, right_numeric, equal_nan=True, rtol=1e-10, atol=1e-10):
                changed.append(column)
        else:
            left_text = left.astype("string").fillna("<NA>")
            right_text = right.astype("string").fillna("<NA>")
            if not left_text.equals(right_text):
                changed.append(column)
    return changed


def annotate_candidate_readiness(
    aggregate: pd.DataFrame,
    folds: pd.DataFrame,
    selected_trades: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    if aggregate.empty:
        return aggregate
    frame = aggregate.copy()
    frame["research_pass"] = (
        (pd.to_numeric(frame["selected_folds"], errors="coerce") >= args.min_selected_folds)
        & (pd.to_numeric(frame["test_trades"], errors="coerce") >= args.min_oos_trades)
        & (pd.to_numeric(frame["test_net_points"], errors="coerce") > 0)
        & (pd.to_numeric(frame["test_profit_factor"], errors="coerce") > 1.0)
        & (pd.to_numeric(frame["positive_test_fold_rate"], errors="coerce") >= args.min_positive_fold_rate)
    )
    frame["candidate_quality"] = np.select(
        [
            frame["research_pass"],
            (pd.to_numeric(frame["test_net_points"], errors="coerce") > 0)
            & (pd.to_numeric(frame["positive_test_fold_rate"], errors="coerce") >= 0.45),
        ],
        ["research_candidate", "watch"],
        default="reject",
    )
    frame["oos_trade_key"] = frame["template"].astype(str)
    return frame.sort_values(
        ["research_pass", "walk_forward_score", "test_net_points", "positive_test_fold_rate"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def build_pressure_frame(
    aggregate: pd.DataFrame,
    selected_trades: pd.DataFrame,
    folds: pd.DataFrame,
    args: argparse.Namespace,
) -> pd.DataFrame:
    if aggregate.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    costs = BacktestCosts()
    fold_groups = dict(tuple(folds.groupby("template", sort=False))) if not folds.empty and "template" in folds else {}
    trade_groups = dict(tuple(selected_trades.groupby("template", sort=False))) if not selected_trades.empty and "template" in selected_trades else {}
    for _, row in aggregate.head(max(args.top_n, 1)).iterrows():
        template = str(row["template"])
        trades = trade_groups.get(template, pd.DataFrame())
        group_folds = fold_groups.get(template, pd.DataFrame())
        summary = summarize_trades(trades)
        yearly = yearly_net_summary(trades)
        rolling = rolling_net_summary(trades, window_days=args.rolling_days, step_days=args.rolling_step_days)
        stress = cost_stress_summary(trades, costs, args.cost_multipliers)
        yearly_net = pd.to_numeric(yearly["net_points"], errors="coerce") if not yearly.empty else pd.Series(dtype=float)
        rolling_net = pd.to_numeric(rolling["net_points"], errors="coerce") if not rolling.empty else pd.Series(dtype=float)
        selected_folds = int(group_folds["fold"].nunique()) if not group_folds.empty and "fold" in group_folds else int(row.get("selected_folds", 0))
        positive_fold_rate = float(row.get("positive_test_fold_rate", 0.0))
        pressure_pass = (
            selected_folds >= args.min_selected_folds
            and summary["trades"] >= args.min_oos_trades
            and summary["net_points"] > 0
            and summary["profit_factor"] > 1.0
            and positive_fold_rate >= args.min_positive_fold_rate
            and stress.get("cost_2x_net_points", 0.0) > 0
        )
        rows.append(
            {
                "pressure_pass": bool(pressure_pass),
                "template": template,
                "feature_id": row.get("feature_id", ""),
                "family": row.get("family", ""),
                "entry_mode": row.get("entry_mode", ""),
                "stop_mode": row.get("stop_mode", ""),
                "context_filter": row.get("context_filter", ""),
                "exit_mode": row.get("exit_mode", ""),
                "reward_risk": row.get("reward_risk", np.nan),
                "horizon_minutes": row.get("horizon_minutes", np.nan),
                "selected_folds": selected_folds,
                "positive_test_fold_rate": positive_fold_rate,
                **{f"oos_{key}": value for key, value in summary.items()},
                **stress,
                "year_count": int(yearly["year"].nunique()) if not yearly.empty and "year" in yearly else 0,
                "positive_year_rate": float((yearly_net > 0).mean()) if not yearly_net.empty else 0.0,
                "min_year_net_points": float(yearly_net.min()) if not yearly_net.empty else 0.0,
                "rolling_window_count": int(len(rolling)),
                "positive_rolling_rate": float((rolling_net > 0).mean()) if not rolling_net.empty else 0.0,
                "min_rolling_net_points": float(rolling_net.min()) if not rolling_net.empty else 0.0,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["pressure_score"] = pressure_score(frame)
    return frame.sort_values(
        ["pressure_pass", "pressure_score", "oos_net_points", "positive_rolling_rate"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def cost_stress_summary(trades: pd.DataFrame, costs: BacktestCosts, multipliers: list[float]) -> dict[str, float]:
    out: dict[str, float] = {}
    gross = pd.to_numeric(trades["gross_points"], errors="coerce").dropna() if not trades.empty and "gross_points" in trades else pd.Series(dtype=float)
    for multiplier in multipliers:
        prefix = f"cost_{multiplier:g}x"
        net = gross - costs.round_trip_cost_points * float(multiplier)
        stats = summarize_net(net)
        out[f"{prefix}_net_points"] = stats["net_points"]
        out[f"{prefix}_profit_factor"] = stats["profit_factor"]
        out[f"{prefix}_win_rate"] = stats["win_rate"]
        out[f"{prefix}_max_drawdown_points"] = stats["max_drawdown_points"]
    return out


def summarize_net(net: pd.Series) -> dict[str, float]:
    if net.empty:
        return {"net_points": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "max_drawdown_points": 0.0}
    wins = net[net > 0]
    losses = net[net < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    return {
        "net_points": float(net.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else (999.0 if gross_profit > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
    }


def yearly_net_summary(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty or "entry_ts" not in trades:
        return pd.DataFrame()
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    frame["year"] = frame["entry_ts"].dt.year
    rows = []
    for year, group in frame.groupby("year", sort=True):
        rows.append({"year": int(year), **summarize_trades(group)})
    return pd.DataFrame(rows)


def rolling_net_summary(trades: pd.DataFrame, *, window_days: int, step_days: int) -> pd.DataFrame:
    if trades.empty or "entry_ts" not in trades:
        return pd.DataFrame()
    frame = trades.copy()
    frame["entry_ts"] = pd.to_datetime(frame["entry_ts"], utc=True)
    start = frame["entry_ts"].min().normalize()
    end = frame["entry_ts"].max().normalize() + pd.Timedelta(days=1)
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor + pd.Timedelta(days=window_days) <= end:
        window_end = cursor + pd.Timedelta(days=window_days)
        window = frame[(frame["entry_ts"] >= cursor) & (frame["entry_ts"] < window_end)]
        if len(window) >= 5:
            rows.append({"start": str(cursor.date()), "end": str(window_end.date()), **summarize_trades(window)})
        cursor += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def pressure_score(frame: pd.DataFrame) -> pd.Series:
    dd = pd.to_numeric(frame["oos_max_drawdown_points"], errors="coerce").clip(lower=1.0).fillna(1.0)
    net = pd.to_numeric(frame["oos_net_points"], errors="coerce").fillna(0.0)
    pf = pd.to_numeric(frame["oos_profit_factor"], errors="coerce").fillna(0.0)
    fold_rate = pd.to_numeric(frame["positive_test_fold_rate"], errors="coerce").fillna(0.0)
    roll_rate = pd.to_numeric(frame["positive_rolling_rate"], errors="coerce").fillna(0.0)
    cost2 = numeric_series(frame, "cost_2x_net_points", default=0.0)
    return net / dd + 5.0 * fold_rate + 4.0 * roll_rate + 3.0 * (pf - 1.0).clip(lower=-1.0) + cost2.clip(lower=-500.0) / 500.0


def invoke_llm_review(
    feature_summary: pd.DataFrame,
    full_sample: pd.DataFrame,
    aggregate: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    memory_notes: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if args.no_llm:
        return fallback_llm_review(feature_summary, aggregate, pressure, leakage, memory_notes, status="fallback_no_llm")
    load_project_env()
    provider = args.provider or DEFAULT_CONFIG["llm_provider"]
    model = args.model or DEFAULT_CONFIG["deep_think_llm"]
    base_url = args.backend_url or DEFAULT_CONFIG.get("backend_url")
    prompt = build_llm_prompt(feature_summary, full_sample, aggregate, pressure, leakage, memory_notes, args)
    try:
        if provider.lower() == "aicode":
            content = invoke_aicode_streaming_json(prompt, model=model, base_url=base_url, timeout=args.llm_timeout)
        else:
            client = create_llm_client(provider, model, base_url=base_url, timeout=args.llm_timeout, streaming=False).get_llm()
            response = client.invoke(prompt)
            content = str(getattr(response, "content", response))
        payload = extract_json_object(content)
        payload.setdefault("status", "parsed")
        payload.setdefault("provider", provider)
        payload.setdefault("model", model)
        payload["raw_response"] = content
        return payload
    except Exception as exc:
        payload = fallback_llm_review(feature_summary, aggregate, pressure, leakage, memory_notes, status="fallback_after_error")
        payload["provider"] = provider
        payload["model"] = model
        payload["error"] = str(exc) or exc.__class__.__name__
        return payload


def build_llm_prompt(
    feature_summary: pd.DataFrame,
    full_sample: pd.DataFrame,
    aggregate: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    memory_notes: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    return (
        "你是NQ 1分钟交易进化系统的研究负责人。请基于严格因果回测结果判断哪些行情特征有交易潜质，"
        "哪些策略组合值得下一轮强化，哪些需要淘汰。不要因为全样本好看就下结论；优先看 purged walk-forward、"
        "成本压力、年度/滚动稳定性和无未来函数审计。\n\n"
        "Return ONLY JSON with keys: market_feature_rankings, strategy_rankings, failure_modes, next_evolution_steps, "
        "risk_principles, production_readiness, summary. strategy_rankings must explain why the setup is tradeable or not, "
        "including entry, stop, exit, filters, and no-lookahead concerns.\n\n"
        f"CONFIG: {json.dumps(selected_config(args), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"LEAKAGE_AUDIT: {json.dumps(leakage, ensure_ascii=False, sort_keys=True, default=str)[:12000]}\n\n"
        f"MEMORY_NOTES: {json.dumps(memory_notes, ensure_ascii=False, sort_keys=True, default=str)[:12000]}\n\n"
        f"FEATURE_TOP: {frame_records(feature_summary.head(args.llm_top_n))}\n\n"
        f"FULL_SAMPLE_TOP: {frame_records(full_sample.head(args.llm_top_n))}\n\n"
        f"WALK_FORWARD_TOP: {frame_records(aggregate.head(args.llm_top_n))}\n\n"
        f"PRESSURE_TOP: {frame_records(pressure.head(args.llm_top_n))}"
    )


def fallback_llm_review(
    feature_summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    memory_notes: list[dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    strategy_rankings = []
    for _, row in aggregate.head(10).iterrows():
        strategy_rankings.append(
            {
                "template": str(row.get("template", "")),
                "verdict": str(row.get("candidate_quality", "research")),
                "reason": (
                    f"selected_folds={int(row.get('selected_folds', 0))}, "
                    f"OOS trades={int(row.get('test_trades', 0))}, net={float(row.get('test_net_points', 0.0)):.2f}, "
                    f"PF={float(row.get('test_profit_factor', 0.0)):.2f}, "
                    f"positive_fold_rate={float(row.get('positive_test_fold_rate', 0.0)):.2%}."
                ),
                "next_change": "Keep only if pressure test remains positive after 2x cost and rolling windows.",
            }
        )
    feature_rankings = []
    for _, row in feature_summary.head(10).iterrows():
        family = str(row.get("family", ""))
        direction = str(row.get("direction_hint", ""))
        feature_rankings.append(
            {
                "feature_id": str(row.get("feature_id", "")),
                "family": family,
                "direction": direction,
                "tradeability": "hypothesis",
                "reason": (
                    f"events={int(row.get('events', 0))}, opportunity_score={float(row.get('opportunity_score', 0.0)):.3f}. "
                    "This is event-path evidence only; execution still needs walk-forward strategy proof."
                ),
                "invalidation": invalidation_for_family(family, direction),
            }
        )
    return {
        "status": status,
        "provider": "rule",
        "model": "causal_lab_fallback",
        "market_feature_rankings": feature_rankings,
        "strategy_rankings": strategy_rankings,
        "failure_modes": [
            "Event-path opportunity can disappear after realistic entry delay and transaction cost.",
            "Strategies selected in only one fold remain data-mined research, even when net points are high.",
            "Volume-price mismatch needs price confirmation; divergence alone is not a signal.",
        ],
        "next_evolution_steps": [
            "For pressure-pass candidates, split by session/volatility and retest only from prior folds.",
            "Add structural early invalidation only after confirming it improves OOS, not full sample.",
            "Promote no strategy without paper execution validation, live slippage checks, and hard risk limits.",
        ],
        "risk_principles": [
            "Every entry must occur after the signal/confirmation bar, never on the same bar close being evaluated.",
            "Stop-first same-bar ambiguity stays conservative.",
            "Do not average down after a structural invalidation.",
            "Prefer fewer robust setups over many correlated variants from the same feature.",
        ],
        "production_readiness": {
            "ready_for_live": False,
            "reason": "This lab produces research candidates; paper validation and execution controls are still required.",
        },
        "summary": "Rule fallback generated a causal research review because the LLM was disabled or unavailable.",
        "leakage_passed": leakage.get("passed"),
        "memory_note_count": len(memory_notes),
    }


def write_outputs(
    *,
    full_sample: pd.DataFrame,
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    selected_trades: pd.DataFrame,
    pressure: pd.DataFrame,
    llm_payload: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    for path_value, frame in [
        (args.full_output, full_sample),
        (args.fold_output, folds),
        (args.aggregate_output, aggregate),
        (args.trades_output, selected_trades),
        (args.pressure_output, pressure),
    ]:
        path = Path(path_value)
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_json(Path(args.llm_output), llm_payload)


def write_html_report(
    path: Path,
    *,
    features: pd.DataFrame,
    feature_summary: pd.DataFrame,
    full_sample: pd.DataFrame,
    folds: pd.DataFrame,
    aggregate: pd.DataFrame,
    selected_trades: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    llm_payload: dict[str, Any],
    selected_feature_ids: list[str],
    templates: list[StrategyTemplate],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    best = aggregate.head(1).to_dict(orient="records")[0] if not aggregate.empty else {}
    pressure_best = pressure.head(1).to_dict(orient="records")[0] if not pressure.empty else {}
    chart_html = build_chart_panels(features, selected_trades, aggregate, args.chart_count)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ 2020+ Causal Strategy Evolution</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin:0; color:#172026; background:#f7f9fc; }}
    main {{ max-width: 1320px; margin: 0 auto; padding: 28px; }}
    h1 {{ font-size: 30px; margin: 0 0 8px; }}
    h2 {{ font-size: 20px; margin: 28px 0 12px; }}
    p {{ line-height: 1.55; }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin:16px 0; }}
    .metric, section {{ background:#fff; border:1px solid #dbe3ec; border-radius:8px; padding:16px; }}
    .label {{ color:#617080; font-size:13px; }}
    .value {{ margin-top:4px; font-size:23px; font-weight:700; }}
    .wrap {{ max-height: 640px; overflow:auto; border:1px solid #dbe3ec; border-radius:8px; background:white; }}
    table {{ border-collapse: collapse; width:100%; font-size:12px; background:white; }}
    th, td {{ border-bottom:1px solid #e7edf3; padding:7px 9px; vertical-align:top; text-align:left; }}
    th {{ background:#eef3f8; position:sticky; top:0; z-index:1; }}
    .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .pass {{ color:#08783f; font-weight:700; }}
    .fail {{ color:#a24100; font-weight:700; }}
    code {{ background:#edf2f7; padding:2px 4px; border-radius:4px; }}
    pre {{ white-space:pre-wrap; overflow:auto; background:#0f1720; color:#e6edf3; border-radius:8px; padding:14px; }}
    .chart-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(430px, 1fr)); gap:14px; }}
    .chart {{ background:#fff; border:1px solid #dbe3ec; border-radius:8px; padding:12px; overflow:hidden; }}
    .muted {{ color:#5f6b78; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 2020+ 1分钟因果策略进化报告</h1>
  <p class="muted">数据来自连续 NQ 1分钟 bar。信号只使用当前和历史K线、技术指标、量价关系、ICT/SMC结构与 TradingView 风格指标；入场发生在信号或确认之后的开盘价，避免未来函数。</p>
  <div class="grid">
    {_metric("Leakage Audit", "PASS" if leakage.get("passed") else "CHECK")}
    {_metric("Feature Rows", f"{len(features):,}")}
    {_metric("Selected Features", f"{len(selected_feature_ids):,}")}
    {_metric("Templates", f"{len(templates):,}")}
    {_metric("WF Candidates", f"{len(aggregate):,}")}
    {_metric("Research Pass", f"{int(aggregate['research_pass'].sum()) if 'research_pass' in aggregate else 0:,}")}
    {_metric("Best OOS Net", _fmt_num(best.get("test_net_points")))}
    {_metric("Best OOS PF", _fmt_num(best.get("test_profit_factor")))}
    {_metric("Pressure Pass", f"{int(pressure['pressure_pass'].sum()) if 'pressure_pass' in pressure else 0:,}")}
    {_metric("2x Cost Net", _fmt_num(pressure_best.get("cost_2x_net_points")))}
  </div>
  <section>
    <h2>因果约束</h2>
    <p>运行时未来扰动审计会修改 cutoff 之后的 OHLCV，并检查 cutoff 之前的特征列和已选信号是否变化。结果：<code>{html.escape(json.dumps(leakage.get("runtime_future_perturbation", {}), ensure_ascii=False, default=str)[:1400])}</code></p>
    <p>静态扫描重点查找 <code>shift(-n)</code>、<code>center=True</code> 等高风险写法。高风险命中数：<code>{len(leakage.get("static_scan", {}).get("high_risk_matches", []))}</code>。</p>
  </section>
  <section>
    <h2>特征假设</h2>
    <p>以下是行情特征路径统计，用于生成研究假设。它不是单独的交易策略，也不会直接作为未来测试成绩。</p>
    <div class="wrap">{html_table(feature_summary.head(args.top_n), feature_columns())}</div>
  </section>
  <section>
    <h2>Walk-Forward 策略排名</h2>
    <p>每个测试折只允许从过去训练窗选择模板，中间保留 purge gap。这里不再强制 53% 胜率，而是看未来净值、PF、正收益折比例、样本数和成本韧性。</p>
    <div class="wrap">{html_table(aggregate.head(args.top_n), aggregate_columns())}</div>
  </section>
  <section>
    <h2>压力测试</h2>
    <div class="wrap">{html_table(pressure.head(args.top_n), pressure_columns())}</div>
  </section>
  <section>
    <h2>K线样本</h2>
    <div class="chart-grid">{chart_html}</div>
  </section>
  <section>
    <h2>LLM / Rule 复盘</h2>
    <pre>{html.escape(json.dumps(llm_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))}</pre>
  </section>
  <section>
    <h2>输出文件</h2>
    <p><code>{html.escape(str(args.full_output))}</code> <code>{html.escape(str(args.fold_output))}</code> <code>{html.escape(str(args.aggregate_output))}</code> <code>{html.escape(str(args.trades_output))}</code> <code>{html.escape(str(args.pressure_output))}</code></p>
  </section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_markdown_report(
    path: Path,
    *,
    feature_summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    llm_payload: dict[str, Any],
    selected_feature_ids: list[str],
    templates: list[StrategyTemplate],
    args: argparse.Namespace,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    best = aggregate.head(1).to_dict(orient="records")[0] if not aggregate.empty else {}
    best_pressure = pressure.head(1).to_dict(orient="records")[0] if not pressure.empty else {}
    lines = [
        "# NQ 2020+ Causal Strategy Evolution",
        "",
        f"- Window: `{args.start_date}` to `{args.end_date}`",
        f"- Leakage audit passed: `{leakage.get('passed')}`",
        f"- Selected features: `{len(selected_feature_ids)}`",
        f"- Templates: `{len(templates)}`",
        f"- Research-pass candidates: `{int(aggregate['research_pass'].sum()) if 'research_pass' in aggregate else 0}`",
        f"- Best OOS candidate: `{best.get('template', 'N/A')}`",
        f"- Best OOS net/PF: `{_fmt_num(best.get('test_net_points'))}` / `{_fmt_num(best.get('test_profit_factor'))}`",
        f"- Best pressure candidate: `{best_pressure.get('template', 'N/A')}`",
        f"- Best 2x cost net: `{_fmt_num(best_pressure.get('cost_2x_net_points'))}`",
        "",
        "## Top Features",
        markdown_table(feature_summary.head(12), feature_columns()) if not feature_summary.empty else "No feature rows.",
        "",
        "## Top Walk-Forward Candidates",
        markdown_table(aggregate.head(12), aggregate_columns()) if not aggregate.empty else "No aggregate rows.",
        "",
        "## Top Pressure Rows",
        markdown_table(pressure.head(12), pressure_columns()) if not pressure.empty else "No pressure rows.",
        "",
        "## Review Summary",
        json.dumps(
            {
                "summary": llm_payload.get("summary"),
                "production_readiness": llm_payload.get("production_readiness"),
                "next_evolution_steps": llm_payload.get("next_evolution_steps"),
                "risk_principles": llm_payload.get("risk_principles"),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        ),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def build_chart_panels(features: pd.DataFrame, selected_trades: pd.DataFrame, aggregate: pd.DataFrame, chart_count: int) -> str:
    if features.empty or selected_trades.empty or aggregate.empty or chart_count <= 0:
        return "<p>No chart samples.</p>"
    best_templates = aggregate.head(3)["template"].astype(str).tolist() if "template" in aggregate else []
    trades = selected_trades[selected_trades["template"].astype(str).isin(best_templates)].copy()
    if trades.empty:
        trades = selected_trades.copy()
    trades["net_points"] = pd.to_numeric(trades["net_points"], errors="coerce")
    sample = pd.concat([trades.nlargest(chart_count // 2 + 1, "net_points"), trades.nsmallest(chart_count // 2 + 1, "net_points")])
    sample = sample.drop_duplicates(subset=[column for column in ["template", "entry_index"] if column in sample.columns]).head(chart_count)
    panels = []
    for _, trade in sample.iterrows():
        panels.append(candlestick_panel(features, trade))
    return "".join(panels) if panels else "<p>No chart samples.</p>"


def candlestick_panel(features: pd.DataFrame, trade: pd.Series, before: int = 80, after: int = 140) -> str:
    if "entry_index" not in trade or pd.isna(trade["entry_index"]):
        return ""
    entry_index = int(trade["entry_index"])
    exit_index = int(trade.get("exit_index", min(entry_index + after, len(features) - 1)))
    start = max(0, entry_index - before)
    end = min(len(features), max(exit_index + 10, entry_index + after))
    window = features.iloc[start:end].reset_index(drop=True)
    if window.empty:
        return ""
    svg = candlestick_svg(window, entry_index=entry_index - start, exit_index=exit_index - start)
    title = html.escape(str(trade.get("template", ""))[:110])
    meta = (
        f"entry={html.escape(str(trade.get('entry_ts', '')))} "
        f"exit={html.escape(str(trade.get('exit_ts', '')))} "
        f"net={_fmt_num(trade.get('net_points'))} reason={html.escape(str(trade.get('exit_reason', '')))}"
    )
    return f"<div class=\"chart\"><strong>{title}</strong><p class=\"muted\">{meta}</p>{svg}</div>"


def candlestick_svg(window: pd.DataFrame, *, entry_index: int, exit_index: int, width: int = 760, height: int = 280) -> str:
    high = pd.to_numeric(window["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(window["Low"], errors="coerce").to_numpy(dtype=float)
    open_ = pd.to_numeric(window["Open"], errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(window["Close"], errors="coerce").to_numpy(dtype=float)
    if len(window) == 0:
        return ""
    pad_left, pad_right, pad_top, pad_bottom = 42, 14, 14, 28
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom
    y_min = float(np.nanmin(low))
    y_max = float(np.nanmax(high))
    if not np.isfinite(y_min) or not np.isfinite(y_max) or y_max <= y_min:
        y_min, y_max = 0.0, 1.0
    y_pad = max((y_max - y_min) * 0.05, 1.0)
    y_min -= y_pad
    y_max += y_pad

    def x_for(index: int) -> float:
        return pad_left + (index + 0.5) * plot_w / max(len(window), 1)

    def y_for(price: float) -> float:
        return pad_top + (y_max - price) * plot_h / (y_max - y_min)

    candle_w = max(2.0, min(8.0, plot_w / max(len(window), 1) * 0.62))
    parts = [
        f"<svg viewBox=\"0 0 {width} {height}\" width=\"100%\" role=\"img\" aria-label=\"candlestick chart\">",
        f"<rect x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\" fill=\"#ffffff\"/>",
        f"<line x1=\"{pad_left}\" y1=\"{pad_top}\" x2=\"{pad_left}\" y2=\"{height - pad_bottom}\" stroke=\"#d4dde7\"/>",
        f"<line x1=\"{pad_left}\" y1=\"{height - pad_bottom}\" x2=\"{width - pad_right}\" y2=\"{height - pad_bottom}\" stroke=\"#d4dde7\"/>",
    ]
    for grid_price in np.linspace(y_min, y_max, 4):
        y = y_for(float(grid_price))
        parts.append(f"<line x1=\"{pad_left}\" y1=\"{y:.2f}\" x2=\"{width - pad_right}\" y2=\"{y:.2f}\" stroke=\"#eef2f6\"/>")
        parts.append(f"<text x=\"4\" y=\"{y + 4:.2f}\" font-size=\"10\" fill=\"#607080\">{grid_price:.0f}</text>")
    for i in range(len(window)):
        x = x_for(i)
        color = "#0f8b4c" if close[i] >= open_[i] else "#c0392b"
        y_high = y_for(high[i])
        y_low = y_for(low[i])
        y_open = y_for(open_[i])
        y_close = y_for(close[i])
        body_y = min(y_open, y_close)
        body_h = max(abs(y_close - y_open), 1.0)
        parts.append(f"<line x1=\"{x:.2f}\" y1=\"{y_high:.2f}\" x2=\"{x:.2f}\" y2=\"{y_low:.2f}\" stroke=\"{color}\" stroke-width=\"1\"/>")
        parts.append(
            f"<rect x=\"{x - candle_w / 2:.2f}\" y=\"{body_y:.2f}\" width=\"{candle_w:.2f}\" height=\"{body_h:.2f}\" fill=\"{color}\" opacity=\"0.88\"/>"
        )
    if 0 <= entry_index < len(window):
        x = x_for(entry_index)
        parts.append(f"<line x1=\"{x:.2f}\" y1=\"{pad_top}\" x2=\"{x:.2f}\" y2=\"{height - pad_bottom}\" stroke=\"#1f5fbf\" stroke-width=\"1.5\"/>")
        parts.append(f"<text x=\"{x + 4:.2f}\" y=\"{pad_top + 12}\" font-size=\"11\" fill=\"#1f5fbf\">ENTRY</text>")
    if 0 <= exit_index < len(window):
        x = x_for(exit_index)
        parts.append(f"<line x1=\"{x:.2f}\" y1=\"{pad_top}\" x2=\"{x:.2f}\" y2=\"{height - pad_bottom}\" stroke=\"#6b3fbf\" stroke-width=\"1.5\"/>")
        parts.append(f"<text x=\"{x + 4:.2f}\" y=\"{pad_top + 26}\" font-size=\"11\" fill=\"#6b3fbf\">EXIT</text>")
    parts.append("</svg>")
    return "".join(parts)


def record_lab_memory(
    memory_db: Path,
    feature_summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    pressure: pd.DataFrame,
    leakage: dict[str, Any],
    llm_payload: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        for _, row in feature_summary.head(args.memory_top_n).iterrows():
            feature_id = str(row.get("feature_id", ""))
            if not feature_id:
                continue
            signature = "labfeat_" + hashlib.sha1(feature_id.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_market_feature_{int(row.get('events', 0))}"
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, 'market_feature', NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    str(row.get("description", "")),
                    invalidation_for_family(str(row.get("family", "")), str(row.get("direction_hint", ""))),
                    (
                        f"Causal lab feature {feature_id}: family={row.get('family')}, direction={row.get('direction_hint')}, "
                        f"events={int(row.get('events', 0))}, opportunity_score={float(row.get('opportunity_score', 0.0)):.3f}. "
                        "Use as a hypothesis source only; require walk-forward strategy confirmation."
                    ),
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row.get("events", 0)) / 2000.0)),
                    now,
                ),
            )
        for _, row in aggregate.head(args.memory_top_n).iterrows():
            template = str(row.get("template", ""))
            if not template:
                continue
            signature = "labstrat_" + hashlib.sha1(template.encode("utf-8")).hexdigest()[:16]
            note_type = "strategy_template" if bool(row.get("research_pass", False)) else "failure_mode"
            note_id = f"note_{signature}_{note_type}_{int(row.get('selected_folds', 0))}_{int(row.get('test_trades', 0))}"
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    note_type,
                    f"Template={template}; feature_id={row.get('feature_id')}; context={row.get('context_filter')}",
                    "Avoid promotion if future refresh loses positive folds, PF>1, or 2x cost resilience.",
                    (
                        f"Causal lab strategy {template}: quality={row.get('candidate_quality')}, "
                        f"folds={int(row.get('selected_folds', 0))}, OOS trades={int(row.get('test_trades', 0))}, "
                        f"net={float(row.get('test_net_points', 0.0)):.2f}, PF={float(row.get('test_profit_factor', 0.0)):.2f}, "
                        f"positive_fold_rate={float(row.get('positive_test_fold_rate', 0.0)):.2%}."
                    ),
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row.get("selected_folds", 0)) / 8.0)),
                    now,
                ),
            )
        for _, row in pressure.head(args.memory_top_n).iterrows():
            template = str(row.get("template", ""))
            if not template:
                continue
            signature = "labpress_" + hashlib.sha1(template.encode("utf-8")).hexdigest()[:16]
            note_type = "effective_feature" if bool(row.get("pressure_pass", False)) else "failure_mode"
            note_id = f"note_{signature}_{note_type}_{int(row.get('oos_trades', 0))}"
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    note_type,
                    f"Pressure-tested template={template}; feature_id={row.get('feature_id')}",
                    "Avoid if cost stress, yearly splits, or rolling windows turn negative.",
                    (
                        f"Pressure row {template}: pass={bool(row.get('pressure_pass', False))}, "
                        f"OOS net={float(row.get('oos_net_points', 0.0)):.2f}, PF={float(row.get('oos_profit_factor', 0.0)):.2f}, "
                        f"2x cost net={float(row.get('cost_2x_net_points', 0.0)):.2f}, "
                        f"positive rolling={float(row.get('positive_rolling_rate', 0.0)):.2%}."
                    ),
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row.get("positive_rolling_rate", 0.0)))),
                    now,
                ),
            )
        memory.connection.execute(
            """
            INSERT OR REPLACE INTO experience_notes (
                note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                lesson, evidence_summary, confidence, status, supersedes_note_id,
                created_at, last_used_at, use_count
            ) VALUES (?, NULL, 'risk_principle', NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
            """,
            (
                "note_lab_causal_guardrails_latest",
                "Use for all NQ 1m strategy evolution runs.",
                "Reject any research path that enters on information unavailable at signal/confirmation time.",
                "Causal lab guardrail: signals must use current/past bars only; entries happen after the signal/confirmation bar; same-bar ambiguity remains conservative; memory is capped by active note key.",
                json.dumps({"leakage_passed": leakage.get("passed"), "llm_status": llm_payload.get("status")}, sort_keys=True, default=str),
                1.0,
                now,
            ),
        )
        memory.limit_active_notes(max_per_key=args.memory_note_cap_per_key)
        memory.connection.commit()
    finally:
        memory.close()


def load_memory_notes(memory_db: Path, limit: int) -> list[dict[str, Any]]:
    if not memory_db.exists():
        return []
    memory = EvolutionMemory(memory_db)
    try:
        return memory.active_notes(limit)
    finally:
        memory.close()


def build_walk_forward_windows(
    *,
    walk_start_date: str,
    end_date: str,
    train_days: int,
    purge_days: int,
    test_days: int,
    step_days: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    test_start = pd.Timestamp(walk_start_date, tz="UTC")
    end = pd.Timestamp(end_date, tz="UTC")
    fold = 0
    while test_start + pd.Timedelta(days=test_days) <= end:
        train_start = test_start - pd.Timedelta(days=train_days + purge_days)
        train_end = test_start - pd.Timedelta(days=purge_days)
        test_end = test_start + pd.Timedelta(days=test_days)
        rows.append(
            {
                "fold": fold,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "purge_days": purge_days,
                "past_only": bool(train_end <= test_start - pd.Timedelta(days=purge_days)),
            }
        )
        fold += 1
        test_start += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def feature_columns() -> list[str]:
    return [
        "feature_id",
        "family",
        "direction_hint",
        "events",
        "opportunity_score",
        "favorable_close_rate_60m",
        "median_mfe_60m",
        "median_mae_60m",
        "hit_20pt_rate_60m",
        "adverse_10pt_rate_60m",
    ]


def aggregate_columns() -> list[str]:
    return [
        "research_pass",
        "candidate_quality",
        "template",
        "feature_id",
        "family",
        "entry_mode",
        "stop_mode",
        "context_filter",
        "exit_mode",
        "reward_risk",
        "horizon_minutes",
        "selected_folds",
        "positive_test_fold_rate",
        "test_trades",
        "test_net_points",
        "test_profit_factor",
        "test_win_rate",
        "test_payoff_ratio",
        "test_max_drawdown_points",
        "walk_forward_score",
    ]


def pressure_columns() -> list[str]:
    return [
        "pressure_pass",
        "template",
        "feature_id",
        "selected_folds",
        "positive_test_fold_rate",
        "oos_trades",
        "oos_net_points",
        "oos_profit_factor",
        "oos_win_rate",
        "oos_payoff_ratio",
        "oos_max_drawdown_points",
        "cost_2x_net_points",
        "cost_2x_profit_factor",
        "cost_3x_net_points",
        "positive_year_rate",
        "positive_rolling_rate",
        "min_rolling_net_points",
        "pressure_score",
    ]


def html_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    available = [column for column in columns if column in frame.columns]
    header = "".join(f"<th>{html.escape(column)}</th>" for column in available)
    body: list[str] = []
    for _, row in frame[available].iterrows():
        cells = []
        for column in available:
            value = row[column]
            if isinstance(value, (bool, np.bool_)):
                text = "PASS" if bool(value) else "FAIL"
                css = "pass" if bool(value) else "fail"
            elif is_number(value):
                text = _fmt_pct(value) if ("rate" in column or column.endswith("_win_rate")) else _fmt_num(value)
                css = "num"
            else:
                text = html.escape(str(value))
                css = ""
            cells.append(f"<td class=\"{css}\">{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "No rows."
    available = [column for column in columns if column in frame.columns]
    if not available:
        return "No matching columns."
    header = "| " + " | ".join(escape_markdown(column) for column in available) + " |"
    separator = "| " + " | ".join("---" for _ in available) + " |"
    rows = []
    for _, row in frame[available].iterrows():
        cells = []
        for column in available:
            value = row[column]
            if isinstance(value, (bool, np.bool_)):
                cells.append("PASS" if bool(value) else "FAIL")
            elif is_number(value):
                cells.append(_fmt_pct(value) if ("rate" in column or column.endswith("_win_rate")) else _fmt_num(value))
            else:
                cells.append(escape_markdown(str(value)))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, separator, *rows])


def numeric_series(frame: pd.DataFrame, column: str, *, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def escape_markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def selected_config(args: argparse.Namespace) -> dict[str, Any]:
    keys = [
        "start_date",
        "walk_start_date",
        "end_date",
        "max_feature_ids",
        "include_summary_ranked_features",
        "max_template_count",
        "train_days",
        "purge_days",
        "test_days",
        "step_days",
        "min_train_trades",
        "max_fold_candidates",
        "min_selected_folds",
        "min_oos_trades",
        "min_positive_fold_rate",
    ]
    return {key: getattr(args, key) for key in keys if hasattr(args, key)}


def frame_records(frame: pd.DataFrame) -> str:
    return json.dumps(
        frame.replace([np.inf, -np.inf], np.nan).where(pd.notna(frame), None).to_dict(orient="records"),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )[:50000]


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def read_json_if_exists(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _metric(label: str, value: str) -> str:
    return f"<div class=\"metric\"><div class=\"label\">{html.escape(label)}</div><div class=\"value\">{value}</div></div>"


def _fmt_num(value: Any) -> str:
    if not is_number(value):
        return "N/A"
    return f"{float(value):,.3f}"


def _fmt_pct(value: Any) -> str:
    if not is_number(value):
        return "N/A"
    return f"{float(value):.2%}"


def is_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return pd.notna(number)


if __name__ == "__main__":
    raise SystemExit(main())
