from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Candidate:
    name: str
    mask_fn: Callable[[pd.DataFrame], pd.Series]


def summarize(trades: pd.DataFrame) -> dict[str, float | int]:
    net = trades["net_points"].astype(float)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity if len(equity) else pd.Series(dtype=float)
    gross_profit = float(net[net > 0].sum())
    gross_loss = float(-net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()) if len(net) else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else np.inf,
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(net.min()) if len(net) else 0.0,
        "best_trade_points": float(net.max()) if len(net) else 0.0,
    }


def load_bars(cache_path: Path) -> pd.DataFrame:
    cached = pd.read_pickle(cache_path)
    bars = cached["features"] if isinstance(cached, dict) and "features" in cached else cached
    bars = bars.copy()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True).astype("datetime64[ns, UTC]")
    bars = bars.sort_values("ts").reset_index(drop=True)
    return bars


def add_market_features(bars: pd.DataFrame) -> pd.DataFrame:
    out = bars.copy()
    close = out["Close"].astype(float)
    high = out["High"].astype(float)
    low = out["Low"].astype(float)
    open_ = out["Open"].astype(float)
    out["ema20"] = close.ewm(span=20, adjust=False).mean()
    out["ema60"] = close.ewm(span=60, adjust=False).mean()
    out["ema20_slope_10"] = out["ema20"] - out["ema20"].shift(10)
    out["ema60_slope_20"] = out["ema60"] - out["ema60"].shift(20)
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    out["atr14"] = true_range.ewm(alpha=1 / 14, adjust=False).mean()
    out["atr14_rank_240"] = out["atr14"].rolling(240, min_periods=60).rank(pct=True)
    out["body_atr"] = (close - open_).abs() / out["atr14"].replace(0, np.nan)
    out["range_atr"] = (high - low) / out["atr14"].replace(0, np.nan)
    for window in (20, 60, 120):
        roll_high = high.rolling(window, min_periods=max(10, window // 2)).max()
        roll_low = low.rolling(window, min_periods=max(10, window // 2)).min()
        denom = (roll_high - roll_low).replace(0, np.nan)
        out[f"range_pos_{window}"] = (close - roll_low) / denom
        out[f"range_width_atr_{window}"] = denom / out["atr14"].replace(0, np.nan)
    for window in (5, 15, 30, 60):
        out[f"mom_{window}_pts"] = close - close.shift(window)
        out[f"mom_{window}_atr"] = out[f"mom_{window}_pts"] / out["atr14"].replace(0, np.nan)
    out["close_ema20_atr"] = (close - out["ema20"]) / out["atr14"].replace(0, np.nan)
    out["close_ema60_atr"] = (close - out["ema60"]) / out["atr14"].replace(0, np.nan)
    out["trend_stack"] = np.select(
        [close.gt(out["ema20"]) & out["ema20"].gt(out["ema60"]), close.lt(out["ema20"]) & out["ema20"].lt(out["ema60"])],
        [1, -1],
        default=0,
    )
    return out


def attach_entry_features(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True).astype("datetime64[ns, UTC]")
    trades["signal_ts"] = pd.to_datetime(trades["signal_ts"], utc=True).astype("datetime64[ns, UTC]")
    bars = bars.reset_index(drop=True)
    feature_cols = [
        "ts",
        "ema20_slope_10",
        "ema60_slope_20",
        "atr14",
        "atr14_rank_240",
        "body_atr",
        "range_atr",
        "range_pos_20",
        "range_pos_60",
        "range_pos_120",
        "range_width_atr_20",
        "range_width_atr_60",
        "range_width_atr_120",
        "mom_5_atr",
        "mom_15_atr",
        "mom_30_atr",
        "mom_60_atr",
        "close_ema20_atr",
        "close_ema60_atr",
        "trend_stack",
        "Volume",
        "volume_z_60",
        "range_mean_30",
    ]
    feature_frame = bars.loc[:, feature_cols].rename(columns={"ts": "feature_ts"})
    # Use the last fully closed bar before the entry timestamp. This is causal for next-open entries.
    merged = pd.merge_asof(
        trades.sort_values("entry_ts"),
        feature_frame.sort_values("feature_ts"),
        left_on="entry_ts",
        right_on="feature_ts",
        direction="backward",
        allow_exact_matches=False,
    )
    merged["dir_mom_5"] = merged["mom_5_atr"] * merged["direction"]
    merged["dir_mom_15"] = merged["mom_15_atr"] * merged["direction"]
    merged["dir_mom_30"] = merged["mom_30_atr"] * merged["direction"]
    merged["dir_mom_60"] = merged["mom_60_atr"] * merged["direction"]
    merged["dir_ema20_dist"] = merged["close_ema20_atr"] * merged["direction"]
    merged["dir_ema60_dist"] = merged["close_ema60_atr"] * merged["direction"]
    merged["dir_ema20_slope"] = merged["ema20_slope_10"] * merged["direction"]
    merged["dir_ema60_slope"] = merged["ema60_slope_20"] * merged["direction"]
    merged["directional_trend_stack"] = merged["trend_stack"] * merged["direction"]
    merged["directional_range_pos_60"] = np.where(
        merged["direction"].gt(0),
        merged["range_pos_60"],
        1.0 - merged["range_pos_60"],
    )
    merged["directional_range_pos_120"] = np.where(
        merged["direction"].gt(0),
        merged["range_pos_120"],
        1.0 - merged["range_pos_120"],
    )
    return merged


def make_candidates() -> list[Candidate]:
    candidates: list[Candidate] = [
        Candidate("baseline_no_filter", lambda df: pd.Series(True, index=df.index)),
    ]
    for col, thresholds in {
        "dir_mom_15": [-1.5, -1.0, -0.5, 0.0, 0.25, 0.5, 1.0],
        "dir_mom_30": [-1.5, -1.0, -0.5, 0.0, 0.25, 0.5, 1.0],
        "dir_mom_60": [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0],
        "dir_ema20_dist": [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0],
        "dir_ema20_slope": [-20.0, -10.0, 0.0, 10.0, 20.0],
        "dir_ema60_slope": [-40.0, -20.0, 0.0, 20.0],
        "directional_trend_stack": [-1.0, 0.0, 1.0],
    }.items():
        for threshold in thresholds:
            candidates.append(Candidate(f"{col}>={threshold:g}", lambda df, c=col, t=threshold: df[c].ge(t)))
    for col in ("directional_range_pos_60", "directional_range_pos_120"):
        for lo in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25]:
            for hi in [0.65, 0.75, 0.85, 0.95, 1.0]:
                if lo < hi:
                    candidates.append(Candidate(f"{col}_between_{lo:g}_{hi:g}", lambda df, c=col, a=lo, b=hi: df[c].between(a, b)))
    for lo in [0.0, 0.1, 0.2, 0.3]:
        for hi in [0.75, 0.85, 0.95, 1.0]:
            if lo < hi:
                candidates.append(Candidate(f"atr14_rank_240_between_{lo:g}_{hi:g}", lambda df, a=lo, b=hi: df["atr14_rank_240"].between(a, b)))
    combo_specs = [
        ("no_chase_range60_and_mom15", lambda df: df["directional_range_pos_60"].between(0.05, 0.85) & df["dir_mom_15"].ge(-0.5)),
        ("no_chase_range120_and_mom30", lambda df: df["directional_range_pos_120"].between(0.05, 0.85) & df["dir_mom_30"].ge(-0.5)),
        ("trend_aligned_not_extended", lambda df: df["directional_trend_stack"].ge(0) & df["directional_range_pos_60"].between(0.05, 0.9)),
        ("pullback_in_aligned_trend", lambda df: df["directional_trend_stack"].ge(1) & df["directional_range_pos_60"].between(0.05, 0.75)),
        ("avoid_extreme_vol_and_chase", lambda df: df["atr14_rank_240"].between(0.1, 0.9) & df["directional_range_pos_60"].between(0.05, 0.85)),
        ("quality_stack_loose", lambda df: df["directional_range_pos_60"].between(0.05, 0.9) & df["dir_mom_15"].ge(-0.75) & df["atr14_rank_240"].between(0.05, 0.95)),
        ("quality_stack_mid", lambda df: df["directional_range_pos_60"].between(0.1, 0.85) & df["dir_mom_15"].ge(-0.5) & df["atr14_rank_240"].between(0.1, 0.9)),
        ("quality_stack_strict", lambda df: df["directional_range_pos_60"].between(0.15, 0.8) & df["dir_mom_15"].ge(0.0) & df["atr14_rank_240"].between(0.15, 0.85)),
    ]
    candidates.extend(Candidate(name, fn) for name, fn in combo_specs)
    return candidates


def scan_candidates(trades: pd.DataFrame, min_trades: int) -> pd.DataFrame:
    baseline = summarize(trades)
    rows = []
    for candidate in make_candidates():
        mask = candidate.mask_fn(trades).fillna(False)
        selected = trades.loc[mask].copy()
        if len(selected) < min_trades:
            continue
        row = {"candidate": candidate.name, **summarize(selected)}
        row["removed_trades"] = int(len(trades) - len(selected))
        row["removed_net_points"] = float(trades.loc[~mask, "net_points"].sum())
        row["net_delta"] = float(row["net_points"] - baseline["net_points"])
        row["pf_delta"] = float(row["profit_factor"] - baseline["profit_factor"])
        row["dd_delta"] = float(row["max_drawdown_points"] - baseline["max_drawdown_points"])
        row["score"] = float(row["net_points"] + 120.0 * row["profit_factor"] - 0.8 * row["max_drawdown_points"])
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False)


def segment_masks(trades: pd.DataFrame) -> list[tuple[str, pd.Series]]:
    masks: list[tuple[str, pd.Series]] = []
    for column in ("signal_family", "entry_mode", "target_plan", "component_strategy"):
        if column not in trades.columns:
            continue
        for value, group in trades.groupby(column, dropna=False):
            if len(group) < 40:
                continue
            masks.append((f"{column}={value}", trades[column].eq(value)))
    for columns in (("signal_family", "entry_mode"), ("signal_family", "session"), ("entry_mode", "target_plan")):
        missing = [column for column in columns if column not in trades.columns]
        if missing:
            continue
        grouped = trades.groupby(list(columns), dropna=False)
        for values, group in grouped:
            if len(group) < 40:
                continue
            if not isinstance(values, tuple):
                values = (values,)
            mask = pd.Series(True, index=trades.index)
            label_parts = []
            for column, value in zip(columns, values):
                mask &= trades[column].eq(value)
                label_parts.append(f"{column}={value}")
            masks.append(("&".join(label_parts), mask))
    return masks


def scan_segment_candidates(trades: pd.DataFrame, min_trades: int, min_segment_trades: int) -> pd.DataFrame:
    baseline = summarize(trades)
    rows = []
    for segment_name, segment_mask in segment_masks(trades):
        segment_count = int(segment_mask.sum())
        if segment_count < min_segment_trades:
            continue
        for candidate in make_candidates()[1:]:
            candidate_mask = candidate.mask_fn(trades).fillna(False)
            final_mask = (~segment_mask) | candidate_mask
            removed_in_segment = segment_mask & ~candidate_mask
            if int(removed_in_segment.sum()) < 5:
                continue
            selected = trades.loc[final_mask].copy()
            if len(selected) < min_trades:
                continue
            removed_net = float(trades.loc[~final_mask, "net_points"].sum())
            row = {
                "candidate": f"{segment_name} :: keep_if {candidate.name}",
                "segment": segment_name,
                "segment_trades": segment_count,
                "filter": candidate.name,
                **summarize(selected),
            }
            row["removed_trades"] = int((~final_mask).sum())
            row["removed_net_points"] = removed_net
            row["net_delta"] = float(row["net_points"] - baseline["net_points"])
            row["pf_delta"] = float(row["profit_factor"] - baseline["profit_factor"])
            row["dd_delta"] = float(row["max_drawdown_points"] - baseline["max_drawdown_points"])
            row["score"] = float(row["net_points"] + 120.0 * row["profit_factor"] - 0.8 * row["max_drawdown_points"])
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["net_delta", "profit_factor"], ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan causal market-feature filters for sum_pos_open2 trades.")
    parser.add_argument("--trades", default="reports/NQ-pine-12m-high-return-sum_pos-open2-dirNone-trades.csv")
    parser.add_argument("--bars-cache", default=".tmp/nq-pine-combo-trailing-12m-bars.pkl")
    parser.add_argument("--output", default="reports/NQ-pine-12m-sum_pos-open2-market-feature-filter-ranking.csv")
    parser.add_argument("--features-output", default="reports/NQ-pine-12m-sum_pos-open2-trades-with-market-features.csv")
    parser.add_argument("--segment-output", default="reports/NQ-pine-12m-sum_pos-open2-segment-market-feature-filter-ranking.csv")
    parser.add_argument("--min-trades", type=int, default=600)
    parser.add_argument("--min-segment-trades", type=int, default=40)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    bars = add_market_features(load_bars(ROOT_DIR / args.bars_cache))
    featured = attach_entry_features(trades, bars)
    ranking = scan_candidates(featured, args.min_trades)
    segment_ranking = scan_segment_candidates(featured, args.min_trades, args.min_segment_trades)

    feature_path = ROOT_DIR / args.features_output
    output_path = ROOT_DIR / args.output
    segment_output_path = ROOT_DIR / args.segment_output
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    featured.to_csv(feature_path, index=False)
    ranking.to_csv(output_path, index=False)
    segment_ranking.to_csv(segment_output_path, index=False)
    print(f"wrote {output_path}")
    print(f"wrote {segment_output_path}")
    print(f"wrote {feature_path}")
    print("GLOBAL")
    print(ranking.head(15).to_string(index=False))
    print("SEGMENT")
    print(segment_ranking.head(25).to_string(index=False))


if __name__ == "__main__":
    main()
