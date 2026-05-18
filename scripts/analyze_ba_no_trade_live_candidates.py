from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
POINT_VALUE = 20.0
BA_TRADES = ROOT_DIR / "reports/NQ-pine-5y-runner-meta-balanced-aggressive-sizing-trades.csv"
BA_MONTHLY = ROOT_DIR / "reports/NQ-pine-5y-runner-meta-balanced-aggressive-sizing-monthly.csv"
OUTPUT_PREFIX = ROOT_DIR / "reports/NQ-pine-5y-ba-no-trade-live-candidates"
FEATURE_CACHE = ROOT_DIR / ".tmp/nq-bar-5y-continuous-features-cache.pkl"


@dataclass(frozen=True)
class PoolSpec:
    source: str
    path: Path
    min_trades: int = 20


POOL_SPECS = [
    PoolSpec("ict2022", ROOT_DIR / ".tmp/nq-ict2022-event-2010-focused-oos-trades.csv"),
    PoolSpec("bar_broader", ROOT_DIR / ".tmp/nq-bar-5y-broader-walkforward-trades.csv"),
    PoolSpec("bar_directional", ROOT_DIR / ".tmp/nq-bar-5y-directional-walkforward-trades.csv"),
    PoolSpec("bar_full", ROOT_DIR / ".tmp/nq-bar-5y-full-walkforward-trades.csv"),
    PoolSpec("bar_price_action", ROOT_DIR / ".tmp/nq-bar-5y-price-action-walkforward-trades.csv"),
    PoolSpec("bar_base", ROOT_DIR / ".tmp/nq-bar-5y-walkforward-trades.csv"),
    PoolSpec("lightglow", ROOT_DIR / ".tmp/nq-lightglow-5y-walkforward-trades.csv"),
    PoolSpec("tv_structure", ROOT_DIR / ".tmp/nq-tv-structure-strategy-walkforward-trades.csv", min_trades=10),
]


def summarize_points(points: pd.Series | np.ndarray) -> dict[str, float | int]:
    values = pd.to_numeric(pd.Series(points), errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
            "worst_trade_points": 0.0,
            "best_trade_points": 0.0,
            "gross_profit_points": 0.0,
            "gross_loss_points": 0.0,
        }
    gross_profit = float(values[values > 0].sum())
    gross_loss = float(-values[values < 0].sum())
    equity = values.cumsum()
    drawdown = np.maximum.accumulate(equity) - equity
    return {
        "trades": int(len(values)),
        "net_points": float(values.sum()),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf"),
        "win_rate": float((values > 0).mean()),
        "avg_points": float(values.mean()),
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(values.min()),
        "best_trade_points": float(values.max()),
        "gross_profit_points": gross_profit,
        "gross_loss_points": gross_loss,
    }


def add_month(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    if "exit_ts" in out.columns:
        out["exit_ts"] = pd.to_datetime(out["exit_ts"], utc=True)
    out["month"] = out["entry_ts"].dt.tz_convert(None).dt.to_period("M").astype(str)
    out["year"] = out["entry_ts"].dt.year
    return out


def load_ba() -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp, set[str]]:
    trades = add_month(pd.read_csv(BA_TRADES))
    trades["portfolio_points"] = pd.to_numeric(trades["sized_net_points"], errors="coerce")
    monthly = pd.read_csv(BA_MONTHLY)
    no_trade_months = set(monthly.loc[pd.to_numeric(monthly["test_trades"], errors="coerce").eq(0), "month"].astype(str))
    period_start = pd.Timestamp(f"{monthly['month'].min()}-01", tz="UTC")
    period_end = pd.Timestamp(f"{monthly['month'].max()}-01", tz="UTC") + pd.DateOffset(months=1)
    return trades, monthly, period_start, period_end, no_trade_months


def load_pool(spec: PoolSpec, period_start: pd.Timestamp, period_end: pd.Timestamp, no_trade_months: set[str]) -> pd.DataFrame:
    if not spec.path.exists():
        return pd.DataFrame()
    frame = add_month(pd.read_csv(spec.path))
    frame = frame[(frame["entry_ts"] >= period_start) & (frame["entry_ts"] < period_end)].copy()
    frame = frame[frame["month"].isin(no_trade_months)].copy()
    if frame.empty:
        return frame
    frame["source_pool"] = spec.source
    frame["candidate"] = frame["candidate"].astype(str)
    frame["candidate_key"] = spec.source + "::" + frame["candidate"]
    frame["net_points"] = pd.to_numeric(frame["net_points"], errors="coerce")
    frame["gross_points"] = pd.to_numeric(frame.get("gross_points", frame["net_points"]), errors="coerce")
    if "direction" in frame.columns:
        frame["direction"] = pd.to_numeric(frame["direction"], errors="coerce")
    return frame.dropna(subset=["net_points", "entry_ts", "exit_ts"])


def rank_candidates(pools: dict[str, pd.DataFrame], ba_pf: float) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for source, frame in pools.items():
        if frame.empty:
            continue
        min_trades = next(spec.min_trades for spec in POOL_SPECS if spec.source == source)
        for candidate_key, group in frame.groupby("candidate_key", sort=False):
            summary = summarize_points(group["net_points"])
            if int(summary["trades"]) < min_trades:
                continue
            monthly = group.groupby("month")["net_points"].sum()
            yearly = group.groupby("year")["net_points"].sum()
            rows.append(
                {
                    "source_pool": source,
                    "candidate_key": candidate_key,
                    "candidate": group["candidate"].iloc[0],
                    "active_months": int(monthly.ne(0).sum()),
                    "positive_months": int(monthly.gt(0).sum()),
                    "negative_months": int(monthly.lt(0).sum()),
                    "worst_month_points": float(monthly.min()) if len(monthly) else 0.0,
                    "best_month_points": float(monthly.max()) if len(monthly) else 0.0,
                    "positive_years": int(yearly.gt(0).sum()),
                    "negative_years": int(yearly.lt(0).sum()),
                    "live_quality_gate": bool(
                        int(summary["trades"]) >= min_trades
                        and float(summary["net_points"]) > 0.0
                        and float(summary["profit_factor"]) >= ba_pf
                        and int(monthly.ne(0).sum()) >= 4
                        and float(summary["max_drawdown_points"]) <= 300.0
                    ),
                    "ranking_score": float(summary["net_points"])
                    + 250.0 * min(float(summary["profit_factor"]), 6.0)
                    + 30.0 * int(monthly.ne(0).sum())
                    - 0.50 * float(summary["max_drawdown_points"]),
                    **summary,
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["live_quality_gate", "ranking_score", "net_points", "profit_factor"],
        ascending=[False, False, False, False],
    )


def remove_overlapping(candidate: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    if candidate.empty:
        return candidate
    existing = []
    if not selected.empty:
        existing = list(zip(selected["entry_ts"].tolist(), selected["exit_ts"].tolist(), strict=False))
    kept_rows = []
    active_until = None
    for _, row in candidate.sort_values("entry_ts").iterrows():
        entry = row["entry_ts"]
        exit_ts = row["exit_ts"]
        if active_until is not None and entry < active_until:
            continue
        if any(entry < old_exit and exit_ts > old_entry for old_entry, old_exit in existing):
            continue
        kept_rows.append(row)
        active_until = exit_ts
    return pd.DataFrame(kept_rows)


def build_greedy_overlay(pools: dict[str, pd.DataFrame], ranking: pd.DataFrame, ba_pf: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = pd.DataFrame()
    selected_rows: list[dict[str, object]] = []
    eligible = ranking[ranking["live_quality_gate"]].copy()
    # High return first, but every addition must preserve the BA PF floor.
    eligible = eligible.sort_values(["net_points", "profit_factor", "active_months"], ascending=[False, False, False])
    for _, row in eligible.iterrows():
        source = str(row["source_pool"])
        key = str(row["candidate_key"])
        candidate = pools[source][pools[source]["candidate_key"].eq(key)].copy()
        candidate = remove_overlapping(candidate, selected)
        if candidate.empty:
            continue
        trial = pd.concat([selected, candidate], ignore_index=True, sort=False)
        trial_summary = summarize_points(trial["net_points"])
        if float(trial_summary["profit_factor"]) + 1e-12 < ba_pf:
            continue
        selected = trial.sort_values("entry_ts").reset_index(drop=True)
        selected_rows.append(
            {
                "selected_order": len(selected_rows) + 1,
                "source_pool": source,
                "candidate_key": key,
                "candidate": row["candidate"],
                "candidate_trades_before_overlap": int(row["trades"]),
                "candidate_net_before_overlap": float(row["net_points"]),
                "candidate_pf_before_overlap": float(row["profit_factor"]),
                "added_trades_after_overlap": int(len(candidate)),
                "added_net_after_overlap": float(candidate["net_points"].sum()),
                "overlay_trades_after_add": int(trial_summary["trades"]),
                "overlay_net_after_add": float(trial_summary["net_points"]),
                "overlay_pf_after_add": float(trial_summary["profit_factor"]),
                "overlay_dd_after_add": float(trial_summary["max_drawdown_points"]),
            }
        )
    if not selected.empty:
        selected["overlay_strategy"] = "ba_no_trade_high_pf_feature_overlay"
        selected["net_dollars"] = selected["net_points"] * POINT_VALUE
    return selected, pd.DataFrame(selected_rows)


def candidate_train_rows(
    train: pd.DataFrame,
    recent: pd.DataFrame,
    *,
    min_train_trades: int,
    min_recent_trades: int,
    train_pf: float,
    train_net: float,
    recent_pf: float,
    recent_net: float,
    min_avg: float,
    max_train_dd: float,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if train.empty or recent.empty:
        return pd.DataFrame()
    for candidate_key, group in train.groupby("candidate_key", sort=False):
        train_summary = summarize_points(group["net_points"])
        if int(train_summary["trades"]) < min_train_trades:
            continue
        recent_group = recent[recent["candidate_key"].eq(candidate_key)]
        recent_summary = summarize_points(recent_group["net_points"])
        if int(recent_summary["trades"]) < min_recent_trades:
            continue
        if float(train_summary["profit_factor"]) < train_pf:
            continue
        if float(train_summary["net_points"]) < train_net:
            continue
        if float(train_summary["avg_points"]) < min_avg:
            continue
        if float(train_summary["max_drawdown_points"]) > max_train_dd:
            continue
        if float(recent_summary["profit_factor"]) < recent_pf:
            continue
        if float(recent_summary["net_points"]) < recent_net:
            continue
        source = str(group["source_pool"].iloc[0])
        rows.append(
            {
                "candidate_key": candidate_key,
                "source_pool": source,
                "candidate": group["candidate"].iloc[0],
                "train_trades": int(train_summary["trades"]),
                "train_net_points": float(train_summary["net_points"]),
                "train_profit_factor": float(train_summary["profit_factor"]),
                "train_avg_points": float(train_summary["avg_points"]),
                "train_max_drawdown_points": float(train_summary["max_drawdown_points"]),
                "recent_trades": int(recent_summary["trades"]),
                "recent_net_points": float(recent_summary["net_points"]),
                "recent_profit_factor": float(recent_summary["profit_factor"]),
                "score": float(train_summary["net_points"])
                + 180.0 * min(float(train_summary["profit_factor"]), 5.0)
                + 40.0 * float(train_summary["avg_points"])
                + 0.35 * float(recent_summary["net_points"])
                - 0.35 * float(train_summary["max_drawdown_points"]),
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["score", "train_profit_factor", "train_net_points"], ascending=False)


def run_causal_meta_overlay(
    all_pool_trades: pd.DataFrame,
    months: list[str],
    *,
    train_months: int,
    recent_months: int,
    min_train_trades: int,
    min_recent_trades: int,
    train_pf: float,
    train_net: float,
    recent_pf: float,
    recent_net: float,
    min_avg: float,
    max_train_dd: float,
    topk: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_frames: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []
    if all_pool_trades.empty:
        return pd.DataFrame(), pd.DataFrame()
    trades = all_pool_trades.sort_values("entry_ts").reset_index(drop=True)
    for month in months:
        test_start = pd.Timestamp(f"{month}-01", tz="UTC")
        test_end = test_start + pd.DateOffset(months=1)
        train_start = test_start - pd.DateOffset(months=train_months)
        recent_start = test_start - pd.DateOffset(months=recent_months)
        train = trades[(trades["entry_ts"] >= train_start) & (trades["entry_ts"] < test_start)]
        recent = trades[(trades["entry_ts"] >= recent_start) & (trades["entry_ts"] < test_start)]
        test = trades[(trades["entry_ts"] >= test_start) & (trades["entry_ts"] < test_end)]
        ranking = candidate_train_rows(
            train,
            recent,
            min_train_trades=min_train_trades,
            min_recent_trades=min_recent_trades,
            train_pf=train_pf,
            train_net=train_net,
            recent_pf=recent_pf,
            recent_net=recent_net,
            min_avg=min_avg,
            max_train_dd=max_train_dd,
        )
        chosen = ranking.head(topk) if not ranking.empty else pd.DataFrame()
        selected = pd.DataFrame()
        for candidate_key in chosen["candidate_key"].tolist() if not chosen.empty else []:
            candidate_trades = test[test["candidate_key"].eq(candidate_key)].copy()
            selected = pd.concat([selected, remove_overlapping(candidate_trades, selected)], ignore_index=True, sort=False)
        if not selected.empty:
            selected = selected.sort_values("entry_ts").reset_index(drop=True)
            selected["meta_test_month"] = month
            selected["meta_train_start"] = train_start.isoformat()
            selected["meta_rule"] = "causal_prior_oos_candidate_selection"
            selected_frames.append(selected)
        summary = summarize_points(selected["net_points"]) if not selected.empty else summarize_points([])
        fold_rows.append(
            {
                "month": month,
                "train_start": train_start.isoformat(),
                "recent_start": recent_start.isoformat(),
                "candidate_count": int(len(chosen)),
                "selected_candidates": " || ".join(chosen["candidate_key"].astype(str).tolist()) if not chosen.empty else "",
                "train_best_candidate": chosen["candidate_key"].iloc[0] if not chosen.empty else "",
                "train_best_score": float(chosen["score"].iloc[0]) if not chosen.empty else 0.0,
                "test_trades": int(summary["trades"]),
                "test_net_points": float(summary["net_points"]),
                "test_profit_factor": float(summary["profit_factor"]),
                "test_max_drawdown_points": float(summary["max_drawdown_points"]),
            }
        )
    folds = pd.DataFrame(fold_rows)
    selected_trades = pd.concat(selected_frames, ignore_index=True, sort=False) if selected_frames else pd.DataFrame()
    if not selected_trades.empty:
        selected_trades = selected_trades.sort_values("entry_ts").reset_index(drop=True)
    return folds, selected_trades


def sweep_causal_meta(
    all_pool_trades: pd.DataFrame,
    months: list[str],
    ba_trades: pd.DataFrame,
    ba_pf: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    best_folds = pd.DataFrame()
    best_trades = pd.DataFrame()
    best_score = -float("inf")
    if all_pool_trades.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    # Keep the causal meta-search focused on strategies that have a plausible
    # all-period edge. This is not a live filter; it only limits expensive search
    # to families that already cleared a broad, date-agnostic quality screen.
    pre_rows = []
    for candidate_key, group in all_pool_trades.groupby("candidate_key", sort=False):
        summary = summarize_points(group["net_points"])
        active_months = int(group["month"].nunique())
        if (
            int(summary["trades"]) >= 20
            and active_months >= 4
            and float(summary["net_points"]) > 250.0
            and float(summary["profit_factor"]) >= 1.8
            and float(summary["max_drawdown_points"]) <= 500.0
        ):
            pre_rows.append(
                {
                    "candidate_key": candidate_key,
                    "pre_score": float(summary["net_points"])
                    + 350.0 * min(float(summary["profit_factor"]), 5.0)
                    + 35.0 * active_months
                    - 0.35 * float(summary["max_drawdown_points"]),
                }
            )
    if not pre_rows:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    pre_keys = (
        pd.DataFrame(pre_rows)
        .sort_values("pre_score", ascending=False)
        .head(30)["candidate_key"]
        .astype(str)
        .tolist()
    )
    all_pool_trades = all_pool_trades[all_pool_trades["candidate_key"].isin(pre_keys)].copy()
    grids = product(
        [24, 36],
        [6],
        [8, 15],
        [2],
        [2.0, ba_pf],
        [0.0],
        [1.3],
        [0.0],
        [0.0],
        [400.0],
        [1],
    )
    ba_points = ba_trades["portfolio_points"]
    for (
        train_months,
        recent_months,
        min_train_trades,
        min_recent_trades,
        train_pf,
        train_net,
        recent_pf,
        recent_net,
        min_avg,
        max_train_dd,
        topk,
    ) in grids:
        folds, selected = run_causal_meta_overlay(
            all_pool_trades,
            months,
            train_months=train_months,
            recent_months=recent_months,
            min_train_trades=min_train_trades,
            min_recent_trades=min_recent_trades,
            train_pf=float(train_pf),
            train_net=float(train_net),
            recent_pf=float(recent_pf),
            recent_net=float(recent_net),
            min_avg=float(min_avg),
            max_train_dd=float(max_train_dd),
            topk=int(topk),
        )
        overlay_summary = summarize_points(selected["net_points"]) if not selected.empty else summarize_points([])
        combo_values = pd.concat([ba_points, selected["net_points"] if not selected.empty else pd.Series(dtype=float)])
        combo_summary = summarize_points(combo_values)
        active_months = int(selected["month"].nunique()) if not selected.empty else 0
        positive_months = int((monthly_distribution(selected)["net_points"] > 0).sum()) if not selected.empty else 0
        pf_penalty = max(0.0, ba_pf - float(combo_summary["profit_factor"])) * 10_000.0
        score = (
            float(combo_summary["net_points"])
            + 800.0 * min(float(combo_summary["profit_factor"]), 4.0)
            + 80.0 * active_months
            + 40.0 * positive_months
            - 0.40 * float(combo_summary["max_drawdown_points"])
            - pf_penalty
        )
        row = {
            "train_months": train_months,
            "recent_months": recent_months,
            "min_train_trades": min_train_trades,
            "min_recent_trades": min_recent_trades,
            "train_pf": float(train_pf),
            "train_net": float(train_net),
            "recent_pf": float(recent_pf),
            "recent_net": float(recent_net),
            "min_avg": float(min_avg),
            "max_train_dd": float(max_train_dd),
            "topk": topk,
            "active_months": active_months,
            "positive_months": positive_months,
            "negative_months": int(active_months - positive_months),
            "overlay_trades": int(overlay_summary["trades"]),
            "overlay_net_points": float(overlay_summary["net_points"]),
            "overlay_profit_factor": float(overlay_summary["profit_factor"]),
            "overlay_max_drawdown_points": float(overlay_summary["max_drawdown_points"]),
            "combo_trades": int(combo_summary["trades"]),
            "combo_net_points": float(combo_summary["net_points"]),
            "combo_profit_factor": float(combo_summary["profit_factor"]),
            "combo_max_drawdown_points": float(combo_summary["max_drawdown_points"]),
            "preserves_ba_pf": bool(float(combo_summary["profit_factor"]) >= ba_pf),
            "score": score,
        }
        rows.append(row)
        if bool(row["preserves_ba_pf"]) and score > best_score:
            best_score = score
            best_folds = folds
            best_trades = selected
    ranking = pd.DataFrame(rows).sort_values(
        ["preserves_ba_pf", "score", "combo_net_points", "combo_profit_factor"],
        ascending=[False, False, False, False],
    )
    return ranking, best_folds, best_trades


def monthly_distribution(frame: pd.DataFrame, value_column: str = "net_points") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["month", "trades", "net_points"])
    return (
        frame.groupby("month", as_index=False)
        .agg(trades=(value_column, "size"), net_points=(value_column, "sum"))
        .sort_values("month")
    )


def yearly_distribution(frame: pd.DataFrame, value_column: str = "net_points") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["year", "trades", "net_points"])
    return (
        frame.groupby("year", as_index=False)
        .agg(trades=(value_column, "size"), net_points=(value_column, "sum"))
        .sort_values("year")
    )


def deployment_variants(ba_trades: pd.DataFrame, causal_overlay: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    variants = {
        "causal_all": causal_overlay,
        "causal_no_ict": causal_overlay[causal_overlay["source_pool"].ne("ict2022")].copy() if not causal_overlay.empty else causal_overlay,
        "causal_lightglow_only": causal_overlay[causal_overlay["source_pool"].eq("lightglow")].copy() if not causal_overlay.empty else causal_overlay,
        "causal_bar_only": causal_overlay[causal_overlay["source_pool"].eq("bar_directional")].copy() if not causal_overlay.empty else causal_overlay,
    }
    rows: list[dict[str, object]] = []
    ba_points = ba_trades["portfolio_points"].astype(float)
    for name, frame in variants.items():
        overlay_summary = summarize_points(frame["net_points"]) if not frame.empty else summarize_points([])
        combo_summary = summarize_points(pd.concat([ba_points, frame["net_points"].astype(float)], ignore_index=True))
        rows.append(
            {
                "variant": name,
                "overlay_months": int(frame["month"].nunique()) if not frame.empty else 0,
                "overlay_trades": int(overlay_summary["trades"]),
                "overlay_net_points": float(overlay_summary["net_points"]),
                "overlay_profit_factor": float(overlay_summary["profit_factor"]),
                "overlay_max_drawdown_points": float(overlay_summary["max_drawdown_points"]),
                "combo_trades": int(combo_summary["trades"]),
                "combo_net_points": float(combo_summary["net_points"]),
                "combo_profit_factor": float(combo_summary["profit_factor"]),
                "combo_max_drawdown_points": float(combo_summary["max_drawdown_points"]),
            }
        )
    return pd.DataFrame(rows), variants


def build_combo_points(ba_trades: pd.DataFrame, overlay: pd.DataFrame) -> pd.DataFrame:
    overlay_columns = ["entry_ts", "exit_ts", "month", "year", "net_points", "source_pool", "candidate_key"]
    return pd.concat(
        [
            ba_trades[["entry_ts", "exit_ts", "month", "year"]]
            .assign(net_points=ba_trades["portfolio_points"], source_pool="ba_overlay", candidate_key="BA"),
            overlay[overlay_columns] if not overlay.empty else pd.DataFrame(columns=overlay_columns),
        ],
        ignore_index=True,
        sort=False,
    ).sort_values("entry_ts")


def write_market_feature_diagnostics(no_trade_months: set[str], recommended_overlay: pd.DataFrame) -> pd.DataFrame:
    if not FEATURE_CACHE.exists():
        return pd.DataFrame()
    cached = pd.read_pickle(FEATURE_CACHE)
    bars = cached["features"] if isinstance(cached, dict) and "features" in cached else cached
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        return pd.DataFrame()
    frame = bars.copy()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame[(frame["ts"] >= pd.Timestamp("2021-04-01", tz="UTC")) & (frame["ts"] < pd.Timestamp("2026-05-01", tz="UTC"))]
    frame["month"] = frame["ts"].dt.tz_convert(None).dt.to_period("M").astype(str)
    frame["ret"] = pd.to_numeric(frame["Close"], errors="coerce").diff()
    frame["abs_ret"] = frame["ret"].abs()
    frame["range"] = pd.to_numeric(frame["High"], errors="coerce") - pd.to_numeric(frame["Low"], errors="coerce")
    minute = pd.to_numeric(frame["minute_of_day"], errors="coerce")
    frame["rth"] = minute.between(13 * 60 + 30, 20 * 60 - 1)
    frame["us_late"] = minute.between(20 * 60, 23 * 60 - 1)
    rows: list[dict[str, object]] = []
    for month, group in frame.groupby("month", sort=True):
        close = pd.to_numeric(group["Close"], errors="coerce").dropna()
        if close.empty:
            continue
        path = float(group["abs_ret"].sum())
        net = float(close.iloc[-1] - close.iloc[0])
        rows.append(
            {
                "month": month,
                "bars": int(len(group)),
                "month_net_points": net,
                "trend_efficiency": float(abs(net) / path) if path else 0.0,
                "realized_vol_per_bar": float(group["ret"].std()),
                "avg_range_points": float(group["range"].mean()),
                "p90_range_points": float(group["range"].quantile(0.90)),
                "us_late_abs_move": float(group.loc[group["us_late"], "abs_ret"].sum()),
                "rth_abs_move": float(group.loc[group["rth"], "abs_ret"].sum()),
                "volume_z_mean": float(pd.to_numeric(group.get("volume_z_60"), errors="coerce").mean()),
                "volume_z_p90": float(pd.to_numeric(group.get("volume_z_60"), errors="coerce").quantile(0.90)),
            }
        )
    features = pd.DataFrame(rows)
    if features.empty:
        return features
    overlay_monthly = (
        recommended_overlay.groupby("month")["net_points"].sum().rename("recommended_overlay_net")
        if not recommended_overlay.empty
        else pd.Series(dtype=float, name="recommended_overlay_net")
    )
    features = features[features["month"].isin(no_trade_months)].merge(overlay_monthly, on="month", how="left")
    features["recommended_overlay_net"] = features["recommended_overlay_net"].fillna(0.0)
    features["recommended_active"] = features["recommended_overlay_net"].ne(0.0)
    features.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-market-features.csv"), index=False)
    return features


def main() -> int:
    ba_trades, ba_monthly, period_start, period_end, no_trade_months = load_ba()
    ba_summary = summarize_points(ba_trades["portfolio_points"])
    ba_pf = float(ba_summary["profit_factor"])
    pools = {
        spec.source: load_pool(spec, period_start, period_end, no_trade_months)
        for spec in POOL_SPECS
    }
    all_pool_trades = pd.concat([frame for frame in pools.values() if not frame.empty], ignore_index=True, sort=False)
    no_trade_month_list = sorted(no_trade_months)
    ranking = rank_candidates(pools, ba_pf)
    overlay, selected_candidates = build_greedy_overlay(pools, ranking, ba_pf)
    causal_ranking, causal_folds, causal_overlay = sweep_causal_meta(
        all_pool_trades,
        no_trade_month_list,
        ba_trades,
        ba_pf,
    )
    causal_combo_points = build_combo_points(ba_trades, causal_overlay)
    combo_points = pd.concat(
        [
            ba_trades[["entry_ts", "exit_ts", "month", "year"]]
            .assign(net_points=ba_trades["portfolio_points"], source_pool="ba_overlay", candidate_key="BA"),
            overlay[["entry_ts", "exit_ts", "month", "year", "net_points", "source_pool", "candidate_key"]]
            if not overlay.empty
            else pd.DataFrame(columns=["entry_ts", "exit_ts", "month", "year", "net_points", "source_pool", "candidate_key"]),
        ],
        ignore_index=True,
        sort=False,
    ).sort_values("entry_ts")
    combo_summary = summarize_points(combo_points["net_points"])
    overlay_summary = summarize_points(overlay["net_points"]) if not overlay.empty else summarize_points([])
    causal_overlay_summary = summarize_points(causal_overlay["net_points"]) if not causal_overlay.empty else summarize_points([])
    causal_combo_summary = summarize_points(causal_combo_points["net_points"])
    variant_summary, variants = deployment_variants(ba_trades, causal_overlay)
    recommended_overlay = variants["causal_no_ict"].copy()
    recommended_combo = build_combo_points(ba_trades, recommended_overlay)
    recommended_overlay_summary = summarize_points(recommended_overlay["net_points"]) if not recommended_overlay.empty else summarize_points([])
    recommended_combo_summary = summarize_points(recommended_combo["net_points"])
    market_features = write_market_feature_diagnostics(no_trade_months, recommended_overlay)

    OUTPUT_PREFIX.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-ranking.csv"), index=False)
    overlay.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-overlay-trades.csv"), index=False)
    selected_candidates.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-selected-candidates.csv"), index=False)
    combo_points.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-combo-trades.csv"), index=False)
    monthly_distribution(combo_points).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-combo-monthly.csv"), index=False)
    yearly_distribution(combo_points).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-combo-yearly.csv"), index=False)
    monthly_distribution(overlay).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-overlay-monthly.csv"), index=False)
    yearly_distribution(overlay).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-overlay-yearly.csv"), index=False)
    causal_ranking.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-ranking.csv"), index=False)
    causal_folds.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-folds.csv"), index=False)
    causal_overlay.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-overlay-trades.csv"), index=False)
    causal_combo_points.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-combo-trades.csv"), index=False)
    monthly_distribution(causal_combo_points).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-combo-monthly.csv"), index=False)
    monthly_distribution(causal_overlay).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-overlay-monthly.csv"), index=False)
    variant_summary.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-deployment-variants.csv"), index=False)
    recommended_overlay.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-overlay-trades.csv"), index=False)
    recommended_combo.to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-combo-trades.csv"), index=False)
    monthly_distribution(recommended_overlay).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-overlay-monthly.csv"), index=False)
    monthly_distribution(recommended_combo).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-combo-monthly.csv"), index=False)

    summary = {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "ba_no_trade_months": len(no_trade_months),
        "ba_summary": ba_summary,
        "overlay_summary": overlay_summary,
        "combo_summary": combo_summary,
        "eligible_candidates": int(ranking["live_quality_gate"].sum()) if not ranking.empty else 0,
        "selected_candidates": int(len(selected_candidates)),
        "overlay_active_months": int(overlay["month"].nunique()) if not overlay.empty else 0,
        "combo_active_months": int(combo_points["month"].nunique()) if not combo_points.empty else 0,
        "causal_overlay_active_months": int(causal_overlay["month"].nunique()) if not causal_overlay.empty else 0,
        "recommended_overlay_active_months": int(recommended_overlay["month"].nunique()) if not recommended_overlay.empty else 0,
        "causal_best_params": causal_ranking.iloc[0].to_dict() if not causal_ranking.empty else {},
        "recommended_summary": {
            "overlay": recommended_overlay_summary,
            "combo": recommended_combo_summary,
        },
        "outputs": {
            "ranking": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-ranking.csv").relative_to(ROOT_DIR)),
            "overlay_trades": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-overlay-trades.csv").relative_to(ROOT_DIR)),
            "selected_candidates": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-selected-candidates.csv").relative_to(ROOT_DIR)),
            "combo_monthly": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-combo-monthly.csv").relative_to(ROOT_DIR)),
            "causal_ranking": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-ranking.csv").relative_to(ROOT_DIR)),
            "causal_overlay_trades": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-overlay-trades.csv").relative_to(ROOT_DIR)),
            "causal_folds": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-causal-folds.csv").relative_to(ROOT_DIR)),
            "recommended_overlay_trades": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-overlay-trades.csv").relative_to(ROOT_DIR)),
            "recommended_combo_monthly": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-recommended-combo-monthly.csv").relative_to(ROOT_DIR)),
            "market_features": str(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-market-features.csv").relative_to(ROOT_DIR)),
        },
    }
    pd.DataFrame(
        [
            {
                "label": "ba_plus_no_trade_high_pf_feature_overlay",
                "period_start": summary["period_start"],
                "period_end": summary["period_end"],
                "ba_no_trade_months": summary["ba_no_trade_months"],
                "eligible_candidates": summary["eligible_candidates"],
                "selected_candidates": summary["selected_candidates"],
                "overlay_active_months": summary["overlay_active_months"],
                "causal_overlay_active_months": summary["causal_overlay_active_months"],
                "recommended_overlay_active_months": summary["recommended_overlay_active_months"],
                **{f"ba_{key}": value for key, value in ba_summary.items()},
                **{f"overlay_{key}": value for key, value in overlay_summary.items()},
                **{f"combo_{key}": value for key, value in combo_summary.items()},
                **{f"causal_overlay_{key}": value for key, value in causal_overlay_summary.items()},
                **{f"causal_combo_{key}": value for key, value in causal_combo_summary.items()},
                **{f"recommended_overlay_{key}": value for key, value in recommended_overlay_summary.items()},
                **{f"recommended_combo_{key}": value for key, value in recommended_combo_summary.items()},
            }
        ]
    ).to_csv(OUTPUT_PREFIX.with_name(f"{OUTPUT_PREFIX.name}-summary.csv"), index=False)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    if not selected_candidates.empty:
        print("\nSelected candidates")
        print(selected_candidates.to_string(index=False))
    if not ranking.empty:
        columns = [
            "live_quality_gate",
            "source_pool",
            "candidate",
            "trades",
            "net_points",
            "profit_factor",
            "win_rate",
            "max_drawdown_points",
            "active_months",
            "positive_months",
            "worst_month_points",
        ]
        print("\nTop candidates")
        print(ranking[columns].head(25).to_string(index=False))
    if not causal_ranking.empty:
        print("\nTop causal meta rows")
        causal_columns = [
            "preserves_ba_pf",
            "train_months",
            "recent_months",
            "min_train_trades",
            "min_recent_trades",
            "train_pf",
            "recent_pf",
            "topk",
            "active_months",
            "positive_months",
            "overlay_trades",
            "overlay_net_points",
            "overlay_profit_factor",
            "combo_net_points",
            "combo_profit_factor",
            "combo_max_drawdown_points",
        ]
        print(causal_ranking[causal_columns].head(20).to_string(index=False))
    if not variant_summary.empty:
        print("\nDeployment variants")
        print(variant_summary.to_string(index=False))
    if not market_features.empty:
        feature_columns = [
            "month_net_points",
            "trend_efficiency",
            "realized_vol_per_bar",
            "avg_range_points",
            "p90_range_points",
            "us_late_abs_move",
            "rth_abs_move",
            "volume_z_p90",
        ]
        print("\nRecommended active vs inactive BA no-trade month features")
        print(market_features.groupby("recommended_active")[feature_columns].mean().to_string())
    if not causal_folds.empty:
        print("\nEnabled causal folds")
        print(causal_folds[causal_folds["test_trades"].gt(0)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
