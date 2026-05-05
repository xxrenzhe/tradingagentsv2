from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class FilterCondition:
    column: str
    op: str
    value: object


@dataclass(frozen=True)
class StateFilter:
    name: str
    conditions: tuple[FilterCondition, ...]


def load_features(cache_path: str) -> pd.DataFrame:
    cache = pd.read_pickle(cache_path)
    features = cache["features"] if isinstance(cache, dict) and "features" in cache else cache
    frame = features.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return enrich_state_features(frame)


def enrich_state_features(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    open_price = pd.to_numeric(frame["Open"], errors="coerce")
    high = pd.to_numeric(frame["High"], errors="coerce")
    low = pd.to_numeric(frame["Low"], errors="coerce")
    close = pd.to_numeric(frame["Close"], errors="coerce")
    volume = pd.to_numeric(frame["Volume"], errors="coerce").fillna(0.0)
    if "vwap" not in frame.columns:
        if "trade_date" in frame.columns:
            grouped_volume = volume.groupby(frame["trade_date"], sort=False)
            cumulative_volume = grouped_volume.cumsum().replace(0, pd.NA)
            frame["vwap"] = (close * volume).groupby(frame["trade_date"], sort=False).cumsum() / cumulative_volume
        else:
            cumulative_volume = volume.cumsum().replace(0, pd.NA)
            frame["vwap"] = (close * volume).cumsum() / cumulative_volume
    frame["vwap_side"] = (close >= pd.to_numeric(frame["vwap"], errors="coerce")).map({True: "above", False: "below"})
    frame["trend_120"] = close - close.rolling(120).mean()
    frame["trend_side_120"] = (frame["trend_120"] >= 0).map({True: "up", False: "down"})
    frame["minute_bucket_30"] = (frame["minute_of_day"] // 30).astype("Int64")
    frame["vol_120_rank"] = pd.to_numeric(frame["vol_120"], errors="coerce").rank(pct=True)
    frame["range_30_rank"] = pd.to_numeric(frame["range_mean_30"], errors="coerce").rank(pct=True)
    frame["entry_range_points"] = (high - low).where((high - low) > 0)
    frame["entry_body_points"] = (close - open_price).abs()
    frame["entry_body_to_range"] = frame["entry_body_points"] / frame["entry_range_points"]
    frame["entry_body_rank"] = frame["entry_body_points"].rank(pct=True)
    frame["entry_close_location"] = (close - low) / frame["entry_range_points"]
    frame["entry_candle_side"] = (close >= open_price).map({True: "up", False: "down"})
    frame["entry_close_zone"] = "middle"
    frame.loc[frame["entry_close_location"] >= 0.70, "entry_close_zone"] = "high"
    frame.loc[frame["entry_close_location"] <= 0.30, "entry_close_zone"] = "low"
    frame["vwap_distance_points"] = close - pd.to_numeric(frame["vwap"], errors="coerce")
    frame["vwap_distance_abs_rank"] = frame["vwap_distance_points"].abs().rank(pct=True)
    frame["vwap_stretch_side"] = "neutral"
    frame.loc[(frame["vwap_distance_points"] > 0) & (frame["vwap_distance_abs_rank"] > 0.67), "vwap_stretch_side"] = "above"
    frame.loc[(frame["vwap_distance_points"] < 0) & (frame["vwap_distance_abs_rank"] > 0.67), "vwap_stretch_side"] = "below"
    frame["return_1m_side"] = (pd.to_numeric(frame["return_1m"], errors="coerce") >= 0).map({True: "positive", False: "negative"})
    return frame


def load_trades(path: str) -> pd.DataFrame:
    trades = pd.read_csv(path)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["net_points"] = pd.to_numeric(trades["net_points"], errors="coerce")
    trades["direction"] = pd.to_numeric(trades["direction"], errors="coerce")
    return trades.dropna(subset=["entry_ts", "candidate", "net_points", "direction"]).copy()


def attach_state(trades: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    state_columns = [
        "ts",
        "Close",
        "vwap",
        "vwap_side",
        "trend_side_120",
        "momentum_60",
        "z_30",
        "vol_120_rank",
        "range_30_rank",
        "volume_z_60",
        "return_1m_side",
        "entry_body_rank",
        "entry_body_to_range",
        "entry_candle_side",
        "entry_close_zone",
        "vwap_distance_abs_rank",
        "vwap_stretch_side",
        "minute_bucket_30",
    ]
    state = features[state_columns].rename(columns={"ts": "entry_ts"})
    return trades.merge(state, on="entry_ts", how="left")


def candidate_filters(frame: pd.DataFrame) -> list[StateFilter]:
    def single(name: str, column: str, op: str, value: object) -> StateFilter:
        return StateFilter(name, (FilterCondition(column, op, value),))

    def combo(name: str, *conditions: FilterCondition) -> StateFilter:
        return StateFilter(name, conditions)

    filters = [
        single("vwap_above", "vwap_side", "eq", "above"),
        single("vwap_below", "vwap_side", "eq", "below"),
        single("trend_120_up", "trend_side_120", "eq", "up"),
        single("trend_120_down", "trend_side_120", "eq", "down"),
        single("momentum_60_positive", "momentum_60", "gt", 0.0),
        single("momentum_60_negative", "momentum_60", "lt", 0.0),
        single("z_30_negative", "z_30", "lt", 0.0),
        single("z_30_positive", "z_30", "gt", 0.0),
        single("vol_120_low_mid", "vol_120_rank", "le", 0.67),
        single("vol_120_high", "vol_120_rank", "gt", 0.67),
        single("range_30_low_mid", "range_30_rank", "le", 0.67),
        single("range_30_high", "range_30_rank", "gt", 0.67),
        single("volume_z_60_high", "volume_z_60", "gt", 1.0),
        single("volume_z_60_low", "volume_z_60", "lt", -1.0),
        single("return_1m_positive", "return_1m_side", "eq", "positive"),
        single("return_1m_negative", "return_1m_side", "eq", "negative"),
        single("entry_candle_up", "entry_candle_side", "eq", "up"),
        single("entry_candle_down", "entry_candle_side", "eq", "down"),
        single("entry_close_high", "entry_close_zone", "eq", "high"),
        single("entry_close_low", "entry_close_zone", "eq", "low"),
        single("entry_body_low_mid", "entry_body_rank", "le", 0.67),
        single("entry_body_high", "entry_body_rank", "gt", 0.67),
        single("vwap_distance_low_mid", "vwap_distance_abs_rank", "le", 0.67),
        single("vwap_distance_high", "vwap_distance_abs_rank", "gt", 0.67),
        single("vwap_stretched_above", "vwap_stretch_side", "eq", "above"),
        single("vwap_stretched_below", "vwap_stretch_side", "eq", "below"),
        combo(
            "vwap_above_and_trend_120_up",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("trend_side_120", "eq", "up"),
        ),
        combo(
            "vwap_below_and_trend_120_down",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("trend_side_120", "eq", "down"),
        ),
        combo(
            "vwap_above_and_momentum_60_positive",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("momentum_60", "gt", 0.0),
        ),
        combo(
            "vwap_below_and_momentum_60_negative",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("momentum_60", "lt", 0.0),
        ),
        combo(
            "trend_120_up_and_z_30_negative",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("z_30", "lt", 0.0),
        ),
        combo(
            "trend_120_down_and_z_30_positive",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("z_30", "gt", 0.0),
        ),
        combo(
            "trend_120_up_and_vol_120_low_mid",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("vol_120_rank", "le", 0.67),
        ),
        combo(
            "trend_120_down_and_vol_120_low_mid",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("vol_120_rank", "le", 0.67),
        ),
        combo(
            "trend_120_up_and_range_30_low_mid",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("range_30_rank", "le", 0.67),
        ),
        combo(
            "trend_120_down_and_range_30_low_mid",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("range_30_rank", "le", 0.67),
        ),
        combo(
            "trend_120_up_and_entry_close_high",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "trend_120_up_and_entry_close_low",
            FilterCondition("trend_side_120", "eq", "up"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "trend_120_down_and_entry_close_low",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "trend_120_down_and_entry_close_high",
            FilterCondition("trend_side_120", "eq", "down"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "vwap_below_and_entry_close_high",
            FilterCondition("vwap_side", "eq", "below"),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "vwap_above_and_entry_close_low",
            FilterCondition("vwap_side", "eq", "above"),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
        combo(
            "momentum_60_positive_and_entry_body_low_mid",
            FilterCondition("momentum_60", "gt", 0.0),
            FilterCondition("entry_body_rank", "le", 0.67),
        ),
        combo(
            "momentum_60_negative_and_entry_body_low_mid",
            FilterCondition("momentum_60", "lt", 0.0),
            FilterCondition("entry_body_rank", "le", 0.67),
        ),
        combo(
            "vwap_stretched_above_and_z_30_positive",
            FilterCondition("vwap_stretch_side", "eq", "above"),
            FilterCondition("z_30", "gt", 0.0),
        ),
        combo(
            "vwap_stretched_below_and_z_30_negative",
            FilterCondition("vwap_stretch_side", "eq", "below"),
            FilterCondition("z_30", "lt", 0.0),
        ),
        combo(
            "volume_z_60_high_and_entry_close_high",
            FilterCondition("volume_z_60", "gt", 1.0),
            FilterCondition("entry_close_zone", "eq", "high"),
        ),
        combo(
            "volume_z_60_high_and_entry_close_low",
            FilterCondition("volume_z_60", "gt", 1.0),
            FilterCondition("entry_close_zone", "eq", "low"),
        ),
    ]
    for bucket in sorted(frame["minute_bucket_30"].dropna().unique()):
        filters.append(single(f"minute_bucket_30_{int(bucket)}", "minute_bucket_30", "eq", int(bucket)))
    return filters


def mine_filters(
    trades: pd.DataFrame,
    *,
    min_trades: int,
    min_folds: int = 1,
    min_net_points: float,
    min_profit_factor: float,
    min_win_rate: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    filters = candidate_filters(trades)
    for candidate, group in trades.groupby("candidate", sort=False):
        baseline = summarize(group)
        for state_filter in filters:
            selected = group[apply_filter(group, state_filter)]
            if selected.empty:
                continue
            summary = summarize(selected)
            if (
                summary["trades"] < min_trades
                or summary["folds"] < min_folds
                or summary["net_points"] < min_net_points
                or summary["profit_factor"] < min_profit_factor
                or summary["win_rate"] < min_win_rate
            ):
                continue
            rows.append(
                {
                    "candidate": candidate,
                    "filter": state_filter.name,
                    "filter_conditions": describe_filter(state_filter),
                    "trades": summary["trades"],
                    "net_points": summary["net_points"],
                    "profit_factor": summary["profit_factor"],
                    "win_rate": summary["win_rate"],
                    "avg_points": summary["avg_points"],
                    "folds": summary["folds"],
                    "positive_fold_rate": summary["positive_fold_rate"],
                    "min_fold_net_points": summary["min_fold_net_points"],
                    "baseline_trades": baseline["trades"],
                    "baseline_net_points": baseline["net_points"],
                    "baseline_profit_factor": baseline["profit_factor"],
                    "baseline_positive_fold_rate": baseline["positive_fold_rate"],
                    "baseline_min_fold_net_points": baseline["min_fold_net_points"],
                    "net_improvement": summary["net_points"] - baseline["net_points"],
                    "profit_factor_improvement": summary["profit_factor"] - baseline["profit_factor"],
                    "retained_trade_rate": summary["trades"] / max(baseline["trades"], 1),
                }
            )
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    return result.sort_values(
        ["net_points", "profit_factor", "win_rate", "trades"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)


def apply_filter(frame: pd.DataFrame, state_filter: StateFilter) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for condition in state_filter.conditions:
        mask &= apply_condition(frame, condition)
    return mask


def apply_condition(frame: pd.DataFrame, condition: FilterCondition) -> pd.Series:
    values = frame[condition.column]
    if condition.op == "eq":
        return values == condition.value
    numeric = pd.to_numeric(values, errors="coerce")
    if condition.op == "gt":
        return numeric > float(condition.value)
    if condition.op == "lt":
        return numeric < float(condition.value)
    if condition.op == "le":
        return numeric <= float(condition.value)
    raise ValueError(f"unknown filter op: {condition.op}")


def describe_filter(state_filter: StateFilter) -> str:
    return ";".join(f"{condition.column}{condition.op}{condition.value}" for condition in state_filter.conditions)


def summarize(frame: pd.DataFrame) -> dict[str, float]:
    net = pd.to_numeric(frame["net_points"], errors="coerce").dropna()
    wins = net[net > 0].sum()
    losses = abs(net[net < 0].sum())
    profit_factor = float(wins / losses) if losses else float("inf")
    return {
        "trades": int(len(net)),
        "net_points": float(net.sum()),
        "profit_factor": profit_factor,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        **summarize_folds(frame),
    }


def summarize_folds(frame: pd.DataFrame) -> dict[str, float]:
    if "fold" not in frame.columns or frame.empty:
        return {"folds": 0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    fold_net = pd.to_numeric(frame["net_points"], errors="coerce").groupby(frame["fold"]).sum()
    if fold_net.empty:
        return {"folds": 0, "positive_fold_rate": 0.0, "min_fold_net_points": 0.0}
    return {
        "folds": int(len(fold_net)),
        "positive_fold_rate": float((fold_net > 0).mean()),
        "min_fold_net_points": float(fold_net.min()),
    }


def write_report(path: Path, mined: pd.DataFrame, args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQ 5y State-Filtered Feature Mining",
        "",
        "This report mines state filters over existing 5-year direction-filtered NQ 1m walk-forward trade rows.",
        "",
        f"- Trades input: `{args.trades_input}`",
        f"- Feature cache: `{args.features_cache}`",
        f"- Rows found: `{len(mined):,}`",
        f"- Gates: min_trades=`{args.min_trades}`, min_folds=`{args.min_folds}`, min_net_points=`{args.min_net_points}`, min_profit_factor=`{args.min_profit_factor}`, min_win_rate=`{args.min_win_rate}`",
        "",
    ]
    if mined.empty:
        lines.append("No state-filtered rows passed the configured gates.")
    else:
        lines.extend(
            [
                "## Top State-Filtered Edges",
                "",
                "```csv",
                mined.head(args.top_n).to_csv(index=False).strip(),
                "```",
                "",
                "## Interpretation",
                "",
                "- These are post-filtered research edges mined from already selected walk-forward trades.",
                "- Use them as LLM debate and paper-validation candidates; they are not live-ready without a fresh walk-forward that selects the filter during training.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine state filters over NQ walk-forward trade rows.")
    parser.add_argument("--features-cache", default=".tmp/nq-bar-5y-continuous-features-cache.pkl")
    parser.add_argument("--trades-input", default=".tmp/nq-bar-5y-directional-walkforward-trades.csv")
    parser.add_argument("--output", default=".tmp/nq-bar-5y-state-filtered-features.csv")
    parser.add_argument("--report", default="reports/NQ-bar-5y-state-filtered-feature-mining.md")
    parser.add_argument("--min-trades", type=int, default=80)
    parser.add_argument("--min-folds", type=int, default=2)
    parser.add_argument("--min-net-points", type=float, default=1500.0)
    parser.add_argument("--min-profit-factor", type=float, default=1.20)
    parser.add_argument("--min-win-rate", type=float, default=0.48)
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    features = load_features(args.features_cache)
    trades = attach_state(load_trades(args.trades_input), features)
    mined = mine_filters(
        trades,
        min_trades=args.min_trades,
        min_folds=args.min_folds,
        min_net_points=args.min_net_points,
        min_profit_factor=args.min_profit_factor,
        min_win_rate=args.min_win_rate,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    mined.to_csv(output, index=False)
    write_report(Path(args.report), mined, args)
    result = {
        "feature_rows": int(len(features)),
        "trade_rows": int(len(trades)),
        "mined_rows": int(len(mined)),
        "output": str(output),
        "report": args.report,
    }
    if not mined.empty:
        result["top_edge"] = mined.iloc[0].to_dict()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
