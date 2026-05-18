from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
POINT_VALUE = 20.0


def summarize(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "net_points": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "avg_points": 0.0,
            "max_drawdown_points": 0.0,
            "worst_trade_points": 0.0,
            "best_trade_points": 0.0,
        }
    net = pd.to_numeric(trades["net_points"], errors="coerce").fillna(0.0)
    equity = net.cumsum()
    drawdown = equity.cummax() - equity
    gross_profit = float(net[net > 0].sum())
    gross_loss = float(-net[net < 0].sum())
    return {
        "trades": int(len(trades)),
        "net_points": float(net.sum()),
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "win_rate": float((net > 0).mean()) if len(net) else 0.0,
        "avg_points": float(net.mean()) if len(net) else 0.0,
        "max_drawdown_points": float(drawdown.max()) if len(drawdown) else 0.0,
        "worst_trade_points": float(net.min()) if len(net) else 0.0,
        "best_trade_points": float(net.max()) if len(net) else 0.0,
    }


def _scale_for_fold(row: pd.Series, params: dict[str, float]) -> float:
    mode = str(row["mode"])
    if mode == "baseline_strong":
        pf = float(row["baseline_recent_profit_factor"])
        net = float(row["baseline_recent_net_points"])
        if pf >= params["baseline_high_pf"] and net >= params["baseline_high_net"]:
            return params["baseline_high_scale"]
        if pf >= params["baseline_mid_pf"] and net >= params["baseline_mid_net"]:
            return params["baseline_mid_scale"]
        return params["baseline_base_scale"]
    if mode == "defensive_filter":
        pf = float(row["selected_recent_profit_factor"])
        net = float(row["selected_recent_net_points"])
        if pf >= params["defensive_high_pf"] and net >= params["defensive_high_net"]:
            return params["defensive_high_scale"]
        return params["defensive_base_scale"]
    return 0.0


def apply_sizing(folds: pd.DataFrame, trades: pd.DataFrame, params: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    sized_folds = folds.copy()
    sized_folds["position_scale"] = sized_folds.apply(lambda row: _scale_for_fold(row, params), axis=1)
    scale_map = dict(zip(sized_folds["test_start"].astype(str), sized_folds["position_scale"].astype(float)))
    sized_trades = trades.copy()
    sized_trades["position_scale"] = sized_trades["adaptive_test_start"].astype(str).map(scale_map).fillna(0.0)
    for column in ("gross_points", "net_points", "net_dollars"):
        if column in sized_trades.columns:
            sized_trades[column] = pd.to_numeric(sized_trades[column], errors="coerce").fillna(0.0) * sized_trades["position_scale"]
    if "net_dollars" not in sized_trades.columns:
        sized_trades["net_dollars"] = sized_trades["net_points"] * POINT_VALUE
    return sized_folds, sized_trades


def score_summary(row: dict[str, float | int], min_net: float, max_dd: float) -> float:
    net = float(row["net_points"])
    pf = float(row["profit_factor"])
    dd = float(row["max_drawdown_points"])
    avg = float(row["avg_points"])
    if net < min_net or dd > max_dd:
        return -1e9 + net - dd
    return net + 850.0 * min(pf, 3.0) + 60.0 * avg - 1.15 * dd


def sweep(folds: pd.DataFrame, trades: pd.DataFrame, min_net: float, max_dd: float) -> pd.DataFrame:
    baseline_high_pf_grid = [1.35, 1.50, 1.75]
    baseline_high_scale_grid = [1.50, 1.75, 2.00]
    baseline_mid_pf_grid = [1.20, 1.30]
    baseline_mid_scale_grid = [1.10, 1.25, 1.40]
    defensive_high_pf_grid = [1.35, 1.50, 1.75]
    defensive_high_scale_grid = [1.00, 1.10, 1.25]
    defensive_base_scale_grid = [0.75, 0.90, 1.00]

    rows: list[dict[str, float | int | str]] = []
    for values in product(
        baseline_high_pf_grid,
        baseline_high_scale_grid,
        baseline_mid_pf_grid,
        baseline_mid_scale_grid,
        defensive_high_pf_grid,
        defensive_high_scale_grid,
        defensive_base_scale_grid,
    ):
        (
            baseline_high_pf,
            baseline_high_scale,
            baseline_mid_pf,
            baseline_mid_scale,
            defensive_high_pf,
            defensive_high_scale,
            defensive_base_scale,
        ) = values
        if baseline_high_pf < baseline_mid_pf:
            continue
        params = {
            "baseline_high_pf": baseline_high_pf,
            "baseline_high_net": 1000.0,
            "baseline_high_scale": baseline_high_scale,
            "baseline_mid_pf": baseline_mid_pf,
            "baseline_mid_net": 0.0,
            "baseline_mid_scale": baseline_mid_scale,
            "baseline_base_scale": 1.0,
            "defensive_high_pf": defensive_high_pf,
            "defensive_high_net": 300.0,
            "defensive_high_scale": defensive_high_scale,
            "defensive_base_scale": defensive_base_scale,
        }
        sized_folds, sized_trades = apply_sizing(folds, trades, params)
        summary = summarize(sized_trades)
        row: dict[str, float | int | str] = {
            **params,
            **summary,
            "avg_scale": float(sized_folds["position_scale"].mean()),
            "max_scale": float(sized_folds["position_scale"].max()),
        }
        row["score"] = score_summary(summary, min_net=min_net, max_dd=max_dd)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["score", "net_points", "profit_factor"], ascending=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Optimize causal fold-level position sizing for adaptive composite trades.")
    parser.add_argument("--prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-24x1-pf102-net0")
    parser.add_argument("--output-prefix", default="reports/NQ-pine-sum_pos-open2-adaptive-composite-position-sized-24x1")
    parser.add_argument("--min-net", type=float, default=9500.0)
    parser.add_argument("--max-dd", type=float, default=900.0)
    args = parser.parse_args()

    prefix = ROOT_DIR / args.prefix
    folds = pd.read_csv(prefix.with_name(f"{prefix.name}-folds.csv"))
    trades = pd.read_csv(prefix.with_name(f"{prefix.name}-trades.csv"))
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)

    ranking = sweep(folds, trades, min_net=args.min_net, max_dd=args.max_dd)
    out_prefix = ROOT_DIR / args.output_prefix
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(out_prefix.with_name(f"{out_prefix.name}-ranking.csv"), index=False)

    best = ranking.iloc[0].to_dict()
    param_keys = [
        "baseline_high_pf",
        "baseline_high_net",
        "baseline_high_scale",
        "baseline_mid_pf",
        "baseline_mid_net",
        "baseline_mid_scale",
        "baseline_base_scale",
        "defensive_high_pf",
        "defensive_high_net",
        "defensive_high_scale",
        "defensive_base_scale",
    ]
    best_params = {key: float(best[key]) for key in param_keys}
    sized_folds, sized_trades = apply_sizing(folds, trades, best_params)
    sized_folds.to_csv(out_prefix.with_name(f"{out_prefix.name}-folds.csv"), index=False)
    sized_trades.to_csv(out_prefix.with_name(f"{out_prefix.name}-trades.csv"), index=False)
    summary = pd.DataFrame([{key: best[key] for key in best.keys() if key != "score"}])
    summary.to_csv(out_prefix.with_name(f"{out_prefix.name}-summary.csv"), index=False)
    print(summary.to_string(index=False))
    print(f"ranking={out_prefix.with_name(f'{out_prefix.name}-ranking.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
