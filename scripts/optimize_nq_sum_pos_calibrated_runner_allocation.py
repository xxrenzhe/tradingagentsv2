from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_market_feature_filters import summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
ROUND_TRIP_COST_POINTS = 1.5
POINT_VALUE = 20.0


def _to_utc(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True).astype("datetime64[ns, UTC]")


def _month_labels(series: pd.Series) -> pd.Series:
    return _to_utc(series).dt.tz_convert(None).dt.to_period("M").astype(str)


def _eligible_scaleout_rows(scaleout_trades: pd.DataFrame) -> pd.DataFrame:
    if "exit_reason" not in scaleout_trades.columns:
        raise ValueError("scaleout trades must include exit_reason")
    eligible = scaleout_trades.loc[scaleout_trades["exit_reason"].astype(str).str.startswith("scaleout")].copy()
    if eligible.empty:
        raise ValueError("no scaleout rows found")
    return eligible


def infer_runner_legs(base_trades: pd.DataFrame, scaleout_trades: pd.DataFrame) -> pd.DataFrame:
    eligible = _eligible_scaleout_rows(scaleout_trades)
    cols = ["trade_id", "gross_points", "net_points", "exit_ts", "exit_price", "exit_reason", "bars_held"]
    merged = base_trades.merge(eligible.loc[:, cols], on="trade_id", how="inner", suffixes=("_base", "_scaleout"))
    if merged.empty:
        raise ValueError("base trades and scaleout trades have no matching eligible trade_id rows")
    direction = merged["direction"].astype(int)
    target_gross = (merged["target"].astype(float) - merged["entry_price"].astype(float)) * direction
    # Current report is a 50/50 blend. Back out the runner leg so allocation can be tested apples-to-apples.
    runner_gross = 2.0 * merged["gross_points_scaleout"].astype(float) - target_gross
    return pd.DataFrame(
        {
            "trade_id": merged["trade_id"].astype(str),
            "target_gross": target_gross.astype(float),
            "runner_gross": runner_gross.astype(float),
            "scaleout_exit_ts": merged["exit_ts_scaleout"],
            "scaleout_exit_price": merged["exit_price_scaleout"].astype(float),
            "scaleout_bars_held": merged["bars_held_scaleout"].astype(int),
        }
    )


def apply_allocation(base_trades: pd.DataFrame, runner_legs: pd.DataFrame, target_fraction: float) -> pd.DataFrame:
    output = base_trades.copy()
    output["calibrated_runner_rule"] = "original"
    output["target_fraction"] = np.nan
    legs = runner_legs.set_index("trade_id")
    ids = set(legs.index.astype(str))
    mask = output["trade_id"].astype(str).isin(ids)
    if not mask.any():
        return output

    selected = output.loc[mask].copy()
    selected_ids = selected["trade_id"].astype(str)
    leg_rows = legs.loc[selected_ids].reset_index(drop=True)
    direction = selected["direction"].astype(int).reset_index(drop=True)
    entry_price = selected["entry_price"].astype(float).reset_index(drop=True)
    target_gross = leg_rows["target_gross"].astype(float)
    runner_gross = leg_rows["runner_gross"].astype(float)
    gross = target_fraction * target_gross + (1.0 - target_fraction) * runner_gross
    net = gross - ROUND_TRIP_COST_POINTS

    output.loc[mask, "gross_points"] = gross.to_numpy()
    output.loc[mask, "net_points"] = net.to_numpy()
    output.loc[mask, "net_dollars"] = (net * POINT_VALUE).to_numpy()
    output.loc[mask, "exit_ts"] = leg_rows["scaleout_exit_ts"].to_numpy()
    output.loc[mask, "exit_price"] = (entry_price + gross * direction).to_numpy()
    output.loc[mask, "bars_held"] = leg_rows["scaleout_bars_held"].to_numpy()
    output.loc[mask, "exit_reason"] = f"calibrated_old_scaleout_f{target_fraction:g}_runner"
    output.loc[mask, "calibrated_runner_rule"] = "old_scaleout_eligible"
    output.loc[mask, "target_fraction"] = float(target_fraction)
    return output.sort_values("entry_ts").reset_index(drop=True)


def _monthly_net(trades: pd.DataFrame) -> dict[str, float]:
    months = _month_labels(trades["entry_ts"])
    return trades.assign(month=months).groupby("month")["net_points"].sum().to_dict()


def _cost_stress_rows(name: str, trades: pd.DataFrame) -> list[dict[str, float | int | str]]:
    rows = []
    for extra_cost in [0.0, 0.5, 1.0, 2.0, 3.0]:
        stressed = trades.copy()
        stressed["net_points"] = stressed["net_points"].astype(float) - extra_cost
        row = {"name": name if extra_cost == 0 else f"{name}_cost+{extra_cost:g}", **summarize(stressed)}
        rows.append(row)
    return rows


def _monte_carlo_drawdown(net_points: pd.Series, *, iterations: int = 1000, seed: int = 42) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    values = net_points.astype(float).to_numpy()
    dds: list[float] = []
    for _ in range(iterations):
        sample = rng.permutation(values)
        equity = np.cumsum(sample)
        dds.append(float((np.maximum.accumulate(equity) - equity).max()) if len(equity) else 0.0)
    return {f"mc_dd_p{q}": float(np.percentile(dds, q)) for q in (50, 90, 95, 99)}


def _summary_with_mc(name: str, trades: pd.DataFrame) -> dict[str, float | int | str]:
    row = {"name": name, **summarize(trades)}
    row.update(_monte_carlo_drawdown(trades["net_points"]))
    return row


def evaluate_allocations(
    base_trades: pd.DataFrame,
    runner_legs: pd.DataFrame,
    fractions: list[float],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    baseline = summarize(base_trades)
    rows: list[dict[str, object]] = []
    outputs: dict[str, pd.DataFrame] = {}
    for fraction in fractions:
        name = f"calibrated_old_scaleout_target_f{fraction:g}_runner_f{1.0 - fraction:g}"
        result = apply_allocation(base_trades, runner_legs, fraction)
        summary = summarize(result)
        monthly = _monthly_net(result)
        changed = int(result["calibrated_runner_rule"].astype(str).eq("old_scaleout_eligible").sum())
        rows.append(
            {
                "rule": name,
                "target_fraction": fraction,
                "runner_fraction": 1.0 - fraction,
                **summary,
                "changed_trades": changed,
                "positive_months": int(sum(value > 0 for value in monthly.values())),
                "worst_month_points": float(min(monthly.values())) if monthly else 0.0,
                "net_delta_vs_early_exit": float(summary["net_points"] - baseline["net_points"]),
                "pf_delta_vs_early_exit": float(summary["profit_factor"] - baseline["profit_factor"]),
                "dd_delta_vs_early_exit": float(summary["max_drawdown_points"] - baseline["max_drawdown_points"]),
            }
        )
        outputs[name] = result
    return pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False), outputs


def walk_forward_allocations(ranking: pd.DataFrame, outputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    all_months = sorted(
        {
            month
            for trades in outputs.values()
            for month in _month_labels(trades["entry_ts"]).unique().tolist()
        }
    )
    rows: list[dict[str, object]] = []
    for idx in range(3, len(all_months)):
        train_months = set(all_months[:idx])
        test_month = all_months[idx]
        train_rows = []
        for _, rank_row in ranking.iterrows():
            rule = str(rank_row["rule"])
            trades = outputs[rule]
            months = _month_labels(trades["entry_ts"])
            train = trades.loc[months.isin(train_months)].copy()
            if len(train) < 120:
                continue
            summary = summarize(train)
            monthly = train.assign(month=months[months.isin(train_months)].to_numpy()).groupby("month")["net_points"].sum()
            train_rows.append(
                {
                    "rule": rule,
                    "target_fraction": float(rank_row["target_fraction"]),
                    "runner_fraction": float(rank_row["runner_fraction"]),
                    "train_net": summary["net_points"],
                    "train_pf": summary["profit_factor"],
                    "train_dd": summary["max_drawdown_points"],
                    "train_worst_month": float(monthly.min()) if len(monthly) else 0.0,
                }
            )
        if not train_rows:
            continue
        train_rank = pd.DataFrame(train_rows)
        # User priority: high return first, then stability/risk. Keep a light DD/worst-month penalty.
        train_rank["score"] = (
            train_rank["train_net"]
            + 100.0 * train_rank["train_pf"]
            - 0.25 * train_rank["train_dd"]
            + 0.10 * train_rank["train_worst_month"]
        )
        selected = train_rank.sort_values(["score", "train_net"], ascending=False).iloc[0]
        trades = outputs[str(selected["rule"])]
        months = _month_labels(trades["entry_ts"])
        test = trades.loc[months.eq(test_month)].copy()
        test_summary = summarize(test)
        rows.append(
            {
                "test_month": test_month,
                "selected_rule": str(selected["rule"]),
                "target_fraction": float(selected["target_fraction"]),
                "runner_fraction": float(selected["runner_fraction"]),
                "train_net": float(selected["train_net"]),
                "train_pf": float(selected["train_pf"]),
                "train_dd": float(selected["train_dd"]),
                "trades": test_summary["trades"],
                "test_net": test_summary["net_points"],
                "test_pf": test_summary["profit_factor"],
                "test_dd": test_summary["max_drawdown_points"],
                "test_worst": test_summary["worst_trade_points"],
            }
        )
    return pd.DataFrame(rows)


def report_row(strategy: str, trades: pd.DataFrame, notes: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "strategy": strategy,
                "families": "sum_pos_open2 third-pass early-exit plus calibrated old scaleout runner allocation",
                "macd_filter": "mixed / source components",
                "macd_timeframe": 1,
                "stop_atr_buffer": "mixed",
                "target_r": "mixed",
                "max_hold_bars": "mixed",
                **summarize(trades),
                "notes": notes,
            }
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize allocation using the already-reported old scaleout runner exits.")
    parser.add_argument("--base-trades", default="reports/NQ-pine-12m-sum_pos-open2-early-exit-small-best-trades.csv")
    parser.add_argument("--scaleout-trades", default="reports/NQ-pine-12m-sum_pos-open2-scaleout-runner-best-trades.csv")
    parser.add_argument("--ranking-output", default="reports/NQ-pine-12m-sum_pos-open2-calibrated-runner-allocation-ranking.csv")
    parser.add_argument("--best-output", default="reports/NQ-pine-12m-sum_pos-open2-calibrated-runner-allocation-best-trades.csv")
    parser.add_argument("--best-ranking-row", default="reports/NQ-pine-12m-sum_pos-open2-calibrated-runner-allocation-ranking-row.csv")
    parser.add_argument("--robustness-output", default="reports/NQ-pine-12m-sum_pos-open2-calibrated-runner-allocation-robustness.csv")
    parser.add_argument("--walk-forward-output", default="reports/NQ-pine-12m-sum_pos-open2-calibrated-runner-allocation-walkforward.csv")
    parser.add_argument("--fractions", nargs="*", type=float, default=[0.0, 0.15, 0.25, 0.35, 0.5, 0.65, 0.75, 1.0])
    args = parser.parse_args()

    base = pd.read_csv(ROOT_DIR / args.base_trades)
    scaleout = pd.read_csv(ROOT_DIR / args.scaleout_trades)
    for frame in [base, scaleout]:
        frame["entry_ts"] = _to_utc(frame["entry_ts"])
        frame["exit_ts"] = _to_utc(frame["exit_ts"])
    runner_legs = infer_runner_legs(base, scaleout)
    ranking, outputs = evaluate_allocations(base, runner_legs, args.fractions)
    best_rule = str(ranking.iloc[0]["rule"])
    best = outputs[best_rule]

    ranking_path = ROOT_DIR / args.ranking_output
    best_path = ROOT_DIR / args.best_output
    row_path = ROOT_DIR / args.best_ranking_row
    robustness_path = ROOT_DIR / args.robustness_output
    wf_path = ROOT_DIR / args.walk_forward_output
    ranking.to_csv(ranking_path, index=False)
    best.to_csv(best_path, index=False)
    report_row(
        "sum_pos_open2_calibrated_runner_allocation_best",
        best,
        (
            f"No month/date filter. Best calibrated allocation: {best_rule}. "
            "Uses only the exact trades and runner exits already present in the prior scaleout report, "
            "then changes only the target-vs-runner allocation."
        ),
    ).to_csv(row_path, index=False)

    robustness_rows = [
        _summary_with_mc("current_scaleout_runner", scaleout),
        _summary_with_mc("calibrated_runner_allocation_best", best),
    ]
    current = scaleout.copy()
    robustness_rows.extend(_cost_stress_rows("current_scaleout_runner", current)[1:])
    robustness_rows.extend(_cost_stress_rows("calibrated_runner_allocation_best", best)[1:])
    pd.DataFrame(robustness_rows).to_csv(robustness_path, index=False)
    wf = walk_forward_allocations(ranking, outputs)
    wf.to_csv(wf_path, index=False)

    print(f"best_rule {best_rule}")
    print(f"wrote {ranking_path}")
    print(f"wrote {best_path}")
    print(f"wrote {row_path}")
    print(f"wrote {robustness_path}")
    print(f"wrote {wf_path}")
    print(ranking.to_string(index=False))
    if not wf.empty:
        print("\nwalk_forward")
        print(wf.to_string(index=False))
        print("\nwalk_forward_total")
        print(summarize(pd.DataFrame({"net_points": wf["test_net"].astype(float)})))


if __name__ == "__main__":
    main()
