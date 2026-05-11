from __future__ import annotations

import argparse
import html
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.evolution.backtest import ValidationResult, backtest_rule_on_features
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.evolution.nq_data import load_continuous_nq_bars
from tradingagents.evolution.rules import TradingRule, parse_rule_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest learned NQ evolution rules on post-2020 1-minute bars.")
    parser.add_argument("--memory-db", default=".tmp/nq-evolution-real-20200101-20200110.sqlite")
    parser.add_argument("--start-date", default="2020-01-10")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--cache", default=".tmp/nq-evolved-rules-backtest-bars.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--summary-output", default=".tmp/nq-evolved-rule-backtest-summary.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-evolved-rule-backtest-trades.csv")
    parser.add_argument("--report", default="reports/NQ-evolved-rules-post2020-backtest.html")
    parser.add_argument("--min-trades", type=int, default=30)
    parser.add_argument("--gate-win-rate", type=float, default=0.53)
    parser.add_argument("--gate-profit-factor", type=float, default=1.0)
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--write-db")
    parser.add_argument("--max-trades-per-rule", type=int)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    parser.add_argument("--commission-per-contract", type=float, default=2.5)
    args = parser.parse_args()

    summary = run_backtest(
        memory_db=Path(args.memory_db),
        start_date=args.start_date,
        end_date=args.end_date,
        cache=Path(args.cache),
        source_csv=Path(args.source_csv) if args.source_csv else None,
        source_zip=Path(args.source_zip) if args.source_zip else None,
        summary_output=Path(args.summary_output),
        trades_output=Path(args.trades_output),
        report=Path(args.report),
        min_trades=args.min_trades,
        gate_win_rate=args.gate_win_rate,
        gate_profit_factor=args.gate_profit_factor,
        record_memory=bool(args.record_memory),
        write_db=Path(args.write_db) if args.write_db else None,
        max_trades_per_rule=args.max_trades_per_rule,
        costs=BacktestCosts(
            slippage_ticks_per_side=float(args.slippage_ticks_per_side),
            commission_per_contract=float(args.commission_per_contract),
        ),
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["passing_rules"] > 0 else 2


def run_backtest(
    *,
    memory_db: Path,
    start_date: str,
    end_date: str,
    cache: Path,
    source_csv: Path | None,
    source_zip: Path | None,
    summary_output: Path,
    trades_output: Path,
    report: Path,
    min_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    record_memory: bool,
    write_db: Path | None,
    max_trades_per_rule: int | None,
    costs: BacktestCosts,
) -> dict[str, Any]:
    learned_rules = load_learned_rules(memory_db)
    bars = load_continuous_nq_bars(
        start_date=start_date,
        end_date=end_date,
        cache_path=cache,
        source_csv=source_csv,
        source_zip=source_zip,
    )
    features = prepare_evolution_features(bars)
    results: list[ValidationResult] = []
    rule_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    validation_segment_id = f"oos_{_compact_date(start_date)}_{_compact_date(end_date)}"
    for learned in learned_rules:
        validation_id = f"{validation_segment_id}_{learned['rule_signature']}"
        result = backtest_rule_on_features(
            rule=learned["rule"],
            rule_id=learned["rule_id"],
            signature=learned["rule_signature"],
            features=features,
            analysis_segment_id=learned["segment_id"],
            validation_segment_id=validation_segment_id,
            validation_id=validation_id,
            max_trades=max_trades_per_rule,
            costs=costs,
        )
        results.append(result)
        row = _summary_row(learned, result, min_trades, gate_win_rate, gate_profit_factor)
        rule_rows.append(row)
        for trade in result.trade_rows:
            enriched = dict(trade)
            enriched["rule_id"] = learned["rule_id"]
            enriched["pattern_name"] = learned["pattern_name"]
            enriched["payoff_ratio"] = row["payoff_ratio"]
            trade_rows.append(enriched)

    summary_frame = pd.DataFrame(rule_rows).sort_values(
        ["passes_gate", "trades", "net_points", "profit_factor"],
        ascending=[False, False, False, False],
    )
    trades_frame = pd.DataFrame(trade_rows)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(summary_output, index=False)
    trades_frame.to_csv(trades_output, index=False)

    target_db = _record_results(
        source_db=memory_db,
        write_db=write_db,
        record_memory=record_memory,
        results=results,
        summary_frame=summary_frame,
    )

    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        _build_html_report(
            summary_frame=summary_frame,
            trades_frame=trades_frame,
            memory_db=memory_db,
            target_db=target_db,
            start_date=start_date,
            end_date=end_date,
            feature_rows=len(features),
            feature_start=str(features["ts"].min()) if not features.empty else "",
            feature_end=str(features["ts"].max()) if not features.empty else "",
            min_trades=min_trades,
            gate_win_rate=gate_win_rate,
            gate_profit_factor=gate_profit_factor,
            costs=costs,
            summary_output=summary_output,
            trades_output=trades_output,
        ),
        encoding="utf-8",
    )

    return {
        "memory_db": str(memory_db),
        "write_db": str(target_db) if target_db else "",
        "start_date": start_date,
        "end_date": end_date,
        "feature_rows": int(len(features)),
        "rules": int(len(learned_rules)),
        "summary_output": str(summary_output),
        "trades_output": str(trades_output),
        "report": str(report),
        "passing_rules": int(summary_frame["passes_gate"].sum()) if not summary_frame.empty else 0,
        "best": summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {},
    }


def load_learned_rules(memory_db: Path) -> list[dict[str, Any]]:
    if not memory_db.exists():
        raise FileNotFoundError(f"Memory DB not found: {memory_db}")
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(memory_db) as connection:
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
            """
            SELECT rule_id, rule_signature, segment_id, pattern_name, direction,
                   market_regime, rule_json, created_at
            FROM pattern_rules
            WHERE status != 'retired'
            ORDER BY created_at, rule_id
            """
        ).fetchall():
            payload = json.loads(row["rule_json"])
            rule = parse_rule_payload(payload)
            rows.append(
                {
                    "rule_id": row["rule_id"],
                    "rule_signature": row["rule_signature"],
                    "segment_id": row["segment_id"],
                    "pattern_name": row["pattern_name"],
                    "direction": row["direction"],
                    "market_regime": row["market_regime"],
                    "rule": rule,
                    "created_at": row["created_at"],
                }
            )
    if not rows:
        raise ValueError(f"No active learned rules found in {memory_db}")
    return rows


def _summary_row(
    learned: dict[str, Any],
    result: ValidationResult,
    min_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
) -> dict[str, Any]:
    rule: TradingRule = learned["rule"]
    avg_loss_abs = abs(float(result.avg_loss_points))
    payoff_ratio = float(result.avg_win_points / avg_loss_abs) if avg_loss_abs else (999.0 if result.avg_win_points > 0 else 0.0)
    passes_gate = result.trades >= min_trades and result.win_rate > gate_win_rate and result.profit_factor > gate_profit_factor
    return {
        "passes_gate": bool(passes_gate),
        "rule_signature": learned["rule_signature"],
        "rule_id": learned["rule_id"],
        "pattern_name": learned["pattern_name"],
        "direction": learned["direction"],
        "market_regime": learned["market_regime"],
        "trades": int(result.trades),
        "net_points": float(result.net_points),
        "gross_points": float(result.gross_points),
        "profit_factor": float(result.profit_factor),
        "win_rate": float(result.win_rate),
        "payoff_ratio": payoff_ratio,
        "avg_win_points": float(result.avg_win_points),
        "avg_loss_points": float(result.avg_loss_points),
        "expectancy_points": float(result.expectancy_points),
        "max_drawdown_points": float(result.max_drawdown_points),
        "stop_points": float(rule.stop_points),
        "target_points": float(rule.target_points),
        "max_hold_bars": int(rule.max_hold_bars),
        "validation_status": result.validation_status,
        "failure_reason": result.failure_reason,
        "exit_reason_json": result.exit_reason_json,
        "entry_conditions": json.dumps([condition.model_dump() for condition in rule.entry_conditions], sort_keys=True, default=str),
    }


def _record_results(
    *,
    source_db: Path,
    write_db: Path | None,
    record_memory: bool,
    results: list[ValidationResult],
    summary_frame: pd.DataFrame,
) -> Path | None:
    if not record_memory:
        return None
    target_db = write_db or source_db
    if write_db is not None:
        write_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_db, write_db)
    memory = EvolutionMemory(target_db)
    try:
        for result in results:
            memory.record_validation(result)
        _record_backtest_notes(memory, summary_frame)
    finally:
        memory.close()
    return target_db


def _record_backtest_notes(memory: EvolutionMemory, summary_frame: pd.DataFrame) -> None:
    if summary_frame.empty:
        return
    now = utc_now()
    for _, row in summary_frame.iterrows():
        signature = str(row["rule_signature"])
        note_type = "effective_feature" if bool(row["passes_gate"]) else "failure_mode"
        status = "active"
        note_id = f"note_{signature}_oos_{note_type}_{_hashable_metric(row)}"
        lesson = (
            f"OOS backtest: {int(row['trades'])} trades, win_rate {float(row['win_rate']):.2%}, "
            f"PF {float(row['profit_factor']):.2f}, payoff {float(row['payoff_ratio']):.2f}, "
            f"net {float(row['net_points']):.2f} points."
        )
        applies_when = f"Use only when entry conditions match: {row['entry_conditions']}"
        avoid_when = "Avoid production use until OOS gate is passed with enough trades."
        if bool(row["passes_gate"]):
            avoid_when = "Avoid if recent OOS validation decays below win_rate 53% or PF 1.0."
        confidence = min(1.0, max(0.05, min(float(row["trades"]) / 250.0, 1.0) * min(float(row["profit_factor"]) / 2.0, 1.0)))
        memory.connection.execute(
            """
            INSERT OR REPLACE INTO experience_notes (
                note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                lesson, evidence_summary, confidence, status, supersedes_note_id,
                created_at, last_used_at, use_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, 0)
            """,
            (
                note_id,
                signature,
                note_type,
                str(row.get("market_regime", "")) or None,
                applies_when,
                avoid_when,
                lesson,
                (
                    f"oos_trades={int(row['trades'])}; win_rate={float(row['win_rate']):.4f}; "
                    f"profit_factor={float(row['profit_factor']):.4f}; payoff_ratio={float(row['payoff_ratio']):.4f}; "
                    f"net_points={float(row['net_points']):.2f}"
                ),
                confidence,
                status,
                now,
            ),
        )
    memory.limit_active_notes()
    memory.connection.commit()


def _build_html_report(
    *,
    summary_frame: pd.DataFrame,
    trades_frame: pd.DataFrame,
    memory_db: Path,
    target_db: Path | None,
    start_date: str,
    end_date: str,
    feature_rows: int,
    feature_start: str,
    feature_end: str,
    min_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    costs: BacktestCosts,
    summary_output: Path,
    trades_output: Path,
) -> str:
    passing = int(summary_frame["passes_gate"].sum()) if not summary_frame.empty else 0
    best = summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {}
    by_status = (
        summary_frame.groupby("passes_gate")
        .agg(rules=("rule_signature", "count"), trades=("trades", "sum"), net_points=("net_points", "sum"))
        .reset_index()
        if not summary_frame.empty
        else pd.DataFrame()
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ Evolved Rule OOS Backtest</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #15202b; background: #f7f8fa; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 28px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 20px; margin-top: 28px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .metric, section {{ background: white; border: 1px solid #dce1e7; border-radius: 8px; padding: 16px; }}
    .metric .label {{ color: #5b6673; font-size: 13px; }}
    .metric .value {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; background: white; }}
    th, td {{ border-bottom: 1px solid #e5e8ec; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f6; position: sticky; top: 0; z-index: 1; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .pass {{ color: #0b7a3b; font-weight: 700; }}
    .fail {{ color: #a33a00; font-weight: 700; }}
    .table-wrap {{ overflow: auto; max-height: 620px; border: 1px solid #dce1e7; border-radius: 8px; }}
    .muted {{ color: #5b6673; }}
    code {{ background: #eef2f6; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
<main>
  <h1>NQ 进化策略 2020+ 1分钟 OOS 回测</h1>
  <p class="muted">规则来自 <code>{_esc(memory_db)}</code>；回测窗口 {html.escape(start_date)} 到 {html.escape(end_date)}，同一套技术、K线、趋势震荡、Lightglow/ICT 与量价特征参与触发。</p>
  <div class="grid">
    {_metric("通过规则", f"{passing}/{len(summary_frame)}")}
    {_metric("最佳规则", _esc(str(best.get("pattern_name", ""))) if best else "N/A")}
    {_metric("最佳 Win Rate", _fmt_pct(best.get("win_rate")) if best else "N/A")}
    {_metric("最佳 PF", _fmt_num(best.get("profit_factor")) if best else "N/A")}
    {_metric("最佳 Payoff", _fmt_num(best.get("payoff_ratio")) if best else "N/A")}
    {_metric("最佳 Net Points", _fmt_num(best.get("net_points")) if best else "N/A")}
    {_metric("Feature Rows", f"{feature_rows:,}")}
    {_metric("成本", f"{costs.round_trip_cost_points:.3f} pts/RT")}
  </div>

  <section>
    <h2>门槛与结论</h2>
    <p>门槛：交易数 >= <code>{min_trades}</code>，胜率 &gt; <code>{gate_win_rate:.2%}</code>，Profit Factor &gt; <code>{gate_profit_factor:.2f}</code>。盈亏比另以 avg win / abs(avg loss) 输出，避免把 PF 和单笔 payoff 混为一谈。</p>
    <p>{_conclusion(passing)}</p>
    <p class="muted">数据实际覆盖：{_esc(feature_start)} 到 {_esc(feature_end)}。输出：<code>{_esc(summary_output)}</code>，<code>{_esc(trades_output)}</code>{_memory_suffix(target_db)}。</p>
  </section>

  <section>
    <h2>规则排名</h2>
    <div class="table-wrap">{_frame_table(summary_frame.head(50), _summary_columns())}</div>
  </section>

  <section>
    <h2>通过/失败聚合</h2>
    <div class="table-wrap">{_frame_table(by_status, ["passes_gate", "rules", "trades", "net_points"])}</div>
  </section>

  <section>
    <h2>最近交易样本</h2>
    <div class="table-wrap">{_frame_table(trades_frame.tail(200), ["entry_ts", "exit_ts", "pattern_name", "direction", "entry_price", "exit_price", "net_points", "exit_reason"])}</div>
  </section>
</main>
</body>
</html>
"""


def _summary_columns() -> list[str]:
    return [
        "passes_gate",
        "pattern_name",
        "direction",
        "market_regime",
        "trades",
        "net_points",
        "profit_factor",
        "win_rate",
        "payoff_ratio",
        "expectancy_points",
        "max_drawdown_points",
        "stop_points",
        "target_points",
        "max_hold_bars",
        "entry_conditions",
    ]


def _frame_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p class=\"muted\">No rows.</p>"
    available = [column for column in columns if column in frame.columns]
    header = "".join(f"<th>{_esc(column)}</th>" for column in available)
    rows = []
    for _, row in frame[available].iterrows():
        cells = []
        for column in available:
            value = row[column]
            css = "num" if _is_number(value) and not isinstance(value, bool) else ""
            if isinstance(value, bool):
                text = "PASS" if value else "FAIL"
                css = "pass" if value else "fail"
            elif "rate" in column and _is_number(value):
                text = _fmt_pct(value)
            elif _is_number(value):
                text = _fmt_num(value)
            else:
                text = _esc(str(value))
            cells.append(f"<td class=\"{css}\">{text}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"


def _metric(label: str, value: str) -> str:
    return f"<div class=\"metric\"><div class=\"label\">{_esc(label)}</div><div class=\"value\">{value}</div></div>"


def _conclusion(passing: int) -> str:
    if passing > 0:
        return f"<span class=\"pass\">找到 {passing} 条满足胜率和 PF 门槛的 learned strategy。</span>"
    return "<span class=\"fail\">未找到满足胜率 &gt; 53% 且 PF &gt; 1 的 learned strategy，需要继续扩大样本并进化交易系统。</span>"


def _memory_suffix(target_db: Path | None) -> str:
    if target_db is None:
        return ""
    return f"，OOS 结果已写入 <code>{_esc(target_db)}</code>"


def _fmt_pct(value: Any) -> str:
    if not _is_number(value):
        return "N/A"
    return f"{float(value):.2%}"


def _fmt_num(value: Any) -> str:
    if not _is_number(value):
        return "N/A"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    return f"{number:.3f}"


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return pd.notna(value)


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _compact_date(value: str) -> str:
    return value.replace("-", "").replace(":", "").replace(" ", "")


def _hashable_metric(row: pd.Series) -> str:
    return f"{int(row['trades'])}_{float(row['win_rate']):.4f}_{float(row['profit_factor']):.4f}".replace(".", "p")


if __name__ == "__main__":
    raise SystemExit(main())
