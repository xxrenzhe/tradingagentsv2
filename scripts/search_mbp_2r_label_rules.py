from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from optimize_mbp_robust_top10 import _load_features


SESSIONS = {
    "all": (0, 24 * 60),
    "asia": (0, 7 * 60),
    "europe": (7 * 60, 13 * 60 + 30),
    "us_rth": (13 * 60 + 30, 20 * 60),
    "us_late": (20 * 60, 24 * 60),
}


@dataclass(frozen=True)
class LabelRule:
    name: str
    direction: int
    stop_loss_points: float
    take_profit_points: float
    horizon_minutes: int
    session: str
    vol_bucket: str
    setup: str
    imbalance_filter: str
    vwap_side: str
    min_gap_minutes: int


def _fmt(value: float | int) -> str:
    return f"{value:.7g}" if isinstance(value, float) else str(value)


def prepare_features(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy().reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    for column in ["Open", "High", "Low", "Close", "Volume", "vwap", "imbalance_last", "imbalance_mean", "spread_mean", "depth_mean"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["return_1m"] = data["Close"].pct_change()
    data["return_3m"] = data["Close"].pct_change(3)
    data["return_5m"] = data["Close"].pct_change(5)
    data["range_1m"] = data["High"] - data["Low"]
    data["realized_vol_30"] = data["return_1m"].rolling(30).std()
    data["vwap_distance"] = (data["Close"] - data["vwap"]) / data["vwap"]
    data["z_5"] = (data["Close"] - data["Close"].rolling(5).mean()) / data["Close"].rolling(5).std().replace(0, pd.NA)
    data["z_10"] = (data["Close"] - data["Close"].rolling(10).mean()) / data["Close"].rolling(10).std().replace(0, pd.NA)
    data["imbalance"] = data["imbalance_last"].fillna(data["imbalance_mean"]).fillna(0)
    data["trade_date"] = data["ts"].dt.date
    sane_range = data["range_1m"].between(0, data["range_1m"].quantile(0.995))
    sane_prices = (data["High"] >= data[["Open", "Close"]].max(axis=1)) & (data["Low"] <= data[["Open", "Close"]].min(axis=1))
    return data[sane_range & sane_prices].reset_index(drop=True)


def generate_rules() -> list[LabelRule]:
    rules: list[LabelRule] = []
    for direction in [1, -1]:
        direction_name = "long" if direction > 0 else "short"
        for stop_loss in [4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0, 24.0, 32.0]:
            take_profit = stop_loss * 2
            for horizon in [10, 20, 30, 45, 60, 90, 120]:
                for session in SESSIONS:
                    for vol_bucket in ["all", "not_low", "high", "low"]:
                        for setup in [
                            "momentum_3",
                            "momentum_5",
                            "mean_revert_z5",
                            "mean_revert_z10",
                            "vwap_reclaim",
                            "vwap_fade",
                            "imbalance_only",
                        ]:
                            for imbalance_filter in ["none", "aligned_0.1", "aligned_0.2", "aligned_0.35", "contrary_0.1", "contrary_0.2"]:
                                for vwap_side in ["any", "above", "below", "far_above", "far_below"]:
                                    for min_gap in [1, 5, 15]:
                                        name = (
                                            f"label2r_{direction_name}_sl{_fmt(stop_loss)}_tp{_fmt(take_profit)}_h{horizon}"
                                            f"_{session}_{vol_bucket}_{setup}_{imbalance_filter}_{vwap_side}_gap{min_gap}"
                                        )
                                        rules.append(
                                            LabelRule(
                                                name,
                                                direction,
                                                stop_loss,
                                                take_profit,
                                                horizon,
                                                session,
                                                vol_bucket,
                                                setup,
                                                imbalance_filter,
                                                vwap_side,
                                                min_gap,
                                            )
                                        )
    return rules


def build_rule_trades(features: pd.DataFrame, rule: LabelRule, cost_points: float = 0.625) -> pd.DataFrame:
    mask = _rule_mask(features, rule)
    rows = []
    next_index = 0
    for signal_index in features.index[mask]:
        signal_index = int(signal_index)
        entry_index = signal_index + 1
        if entry_index <= next_index or entry_index >= len(features):
            continue
        max_exit_index = min(entry_index + rule.horizon_minutes, len(features) - 1)
        entry_price = float(features.at[entry_index, "Open"])
        target = entry_price + rule.take_profit_points if rule.direction > 0 else entry_price - rule.take_profit_points
        stop = entry_price - rule.stop_loss_points if rule.direction > 0 else entry_price + rule.stop_loss_points
        exit_index = max_exit_index
        exit_price = float(features.at[max_exit_index, "Close"])
        exit_reason = "timeout"
        for path_index in range(entry_index, max_exit_index + 1):
            high = float(features.at[path_index, "High"])
            low = float(features.at[path_index, "Low"])
            if rule.direction > 0:
                stop_hit = low <= stop
                target_hit = high >= target
            else:
                stop_hit = high >= stop
                target_hit = low <= target
            if stop_hit:
                exit_index = path_index
                exit_price = stop
                exit_reason = "stop_loss"
                break
            if target_hit:
                exit_index = path_index
                exit_price = target
                exit_reason = "take_profit"
                break
        gross_points = (exit_price - entry_price) * rule.direction
        net_points = gross_points - cost_points
        rows.append(
            {
                "entry_ts": features.at[entry_index, "ts"],
                "exit_ts": features.at[exit_index, "ts"],
                "entry_index": entry_index,
                "exit_index": exit_index,
                "direction": rule.direction,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "gross_points": gross_points,
                "net_points": net_points,
                "trade_date": features.at[entry_index, "trade_date"],
            }
        )
        next_index = exit_index + rule.min_gap_minutes
    return pd.DataFrame(rows)


def _rule_mask(features: pd.DataFrame, rule: LabelRule) -> pd.Series:
    mask = pd.Series(True, index=features.index)
    start, end = SESSIONS[rule.session]
    if rule.session != "all":
        mask &= features["minute_of_day"].between(start, end - 1)
    vol = features["realized_vol_30"]
    low_cutoff = vol.quantile(0.33)
    high_cutoff = vol.quantile(0.67)
    if rule.vol_bucket == "not_low":
        mask &= vol >= low_cutoff
    elif rule.vol_bucket == "high":
        mask &= vol >= high_cutoff
    elif rule.vol_bucket == "low":
        mask &= vol <= low_cutoff
    mask &= _setup_mask(features, rule)
    mask &= _imbalance_mask(features, rule)
    mask &= _vwap_side_mask(features, rule)
    mask &= features[["Open", "High", "Low", "Close", "vwap"]].notna().all(axis=1)
    return mask.fillna(False)


def _setup_mask(features: pd.DataFrame, rule: LabelRule) -> pd.Series:
    direction = rule.direction
    if rule.setup == "momentum_3":
        return features["return_3m"] * direction > 0
    if rule.setup == "momentum_5":
        return features["return_5m"] * direction > 0
    if rule.setup == "mean_revert_z5":
        return features["z_5"] * direction < -0.7
    if rule.setup == "mean_revert_z10":
        return features["z_10"] * direction < -0.7
    if rule.setup == "vwap_reclaim":
        return features["vwap_distance"] * direction > 0
    if rule.setup == "vwap_fade":
        return features["vwap_distance"] * direction < 0
    if rule.setup == "imbalance_only":
        return pd.Series(True, index=features.index)
    raise ValueError(f"Unknown setup: {rule.setup}")


def _imbalance_mask(features: pd.DataFrame, rule: LabelRule) -> pd.Series:
    if rule.imbalance_filter == "none":
        return pd.Series(True, index=features.index)
    mode, threshold_text = rule.imbalance_filter.split("_", 1)
    threshold = float(threshold_text)
    signed = features["imbalance"] * rule.direction
    if mode == "aligned":
        return signed >= threshold
    if mode == "contrary":
        return signed <= -threshold
    raise ValueError(f"Unknown imbalance filter: {rule.imbalance_filter}")


def _vwap_side_mask(features: pd.DataFrame, rule: LabelRule) -> pd.Series:
    distance = features["vwap_distance"]
    if rule.vwap_side == "any":
        return pd.Series(True, index=features.index)
    if rule.vwap_side == "above":
        return distance > 0
    if rule.vwap_side == "below":
        return distance < 0
    if rule.vwap_side == "far_above":
        return distance > distance.quantile(0.70)
    if rule.vwap_side == "far_below":
        return distance < distance.quantile(0.30)
    raise ValueError(f"Unknown VWAP side: {rule.vwap_side}")


def summarize_trades(name: str, trades: pd.DataFrame) -> dict:
    if trades.empty:
        return _empty_summary(name)
    net = pd.to_numeric(trades["net_points"], errors="coerce")
    equity = net.cumsum()
    drawdown = equity - equity.cummax()
    wins = net[net > 0]
    losses = net[net < 0]
    return {
        "name": name,
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if float(losses.sum()) else float("inf"),
        "win_rate": float((net > 0).mean()),
        "max_drawdown_points": float(abs(drawdown.min())),
        "target_exit_share": float((trades["exit_reason"] == "take_profit").mean()),
        "stop_exit_share": float((trades["exit_reason"] == "stop_loss").mean()),
        "timeout_share": float((trades["exit_reason"] == "timeout").mean()),
    }


def _empty_summary(name: str) -> dict:
    return {
        "name": name,
        "trades": 0,
        "net_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "max_drawdown_points": 0.0,
        "target_exit_share": 0.0,
        "stop_exit_share": 0.0,
        "timeout_share": 0.0,
    }


def positive_window_rate(trades: pd.DataFrame, window_days: int = 10, step_days: int = 5) -> float:
    if trades.empty:
        return 0.0
    dates = sorted(pd.to_datetime(trades["entry_ts"], utc=True).dt.date.unique())
    window_days = min(window_days, len(dates))
    nets = []
    trade_dates = pd.to_datetime(trades["entry_ts"], utc=True).dt.date
    for start in range(0, len(dates) - window_days + 1, step_days):
        window_dates = set(dates[start : start + window_days])
        nets.append(float(trades.loc[trade_dates.isin(window_dates), "net_points"].sum()))
    if not nets:
        nets = [float(trades["net_points"].sum())]
    return float(sum(net > 0 for net in nets) / len(nets))


def _split_features(features: pd.DataFrame, train_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(features["trade_date"].dropna().unique())
    split_index = max(1, min(int(len(dates) * train_fraction), len(dates) - 1))
    train_dates = set(dates[:split_index])
    test_dates = set(dates[split_index:])
    return (
        features[features["trade_date"].isin(train_dates)].reset_index(drop=True),
        features[features["trade_date"].isin(test_dates)].reset_index(drop=True),
    )


def search_rules(features: pd.DataFrame, rules: list[LabelRule], args: argparse.Namespace) -> pd.DataFrame:
    train_features, test_features = _split_features(features, args.train_fraction)
    rows = []
    for index, rule in enumerate(rules, start=1):
        if args.progress_every and index % args.progress_every == 0:
            print(f"Rule scan: {index:,}/{len(rules):,}", flush=True)
        train_trades = build_rule_trades(train_features, rule)
        train = summarize_trades(rule.name, train_trades)
        if (
            train["trades"] < args.min_train_trades
            or train["net_points"] <= 0
            or train["win_rate"] < args.min_train_win_rate
            or train["profit_factor"] < args.min_profit_factor
        ):
            continue
        test_trades = build_rule_trades(test_features, rule)
        test = summarize_trades(rule.name, test_trades)
        test_window_rate = positive_window_rate(test_trades)
        row = {
            "name": rule.name,
            "direction": rule.direction,
            "stop_loss_points": rule.stop_loss_points,
            "take_profit_points": rule.take_profit_points,
            "horizon_minutes": rule.horizon_minutes,
            "session": rule.session,
            "vol_bucket": rule.vol_bucket,
            "setup": rule.setup,
            "imbalance_filter": rule.imbalance_filter,
            "vwap_side": rule.vwap_side,
            "min_gap_minutes": rule.min_gap_minutes,
            "train_trades": train["trades"],
            "train_net_points": train["net_points"],
            "train_win_rate": train["win_rate"],
            "train_profit_factor": train["profit_factor"],
            "test_trades": test["trades"],
            "test_net_points": test["net_points"],
            "test_win_rate": test["win_rate"],
            "test_profit_factor": test["profit_factor"],
            "test_max_drawdown_points": test["max_drawdown_points"],
            "test_target_exit_share": test["target_exit_share"],
            "test_stop_exit_share": test["stop_exit_share"],
            "test_timeout_share": test["timeout_share"],
            "test_positive_window_rate": test_window_rate,
        }
        row["blackbox_pass"] = (
            row["test_trades"] >= args.min_test_trades
            and row["test_net_points"] > 0
            and row["test_win_rate"] >= args.min_test_win_rate
            and row["test_profit_factor"] >= args.min_profit_factor
            and row["test_positive_window_rate"] >= args.min_positive_window_rate
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["blackbox_pass", "test_win_rate", "test_net_points", "test_profit_factor"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def _write_report(path: Path, results: pd.DataFrame, features: pd.DataFrame, rule_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "name",
        "train_trades",
        "train_win_rate",
        "train_net_points",
        "test_trades",
        "test_win_rate",
        "test_net_points",
        "test_profit_factor",
        "test_positive_window_rate",
        "blackbox_pass",
    ]
    passed = results[results["blackbox_pass"]] if not results.empty else pd.DataFrame()
    lines = [
        "# NQM6 2R Label Rule Search",
        "",
        f"Feature rows: {len(features):,}",
        f"Date range: {features['ts'].min()} to {features['ts'].max()}",
        f"Rules scanned: {rule_count:,}",
        f"Training-gated rules: {len(results):,}",
        f"Black-box passed rules: {len(passed):,}",
        "",
        "## Passed Rules",
        "",
        _markdown_table(passed.head(20)[columns]) if not passed.empty else "_No rows._",
        "",
        "## Top Training-Gated Rules",
        "",
        _markdown_table(results.head(20)[columns]) if not results.empty else "_No rows._",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Search simple 2R label rules from MBP minute features.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-2r-label-rules.csv")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-label-rules.md")
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--min-train-trades", type=int, default=120)
    parser.add_argument("--min-test-trades", type=int, default=50)
    parser.add_argument("--min-train-win-rate", type=float, default=0.56)
    parser.add_argument("--min-test-win-rate", type=float, default=0.60)
    parser.add_argument("--min-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-positive-window-rate", type=float, default=0.70)
    parser.add_argument("--max-rules", type=int, default=60000)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--progress-every", type=int, default=1000)
    args = parser.parse_args()

    features = prepare_features(_load_features(Path(args.features_cache)))
    rules = generate_rules()[: args.max_rules]
    if args.shard_count > 1:
        rules = [rule for index, rule in enumerate(rules) if index % args.shard_count == args.shard_index]
    results = search_rules(features, rules, args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(output, index=False)
    _write_report(Path(args.report), results, features, len(rules))
    print(f"Rules scanned: {len(rules):,}")
    print(f"Training-gated rules: {len(results):,}")
    print(f"Black-box pass: {int(results['blackbox_pass'].sum()) if not results.empty else 0}")
    print(f"CSV: {output}")
    print(f"Report: {args.report}")
    if not results.empty:
        print(results.head(20)[["name", "train_trades", "train_win_rate", "train_net_points", "test_trades", "test_win_rate", "test_net_points", "test_profit_factor", "blackbox_pass"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
