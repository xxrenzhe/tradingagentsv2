from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_INPUTS = [
    (".tmp/nq-bar-best-strategy-walkforward-aggregate.csv", "walkforward_5y_1m"),
]


def load_candidate_results(inputs: list[tuple[str, str]]) -> pd.DataFrame:
    frames = []
    for path_text, universe in inputs:
        path = Path(path_text)
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame = frame.copy()
        _normalize_candidate_columns(frame)
        frame["candidate_universe"] = universe
        frame["source"] = frame.get("source", "walkforward")
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    rows = pd.concat(frames, ignore_index=True, sort=False)
    rows = rows.loc[:, ~rows.columns.duplicated()]
    return rows


def load_trade_results(path_text: str | None) -> pd.DataFrame:
    if not path_text:
        return pd.DataFrame()
    path = Path(path_text)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    required = {"candidate", "direction", "net_points"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame()
    frame = frame.copy()
    frame["direction"] = pd.to_numeric(frame["direction"], errors="coerce")
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce")
    return frame.dropna(subset=["candidate", "direction", "net_points"])


def _normalize_candidate_columns(frame: pd.DataFrame) -> None:
    fallback_columns = {
        "full_trades": ["test_trades"],
        "full_net_points": ["test_net_points"],
        "full_max_drawdown_points": ["test_max_drawdown_points"],
        "full_profit_factor": ["avg_test_profit_factor"],
        "full_win_rate": ["avg_test_win_rate"],
        "full_stability": ["avg_test_stability"],
        "positive_fold_rate": ["positive_test_fold_rate"],
        "positive_window_rate": ["pass_fold_rate", "positive_test_fold_rate"],
        "min_window_net_points": ["min_test_net_points"],
        "stress_net_points": ["min_test_net_points", "test_net_points"],
        "best_strategy_score": ["long_history_score"],
        "selected_folds": ["selected_folds"],
        "live_ready": ["stable_candidate"],
    }
    for target, fallbacks in fallback_columns.items():
        if target not in frame.columns:
            frame[target] = pd.NA
        for fallback in fallbacks:
            if fallback in frame.columns:
                frame[target] = frame[target].fillna(frame[fallback])

    if "name" not in frame.columns and "candidate" in frame.columns:
        frame["name"] = frame["candidate"]
    if "source" not in frame.columns:
        frame["source"] = "walkforward"
    if "session" not in frame.columns:
        frame["session"] = pd.NA
    if "holding_minutes" not in frame.columns:
        frame["holding_minutes"] = pd.NA
    if "lookback" not in frame.columns:
        frame["lookback"] = pd.NA
    if "threshold" not in frame.columns:
        frame["threshold"] = pd.NA
    parsed = frame["name"].apply(_parse_candidate_name)
    for key in ["session", "holding_minutes", "lookback", "threshold"]:
        values = parsed.apply(lambda item: item.get(key))
        frame[key] = frame[key].fillna(values)


def _parse_candidate_name(name: object) -> dict[str, object]:
    text = str(name or "")
    parts: dict[str, object] = {}
    for session in ["us_rth", "us_late", "europe", "asia", "all"]:
        if text.endswith(f"_{session}") or f"_{session}_" in text:
            parts["session"] = session
            break
    import re

    lookback = re.search(r"_lb(\d+)", text)
    if lookback:
        parts["lookback"] = int(lookback.group(1))
    hold = re.search(r"_hold(\d+)", text)
    if hold:
        parts["holding_minutes"] = int(hold.group(1))
    threshold = re.search(r"_thr([0-9]+(?:\.[0-9]+)?)", text)
    if threshold:
        parts["threshold"] = float(threshold.group(1))
    return parts


def rank_candidates(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    ranked = rows.copy()
    _ensure_numeric(
        ranked,
        [
            "full_trades",
            "full_net_points",
            "full_max_drawdown_points",
            "full_profit_factor",
            "full_win_rate",
            "full_stability",
            "positive_fold_rate",
            "positive_window_rate",
            "min_window_net_points",
            "stress_net_points",
            "best_strategy_score",
            "selected_folds",
        ],
    )
    ranked["risk_denominator"] = ranked["full_max_drawdown_points"].clip(lower=1.0)
    ranked["net_to_drawdown"] = ranked["full_net_points"] / ranked["risk_denominator"]
    ranked["stress_to_drawdown"] = ranked["stress_net_points"] / ranked["risk_denominator"]
    ranked["fold_count_pass"] = ranked["selected_folds"].fillna(0) >= 3
    ranked["risk_control_pass"] = (
        ranked["fold_count_pass"]
        & (ranked["full_trades"] >= 200)
        & (ranked["full_profit_factor"] >= 1.08)
        & (ranked["positive_fold_rate"] >= 0.80)
        & (ranked["positive_window_rate"] >= 0.80)
        & (ranked["min_window_net_points"] > 0)
        & (ranked["stress_net_points"] > 0)
    )
    ranked["stability_pass"] = ranked["full_stability"].fillna(0.0) >= 0.70
    ranked["selection_tier"] = "research_only"
    ranked.loc[ranked["risk_control_pass"], "selection_tier"] = "risk_controlled"
    ranked.loc[ranked["risk_control_pass"] & ranked["stability_pass"], "selection_tier"] = "balanced_best"
    ranked["live_ready"] = ranked["selection_tier"].eq("balanced_best")
    ranked["best_strategy_score"] = ranked["best_strategy_score"].fillna(
        ranked["full_net_points"].clip(lower=0) * 0.30
        + ranked["stress_net_points"].clip(lower=0) * 0.22
        + ranked["net_to_drawdown"].clip(lower=0) * 150
        + ranked["stress_to_drawdown"].clip(lower=0) * 120
        + ranked["full_profit_factor"].clip(upper=3.0).fillna(0) * 320
        + ranked["full_stability"].clip(lower=0, upper=1).fillna(0) * 900
        + ranked["positive_fold_rate"].fillna(0) * 450
        + ranked["positive_window_rate"].fillna(0) * 650
        + ranked["min_window_net_points"].clip(lower=-500, upper=500).fillna(-500) * 0.35
        - ranked["full_max_drawdown_points"].fillna(0) * 0.35
    )
    tier_order = {"balanced_best": 0, "risk_controlled": 1, "research_only": 2}
    ranked = ranked.sort_values(
        ["selection_tier", "best_strategy_score", "full_net_points", "stress_net_points"],
        ascending=[True, False, False, False],
        key=lambda series: series.map(tier_order) if series.name == "selection_tier" else series,
    ).reset_index(drop=True)
    ranked = ranked.drop_duplicates(["name", "candidate_universe"], keep="first")
    return ranked


def summarize_direction_stats(trades: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    if trades.empty:
        return {}
    stats: dict[str, list[dict[str, object]]] = {}
    for (candidate, direction), group in trades.groupby(["candidate", "direction"], sort=True):
        net = pd.to_numeric(group["net_points"], errors="coerce").dropna()
        if net.empty:
            continue
        wins = net[net > 0].sum()
        losses = abs(net[net < 0].sum())
        profit_factor = float(wins / losses) if losses else None
        direction_label = "long" if int(direction) > 0 else "short"
        stats.setdefault(str(candidate), []).append(
            {
                "direction": direction_label,
                "trades": int(len(net)),
                "net_points": float(net.sum()),
                "profit_factor": profit_factor,
                "win_rate": float((net > 0).mean()),
                "avg_points": float(net.mean()),
            }
        )
    for rows in stats.values():
        rows.sort(key=lambda item: str(item["direction"]))
    return stats


def build_debate_pack(
    ranked: pd.DataFrame,
    top_n: int = 3,
    direction_stats: dict[str, list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    if ranked.empty:
        return {"candidates": [], "message": "no ranked candidates"}
    direction_stats = direction_stats or {}
    candidates = []
    for _, row in ranked.head(top_n).iterrows():
        bull_case = [
            f"positive_fold_rate={_fmt(row.get('positive_fold_rate'))}",
            f"positive_window_rate={_fmt(row.get('positive_window_rate'))}",
            f"full_profit_factor={_fmt(row.get('full_profit_factor'))}",
            f"full_stability={_fmt(row.get('full_stability'))}",
            f"net_to_drawdown={_fmt(row.get('net_to_drawdown'))}",
        ]
        bear_case = [
            f"full_max_drawdown_points={_fmt(row.get('full_max_drawdown_points'))}",
            f"min_window_net_points={_fmt(row.get('min_window_net_points'))}",
            f"stress_net_points={_fmt(row.get('stress_net_points'))}",
            f"full_trades={_fmt(row.get('full_trades'), 0)}",
        ]
        candidates.append(
            {
                "name": row.get("name"),
                "candidate_universe": row.get("candidate_universe"),
                "selection_tier": row.get("selection_tier"),
                "signal_rule": signal_rule(row),
                "session_window_utc": session_window_utc(row.get("session")),
                "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
                "exit_rule": f"time exit after {int(row.get('holding_minutes', 0) or 0)} minutes unless a strategy-specific stop/target is configured",
                "family": row.get("family"),
                "best_strategy_score": _to_python_value(row.get("best_strategy_score")),
                "full_net_points": _to_python_value(row.get("full_net_points")),
                "full_profit_factor": _to_python_value(row.get("full_profit_factor")),
                "positive_fold_rate": _to_python_value(row.get("positive_fold_rate")),
                "positive_window_rate": _to_python_value(row.get("positive_window_rate")),
                "full_stability": _to_python_value(row.get("full_stability")),
                "direction_stats": direction_stats.get(str(row.get("name")), []),
                "bull_case": bull_case,
                "bear_case": bear_case,
                "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
            }
        )
    return {"candidates": candidates}


def signal_rule(row: pd.Series) -> str:
    family = str(row.get("family", ""))
    lookback = int(row.get("lookback", 0) or 0)
    threshold = float(row.get("threshold", 0.0) or 0.0)
    if family == "momentum":
        return (
            f"go long when {lookback}m close-to-close return is above {threshold:g}; "
            f"go short when it is below {-threshold:g}"
        )
    if family == "mean_reversion":
        return (
            f"go long when close is below its {lookback}m mean by more than {threshold:g} rolling standard deviations; "
            f"go short when it is above its {lookback}m mean by more than {threshold:g} rolling standard deviations"
        )
    if family == "breakout":
        return (
            f"go long when close breaks above the prior {lookback}m high; "
            f"go short when close breaks below the prior {lookback}m low"
        )
    if family == "vwap_reclaim":
        return (
            f"go long when close is more than {threshold:g} above cumulative VWAP and {lookback}m momentum is positive; "
            f"go short when close is more than {threshold:g} below cumulative VWAP and {lookback}m momentum is negative"
        )
    return "unknown signal family"


def session_window_utc(session: object) -> str:
    session_name = str(session)
    windows = {
        "all": "00:00-24:00",
        "europe": "07:00-13:30",
        "us_rth": "13:30-20:00",
        "us_late": "20:00-23:00",
        "asia": "23:00-07:00",
    }
    return windows.get(session_name, "unknown")


def write_report(
    path: Path,
    ranked: pd.DataFrame,
    debate_pack: dict[str, object],
    source_path: Path,
    direction_stats: dict[str, list[dict[str, object]]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ 1m Feature Discovery Ranking",
        "",
        "This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.",
        "",
        f"- Source aggregate: `{source_path}`",
        f"- Candidates ranked: `{len(ranked):,}`",
        f"- Balanced candidates: `{int((ranked['selection_tier'] == 'balanced_best').sum()) if not ranked.empty else 0}`",
        "",
    ]
    if ranked.empty:
        lines.append("No candidates were ranked.")
    else:
        balanced = ranked[ranked["selection_tier"].eq("balanced_best")]
        risk_controlled = ranked[ranked["selection_tier"].eq("risk_controlled")]
        if not balanced.empty:
            best = balanced.iloc[0]
            verdict = "Best balanced candidate"
            warning = "This candidate passed ranking gates, but live trading still requires paper validation, current-market confirmation, and risk checks."
        elif not risk_controlled.empty:
            best = risk_controlled.iloc[0]
            verdict = "Best risk-controlled candidate"
            warning = "No balanced candidate passed the stability tier; this remains a paper-validation candidate."
        else:
            best = ranked.iloc[0]
            verdict = "Best research candidate"
            warning = "No candidate passed the risk-control gate; use these rows for research and LLM debate only, not automatic submission."
        best_direction_stats = direction_stats.get(str(best["name"]), []) if direction_stats else []
        lines.extend(
            [
                "## Verdict",
                "",
                f"{verdict}: `{best['name']}`",
                "",
                warning,
                "",
                "## Trading Rule",
                "",
                f"- Signal: {signal_rule(best)}.",
                f"- Session: `{best.get('session')}` UTC window `{session_window_utc(best.get('session'))}`.",
                "- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.",
                f"- Exit rule: time exit after `{int(best.get('holding_minutes', 0) or 0)}` minutes unless a stop/target is configured.",
                f"- Readiness: `{best.get('selection_tier')}`; live_ready=`{bool(best.get('live_ready'))}`.",
                "",
            ]
        )
        if best_direction_stats:
            lines.extend(
                [
                    "## Directional Evidence",
                    "",
                    "```csv",
                    pd.DataFrame(best_direction_stats).to_csv(index=False).strip(),
                    "```",
                    "",
                ]
            )
        lines.extend(
            [
                "## Best Candidate",
                "",
                "```csv",
                pd.DataFrame([best]).to_csv(index=False).strip(),
                "```",
                "",
                "## Top Candidates",
                "",
                "```csv",
                ranked.head(10)[
                    [
                        "name",
                        "candidate_universe",
                        "selection_tier",
                        "family",
                        "full_trades",
                        "full_net_points",
                        "full_max_drawdown_points",
                        "full_profit_factor",
                        "positive_fold_rate",
                        "positive_window_rate",
                        "min_window_net_points",
                        "stress_net_points",
                        "best_strategy_score",
                    ]
                ].to_csv(index=False).strip(),
                "```",
                "",
                "## LLM Debate Pack",
                "",
                "```json",
                json.dumps(debate_pack, indent=2, sort_keys=True, default=str),
                "```",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _ensure_numeric(frame: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")


def _fmt(value: object, decimals: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if decimals == 0:
        return str(int(round(number)))
    return f"{number:.{decimals}f}"


def _to_python_value(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, str, bool)):
        return value
    try:
        return value.item()
    except Exception:
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank 5-year NQ bar walk-forward candidates and export an LLM debate pack.")
    parser.add_argument("--input", default=".tmp/nq-bar-best-strategy-walkforward-aggregate.csv")
    parser.add_argument("--output", default=".tmp/nq-bar-best-strategy-ranking.csv")
    parser.add_argument("--report", default="reports/NQ-bar-best-strategy-ranking.md")
    parser.add_argument("--debate-output", default=".tmp/nq-bar-best-strategy-debate.json")
    parser.add_argument("--trades-input", default=None)
    args = parser.parse_args()

    rows = load_candidate_results([(args.input, "walkforward_5y_1m")])
    ranked = rank_candidates(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(output, index=False)
    direction_stats = summarize_direction_stats(load_trade_results(args.trades_input))
    debate_pack = build_debate_pack(ranked, direction_stats=direction_stats)
    debate_path = Path(args.debate_output)
    debate_path.parent.mkdir(parents=True, exist_ok=True)
    debate_path.write_text(json.dumps(debate_pack, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_report(Path(args.report), ranked, debate_pack, Path(args.input), direction_stats=direction_stats)
    print(f"Candidates ranked: {len(ranked):,}")
    print(f"CSV: {output}")
    print(f"Debate pack: {debate_path}")
    print(f"Report: {args.report}")
    if not ranked.empty:
        print(ranked.head(10)[["selection_tier", "name", "full_trades", "full_net_points", "full_profit_factor", "best_strategy_score"]].to_csv(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
