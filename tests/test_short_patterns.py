import pandas as pd

from tradingagents.backtesting.short_patterns import (
    BacktestCosts,
    StrategySpec,
    build_trades,
    evaluate_strategies,
    prepare_minute_features,
)


def _sample_bars():
    rows = []
    price = 100.0
    for minute in range(40):
        price += 0.25 if minute < 20 else -0.1
        rows.append(
            {
                "Date": f"2026-04-27T00:{minute:02d}:00Z",
                "Open": price,
                "High": price + 0.25,
                "Low": price - 0.25,
                "Close": price + 0.1,
                "Volume": 100 + minute,
            }
        )
    return pd.DataFrame(rows)


def _sample_mbp():
    rows = []
    for minute in range(40):
        rows.append(
            {
                "ts_event": f"2026-04-27T00:{minute:02d}:15Z",
                "bid_px_00": 100 + minute * 0.1,
                "ask_px_00": 100.25 + minute * 0.1,
                "bid_sz_00": 8 if minute < 20 else 2,
                "ask_sz_00": 2 if minute < 20 else 8,
            }
        )
    return pd.DataFrame(rows)


def test_prepare_minute_features_merges_mbp():
    features = prepare_minute_features(_sample_bars(), _sample_mbp())

    assert "imbalance_last" in features.columns
    assert "spread_mean" in features.columns
    assert features["imbalance_last"].notna().any()


def test_build_trades_applies_costs():
    features = prepare_minute_features(_sample_bars(), _sample_mbp())
    spec = StrategySpec(
        name="momentum_test",
        family="momentum",
        lookback=3,
        threshold=0.0001,
        holding_minutes=3,
        imbalance_threshold=0.1,
        max_spread_quantile=1.0,
        min_depth_quantile=0.0,
    )

    trades = build_trades(features, spec, BacktestCosts(slippage_ticks_per_side=0, commission_per_contract=0))

    assert not trades.empty
    assert set(trades["direction"]).issubset({-1, 1})
    assert "net_points" in trades.columns


def test_build_trades_applies_stop_loss_and_take_profit():
    features = prepare_minute_features(_sample_bars(), _sample_mbp())
    spec = StrategySpec(
        name="momentum_risk_test",
        family="momentum",
        lookback=3,
        threshold=0.0001,
        holding_minutes=10,
        imbalance_threshold=0.1,
        max_spread_quantile=1.0,
        min_depth_quantile=0.0,
        stop_loss_points=0.25,
        take_profit_points=0.75,
    )

    trades = build_trades(features, spec, BacktestCosts(slippage_ticks_per_side=0, commission_per_contract=0))

    assert not trades.empty
    assert set(trades["exit_reason"]).intersection({"stop_loss", "take_profit"})
    assert (trades["exit_index"] >= trades["entry_index"]).all()


def test_evaluate_strategies_returns_ranked_results():
    features = prepare_minute_features(_sample_bars(), _sample_mbp())
    specs = [
        StrategySpec("momentum", "momentum", 3, 0.0001, 3),
        StrategySpec("mean_reversion", "mean_reversion", 5, 0.5, 3),
    ]

    results, trades_by_name = evaluate_strategies(features, specs=specs, min_trades=1)

    assert not results.empty
    assert results.iloc[0]["score"] >= results.iloc[-1]["score"]
    assert "stability" in results.columns
    assert "worst_trade_points" in results.columns
    assert set(trades_by_name).issubset({"momentum", "mean_reversion"})
