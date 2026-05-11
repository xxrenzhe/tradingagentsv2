from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.evolution import EvolutionConfig, run_evolution
from tradingagents.evolution.backtest import validate_rule_on_segment
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.llm import MockRuleGenerator
from tradingagents.evolution.memory import EvolutionMemory
from tradingagents.evolution.nq_data import load_continuous_nq_bars
from tradingagents.evolution.rules import EntryCondition, TradingRule, rule_signature
from tradingagents.evolution.segmentation import SegmentConfig, segment_market


FIXTURE = Path("tests/fixtures/nq_evolution_llm.jsonl")


def _synthetic_nq_bars(rows: int = 140, start: str = "2020-01-02 13:30:00+00:00") -> pd.DataFrame:
    ts = pd.date_range(start, periods=rows, freq="min")
    prices = []
    price = 9000.0
    for index in range(rows):
        if index < 35:
            price += 1.2
        elif index < 70:
            price -= 1.6
        elif index < 105:
            price += 1.8
        else:
            price -= 1.1
        prices.append(price)

    bars = []
    for index, close in enumerate(prices):
        open_ = close - (0.8 if index % 2 == 0 else -0.4)
        high = max(open_, close) + 2.0
        low = min(open_, close) - 2.0
        if index in {42, 86}:
            high += 9.0
            low -= 9.0
        bars.append(
            {
                "ts": ts[index],
                "symbol": "NQH0",
                "Open": open_,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": 100 + index % 11,
            }
        )
    return pd.DataFrame(bars)


def test_load_continuous_nq_selects_highest_volume_contract_per_minute(tmp_path: Path) -> None:
    csv_path = tmp_path / "bars.csv"
    rows = [
        {"ts_event": "2020-01-02T00:00:00Z", "symbol": "NQH0", "open": 1, "high": 2, "low": 0, "close": 1.5, "volume": 10},
        {"ts_event": "2020-01-02T00:00:00Z", "symbol": "NQM0", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 50},
        {"ts_event": "2020-01-02T00:01:00Z", "symbol": "NQH0-NQM0", "open": 1, "high": 2, "low": 0, "close": 1, "volume": 99},
        {"ts_event": "2020-01-02T00:01:00Z", "symbol": "NQH0", "open": 2, "high": 3, "low": 1, "close": 2.5, "volume": 20},
    ]
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    bars = load_continuous_nq_bars(start_date="2020-01-02", end_date="2020-01-03", source_csv=csv_path)

    assert list(bars["symbol"]) == ["NQM0", "NQH0"]
    assert list(bars["Close"]) == [11.0, 2.5]


def test_dynamic_segmentation_uses_100_as_baseline_not_fixed_length() -> None:
    features = prepare_evolution_features(_synthetic_nq_bars(160))
    segments = segment_market(features, SegmentConfig(base_bars=100, min_bars=20, max_bars=130, split_threshold=0.35))

    assert segments
    assert segments[0].start_index == 0
    for previous, current in zip(segments, segments[1:]):
        assert previous.end_index == current.start_index
    assert segments[-1].end_index == len(features)
    assert any(segment.bars != 100 for segment in segments)
    assert {"sweep_signal_count", "pd_zone_last"} & set(json.loads(segments[0].feature_json))


def test_rule_signature_is_stable_for_reordered_conditions() -> None:
    left = TradingRule(
        pattern_name="a",
        hypothesis="same",
        direction="long",
        entry_conditions=[
            EntryCondition(feature="z_30", operator="<=", value=-0.5),
            EntryCondition(feature="regime", operator="==", value="range"),
        ],
    )
    right = TradingRule(
        pattern_name="b",
        hypothesis="same",
        direction="long",
        entry_conditions=list(reversed(left.entry_conditions)),
    )

    assert rule_signature(left) == rule_signature(right)


def test_backtest_uses_next_open_validation_bars_and_stop_first() -> None:
    frame = pd.DataFrame(
        [
            {"ts": "2020-01-02T00:00:00Z", "Open": 100, "High": 101, "Low": 99, "Close": 100, "Volume": 1, "symbol": "NQH0", "z_30": -1.0},
            {"ts": "2020-01-02T00:01:00Z", "Open": 100, "High": 107, "Low": 95, "Close": 102, "Volume": 1, "symbol": "NQH0", "z_30": 0.0},
            {"ts": "2020-01-02T00:02:00Z", "Open": 102, "High": 110, "Low": 101, "Close": 109, "Volume": 1, "symbol": "NQH0", "z_30": -1.0},
            {"ts": "2020-01-02T00:03:00Z", "Open": 109, "High": 115, "Low": 108, "Close": 114, "Volume": 1, "symbol": "NQH0", "z_30": -1.0},
        ]
    )
    rule = TradingRule(
        pattern_name="ambiguous",
        hypothesis="test",
        direction="long",
        entry_conditions=[EntryCondition(feature="z_30", operator="<=", value=-0.5)],
        stop_points=4.0,
        target_points=6.0,
        max_hold_bars=1,
        validation_bars=3,
        max_trades_per_validation=10,
    )
    segment = segment_market(prepare_evolution_features(_synthetic_nq_bars(30)), SegmentConfig(min_bars=5))[0]
    segment = type(segment)(
        segment_id="seg_manual",
        start_index=0,
        end_index=4,
        start_ts=str(frame["ts"].iloc[0]),
        end_ts=str(frame["ts"].iloc[-1]),
        bars=4,
        symbol_start="NQH0",
        symbol_end="NQH0",
        regime="range",
        split_reason="manual",
        high_info_score=1.0,
        feature_json="{}",
    )

    result = validate_rule_on_segment(
        rule=rule,
        rule_id="rule",
        signature="sig",
        analysis_segment_id="seg_previous",
        validation_segment=segment,
        features=frame,
        costs=BacktestCosts(slippage_ticks_per_side=0, commission_per_contract=0),
    )

    assert result.trades == 1
    assert result.trade_rows[0]["entry_price"] == 100.0
    assert result.trade_rows[0]["exit_reason"] == "stop_loss_ambiguous"
    assert result.trade_rows[0]["net_points"] == -4.0


def test_memory_records_full_chain_and_limits_prompt_state(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.sqlite"
    memory = EvolutionMemory(db_path)
    features = prepare_evolution_features(_synthetic_nq_bars(70))
    segment = segment_market(features, SegmentConfig(min_bars=20, split_threshold=0.2))[0]
    generator = MockRuleGenerator(FIXTURE)
    try:
        memory.upsert_segment(segment)
        packet = memory.build_memory_packet(segment=segment, token_budget=100)
        generated = generator.generate(segment=segment, memory_packet=packet)
        assert generated.rule is not None
        memory.record_llm_analysis(generated.analysis_event)
        memory.record_rule(
            rule_id="rule_1",
            signature=generated.signature or "signature",
            rule=generated.rule,
            analysis_id=generated.analysis_event["analysis_id"],
            segment_id=segment.segment_id,
        )
        result = validate_rule_on_segment(
            rule=generated.rule,
            rule_id="rule_1",
            signature=generated.signature or "signature",
            analysis_segment_id=segment.segment_id,
            validation_segment=segment,
            features=features,
            costs=BacktestCosts(slippage_ticks_per_side=0, commission_per_contract=0),
        )
        memory.record_validation(result)
        for index in range(5):
            memory.connection.execute(
                """
                INSERT INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, 'effective_feature', 'range', 'same', 'none', ?, 'evidence', ?, 'active', NULL, ?, NULL, 0)
                """,
                (f"note_extra_{index}", "sig_extra", f"lesson {index}", 0.5 + index / 10, "2020-01-01T00:00:00+00:00"),
            )
        memory.connection.commit()
        memory.limit_active_notes(max_per_key=3)
        memory.connection.commit()

        counts = memory.counts()
        assert counts["segments"] == 1
        assert counts["llm_analyses"] == 1
        assert counts["pattern_rules"] == 1
        assert counts["validations"] == 1
        assert counts["pattern_stats"] == 1
        assert counts["memory_packets"] >= 1
        active_notes = memory.connection.execute(
            "SELECT COUNT(*) AS n FROM experience_notes WHERE status = 'active' AND rule_signature = 'sig_extra'"
        ).fetchone()["n"]
        assert active_notes == 3
        assert memory.memory_token_total() > 0
    finally:
        memory.close()


def test_memory_packet_prefers_matching_regime_and_respects_budget(tmp_path: Path) -> None:
    db_path = tmp_path / "memory-budget.sqlite"
    memory = EvolutionMemory(db_path)
    try:
        for signature, regime, edge_score in [
            ("sig_range", "range", 0.5),
            ("sig_trend", "trend_up", 9.0),
        ]:
            memory.connection.execute(
                """
                INSERT INTO pattern_stats (
                    rule_signature, status, validations, trades, net_points, max_drawdown_points,
                    profit_factor, win_rate, positive_validation_rate, recent_net_points,
                    recent_profit_factor, consecutive_losing_validations, edge_score,
                    last_promoted_at, last_validated_at, retired_reason
                ) VALUES (?, 'research', 10, 20, 40, 8, 1.5, 0.6, 0.7, 10, 1.2, 0, ?, NULL, '2020-01-01T00:00:00+00:00', NULL)
                """,
                (signature, edge_score),
            )
            rule = TradingRule(
                pattern_name=signature,
                hypothesis="budget",
                market_regime=regime,
                direction="long",
                entry_conditions=[EntryCondition(feature="z_30", operator="<=", value=-0.5)],
            )
            memory.record_rule(
                rule_id=f"rule_{signature}",
                signature=signature,
                rule=rule,
                analysis_id="analysis",
                segment_id="segment",
            )
        features = prepare_evolution_features(_synthetic_nq_bars(60))
        segment = segment_market(features, SegmentConfig(min_bars=20))[0]
        segment = type(segment)(
            segment_id=segment.segment_id,
            start_index=segment.start_index,
            end_index=segment.end_index,
            start_ts=segment.start_ts,
            end_ts=segment.end_ts,
            bars=segment.bars,
            symbol_start=segment.symbol_start,
            symbol_end=segment.symbol_end,
            regime="range",
            split_reason=segment.split_reason,
            high_info_score=segment.high_info_score,
            feature_json=segment.feature_json,
        )

        packet = memory.build_memory_packet(segment=segment, token_budget=180)

        assert packet["top_rules"]
        assert packet["top_rules"][0]["rule_signature"] == "sig_range"
        assert packet["token_estimate"] <= 180
    finally:
        memory.close()


def test_pipeline_smoke_writes_sqlite_html_and_validation(tmp_path: Path) -> None:
    summary = run_evolution(
        EvolutionConfig(
            memory_db=tmp_path / "evolution.sqlite",
            report=tmp_path / "evolution.html",
            mock_llm_fixture=FIXTURE,
            llm_mode="strict-every-segment",
            base_bars=35,
            min_bars=20,
            max_bars=45,
            split_threshold=2.0,
            daily_llm_call_limit=10,
            max_segments=4,
        ),
        bars=_synthetic_nq_bars(130),
    )

    assert summary["llm_calls"] >= 2
    assert summary["counts"]["segments"] >= 2
    assert summary["counts"]["pattern_rules"] >= 2
    assert summary["counts"]["validations"] >= 1
    assert summary["counts"]["memory_packets"] >= 2
    html = Path(summary["report"]).read_text(encoding="utf-8")
    for label in ["动态窗口概览", "Top 模式统计", "记忆系统状态", "失败模式总结"]:
        assert label in html


def test_cli_smoke_uses_source_csv_and_mock_llm(tmp_path: Path) -> None:
    csv_path = tmp_path / "source.csv"
    source = _synthetic_nq_bars(130).rename(
        columns={"ts": "ts_event", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    source.to_csv(csv_path, index=False)
    db_path = tmp_path / "cli.sqlite"
    report_path = tmp_path / "cli.html"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_nq_trading_evolution.py",
            "--source-csv",
            str(csv_path),
            "--start-date",
            "2020-01-02",
            "--end-date",
            "2020-01-03",
            "--mock-llm-fixture",
            str(FIXTURE),
            "--memory-db",
            str(db_path),
            "--report",
            str(report_path),
            "--llm-mode",
            "strict-every-segment",
            "--base-bars",
            "35",
            "--min-bars",
            "20",
            "--max-bars",
            "45",
            "--split-threshold",
            "2.0",
            "--daily-llm-call-limit",
            "10",
            "--max-segments",
            "4",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )

    summary = json.loads(result.stdout)
    assert summary["counts"]["segments"] >= 2
    assert summary["counts"]["pattern_rules"] >= 2
    assert summary["counts"]["validations"] >= 1
    assert db_path.exists()
    assert report_path.exists()
    with sqlite3.connect(db_path) as connection:
        validation_count = connection.execute("SELECT COUNT(*) FROM validations").fetchone()[0]
    assert validation_count >= 1
