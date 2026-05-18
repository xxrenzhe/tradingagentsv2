from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

from walk_forward_nq_sum_pos_meta_feature_filters import (  # noqa: E402
    MaskCandidate,
    build_candidates,
    fast_summarize_points,
    slice_summary,
)
from optimize_nq_sum_pos_market_feature_filters import summarize  # noqa: E402


def _summary_for_mask(net_points: np.ndarray, mask: np.ndarray) -> dict[str, float | int]:
    return fast_summarize_points(net_points[mask]).as_dict()


def _passes(summary: dict[str, float | int], min_trades: int, min_pf: float, min_net: float, min_avg: float) -> bool:
    return (
        int(summary["trades"]) >= min_trades
        and float(summary["profit_factor"]) >= min_pf
        and float(summary["net_points"]) >= min_net
        and float(summary["avg_points"]) >= min_avg
    )


def _score(summary: dict[str, float | int], dd_penalty: float) -> float:
    pf = min(float(summary["profit_factor"]), 3.0)
    return (
        float(summary["net_points"])
        + 140.0 * pf
        + 18.0 * float(summary["avg_points"])
        - dd_penalty * float(summary["max_drawdown_points"])
        + 0.025 * int(summary["trades"])
    )


def _half_positive_rate(net_points: np.ndarray, candidate_mask: np.ndarray, fit_mask: np.ndarray, entry_ts: pd.Series) -> float:
    fit_idx = np.flatnonzero(fit_mask)
    if len(fit_idx) < 2:
        return 0.0
    fit_times = entry_ts.iloc[fit_idx]
    midpoint = fit_times.min() + (fit_times.max() - fit_times.min()) / 2
    first = fit_mask & (entry_ts < midpoint).to_numpy() & candidate_mask
    second = fit_mask & (entry_ts >= midpoint).to_numpy() & candidate_mask
    nets = [float(net_points[first].sum()), float(net_points[second].sum())]
    return float(np.mean([value > 0 for value in nets]))


def select_ensemble(
    trades: pd.DataFrame,
    candidates: list[MaskCandidate],
    net_points: np.ndarray,
    fit_mask: np.ndarray,
    recent_mask: np.ndarray,
    min_fit_trades: int,
    min_recent_trades: int,
    min_fit_delta: float,
    min_fit_pf: float,
    enable_pf: float,
    enable_net: float,
    enable_avg: float,
    max_candidates: int,
    top_k: int,
    quorum: int,
    dd_penalty: float,
) -> tuple[np.ndarray, list[dict[str, object]], dict[str, float | int]]:
    baseline_fit = _summary_for_mask(net_points, fit_mask & candidates[0].mask)
    eligible: list[dict[str, object]] = []
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)

    for candidate in candidates:
        fit_selected = fit_mask & candidate.mask
        recent_selected = recent_mask & candidate.mask
        fit_summary = _summary_for_mask(net_points, fit_selected)
        if int(fit_summary["trades"]) < min_fit_trades:
            continue
        if candidate.name != "baseline_no_filter":
            removed = int(np.count_nonzero(fit_mask & ~candidate.mask))
            if removed < 20:
                continue
            if float(fit_summary["net_points"]) < float(baseline_fit["net_points"]) + min_fit_delta:
                continue
        if float(fit_summary["profit_factor"]) < min_fit_pf:
            continue

        recent_summary = _summary_for_mask(net_points, recent_selected)
        if not _passes(recent_summary, min_recent_trades, enable_pf, enable_net, enable_avg):
            continue
        stability = _half_positive_rate(net_points, candidate.mask, fit_mask, entry_ts)
        eligible.append(
            {
                "candidate": candidate,
                "name": candidate.name,
                "fit_summary": fit_summary,
                "recent_summary": recent_summary,
                "fit_positive_half_rate": stability,
                "score": _score(recent_summary, dd_penalty) + 50.0 * stability + 0.05 * float(fit_summary["net_points"]),
            }
        )

    eligible.sort(key=lambda item: float(item["score"]), reverse=True)
    selected = eligible[: max(1, min(top_k, max_candidates, len(eligible)))]
    if not selected:
        return np.zeros(len(trades), dtype=bool), [], baseline_fit

    votes = np.zeros(len(trades), dtype=np.int16)
    for item in selected:
        votes += item["candidate"].mask.astype(np.int16)
    selected_mask = votes >= max(1, min(quorum, len(selected)))
    return selected_mask, selected, baseline_fit


def run_adaptive_ensemble(
    trades: pd.DataFrame,
    candidates: list[MaskCandidate],
    train_months: int,
    test_months: int,
    start_date: str,
    recent_months: int,
    min_fit_frac: float,
    min_fit_delta: float,
    min_fit_pf: float,
    min_recent_trades: int,
    enable_pf: float,
    enable_net: float,
    enable_avg: float,
    baseline_strong_pf: float,
    baseline_strong_net: float,
    top_k: int,
    quorum: int,
    max_candidates: int,
    dd_penalty: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True)
    net_points = trades["net_points"].to_numpy(dtype=float)
    start = pd.Timestamp(start_date, tz="UTC")
    end = entry_ts.max()
    baseline = candidates[0]
    fold_rows: list[dict[str, object]] = []
    trade_frames: list[pd.DataFrame] = []

    test_start = start
    while test_start <= end:
        train_start = test_start - pd.DateOffset(months=train_months)
        recent_start = test_start - pd.DateOffset(months=recent_months)
        test_end = test_start + pd.DateOffset(months=test_months)
        fit_mask = ((entry_ts >= train_start) & (entry_ts < recent_start)).to_numpy()
        recent_mask = ((entry_ts >= recent_start) & (entry_ts < test_start)).to_numpy()
        test_mask = ((entry_ts >= test_start) & (entry_ts < test_end)).to_numpy()
        fit_count = int(np.count_nonzero(fit_mask))
        recent_count = int(np.count_nonzero(recent_mask))
        test_count = int(np.count_nonzero(test_mask))
        if fit_count < 200 or recent_count < min_recent_trades or test_count == 0:
            test_start = test_end
            continue

        min_fit_trades = max(120, int(fit_count * min_fit_frac))
        baseline_recent = _summary_for_mask(net_points, recent_mask & baseline.mask)
        base_test_summary = slice_summary(trades, test_mask)
        if _passes(
            baseline_recent,
            min_trades=min_recent_trades,
            min_pf=baseline_strong_pf,
            min_net=baseline_strong_net,
            min_avg=-float("inf"),
        ):
            selected_mask = baseline.mask.copy()
            selected_items: list[dict[str, object]] = []
            mode = "baseline_strong"
            enabled = True
            fit_baseline = _summary_for_mask(net_points, fit_mask & baseline.mask)
            selected_recent = baseline_recent
        else:
            selected_mask, selected_items, fit_baseline = select_ensemble(
                trades=trades,
                candidates=candidates,
                net_points=net_points,
                fit_mask=fit_mask,
                recent_mask=recent_mask,
                min_fit_trades=min_fit_trades,
                min_recent_trades=min_recent_trades,
                min_fit_delta=min_fit_delta,
                min_fit_pf=min_fit_pf,
                enable_pf=enable_pf,
                enable_net=enable_net,
                enable_avg=enable_avg,
                max_candidates=max_candidates,
                top_k=top_k,
                quorum=quorum,
                dd_penalty=dd_penalty,
            )
            enabled = bool(selected_items)
            mode = "ensemble_filter" if enabled else "no_trade"
            if enabled:
                selected_recent = _summary_for_mask(net_points, recent_mask & selected_mask)
            else:
                selected_recent = {"trades": 0, "net_points": 0.0, "profit_factor": 0.0, "avg_points": 0.0}

        selected_test_mask = test_mask & selected_mask
        selected_test_summary = slice_summary(trades, selected_test_mask)
        selected_names = [str(item["name"]) for item in selected_items]
        fold_rows.append(
            {
                "test_start": test_start.date().isoformat(),
                "test_end": test_end.date().isoformat(),
                "train_start": train_start.date().isoformat(),
                "recent_start": recent_start.date().isoformat(),
                "mode": mode,
                "enabled": bool(enabled),
                "selected_count": len(selected_names),
                "selected_candidates": " | ".join(selected_names[:10]) if selected_names else ("baseline_no_filter" if mode == "baseline_strong" else "NO_TRADE"),
                "top_candidate": selected_names[0] if selected_names else ("baseline_no_filter" if mode == "baseline_strong" else "NO_TRADE"),
                "fit_baseline_trades": int(fit_baseline["trades"]),
                "fit_baseline_net_points": float(fit_baseline["net_points"]),
                "fit_baseline_profit_factor": float(fit_baseline["profit_factor"]),
                "baseline_recent_trades": int(baseline_recent["trades"]),
                "baseline_recent_net_points": float(baseline_recent["net_points"]),
                "baseline_recent_profit_factor": float(baseline_recent["profit_factor"]),
                "selected_recent_trades": int(selected_recent["trades"]),
                "selected_recent_net_points": float(selected_recent["net_points"]),
                "selected_recent_profit_factor": float(selected_recent["profit_factor"]),
                "base_test_trades": int(base_test_summary["trades"]),
                "base_test_net_points": float(base_test_summary["net_points"]),
                "base_test_profit_factor": float(base_test_summary["profit_factor"]),
                "test_trades": int(selected_test_summary["trades"]),
                "test_net_points": float(selected_test_summary["net_points"]),
                "test_profit_factor": float(selected_test_summary["profit_factor"]),
                "test_max_drawdown_points": float(selected_test_summary["max_drawdown_points"]),
                "test_delta_net_points": float(selected_test_summary["net_points"] - base_test_summary["net_points"]),
            }
        )

        selected = trades.loc[selected_test_mask].copy()
        if not selected.empty:
            selected["adaptive_mode"] = mode
            selected["adaptive_candidate"] = fold_rows[-1]["top_candidate"]
            selected["adaptive_selected_candidates"] = fold_rows[-1]["selected_candidates"]
            selected["adaptive_test_start"] = test_start.date().isoformat()
            trade_frames.append(selected)
        test_start = test_end

    folds = pd.DataFrame(fold_rows)
    selected_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    return folds, selected_trades


def summary_row(label: str, trades: pd.DataFrame, folds: pd.DataFrame) -> dict[str, object]:
    row = {"label": label, **summarize(trades)} if not trades.empty else {
        "label": label,
        "trades": 0,
        "net_points": 0.0,
        "profit_factor": 0.0,
        "win_rate": 0.0,
        "avg_points": 0.0,
        "max_drawdown_points": 0.0,
        "worst_trade_points": 0.0,
        "best_trade_points": 0.0,
    }
    row["folds"] = int(len(folds))
    row["enabled_folds"] = int(folds["enabled"].sum()) if not folds.empty else 0
    row["positive_folds"] = int((folds["test_net_points"] > 0).sum()) if not folds.empty else 0
    row["base_test_net_points"] = float(folds["base_test_net_points"].sum()) if not folds.empty else 0.0
    row["test_delta_net_points"] = float(folds["test_delta_net_points"].sum()) if not folds.empty else 0.0
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Causal train/validation/test adaptive ensemble selector for sum_pos fixed-meta trades.")
    parser.add_argument("--trades", default="reports/NQ-pine-sum_pos-open2-fixed-meta-oos-fixed_meta-trades.csv")
    parser.add_argument("--output-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-ensemble")
    parser.add_argument("--train-months", type=int, default=24)
    parser.add_argument("--test-months", type=int, default=1)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--recent-months", type=int, default=6)
    parser.add_argument("--min-fit-frac", type=float, default=0.16)
    parser.add_argument("--min-fit-delta", type=float, default=50.0)
    parser.add_argument("--min-fit-pf", type=float, default=0.95)
    parser.add_argument("--min-recent-trades", type=int, default=30)
    parser.add_argument("--enable-pf", type=float, default=1.02)
    parser.add_argument("--enable-net", type=float, default=0.0)
    parser.add_argument("--enable-avg", type=float, default=-999.0)
    parser.add_argument("--baseline-strong-pf", type=float, default=1.20)
    parser.add_argument("--baseline-strong-net", type=float, default=0.0)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--quorum", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--dd-penalty", type=float, default=0.20)
    parser.add_argument("--min-segment-trades", type=int, default=300)
    parser.add_argument("--min-removed-in-segment", type=int, default=80)
    args = parser.parse_args()

    trades = pd.read_csv(ROOT_DIR / args.trades)
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    candidates = build_candidates(trades, args.min_segment_trades, args.min_removed_in_segment)
    folds, selected = run_adaptive_ensemble(
        trades=trades,
        candidates=candidates,
        train_months=args.train_months,
        test_months=args.test_months,
        start_date=args.start_date,
        recent_months=args.recent_months,
        min_fit_frac=args.min_fit_frac,
        min_fit_delta=args.min_fit_delta,
        min_fit_pf=args.min_fit_pf,
        min_recent_trades=args.min_recent_trades,
        enable_pf=args.enable_pf,
        enable_net=args.enable_net,
        enable_avg=args.enable_avg,
        baseline_strong_pf=args.baseline_strong_pf,
        baseline_strong_net=args.baseline_strong_net,
        top_k=args.top_k,
        quorum=args.quorum,
        max_candidates=args.max_candidates,
        dd_penalty=args.dd_penalty,
    )
    prefix = ROOT_DIR / args.output_prefix
    prefix.parent.mkdir(parents=True, exist_ok=True)
    folds.to_csv(prefix.with_name(f"{prefix.name}-folds.csv"), index=False)
    selected.to_csv(prefix.with_name(f"{prefix.name}-trades.csv"), index=False)
    summary = pd.DataFrame([summary_row("adaptive_ensemble", selected, folds)])
    summary.to_csv(prefix.with_name(f"{prefix.name}-summary.csv"), index=False)
    print(f"candidates={len(candidates)}")
    print(summary.to_string(index=False))
    print(folds.to_string(index=False))


if __name__ == "__main__":
    main()
