from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from optimize_nq_sum_pos_calibrated_runner_allocation import (
    _cost_stress_rows,
    _month_labels,
    _summary_with_mc,
    _to_utc,
    apply_allocation,
    infer_runner_legs,
    report_row,
)
from optimize_nq_sum_pos_market_feature_filters import summarize


ROOT_DIR = Path(__file__).resolve().parents[1]
ROUND_TRIP_COST_POINTS = 1.5
POINT_VALUE = 20.0


@dataclass(frozen=True)
class MetaRule:
    name: str
    mask_fn: Callable[[pd.DataFrame], pd.Series]
    target_fraction: float = 1.0


def build_eligible_frame(base: pd.DataFrame, runner_legs: pd.DataFrame) -> pd.DataFrame:
    eligible = base.merge(runner_legs, on="trade_id", how="inner")
    eligible["runner_advantage"] = eligible["runner_gross"].astype(float) - eligible["target_gross"].astype(float)
    eligible["target_net"] = eligible["target_gross"].astype(float) - ROUND_TRIP_COST_POINTS
    eligible["runner_net"] = eligible["runner_gross"].astype(float) - ROUND_TRIP_COST_POINTS
    return eligible


def _safe_col(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")


def build_meta_rules() -> list[MetaRule]:
    rules: list[MetaRule] = [
        MetaRule("baseline_all_runner", lambda df: pd.Series(False, index=df.index), target_fraction=1.0),
        MetaRule("all_shorts_to_target", lambda df: df["direction"].astype(int).lt(0), target_fraction=1.0),
        MetaRule("asia_to_target", lambda df: df["session"].astype(str).eq("asia"), target_fraction=1.0),
        MetaRule(
            "transition_short_asia_to_target",
            lambda df: df["signal_family"].astype(str).eq("trend_transition_short_asia"),
            target_fraction=1.0,
        ),
        MetaRule(
            "trend_pullback_long_to_target",
            lambda df: df["signal_family"].astype(str).eq("trend_pullback_long"),
            target_fraction=1.0,
        ),
        MetaRule(
            "pullback_extension_to_target",
            lambda df: df["target_plan"].astype(str).eq("trend_pullback_extension"),
            target_fraction=1.0,
        ),
        MetaRule(
            "short_asia_or_pullback_long_to_target",
            lambda df: df["signal_family"].astype(str).isin(["trend_transition_short_asia", "trend_pullback_long"]),
            target_fraction=1.0,
        ),
        MetaRule(
            "weak_runner_family_set_to_target",
            lambda df: df["signal_family"].astype(str).isin(
                [
                    "trend_transition_short_asia",
                    "trend_pullback_long",
                    "trend_pullback_short_asia_europe",
                    "smc_ob_retest_long",
                ]
            ),
            target_fraction=1.0,
        ),
    ]

    for column, thresholds in {
        "directional_range_pos_60": [0.75, 0.85, 0.9, 0.95],
        "directional_range_pos_120": [0.75, 0.85, 0.9, 0.95],
        "dir_mom_15": [1.0, 1.5, 2.0, 2.5],
        "dir_mom_30": [1.0, 1.5, 2.0, 2.5, 3.0],
        "dir_ema20_dist": [1.0, 1.5, 2.0],
        "atr14_rank_240": [0.75, 0.85, 0.95],
    }.items():
        for threshold in thresholds:
            rules.append(
                MetaRule(
                    f"{column}_gte_{threshold:g}_to_target",
                    lambda df, c=column, t=threshold: _safe_col(df, c).ge(t),
                    target_fraction=1.0,
                )
            )
    for column, thresholds in {
        "directional_range_pos_60": [0.1, 0.2, 0.3],
        "directional_range_pos_120": [0.1, 0.2, 0.3],
        "dir_mom_15": [-2.0, -1.0, -0.5, 0.0],
        "dir_mom_30": [-2.0, -1.0, -0.5, 0.0],
        "dir_ema20_dist": [-1.0, -0.5, 0.0],
        "atr14_rank_240": [0.05, 0.1, 0.2],
    }.items():
        for threshold in thresholds:
            rules.append(
                MetaRule(
                    f"{column}_lte_{threshold:g}_to_target",
                    lambda df, c=column, t=threshold: _safe_col(df, c).le(t),
                    target_fraction=1.0,
                )
            )

    combo_specs = [
        (
            "short_chase_to_target",
            lambda df: df["direction"].astype(int).lt(0) & _safe_col(df, "directional_range_pos_60").ge(0.85),
        ),
        (
            "long_chase_to_target",
            lambda df: df["direction"].astype(int).gt(0) & _safe_col(df, "directional_range_pos_60").ge(0.9),
        ),
        (
            "pullback_long_chase_to_target",
            lambda df: df["signal_family"].astype(str).eq("trend_pullback_long")
            & _safe_col(df, "directional_range_pos_60").ge(0.8),
        ),
        (
            "transition_short_asia_chase_to_target",
            lambda df: df["signal_family"].astype(str).eq("trend_transition_short_asia")
            & _safe_col(df, "directional_range_pos_60").ge(0.7),
        ),
        (
            "short_positive_mom_to_target",
            lambda df: df["direction"].astype(int).lt(0) & _safe_col(df, "dir_mom_30").ge(1.5),
        ),
        (
            "long_deep_discount_keep_runner_else_target",
            lambda df: df["direction"].astype(int).gt(0)
            & _safe_col(df, "directional_range_pos_60").ge(0.85)
            & _safe_col(df, "dir_mom_30").ge(1.5),
        ),
    ]
    rules.extend(MetaRule(name, fn, target_fraction=1.0) for name, fn in combo_specs)
    return rules


def apply_meta_rule(base: pd.DataFrame, runner_legs: pd.DataFrame, eligible: pd.DataFrame, rule: MetaRule) -> pd.DataFrame:
    # Start from strongest calibrated candidate: all eligible trades use 100% runner.
    result = apply_allocation(base, runner_legs, 0.0)
    mask = rule.mask_fn(eligible).fillna(False).astype(bool)
    target_ids = set(eligible.loc[mask, "trade_id"].astype(str))
    if not target_ids:
        result["meta_rule"] = rule.name
        result["meta_targeted"] = False
        return result

    legs = runner_legs.set_index("trade_id")
    row_mask = result["trade_id"].astype(str).isin(target_ids)
    selected = result.loc[row_mask].copy()
    selected_ids = selected["trade_id"].astype(str)
    leg_rows = legs.loc[selected_ids].reset_index(drop=True)
    direction = selected["direction"].astype(int).reset_index(drop=True)
    entry_price = selected["entry_price"].astype(float).reset_index(drop=True)
    target_gross = leg_rows["target_gross"].astype(float)
    runner_gross = leg_rows["runner_gross"].astype(float)
    gross = rule.target_fraction * target_gross + (1.0 - rule.target_fraction) * runner_gross
    net = gross - ROUND_TRIP_COST_POINTS
    result.loc[row_mask, "gross_points"] = gross.to_numpy()
    result.loc[row_mask, "net_points"] = net.to_numpy()
    result.loc[row_mask, "net_dollars"] = (net * POINT_VALUE).to_numpy()
    result.loc[row_mask, "exit_price"] = (entry_price + gross * direction).to_numpy()
    result.loc[row_mask, "exit_reason"] = f"meta_{rule.name}_target_f{rule.target_fraction:g}"
    result["meta_rule"] = rule.name
    result["meta_targeted"] = row_mask.to_numpy()
    return result.sort_values("entry_ts").reset_index(drop=True)


def _monthly_net(trades: pd.DataFrame) -> pd.Series:
    return trades.assign(month=_month_labels(trades["entry_ts"])).groupby("month")["net_points"].sum()


def evaluate_rules(base: pd.DataFrame, runner_legs: pd.DataFrame, rules: list[MetaRule]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    eligible = build_eligible_frame(base, runner_legs)
    baseline = apply_allocation(base, runner_legs, 0.0)
    baseline_summary = summarize(baseline)
    rows: list[dict[str, object]] = []
    outputs: dict[str, pd.DataFrame] = {}
    for rule in rules:
        result = apply_meta_rule(base, runner_legs, eligible, rule)
        summary = summarize(result)
        monthly = _monthly_net(result)
        targeted_count = int(result.get("meta_targeted", pd.Series(False, index=result.index)).sum())
        rows.append(
            {
                "rule": rule.name,
                "target_fraction": rule.target_fraction,
                **summary,
                "targeted_trades": targeted_count,
                "positive_months": int((monthly > 0).sum()),
                "worst_month_points": float(monthly.min()) if len(monthly) else 0.0,
                "net_delta_vs_all_runner": float(summary["net_points"] - baseline_summary["net_points"]),
                "pf_delta_vs_all_runner": float(summary["profit_factor"] - baseline_summary["profit_factor"]),
                "dd_delta_vs_all_runner": float(summary["max_drawdown_points"] - baseline_summary["max_drawdown_points"]),
            }
        )
        outputs[rule.name] = result
    ranking = pd.DataFrame(rows).sort_values(["net_points", "profit_factor"], ascending=False)
    return ranking, outputs


def build_pair_rules(base_rules: list[MetaRule], ranking: pd.DataFrame, top_n: int = 12) -> list[MetaRule]:
    lookup = {rule.name: rule for rule in base_rules}
    top_names = [name for name in ranking["rule"].astype(str).head(top_n).tolist() if name in lookup and name != "baseline_all_runner"]
    pairs: list[MetaRule] = []
    for left, right in itertools.combinations(top_names, 2):
        left_rule = lookup[left]
        right_rule = lookup[right]
        pairs.append(
            MetaRule(
                f"pair__{left}__OR__{right}",
                lambda df, a=left_rule.mask_fn, b=right_rule.mask_fn: a(df).fillna(False) | b(df).fillna(False),
                target_fraction=1.0,
            )
        )
    return pairs


def walk_forward_selection(ranking: pd.DataFrame, outputs: dict[str, pd.DataFrame], top_rules: int = 40) -> pd.DataFrame:
    selected_rules = [rule for rule in ranking["rule"].astype(str).head(top_rules).tolist() if rule in outputs]
    outputs = {rule: outputs[rule] for rule in selected_rules}
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
        for rule, trades in outputs.items():
            months = _month_labels(trades["entry_ts"])
            train = trades.loc[months.isin(train_months)].copy()
            if len(train) < 120:
                continue
            summary = summarize(train)
            monthly = _monthly_net(train)
            train_rows.append(
                {
                    "rule": rule,
                    "train_net": summary["net_points"],
                    "train_pf": summary["profit_factor"],
                    "train_dd": summary["max_drawdown_points"],
                    "train_worst_month": float(monthly.min()) if len(monthly) else 0.0,
                }
            )
        if not train_rows:
            continue
        train_rank = pd.DataFrame(train_rows)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize causal meta allocation rules on calibrated runner-eligible trades.")
    parser.add_argument("--base-trades", default="reports/NQ-pine-12m-sum_pos-open2-early-exit-small-best-trades.csv")
    parser.add_argument("--scaleout-trades", default="reports/NQ-pine-12m-sum_pos-open2-scaleout-runner-best-trades.csv")
    parser.add_argument("--ranking-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-meta-allocation-ranking.csv")
    parser.add_argument("--best-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-meta-allocation-best-trades.csv")
    parser.add_argument("--best-ranking-row", default="reports/NQ-pine-12m-sum_pos-open2-runner-meta-allocation-ranking-row.csv")
    parser.add_argument("--walk-forward-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-meta-allocation-walkforward.csv")
    parser.add_argument("--robustness-output", default="reports/NQ-pine-12m-sum_pos-open2-runner-meta-allocation-robustness.csv")
    args = parser.parse_args()

    base = pd.read_csv(ROOT_DIR / args.base_trades)
    scaleout = pd.read_csv(ROOT_DIR / args.scaleout_trades)
    for frame in [base, scaleout]:
        frame["entry_ts"] = _to_utc(frame["entry_ts"])
        frame["exit_ts"] = _to_utc(frame["exit_ts"])
    runner_legs = infer_runner_legs(base, scaleout)
    base_rules = build_meta_rules()
    initial_ranking, _ = evaluate_rules(base, runner_legs, base_rules)
    pair_rules = build_pair_rules(base_rules, initial_ranking)
    ranking, outputs = evaluate_rules(base, runner_legs, [*base_rules, *pair_rules])
    best_rule = str(ranking.iloc[0]["rule"])
    best = outputs[best_rule]
    wf = walk_forward_selection(ranking, outputs)

    ranking_path = ROOT_DIR / args.ranking_output
    best_path = ROOT_DIR / args.best_output
    row_path = ROOT_DIR / args.best_ranking_row
    wf_path = ROOT_DIR / args.walk_forward_output
    robustness_path = ROOT_DIR / args.robustness_output
    ranking.to_csv(ranking_path, index=False)
    best.to_csv(best_path, index=False)
    wf.to_csv(wf_path, index=False)
    report_row(
        "sum_pos_open2_runner_meta_allocation_best",
        best,
        (
            f"No month/date filter. Best causal meta allocation rule: {best_rule}. "
            "Default is 100% runner on prior scaleout-eligible trades; matched weak-runner structures are sent to target exit."
        ),
    ).to_csv(row_path, index=False)
    calibrated = apply_allocation(base, runner_legs, 0.0)
    robustness_rows = [
        _summary_with_mc("current_50_50", scaleout),
        _summary_with_mc("calibrated_0_100", calibrated),
        _summary_with_mc("meta_allocation", best),
    ]
    robustness_rows.extend(_cost_stress_rows("current_50_50", scaleout)[1:])
    robustness_rows.extend(_cost_stress_rows("calibrated_0_100", calibrated)[1:])
    robustness_rows.extend(_cost_stress_rows("meta_allocation", best)[1:])
    pd.DataFrame(robustness_rows).to_csv(robustness_path, index=False)
    print(f"best_rule {best_rule}")
    print(f"wrote {ranking_path}")
    print(f"wrote {best_path}")
    print(f"wrote {row_path}")
    print(f"wrote {wf_path}")
    print(f"wrote {robustness_path}")
    print(ranking.head(40).to_string(index=False))
    if not wf.empty:
        print("\nwalk_forward")
        print(wf.to_string(index=False))
        print("\nwalk_forward_total")
        print(summarize(pd.DataFrame({"net_points": wf["test_net"].astype(float)})))


if __name__ == "__main__":
    main()
