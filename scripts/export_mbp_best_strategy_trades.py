from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pandas as pd

from generate_mbp_history_report import _load_features
from generate_mbp_live_ready_report import _advanced_spec_from_row, _base_spec_from_row
from mine_mbp_advanced_patterns import build_advanced_trades
from tradingagents.backtesting.short_patterns import build_trades


def export_best_strategy_trades(
    *,
    ranking_path: Path,
    features_cache: Path,
    output_path: Path,
    strategy_rank: int,
) -> tuple[pd.Series, pd.DataFrame]:
    ranking = pd.read_csv(ranking_path)
    if ranking.empty:
        raise SystemExit(f"No ranked strategy candidates found: {ranking_path}")
    if strategy_rank < 1 or strategy_rank > len(ranking):
        raise SystemExit(f"Strategy rank must be between 1 and {len(ranking)}")

    row = ranking.iloc[strategy_rank - 1]
    features = _load_features(features_cache)
    if str(row.get("source", "advanced")) == "base":
        spec = _base_spec_from_row(row)
        if spec is None:
            raise SystemExit(f"Could not rebuild base strategy spec: {row.get('name')}")
        trades = build_trades(features, spec)
    else:
        spec = _advanced_spec_from_row(row)
        if spec is None:
            raise SystemExit(f"Could not rebuild advanced strategy spec: {row.get('name')}")
        trades = build_advanced_trades(features, spec)

    if trades.empty:
        raise SystemExit(f"Best strategy produced no trades: {row.get('name')}")

    trades = trades.sort_values("entry_ts").reset_index(drop=True)
    strategy_name = str(row["name"])
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades["trade_date"] = trades["entry_ts"].dt.date.astype(str)
    trades["portfolio_rule"] = strategy_name
    trades["selected_alias"] = "best_strategy"
    trades["candidate_universe"] = str(row.get("candidate_universe", ""))
    trades["selection_tier"] = str(row.get("selection_tier", ""))
    trades["strategy_rank"] = strategy_rank

    ordered_columns = [
        "entry_ts",
        "exit_ts",
        "trade_date",
        "portfolio_rule",
        "selected_alias",
        "direction",
        "entry_price",
        "exit_price",
        "gross_points",
        "net_points",
        "net_dollars",
        "exit_reason",
        "entry_index",
        "exit_index",
        "holding_minutes",
        "candidate_universe",
        "selection_tier",
        "strategy_rank",
    ]
    extra_columns = [column for column in trades.columns if column not in ordered_columns]
    output = trades[ordered_columns + extra_columns]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)
    return row, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ranked MBP best-strategy trades for gate validation.")
    parser.add_argument("--ranking", default=".tmp/mbp-best-strategy-ranking.csv")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--output", default=".tmp/mbp-best-strategy-trades.csv")
    parser.add_argument("--strategy-rank", type=int, default=1)
    args = parser.parse_args()

    row, trades = export_best_strategy_trades(
        ranking_path=Path(args.ranking),
        features_cache=Path(args.features_cache),
        output_path=Path(args.output),
        strategy_rank=args.strategy_rank,
    )
    print(f"Strategy: {row['name']}")
    print(f"Trades: {len(trades):,}")
    print(f"Net points: {trades['net_points'].sum():,.4f}")
    print(f"Output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
