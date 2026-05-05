from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from tradingagents.execution.live_strategy import _load_bootstrap_bars


@pytest.mark.unit
def test_load_bootstrap_bars_shifts_feature_cache_to_live_warmup_window(tmp_path) -> None:
    source_ts = pd.date_range("2026-05-01T12:00:00Z", periods=100, freq="min")
    frame = pd.DataFrame(
        {
            "ts": source_ts,
            "Open": [100.0 + i for i in range(100)],
            "High": [100.5 + i for i in range(100)],
            "Low": [99.5 + i for i in range(100)],
            "Close": [100.25 + i for i in range(100)],
            "Volume": [10] * 100,
            "spread_mean": [0.5] * 100,
            "imbalance_last": [0.2] * 100,
            "depth_mean": [20.0] * 100,
        }
    )
    cache_path = tmp_path / "features.pkl"
    pd.to_pickle({"sample": frame}, cache_path)

    now = datetime(2026, 5, 5, 14, 30, tzinfo=UTC)
    bars = _load_bootstrap_bars(cache_path, now, required_bars=60)

    assert len(bars) == 90
    assert bars.iloc[-1]["ts"].to_pydatetime() == now - timedelta(minutes=1)
    assert {"Open", "High", "Low", "Close", "imbalance_last", "minute_of_day"}.issubset(bars.columns)
