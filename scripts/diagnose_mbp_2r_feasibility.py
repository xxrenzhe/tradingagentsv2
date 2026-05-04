from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_mbp_robust_top10 import _load_features
from search_mbp_2r_purged_walkforward import build_2r_events, prepare_features
from tradingagents.backtesting.short_patterns import BacktestCosts


SESSIONS = {
    "all": (0, 24 * 60),
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


def feature_columns() -> list[str]:
    return [
        "return_3m",
        "return_5m",
        "range_1m",
        "body_to_range",
        "realized_vol_15",
        "realized_vol_30",
        "z_5",
        "z_10",
        "vwap_distance",
        "imbalance",
        "spread_mean",
        "depth_mean",
        "quote_count",
    ]


def run_diagnostics(features: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    bin_rows = []
    costs = BacktestCosts(slippage_ticks_per_side=args.slippage_ticks_per_side)
    for direction in [1, -1]:
        for stop_loss in args.stop_loss_points:
            for horizon in args.horizon_minutes:
                events = build_2r_events(
                    features,
                    direction=direction,
                    stop_loss_points=float(stop_loss),
                    horizon_minutes=int(horizon),
                    cost_points=costs.round_trip_cost_points,
                )
                if events.empty:
                    continue
                for session in args.sessions:
                    mask = session_mask(events["minute_of_day"], session)
                    subset = events.loc[mask].reset_index(drop=True)
                    summary = summarize_events(subset)
                    rows.append(
                        {
                            "direction": direction,
                            "stop_loss_points": float(stop_loss),
                            "take_profit_points": float(stop_loss) * 2.0,
                            "horizon_minutes": int(horizon),
                            "session": session,
                            **summary,
                        }
                    )
                    bin_rows.extend(
                        best_feature_bins(
                            features,
                            events.loc[mask],
                            direction=direction,
                            stop_loss_points=float(stop_loss),
                            horizon_minutes=int(horizon),
                            session=session,
                            min_events=args.min_bin_events,
                            quantile_count=args.quantile_count,
                            train_fraction=args.train_fraction,
                            top_n=args.top_bins_per_setup,
                            include_pairs=args.include_pair_bins,
                            pair_pool_size=args.pair_pool_size,
                        )
                    )
    setups = pd.DataFrame(rows)
    bins = pd.DataFrame(bin_rows)
    if not setups.empty:
        setups = setups.sort_values(["win_rate", "net_points", "profit_factor"], ascending=[False, False, False]).reset_index(drop=True)
    if not bins.empty:
        bins = bins.sort_values(
            ["test_win_rate", "test_net_points", "test_profit_factor", "train_win_rate"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True)
    return setups, bins


def summarize_events(events: pd.DataFrame) -> dict:
    if events.empty:
        return {
            "events": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "target_exit_share": 0.0,
            "stop_exit_share": 0.0,
            "timeout_share": 0.0,
            "bracket_exit_share": 0.0,
        }
    net = pd.to_numeric(events["net_points"], errors="coerce")
    wins = net[net > 0]
    losses = net[net < 0]
    reasons = events["exit_reason"].astype(str)
    return {
        "events": int(len(events)),
        "net_points": float(net.sum()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if float(losses.sum()) else float("inf"),
        "win_rate": float((net > 0).mean()),
        "target_exit_share": float((reasons == "take_profit").mean()),
        "stop_exit_share": float((reasons == "stop_loss").mean()),
        "timeout_share": float((reasons == "timeout").mean()),
        "bracket_exit_share": float(reasons.isin(["take_profit", "stop_loss"]).mean()),
    }


def best_feature_bins(
    features: pd.DataFrame,
    events: pd.DataFrame,
    *,
    direction: int,
    stop_loss_points: float,
    horizon_minutes: int,
    session: str,
    min_events: int,
    quantile_count: int,
    train_fraction: float,
    top_n: int,
    include_pairs: bool = False,
    pair_pool_size: int = 0,
) -> list[dict]:
    if events.empty:
        return []
    dates = sorted(events["trade_date"].dropna().unique())
    split_index = max(1, min(int(len(dates) * train_fraction), len(dates) - 1))
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    train_events = events[events["trade_date"].isin(train_dates)].copy()
    test_events = events[events["trade_date"].isin(test_dates)].copy()
    if train_events.empty or test_events.empty:
        return []
    aligned = features.loc[events["signal_index"].astype(int), feature_columns()].copy()
    aligned.index = events.index
    rows = []
    train_masks: list[tuple[dict, pd.Series, pd.Series]] = []
    for feature in feature_columns():
        values = pd.to_numeric(aligned.loc[train_events.index, feature], errors="coerce")
        quantiles = np.linspace(0.05, 0.95, quantile_count)
        thresholds = values.quantile(quantiles).dropna().drop_duplicates()
        for threshold in thresholds:
            for op in ["<=", ">="]:
                train_mask = compare(pd.to_numeric(aligned.loc[train_events.index, feature], errors="coerce"), op, float(threshold))
                test_mask = compare(pd.to_numeric(aligned.loc[test_events.index, feature], errors="coerce"), op, float(threshold))
                train_subset = train_events.loc[train_mask]
                test_subset = test_events.loc[test_mask]
                if len(train_subset) < min_events or len(test_subset) < max(5, min_events // 3):
                    continue
                train_summary = summarize_events(train_subset)
                test_summary = summarize_events(test_subset)
                row = {
                    "direction": direction,
                    "stop_loss_points": stop_loss_points,
                    "take_profit_points": stop_loss_points * 2.0,
                    "horizon_minutes": horizon_minutes,
                    "session": session,
                    "bin_type": "single",
                    "feature": feature,
                    "feature_2": "",
                    "op": op,
                    "op_2": "",
                    "threshold": float(threshold),
                    "threshold_2": np.nan,
                    "train_events": train_summary["events"],
                    "train_win_rate": train_summary["win_rate"],
                    "train_net_points": train_summary["net_points"],
                    "train_profit_factor": train_summary["profit_factor"],
                    "test_events": test_summary["events"],
                    "test_win_rate": test_summary["win_rate"],
                    "test_net_points": test_summary["net_points"],
                    "test_profit_factor": test_summary["profit_factor"],
                    "test_bracket_exit_share": test_summary["bracket_exit_share"],
                    "oracle_60wr_2r_pass": (
                        test_summary["events"] >= max(5, min_events // 3)
                        and test_summary["win_rate"] >= 0.60
                        and test_summary["net_points"] > 0
                        and test_summary["profit_factor"] >= 1.20
                        and test_summary["bracket_exit_share"] >= 0.70
                    ),
                }
                rows.append(row)
                train_masks.append((row, train_mask, test_mask))
    if include_pairs and pair_pool_size > 1 and train_masks:
        ranked_masks = sorted(
            train_masks,
            key=lambda item: (item[0]["train_win_rate"], item[0]["train_net_points"], item[0]["train_events"]),
            reverse=True,
        )[:pair_pool_size]
        for left_index, (left_row, left_train_mask, left_test_mask) in enumerate(ranked_masks):
            for right_row, right_train_mask, right_test_mask in ranked_masks[left_index + 1 :]:
                if left_row["feature"] == right_row["feature"]:
                    continue
                train_mask = left_train_mask & right_train_mask
                test_mask = left_test_mask & right_test_mask
                train_subset = train_events.loc[train_mask]
                test_subset = test_events.loc[test_mask]
                if len(train_subset) < min_events or len(test_subset) < max(5, min_events // 3):
                    continue
                train_summary = summarize_events(train_subset)
                test_summary = summarize_events(test_subset)
                rows.append(
                    {
                        "direction": direction,
                        "stop_loss_points": stop_loss_points,
                        "take_profit_points": stop_loss_points * 2.0,
                        "horizon_minutes": horizon_minutes,
                        "session": session,
                        "bin_type": "pair",
                        "feature": left_row["feature"],
                        "feature_2": right_row["feature"],
                        "op": left_row["op"],
                        "op_2": right_row["op"],
                        "threshold": left_row["threshold"],
                        "threshold_2": right_row["threshold"],
                        "train_events": train_summary["events"],
                        "train_win_rate": train_summary["win_rate"],
                        "train_net_points": train_summary["net_points"],
                        "train_profit_factor": train_summary["profit_factor"],
                        "test_events": test_summary["events"],
                        "test_win_rate": test_summary["win_rate"],
                        "test_net_points": test_summary["net_points"],
                        "test_profit_factor": test_summary["profit_factor"],
                        "test_bracket_exit_share": test_summary["bracket_exit_share"],
                        "oracle_60wr_2r_pass": (
                            test_summary["events"] >= max(5, min_events // 3)
                            and test_summary["win_rate"] >= 0.60
                            and test_summary["net_points"] > 0
                            and test_summary["profit_factor"] >= 1.20
                            and test_summary["bracket_exit_share"] >= 0.70
                        ),
                    }
                )
    return sorted(rows, key=lambda row: (row["test_win_rate"], row["test_net_points"], row["train_win_rate"]), reverse=True)[:top_n]


def session_mask(minutes: pd.Series, session: str) -> pd.Series:
    start, end = SESSIONS[session]
    return minutes.between(start, end - 1)


def compare(values: pd.Series, op: str, threshold: float) -> pd.Series:
    if op == "<=":
        return (values <= threshold).fillna(False)
    if op == ">=":
        return (values >= threshold).fillna(False)
    raise ValueError(f"Unsupported op: {op}")


def write_report(path: Path, setups: pd.DataFrame, bins: pd.DataFrame, features: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    setup_columns = [
        "direction",
        "stop_loss_points",
        "take_profit_points",
        "horizon_minutes",
        "session",
        "events",
        "win_rate",
        "net_points",
        "profit_factor",
        "target_exit_share",
        "stop_exit_share",
        "timeout_share",
    ]
    bin_columns = [
        "direction",
        "stop_loss_points",
        "horizon_minutes",
        "session",
        "bin_type",
        "feature",
        "feature_2",
        "op",
        "op_2",
        "threshold",
        "threshold_2",
        "train_events",
        "train_win_rate",
        "test_events",
        "test_win_rate",
        "test_net_points",
        "test_profit_factor",
        "oracle_60wr_2r_pass",
    ]
    passed_bins = bins[bins["oracle_60wr_2r_pass"]] if not bins.empty else pd.DataFrame()
    lines = [
        "# NQM6 2R Feasibility Diagnostics",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Stop-loss points: {', '.join(str(value) for value in args.stop_loss_points)}",
        f"Horizons: {', '.join(str(value) for value in args.horizon_minutes)}",
        f"Sessions: {', '.join(args.sessions)}",
        "",
        "## Interpretation",
        "",
        "- Setup rows test every eligible minute entry for fixed 2R brackets, before adding strategy-specific filters.",
        "- Feature-bin rows use train-period quantiles for a single feature and report future holdout results for the same bin.",
        "- Pair-bin rows, when enabled, combine only the best train-period single bins before future evaluation.",
        "- A passing feature bin is not a live strategy; it is only evidence that a simple learnable 2R edge may exist.",
        "",
        f"Setups evaluated: {len(setups):,}",
        f"Feature bins evaluated: {len(bins):,}",
        f"Future feature bins passing 60%/2R feasibility gate: {len(passed_bins):,}",
        "",
        "## Passed Feature Bins",
        "",
        markdown_table(passed_bins.head(20)[bin_columns]) if not passed_bins.empty else "_No rows._",
        "",
        "## Best Base Setups",
        "",
        markdown_table(setups.head(20)[setup_columns]) if not setups.empty else "_No rows._",
        "",
        "## Best Future Feature Bins",
        "",
        markdown_table(bins.head(30)[bin_columns]) if not bins.empty else "_No rows._",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose whether fixed 2R target-hit rates are feasible in MBP minute data.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--setups-output", default=".tmp/mbp-2r-feasibility-setups.csv")
    parser.add_argument("--bins-output", default=".tmp/mbp-2r-feasibility-feature-bins.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-feasibility.md")
    parser.add_argument("--stop-loss-points", type=float, nargs="+", default=[4.0, 6.0, 8.0, 12.0, 16.0])
    parser.add_argument("--horizon-minutes", type=int, nargs="+", default=[20, 30, 45, 60, 90, 120])
    parser.add_argument("--sessions", nargs="+", default=["all", "europe", "us_rth", "us_late"])
    parser.add_argument("--min-bin-events", type=int, default=80)
    parser.add_argument("--quantile-count", type=int, default=11)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--top-bins-per-setup", type=int, default=5)
    parser.add_argument("--include-pair-bins", action="store_true")
    parser.add_argument("--pair-pool-size", type=int, default=8)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    args = parser.parse_args()

    features = prepare_features(_load_features(Path(args.features_cache)))
    setups, bins = run_diagnostics(features, args)
    setups_output = Path(args.setups_output)
    bins_output = Path(args.bins_output)
    setups_output.parent.mkdir(parents=True, exist_ok=True)
    bins_output.parent.mkdir(parents=True, exist_ok=True)
    setups.to_csv(setups_output, index=False)
    bins.to_csv(bins_output, index=False)
    write_report(Path(args.report), setups, bins, features, args)
    passed_bins = int(bins["oracle_60wr_2r_pass"].sum()) if not bins.empty else 0
    print(f"Setups evaluated: {len(setups):,}")
    print(f"Feature bins evaluated: {len(bins):,}")
    print(f"Future feature bins passing feasibility gate: {passed_bins:,}")
    print(f"Setups CSV: {setups_output}")
    print(f"Bins CSV: {bins_output}")
    print(f"Report: {args.report}")
    if not setups.empty:
        print("Best setups:")
        print(setups.head(10)[["direction", "stop_loss_points", "horizon_minutes", "session", "events", "win_rate", "net_points", "profit_factor"]].to_string(index=False))
    if not bins.empty:
        print("Best feature bins:")
        print(bins.head(10)[["direction", "stop_loss_points", "horizon_minutes", "session", "feature", "op", "test_events", "test_win_rate", "test_net_points", "oracle_60wr_2r_pass"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
