from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .backtest import validate_rule_on_segment
from .features import prepare_evolution_features, summarize_segment_features
from .llm import FallbackRuleGenerator, MockRuleGenerator, RealLLMRuleGenerator, RuleGenerator
from .memory import EvolutionMemory
from .nq_data import load_continuous_nq_bars
from .report import write_html_report
from .rules import TradingRule
from .segmentation import Segment, SegmentConfig, segment_market


@dataclass(frozen=True)
class EvolutionConfig:
    start_date: str = "2020-01-01"
    end_date: str = "2026-04-28"
    cache: Path = Path(".tmp/nq-evolution-continuous-cache.pkl")
    memory_db: Path = Path(".tmp/nq-trading-evolution.sqlite")
    report: Path = Path("reports/NQ-trading-evolution-report.html")
    source_csv: Path | None = None
    source_zip: Path | None = None
    llm_mode: str = "layered"
    mock_llm_fixture: Path | None = None
    no_llm: bool = False
    resume: bool = False
    max_segments: int | None = None
    base_bars: int = 100
    min_bars: int = 20
    max_bars: int = 300
    split_threshold: float = 0.75
    high_info_threshold: float = 0.80
    daily_llm_call_limit: int = 3
    provider: str | None = None
    model: str | None = None
    backend_url: str | None = None


@dataclass(frozen=True)
class PendingRule:
    rule_id: str
    signature: str
    rule: TradingRule
    analysis_segment_id: str
    validation_start_index: int


def run_evolution(config: EvolutionConfig, bars: pd.DataFrame | None = None) -> dict:
    raw_bars = bars if bars is not None else load_continuous_nq_bars(
        start_date=config.start_date,
        end_date=config.end_date,
        cache_path=config.cache,
        source_csv=config.source_csv,
        source_zip=config.source_zip,
    )
    features = prepare_evolution_features(raw_bars)
    segments = segment_market(
        features,
        SegmentConfig(
            base_bars=config.base_bars,
            min_bars=config.min_bars,
            max_bars=config.max_bars,
            split_threshold=config.split_threshold,
            high_info_threshold=config.high_info_threshold,
        ),
    )
    if config.max_segments is not None:
        segments = segments[: config.max_segments]

    if not config.resume and config.memory_db.exists():
        os.remove(config.memory_db)
    memory = EvolutionMemory(config.memory_db)
    generator = _build_generator(config)
    pending: list[PendingRule] = []
    llm_calls = 0
    llm_successes = 0
    llm_parse_errors = 0
    llm_fallback_rules = 0
    validations = 0
    daily_calls: dict[str, int] = {}

    try:
        for segment_index, segment in enumerate(segments):
            is_last_segment = segment_index == len(segments) - 1
            memory.upsert_segment(segment)

            for pending_rule in list(pending):
                validation_segment = _build_validation_segment_if_ready(
                    pending_rule=pending_rule,
                    processed_segment=segment,
                    features=features,
                    is_last_segment=is_last_segment,
                )
                if validation_segment is None:
                    continue
                result = validate_rule_on_segment(
                    rule=pending_rule.rule,
                    rule_id=pending_rule.rule_id,
                    signature=pending_rule.signature,
                    analysis_segment_id=pending_rule.analysis_segment_id,
                    validation_segment=validation_segment,
                    features=features,
                )
                memory.record_validation(result)
                validations += 1
                pending.remove(pending_rule)

            if not _should_call_llm(segment, config, daily_calls):
                continue
            packet = memory.build_memory_packet(segment=segment)
            generated = generator.generate(segment=segment, memory_packet=packet)
            memory.record_llm_analysis(generated.analysis_event)
            llm_calls += 1
            if generated.analysis_event.get("status") == "parsed":
                llm_successes += 1
            elif generated.analysis_event.get("status") == "parse_error":
                llm_parse_errors += 1
            elif generated.analysis_event.get("status") == "error" and generated.rule is not None:
                llm_fallback_rules += 1
            if generated.rule is None or generated.signature is None:
                continue
            rule_id = f"pr_{generated.signature}_{segment.segment_id}"
            memory.record_rule(
                rule_id=rule_id,
                signature=generated.signature,
                rule=generated.rule,
                analysis_id=generated.analysis_event["analysis_id"],
                segment_id=segment.segment_id,
            )
            pending.append(
                PendingRule(
                    rule_id=rule_id,
                    signature=generated.signature,
                    rule=generated.rule,
                    analysis_segment_id=segment.segment_id,
                    validation_start_index=segment.end_index,
                )
            )
            day = str(pd.Timestamp(segment.start_ts).date())
            daily_calls[day] = daily_calls.get(day, 0) + 1

        memory.prune_raw_responses()
        memory.prune_memory_packets()
        summary = {
            "config": _config_summary(config),
            "feature_rows": int(len(features)),
            "feature_start": str(features["ts"].min()) if not features.empty else "",
            "feature_end": str(features["ts"].max()) if not features.empty else "",
            "segments": int(len(segments)),
            "llm_calls": int(llm_calls),
            "llm_successes": int(llm_successes),
            "llm_parse_errors": int(llm_parse_errors),
            "llm_fallback_rules": int(llm_fallback_rules),
            "validations": int(validations),
            "memory_db": str(config.memory_db),
            "report": str(config.report),
            "counts": memory.counts(),
            "memory_token_total": memory.memory_token_total(),
        }
        write_html_report(path=config.report, features=features, segments=segments, memory=memory, summary=summary)
        summary["counts"] = memory.counts()
        summary["memory_token_total"] = memory.memory_token_total()
        return summary
    finally:
        memory.close()


def _build_generator(config: EvolutionConfig) -> RuleGenerator:
    if config.mock_llm_fixture:
        return MockRuleGenerator(config.mock_llm_fixture)
    if config.no_llm:
        return FallbackRuleGenerator()
    return RealLLMRuleGenerator(provider=config.provider, model=config.model, base_url=config.backend_url)


def _should_call_llm(segment: Segment, config: EvolutionConfig, daily_calls: dict[str, int]) -> bool:
    if config.no_llm:
        return False
    day = str(pd.Timestamp(segment.start_ts).date())
    if daily_calls.get(day, 0) >= config.daily_llm_call_limit:
        return False
    if config.llm_mode == "strict-every-segment":
        return True
    if _has_rare_structure_combo(segment):
        return True
    return segment.high_info_score >= config.high_info_threshold


def _build_validation_segment_if_ready(
    *,
    pending_rule: PendingRule,
    processed_segment: Segment,
    features: pd.DataFrame,
    is_last_segment: bool,
) -> Segment | None:
    start = int(pending_rule.validation_start_index)
    if start >= len(features):
        return None
    target_end = min(len(features), start + int(pending_rule.rule.validation_bars))
    available_end = min(int(processed_segment.end_index), target_end)
    minimum_end = start + int(pending_rule.rule.max_hold_bars) + 2
    if available_end < minimum_end and not is_last_segment:
        return None
    if available_end < target_end and not is_last_segment:
        return None
    if available_end <= start:
        return None
    selected = features.iloc[start:available_end]
    summary = summarize_segment_features(selected)
    regime = str(selected["regime"].mode().iloc[0]) if not selected["regime"].mode().empty else str(selected["regime"].iloc[-1])
    return Segment(
        segment_id=f"valwin_{pending_rule.signature}_{start}_{available_end}",
        start_index=start,
        end_index=available_end,
        start_ts=str(selected["ts"].iloc[0]),
        end_ts=str(selected["ts"].iloc[-1]),
        bars=int(len(selected)),
        symbol_start=str(selected["symbol"].iloc[0]),
        symbol_end=str(selected["symbol"].iloc[-1]),
        regime=regime,
        split_reason="rule_validation_bars",
        high_info_score=float(processed_segment.high_info_score),
        feature_json=json.dumps(summary, sort_keys=True, default=str),
    )


def _has_rare_structure_combo(segment: Segment) -> bool:
    try:
        features = json.loads(segment.feature_json)
    except json.JSONDecodeError:
        return False
    event_keys = ["sweep_signal_count", "choch_signal_count", "bos_signal_count", "fvg_signal_count", "displacement_candle_count"]
    active_events = sum(1 for key in event_keys if float(features.get(key, 0) or 0) > 0)
    return active_events >= 2


def _config_summary(config: EvolutionConfig) -> dict:
    data = asdict(config)
    return {key: str(value) if isinstance(value, Path) else value for key, value in data.items()}
