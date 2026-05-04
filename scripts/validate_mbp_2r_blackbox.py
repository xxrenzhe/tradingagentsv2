from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mine_mbp_advanced_patterns import AdvancedStrategySpec, build_advanced_trades, generate_advanced_specs
from optimize_mbp_robust_top10 import Candidate, _load_features
from tradingagents.backtesting.short_patterns import BacktestCosts, StrategySpec, build_trades, generate_strategy_specs


@dataclass(frozen=True)
class BlackBoxConfig:
    train_fraction: float = 0.70
    min_train_trades: int = 120
    min_test_trades: int = 50
    min_train_win_rate: float = 0.58
    min_test_win_rate: float = 0.60
    min_profit_factor: float = 1.25
    min_positive_window_rate: float = 0.70
    min_bracket_exit_share: float = 0.70
    window_days: int = 10
    window_step_days: int = 5


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate: Candidate
    train: dict
    test: dict
    test_windows: dict


def _risk_is_2r(stop_loss: object, take_profit: object) -> bool:
    if pd.isna(stop_loss) or pd.isna(take_profit):
        return False
    stop = float(stop_loss)
    target = float(take_profit)
    return stop > 0 and target > 0 and abs((target / stop) - 2.0) < 1e-9


def build_2r_candidates(*, include_base: bool = True, include_advanced: bool = True) -> list[Candidate]:
    candidates: list[Candidate] = []
    if include_base:
        for spec in generate_strategy_specs(include_microstructure=True):
            if _risk_is_2r(spec.stop_loss_points, spec.take_profit_points):
                candidates.append(Candidate("base", spec.name, spec))
    if include_advanced:
        for spec in generate_advanced_specs():
            if _risk_is_2r(spec.stop_loss_points, spec.take_profit_points):
                candidates.append(Candidate("advanced", spec.name, spec))
    return candidates


def _split_features(features: pd.DataFrame, train_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(features["trade_date"].dropna().unique())
    if len(dates) < 2:
        raise SystemExit("Need at least two trade dates for a chronological black-box split.")
    split_index = int(len(dates) * train_fraction)
    split_index = max(1, min(split_index, len(dates) - 1))
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    return (
        features[features["trade_date"].isin(train_dates)].reset_index(drop=True),
        features[features["trade_date"].isin(test_dates)].reset_index(drop=True),
    )


def _build_candidate_trades(candidate: Candidate, features: pd.DataFrame, costs: BacktestCosts) -> pd.DataFrame:
    if candidate.source == "base":
        return build_trades(features.reset_index(drop=True), candidate.spec, costs)
    return build_advanced_trades(features.reset_index(drop=True), candidate.spec, costs)


def summarize_2r_trades(name: str, trades: pd.DataFrame) -> dict:
    if trades.empty:
        return _empty_summary(name)
    net = pd.to_numeric(trades["net_points"], errors="coerce")
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    gross_profit = float(net[net > 0].sum())
    gross_loss = abs(float(net[net < 0].sum()))
    exit_reasons = trades["exit_reason"].astype(str)
    bracket_exits = exit_reasons.isin(["stop_loss", "take_profit"])
    return {
        "name": name,
        "trades": int(len(trades)),
        "net_points": float(equity.iloc[-1]),
        "max_drawdown_points": float(abs(drawdown.min())),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf"),
        "win_rate": float((net > 0).mean()),
        "avg_points": float(net.mean()),
        "target_exit_share": float((exit_reasons == "take_profit").mean()),
        "stop_exit_share": float((exit_reasons == "stop_loss").mean()),
        "bracket_exit_share": float(bracket_exits.mean()),
        "worst_trade_points": float(net.min()),
    }


def _empty_summary(name: str) -> dict:
    return {
        "name": name,
        "trades": 0,
        "net_points": 0.0,
        "max_drawdown_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "avg_points": 0.0,
        "target_exit_share": 0.0,
        "stop_exit_share": 0.0,
        "bracket_exit_share": 0.0,
        "worst_trade_points": 0.0,
    }


def _rolling_window_summary(trades: pd.DataFrame, window_days: int, step_days: int) -> dict:
    if trades.empty:
        return {"window_count": 0, "positive_window_rate": 0.0, "min_window_trades": 0, "min_window_net_points": 0.0}
    trade_dates = pd.to_datetime(trades["entry_ts"], utc=True).dt.date
    dates = sorted(trade_dates.unique())
    window_days = max(1, min(window_days, len(dates)))
    step_days = max(1, step_days)
    nets: list[float] = []
    counts: list[int] = []
    for start in range(0, len(dates) - window_days + 1, step_days):
        window_dates = set(dates[start : start + window_days])
        window_net = pd.to_numeric(trades.loc[trade_dates.isin(window_dates), "net_points"], errors="coerce")
        nets.append(float(window_net.sum()))
        counts.append(int(window_net.count()))
    if not nets:
        window_net = pd.to_numeric(trades["net_points"], errors="coerce")
        nets = [float(window_net.sum())]
        counts = [int(window_net.count())]
    return {
        "window_count": len(nets),
        "positive_window_rate": float(sum(value > 0 for value in nets) / len(nets)),
        "min_window_trades": min(counts),
        "min_window_net_points": min(nets),
    }


def evaluate_blackbox(
    features: pd.DataFrame,
    candidates: list[Candidate],
    config: BlackBoxConfig,
    *,
    costs: BacktestCosts | None = None,
    max_train_candidates: int | None = None,
    progress_every: int = 100,
) -> pd.DataFrame:
    evaluations = collect_candidate_evaluations(
        features,
        candidates,
        config,
        costs=costs,
        progress_every=progress_every,
    )
    train_rows = []
    for item in evaluations:
        train = item.train
        if not _passes_train_gate(train, config):
            continue
        train_rows.append(
            {
                "name": item.candidate.name,
                "train_trades": train["trades"],
                "train_net_points": train["net_points"],
                "train_win_rate": train["win_rate"],
                "train_profit_factor": train["profit_factor"],
                "train_bracket_exit_share": train["bracket_exit_share"],
                "train_score": train["net_points"] + train["profit_factor"] * 100 + train["win_rate"] * 250,
            }
        )
    if not train_rows:
        return pd.DataFrame()

    train_ranked = pd.DataFrame(train_rows).sort_values(
        ["train_win_rate", "train_net_points", "train_profit_factor", "train_score"],
        ascending=[False, False, False, False],
    )
    if max_train_candidates is not None and max_train_candidates > 0:
        selected_names = set(train_ranked.head(max_train_candidates)["name"])
    else:
        selected_names = set(train_ranked["name"])
    rows = [_evaluation_row(item, config) for item in evaluations if item.candidate.name in selected_names]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["blackbox_pass", "test_win_rate", "test_net_points", "test_profit_factor", "blackbox_score"],
        ascending=[False, False, False, False, False],
    ).reset_index(drop=True)


def collect_candidate_evaluations(
    features: pd.DataFrame,
    candidates: list[Candidate],
    config: BlackBoxConfig,
    *,
    costs: BacktestCosts | None = None,
    progress_every: int = 100,
) -> list[CandidateEvaluation]:
    costs = costs or BacktestCosts()
    train_features, test_features = _split_features(features, config.train_fraction)
    evaluations = []
    for index, candidate in enumerate(candidates, start=1):
        if progress_every > 0 and index % progress_every == 0:
            print(f"Training scan: {index:,}/{len(candidates):,}", flush=True)
        train_trades = _build_candidate_trades(candidate, train_features, costs)
        train = summarize_2r_trades(candidate.name, train_trades)
        test_trades = _build_candidate_trades(candidate, test_features, costs)
        test = summarize_2r_trades(candidate.name, test_trades)
        windows = _rolling_window_summary(test_trades, config.window_days, config.window_step_days)
        evaluations.append(CandidateEvaluation(candidate, train, test, windows))
    return evaluations


def _evaluation_row(item: CandidateEvaluation, config: BlackBoxConfig) -> dict:
    candidate = item.candidate
    train = item.train
    test = item.test
    windows = item.test_windows
    row = {
        "name": candidate.name,
        "source": candidate.source,
        "family": candidate.spec.family,
        "lookback": candidate.spec.lookback,
        "threshold": candidate.spec.threshold,
        "stop_loss_points": candidate.spec.stop_loss_points,
        "take_profit_points": candidate.spec.take_profit_points,
        "train_trades": train["trades"],
        "train_net_points": train["net_points"],
        "train_win_rate": train["win_rate"],
        "train_profit_factor": train["profit_factor"],
        "train_bracket_exit_share": train["bracket_exit_share"],
        "test_trades": test["trades"],
        "test_net_points": test["net_points"],
        "test_max_drawdown_points": test["max_drawdown_points"],
        "test_win_rate": test["win_rate"],
        "test_profit_factor": test["profit_factor"],
        "test_avg_points": test["avg_points"],
        "test_target_exit_share": test["target_exit_share"],
        "test_stop_exit_share": test["stop_exit_share"],
        "test_bracket_exit_share": test["bracket_exit_share"],
        **{f"test_{key}": value for key, value in windows.items()},
    }
    row["blackbox_pass"] = passes_blackbox_gate(row, config)
    row["blackbox_score"] = (
        row["test_net_points"]
        - row["test_max_drawdown_points"]
        + row["test_profit_factor"] * 100
        + row["test_win_rate"] * 250
        + row["test_positive_window_rate"] * 100
    )
    return row


def _passes_train_gate(summary: dict, config: BlackBoxConfig) -> bool:
    return (
        int(summary["trades"]) >= config.min_train_trades
        and float(summary["net_points"]) > 0
        and float(summary["win_rate"]) >= config.min_train_win_rate
        and float(summary["profit_factor"]) >= config.min_profit_factor
        and float(summary["bracket_exit_share"]) >= config.min_bracket_exit_share
    )


def passes_blackbox_gate(row: dict | pd.Series, config: BlackBoxConfig) -> bool:
    return (
        int(row["test_trades"]) >= config.min_test_trades
        and float(row["test_net_points"]) > 0
        and float(row["test_win_rate"]) >= config.min_test_win_rate
        and float(row["test_profit_factor"]) >= config.min_profit_factor
        and float(row["test_positive_window_rate"]) >= config.min_positive_window_rate
        and int(row["test_min_window_trades"]) >= 5
        and float(row["test_bracket_exit_share"]) >= config.min_bracket_exit_share
    )


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = ["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        values = []
        for column in frame.columns:
            value = row[column]
            values.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def write_report(output: Path, results: pd.DataFrame, features: pd.DataFrame, config: BlackBoxConfig) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    passed = results[results["blackbox_pass"]] if not results.empty else pd.DataFrame()
    display_columns = [
        "name",
        "source",
        "family",
        "stop_loss_points",
        "take_profit_points",
        "train_trades",
        "train_win_rate",
        "train_profit_factor",
        "test_trades",
        "test_net_points",
        "test_win_rate",
        "test_profit_factor",
        "test_positive_window_rate",
        "test_bracket_exit_share",
        "blackbox_pass",
    ]
    report = [
        "# NQM6 2R Black-Box Validation",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Train fraction: {config.train_fraction:.2%}",
        f"2R rule: stop_loss_points > 0 and take_profit_points = 2 * stop_loss_points.",
        f"Black-box pass requires test win rate >= {config.min_test_win_rate:.2%}, test net > 0, test PF >= {config.min_profit_factor:.2f}, positive test window rate >= {config.min_positive_window_rate:.2%}, >= {config.min_test_trades} test trades, and bracket exit share >= {config.min_bracket_exit_share:.2%}.",
        "",
        f"Candidates passing training gate: {len(results):,}",
        f"Candidates passing black-box gate: {len(passed):,}",
        "",
    ]
    if passed.empty:
        report.extend(
            [
                "## Verdict",
                "",
                "No 60% win-rate 2R strategy passed the chronological black-box gate. Existing candidates remain research candidates, not production-ready strategies.",
                "",
            ]
        )
    else:
        report.extend(["## Passed Candidates", "", _markdown_table(passed.head(10)[display_columns]), ""])
    report.extend(["## Top Tested Candidates", "", _markdown_table(results.head(20)[display_columns]) if not results.empty else "_No training-gated candidates._", ""])
    output.write_text("\n".join(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate 2R MBP strategies on a chronological black-box holdout.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-blackbox.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-blackbox-validation.md")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--min-train-trades", type=int, default=120)
    parser.add_argument("--min-test-trades", type=int, default=50)
    parser.add_argument("--min-train-win-rate", type=float, default=0.58)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-profit-factor", type=float, default=1.25)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.70)
    parser.add_argument("--min-bracket-exit-share", type=float, default=0.70)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--window-step-days", type=int, default=5)
    parser.add_argument("--max-train-candidates", type=int, default=80)
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()

    config = BlackBoxConfig(
        train_fraction=args.train_fraction,
        min_train_trades=args.min_train_trades,
        min_test_trades=args.min_test_trades,
        min_train_win_rate=args.min_train_win_rate,
        min_test_win_rate=args.min_test_win_rate,
        min_profit_factor=args.min_profit_factor,
        min_positive_window_rate=args.min_positive_window_rate,
        min_bracket_exit_share=args.min_bracket_exit_share,
        window_days=args.window_days,
        window_step_days=args.window_step_days,
    )
    features = _load_features(Path(args.features_cache))
    candidates = build_2r_candidates()
    results = evaluate_blackbox(
        features,
        candidates,
        config,
        max_train_candidates=args.max_train_candidates,
        progress_every=args.progress_every,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    write_report(Path(args.report), results, features, config)
    print(f"2R candidates: {len(candidates):,}")
    print(f"Training-gated candidates: {len(results):,}")
    print(f"Black-box pass: {int(results['blackbox_pass'].sum()) if not results.empty else 0}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    if not results.empty:
        print(results.head(10)[["name", "source", "test_trades", "test_win_rate", "test_net_points", "test_profit_factor", "test_positive_window_rate", "blackbox_pass"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
