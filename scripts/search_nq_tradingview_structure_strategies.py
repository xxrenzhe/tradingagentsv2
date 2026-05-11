from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.evolution.nq_data import load_continuous_nq_bars


@dataclass(frozen=True)
class TVStructureCandidate:
    name: str
    direction: int
    trigger: str
    filters: tuple[str, ...]
    stop_points: float
    target_points: float
    hold_bars: int
    session: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Search NQ TradingView-style chart-structure strategies.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--train-end-date", default="2022-01-01")
    parser.add_argument("--cache", default=".tmp/nq-tv-structure-bars-20200101-20260428.pkl")
    parser.add_argument("--summary-output", default=".tmp/nq-tv-structure-strategy-summary.csv")
    parser.add_argument("--trades-output", default=".tmp/nq-tv-structure-strategy-trades.csv")
    parser.add_argument("--report", default="reports/NQ-tradingview-structure-strategy-search.html")
    parser.add_argument("--memory-db")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--max-candidates", type=int, default=400)
    parser.add_argument("--min-test-trades", type=int, default=30)
    parser.add_argument("--gate-win-rate", type=float, default=0.53)
    parser.add_argument("--gate-profit-factor", type=float, default=1.0)
    args = parser.parse_args()

    summary = run_search(
        start_date=args.start_date,
        end_date=args.end_date,
        train_end_date=args.train_end_date,
        cache=Path(args.cache),
        summary_output=Path(args.summary_output),
        trades_output=Path(args.trades_output),
        report=Path(args.report),
        memory_db=Path(args.memory_db) if args.memory_db else None,
        record_memory=bool(args.record_memory),
        max_candidates=args.max_candidates,
        min_test_trades=args.min_test_trades,
        gate_win_rate=args.gate_win_rate,
        gate_profit_factor=args.gate_profit_factor,
    )
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["passing_test_candidates"] > 0 else 2


def run_search(
    *,
    start_date: str,
    end_date: str,
    train_end_date: str,
    cache: Path,
    summary_output: Path,
    trades_output: Path,
    report: Path,
    memory_db: Path | None,
    record_memory: bool,
    max_candidates: int,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
) -> dict[str, Any]:
    bars = load_continuous_nq_bars(start_date=start_date, end_date=end_date, cache_path=cache)
    features = prepare_evolution_features(bars)
    candidates = build_candidates()[:max_candidates]
    train_end = pd.Timestamp(train_end_date, tz="UTC")
    costs = BacktestCosts()
    rows: list[dict[str, Any]] = []
    selected_trades: list[pd.DataFrame] = []
    for candidate in candidates:
        trades = build_candidate_trades(features, candidate, costs)
        train = trades[trades["entry_ts"] < train_end]
        test = trades[trades["entry_ts"] >= train_end]
        train_summary = summarize_trades(train)
        test_summary = summarize_trades(test)
        pass_test = (
            test_summary["trades"] >= min_test_trades
            and test_summary["win_rate"] > gate_win_rate
            and test_summary["profit_factor"] > gate_profit_factor
        )
        rows.append(
            {
                "passes_test_gate": bool(pass_test),
                "name": candidate.name,
                "direction": "long" if candidate.direction > 0 else "short",
                "trigger": candidate.trigger,
                "filters": " & ".join(candidate.filters),
                "session": candidate.session,
                "stop_points": candidate.stop_points,
                "target_points": candidate.target_points,
                "hold_bars": candidate.hold_bars,
                **{f"train_{key}": value for key, value in train_summary.items()},
                **{f"test_{key}": value for key, value in test_summary.items()},
            }
        )
        if pass_test or len(selected_trades) < 5:
            sample = test.copy()
            if not sample.empty:
                sample["candidate"] = candidate.name
                selected_trades.append(sample.tail(1000))

    summary_frame = pd.DataFrame(rows).sort_values(
        ["passes_test_gate", "test_net_points", "test_profit_factor", "test_trades"],
        ascending=[False, False, False, False],
    )
    trades_frame = pd.concat(selected_trades, ignore_index=True, sort=False) if selected_trades else pd.DataFrame()
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    trades_output.parent.mkdir(parents=True, exist_ok=True)
    summary_frame.to_csv(summary_output, index=False)
    trades_frame.to_csv(trades_output, index=False)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        build_report(
            summary_frame=summary_frame,
            trades_frame=trades_frame,
            start_date=start_date,
            end_date=end_date,
            train_end_date=train_end_date,
            feature_rows=len(features),
            min_test_trades=min_test_trades,
            gate_win_rate=gate_win_rate,
            gate_profit_factor=gate_profit_factor,
            summary_output=summary_output,
            trades_output=trades_output,
        ),
        encoding="utf-8",
    )
    if record_memory and memory_db is not None:
        record_search_memory(memory_db, summary_frame, min_test_trades, gate_win_rate, gate_profit_factor)
    return {
        "start_date": start_date,
        "end_date": end_date,
        "train_end_date": train_end_date,
        "feature_rows": int(len(features)),
        "candidates": int(len(candidates)),
        "passing_test_candidates": int(summary_frame["passes_test_gate"].sum()) if not summary_frame.empty else 0,
        "best": summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {},
        "summary_output": str(summary_output),
        "trades_output": str(trades_output),
        "report": str(report),
        "memory_db": str(memory_db) if memory_db else "",
    }


def build_candidates() -> list[TVStructureCandidate]:
    triggers = {
        "long": [
            "choch_long",
            "bos_long",
            "eql_reclaim",
            "demand_retest",
            "vfi_zero_cross_up",
            "vfi_signal_cross_up",
        ],
        "short": [
            "choch_short",
            "bos_short",
            "eqh_reject",
            "supply_retest",
            "vfi_zero_cross_down",
            "vfi_signal_cross_down",
        ],
    }
    filter_sets = {
        "long": [
            ("vfi_positive",),
            ("vfi_positive", "di_long"),
            ("range_discount", "vfi_hist_rising"),
            ("supertrend_long", "vfi_positive"),
            ("macd_positive", "adx_active"),
            ("stoch_recovering", "range_discount"),
            ("orderflow_bullish",),
        ],
        "short": [
            ("vfi_negative",),
            ("vfi_negative", "di_short"),
            ("range_premium", "vfi_hist_falling"),
            ("supertrend_short", "vfi_negative"),
            ("macd_negative", "adx_active"),
            ("stoch_fading", "range_premium"),
            ("orderflow_bearish",),
        ],
    }
    candidates: list[TVStructureCandidate] = []
    for side, direction in [("long", 1), ("short", -1)]:
        for trigger, filters, hold_bars, risk, session in itertools.product(
            triggers[side],
            filter_sets[side],
            [8, 15, 30],
            [(4.0, 6.0), (6.0, 9.0), (8.0, 12.0)],
            ["all", "us_rth", "ldn_ny"],
        ):
            stop, target = risk
            candidates.append(
                TVStructureCandidate(
                    name=f"{side}_{trigger}_{'_'.join(filters)}_sl{stop:g}_tp{target:g}_h{hold_bars}_{session}",
                    direction=direction,
                    trigger=trigger,
                    filters=tuple(filters),
                    stop_points=stop,
                    target_points=target,
                    hold_bars=hold_bars,
                    session=session,
                )
            )
    return candidates


def build_candidate_trades(features: pd.DataFrame, candidate: TVStructureCandidate, costs: BacktestCosts) -> pd.DataFrame:
    data = features.reset_index(drop=True)
    signal = trigger_mask(data, candidate.trigger) & session_mask(data, candidate.session)
    for filter_name in candidate.filters:
        signal &= filter_mask(data, filter_name)
    signal_indexes = [int(index) for index in data.index[signal.fillna(False)]]
    rows: list[dict[str, Any]] = []
    next_available = 0
    for signal_index in signal_indexes:
        entry_index = signal_index + 1
        if entry_index < next_available or entry_index >= len(data):
            continue
        exit_index = min(entry_index + candidate.hold_bars, len(data) - 1)
        if exit_index <= entry_index:
            continue
        if "symbol" in data.columns:
            symbols = data.loc[entry_index:exit_index, "symbol"].astype(str)
            if not symbols.eq(str(data.at[entry_index, "symbol"])).all():
                continue
        direction = candidate.direction
        entry_price = float(data.at[entry_index, "Open"])
        stop_price = entry_price - candidate.stop_points if direction > 0 else entry_price + candidate.stop_points
        target_price = entry_price + candidate.target_points if direction > 0 else entry_price - candidate.target_points
        exit_price = float(data.at[exit_index, "Close"])
        realized_exit_index = exit_index
        exit_reason = "timeout"
        for path_index in range(entry_index, exit_index + 1):
            high = float(data.at[path_index, "High"])
            low = float(data.at[path_index, "Low"])
            stop_hit = low <= stop_price if direction > 0 else high >= stop_price
            target_hit = high >= target_price if direction > 0 else low <= target_price
            if stop_hit:
                exit_price = stop_price
                exit_reason = "stop_loss_ambiguous" if target_hit else "stop_loss"
                realized_exit_index = path_index
                break
            if target_hit:
                exit_price = target_price
                exit_reason = "take_profit"
                realized_exit_index = path_index
                break
        gross_points = (exit_price - entry_price) * direction
        net_points = gross_points - costs.round_trip_cost_points
        rows.append(
            {
                "entry_ts": data.at[entry_index, "ts"],
                "exit_ts": data.at[realized_exit_index, "ts"],
                "direction": direction,
                "entry_price": entry_price,
                "exit_price": float(exit_price),
                "gross_points": float(gross_points),
                "net_points": float(net_points),
                "exit_reason": exit_reason,
            }
        )
        next_available = realized_exit_index + 1
    return pd.DataFrame(rows)


def trigger_mask(data: pd.DataFrame, trigger: str) -> pd.Series:
    if trigger == "choch_long":
        return data["choch_signal"] > 0
    if trigger == "choch_short":
        return data["choch_signal"] < 0
    if trigger == "bos_long":
        return data["bos_signal"] > 0
    if trigger == "bos_short":
        return data["bos_signal"] < 0
    if trigger == "eql_reclaim":
        return data["eql_signal"] > 0
    if trigger == "eqh_reject":
        return data["eqh_signal"] > 0
    if trigger == "demand_retest":
        return data["demand_zone_retest"] > 0
    if trigger == "supply_retest":
        return data["supply_zone_retest"] > 0
    if trigger == "vfi_zero_cross_up":
        return data["vfi_zero_cross_up"] > 0
    if trigger == "vfi_zero_cross_down":
        return data["vfi_zero_cross_down"] > 0
    if trigger == "vfi_signal_cross_up":
        return data["vfi_cross_up"] > 0
    if trigger == "vfi_signal_cross_down":
        return data["vfi_cross_down"] > 0
    raise ValueError(f"unknown trigger: {trigger}")


def filter_mask(data: pd.DataFrame, filter_name: str) -> pd.Series:
    if filter_name == "vfi_positive":
        return data["vfi_130"] > 0
    if filter_name == "vfi_negative":
        return data["vfi_130"] < 0
    if filter_name == "di_long":
        return data["di_spread_14"] > 0
    if filter_name == "di_short":
        return data["di_spread_14"] < 0
    if filter_name == "range_discount":
        return data["range_100_position"] < 0.35
    if filter_name == "range_premium":
        return data["range_100_position"] > 0.65
    if filter_name == "vfi_hist_rising":
        return data["vfi_hist"] > data["vfi_hist"].shift(3)
    if filter_name == "vfi_hist_falling":
        return data["vfi_hist"] < data["vfi_hist"].shift(3)
    if filter_name == "supertrend_long":
        return data["supertrend_direction"] > 0
    if filter_name == "supertrend_short":
        return data["supertrend_direction"] < 0
    if filter_name == "macd_positive":
        return data["macd_hist"] > 0
    if filter_name == "macd_negative":
        return data["macd_hist"] < 0
    if filter_name == "adx_active":
        return data["adx_14"] >= 20
    if filter_name == "stoch_recovering":
        return (data["stoch_rsi_k"] > data["stoch_rsi_d"]) & (data["stoch_rsi_k"] < 80)
    if filter_name == "stoch_fading":
        return (data["stoch_rsi_k"] < data["stoch_rsi_d"]) & (data["stoch_rsi_k"] > 20)
    if filter_name == "orderflow_bullish":
        return (data["cmf_20"] > 0) & (data["obv_slope_20"] > 0)
    if filter_name == "orderflow_bearish":
        return (data["cmf_20"] < 0) & (data["obv_slope_20"] < 0)
    raise ValueError(f"unknown filter: {filter_name}")


def session_mask(data: pd.DataFrame, session: str) -> pd.Series:
    minute = data["minute_of_day"]
    if session == "all":
        return pd.Series(True, index=data.index)
    if session == "us_rth":
        return (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    if session == "ldn_ny":
        return (minute >= 7 * 60) & (minute < 20 * 60)
    raise ValueError(f"unknown session: {session}")


def summarize_trades(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "payoff_ratio": 0.0,
            "expectancy_points": 0.0,
            "max_drawdown_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0)
    wins = net[net > 0]
    losses = net[net < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss_abs = float(-losses.mean()) if not losses.empty else 0.0
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": float(gross_win / gross_loss) if gross_loss else (999.0 if gross_win > 0 else 0.0),
        "win_rate": float((net > 0).mean()),
        "payoff_ratio": float(avg_win / avg_loss_abs) if avg_loss_abs else (999.0 if avg_win > 0 else 0.0),
        "expectancy_points": float(net.mean()),
        "max_drawdown_points": float(drawdown.max()) if not drawdown.empty else 0.0,
    }


def build_report(
    *,
    summary_frame: pd.DataFrame,
    trades_frame: pd.DataFrame,
    start_date: str,
    end_date: str,
    train_end_date: str,
    feature_rows: int,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
    summary_output: Path,
    trades_output: Path,
) -> str:
    passing = int(summary_frame["passes_test_gate"].sum()) if not summary_frame.empty else 0
    best = summary_frame.head(1).to_dict(orient="records")[0] if not summary_frame.empty else {}
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NQ TradingView Structure Strategy Search</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f6f8fb; color:#17212b; margin:0; }}
    main {{ max-width:1280px; margin:0 auto; padding:28px; }}
    h1 {{ font-size:30px; margin:0 0 10px; }}
    h2 {{ font-size:20px; margin:28px 0 12px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }}
    .metric, section {{ background:white; border:1px solid #dce3ea; border-radius:8px; padding:16px; }}
    .label {{ color:#5f6b78; font-size:13px; }}
    .value {{ font-size:23px; font-weight:700; margin-top:4px; }}
    .wrap {{ max-height:650px; overflow:auto; border:1px solid #dce3ea; border-radius:8px; }}
    table {{ border-collapse:collapse; width:100%; font-size:13px; background:white; }}
    th, td {{ border-bottom:1px solid #e5e9ee; padding:8px 10px; text-align:left; vertical-align:top; }}
    th {{ background:#eef3f8; position:sticky; top:0; }}
    .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .pass {{ color:#08783f; font-weight:700; }}
    .fail {{ color:#a24100; font-weight:700; }}
    code {{ background:#edf2f7; padding:2px 4px; border-radius:4px; }}
  </style>
</head>
<body>
<main>
  <h1>NQ TradingView 结构/指标策略搜索</h1>
  <p>从截图抽象出 BOS/ChoCH、EQH/EQL、供需区 retest、VFI 资金流、ADX/DI、MACD、Stoch RSI、Supertrend 等可复现特征，并在 2020+ 1分钟连续 NQ 数据上做训练/测试拆分。</p>
  <div class="grid">
    {_metric("通过测试门槛", f"{passing}/{len(summary_frame)}")}
    {_metric("最佳策略", _esc(best.get("name", "N/A")))}
    {_metric("测试 Win", _fmt_pct(best.get("test_win_rate")))}
    {_metric("测试 PF", _fmt_num(best.get("test_profit_factor")))}
    {_metric("测试 Net", _fmt_num(best.get("test_net_points")))}
    {_metric("Feature Rows", f"{feature_rows:,}")}
  </div>
  <section>
    <h2>门槛</h2>
    <p>训练窗口：{_esc(start_date)} 到 {_esc(train_end_date)}；测试窗口：{_esc(train_end_date)} 到 {_esc(end_date)}。测试门槛：交易数 >= <code>{min_test_trades}</code>，胜率 &gt; <code>{gate_win_rate:.2%}</code>，PF &gt; <code>{gate_profit_factor:.2f}</code>。</p>
    <p>CSV 输出：<code>{_esc(summary_output)}</code>，<code>{_esc(trades_output)}</code>。</p>
  </section>
  <section>
    <h2>Top 候选</h2>
    <div class="wrap">{_table(summary_frame.head(100), _summary_columns())}</div>
  </section>
  <section>
    <h2>交易样本</h2>
    <div class="wrap">{_table(trades_frame.tail(300), ["candidate", "entry_ts", "exit_ts", "direction", "entry_price", "exit_price", "net_points", "exit_reason"])}</div>
  </section>
</main>
</body>
</html>
"""


def record_search_memory(
    memory_db: Path,
    summary_frame: pd.DataFrame,
    min_test_trades: int,
    gate_win_rate: float,
    gate_profit_factor: float,
) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        for _, row in summary_frame.head(50).iterrows():
            name = str(row["name"])
            note_type = "effective_feature" if bool(row["passes_test_gate"]) else "failure_mode"
            signature = "tv_" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_{note_type}_{int(row['test_trades'])}"
            lesson = (
                f"TradingView-style structure search candidate {name}: test trades={int(row['test_trades'])}, "
                f"win_rate={float(row['test_win_rate']):.2%}, PF={float(row['test_profit_factor']):.2f}, "
                f"net={float(row['test_net_points']):.2f}. Gate requires trades>={min_test_trades}, "
                f"win_rate>{gate_win_rate:.2%}, PF>{gate_profit_factor:.2f}."
            )
            avoid_when = "Avoid as standalone strategy until it passes OOS win-rate/PF gate."
            if bool(row["passes_test_gate"]):
                avoid_when = "Avoid if later walk-forward folds fall below OOS gate."
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
                    f"Candidate trigger={row['trigger']}; filters={row['filters']}; session={row['session']}",
                    avoid_when,
                    lesson,
                    (
                        f"train_trades={int(row['train_trades'])}; train_pf={float(row['train_profit_factor']):.4f}; "
                        f"test_trades={int(row['test_trades'])}; test_pf={float(row['test_profit_factor']):.4f}; "
                        f"test_win_rate={float(row['test_win_rate']):.4f}; test_net={float(row['test_net_points']):.2f}"
                    ),
                    min(1.0, max(0.05, float(row["test_trades"]) / 300.0)),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def _summary_columns() -> list[str]:
    return [
        "passes_test_gate",
        "name",
        "direction",
        "trigger",
        "filters",
        "session",
        "stop_points",
        "target_points",
        "hold_bars",
        "train_trades",
        "train_net_points",
        "train_profit_factor",
        "train_win_rate",
        "test_trades",
        "test_net_points",
        "test_profit_factor",
        "test_win_rate",
        "test_payoff_ratio",
        "test_max_drawdown_points",
    ]


def _table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    available = [column for column in columns if column in frame.columns]
    header = "".join(f"<th>{_esc(column)}</th>" for column in available)
    body = []
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
                text = _esc(value)
            cells.append(f"<td class=\"{css}\">{text}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def _metric(label: str, value: str) -> str:
    return f"<div class=\"metric\"><div class=\"label\">{_esc(label)}</div><div class=\"value\">{value}</div></div>"


def _fmt_pct(value: Any) -> str:
    return f"{float(value):.2%}" if _is_number(value) else "N/A"


def _fmt_num(value: Any) -> str:
    if not _is_number(value):
        return "N/A"
    return f"{float(value):,.3f}"


def _is_number(value: Any) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return pd.notna(value)


def _esc(value: Any) -> str:
    return html.escape(str(value))


if __name__ == "__main__":
    raise SystemExit(main())
