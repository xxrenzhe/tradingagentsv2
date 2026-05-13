from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "search_nq_rollstable_timecell_oos.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("search_nq_rollstable_timecell_oos", SCRIPT_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["search_nq_rollstable_timecell_oos"] = module
SPEC.loader.exec_module(module)


def _bars(start: str, rows: int, symbol: str = "NQH0", *, close_offset: float = 2.0) -> pd.DataFrame:
    ts = pd.date_range(start, periods=rows, freq="min", tz="UTC")
    base = pd.Series(range(rows), dtype="float64") + 100.0
    return pd.DataFrame(
        {
            "ts": ts,
            "trade_date": ts.date,
            "symbol": symbol,
            "Open": base,
            "High": base + close_offset + 0.5,
            "Low": base - 0.5,
            "Close": base + close_offset,
            "Volume": 10,
        }
    )


def test_build_events_uses_next_bar_entry_and_rejects_contract_break() -> None:
    frame = _bars("2020-01-01 00:00", 6)
    frame.loc[2:, "symbol"] = "NQM0"

    events = module.build_events(
        frame,
        step=1,
        hold=2,
        session="all",
        key_columns=["hour"],
        prevent_overlap=True,
    )

    assert events["signal_index"].tolist() == [2]
    assert events["entry_index"].tolist() == [3]
    assert events["exit_index"].tolist() == [4]
    assert events["entry_ts"].iloc[0] == frame["ts"].iloc[3]
    assert events["entry_price"].iloc[0] == frame["Open"].iloc[3]


def test_action_map_is_trained_only_on_train_years_and_applied_only_to_test_years() -> None:
    events = pd.DataFrame(
        [
            {
                "entry_ts": "2019-01-01 00:01:00+00:00",
                "exit_ts": "2019-01-01 00:03:00+00:00",
                "year": 2019,
                "hour": 0,
                "gross_long": 4.0,
                "entry_price": 100.0,
                "exit_price": 104.0,
            },
            {
                "entry_ts": "2020-01-01 00:01:00+00:00",
                "exit_ts": "2020-01-01 00:03:00+00:00",
                "year": 2020,
                "hour": 0,
                "gross_long": 5.0,
                "entry_price": 110.0,
                "exit_price": 115.0,
            },
        ]
    )

    actions = module.train_action_map(events, key_columns=["hour"], train_years=[2019], min_cell=1)
    trades = module.apply_actions(
        events,
        actions,
        key_columns=["hour"],
        test_years=[2020],
        label="strict_oos",
    )

    assert actions == {(0,): 1}
    assert trades["year"].tolist() == [2020]
    assert trades["net_points"].tolist() == [5.0 - module.ROUND_TRIP_COST_POINTS]
    assert trades["strategy_label"].tolist() == ["strict_oos"]


def test_search_timecells_sorts_quality_gated_rows_and_exports_best_test_trades() -> None:
    bars = pd.concat(
        [
            _bars("2019-01-01 00:00", 8, "NQH9", close_offset=2.0),
            _bars("2020-01-01 00:00", 8, "NQH0", close_offset=3.0),
        ],
        ignore_index=True,
    )

    search, trades, actions = module.search_timecells(
        bars,
        train_years=[2019],
        test_years=[2020],
        steps=[1],
        holds=[2],
        sessions=["all"],
        key_sets=["hour", "dow/hour"],
        min_cells=[1],
        annual_floor=1,
        min_profit_factor=1.25,
        min_net_to_drawdown=1.0,
    )

    assert len(search) == 2
    assert bool(search.iloc[0]["quality_gate"]) is True
    assert bool(search.iloc[0]["gate"]) is True
    assert search.iloc[0]["net"] >= search.iloc[1]["net"]
    assert actions
    assert set(pd.to_datetime(trades["entry_ts"], utc=True).dt.year) == {2020}
    assert (trades["entry_ts"] > trades["signal_ts"]).all()
