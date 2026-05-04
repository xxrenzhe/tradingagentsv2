from unittest.mock import MagicMock

import pandas as pd

from tradingagents.agents.analysts import market_analyst
from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.dataflows.config import set_config


def test_aicode_databento_market_analyst_uses_deterministic_report(monkeypatch):
    bars = pd.DataFrame(
        {
            "Date": pd.date_range("2026-04-27", periods=20, freq="min", tz="UTC"),
            "Open": range(100, 120),
            "High": range(101, 121),
            "Low": range(99, 119),
            "Close": range(100, 120),
            "Volume": [10] * 20,
        }
    )
    monkeypatch.setattr(market_analyst, "_read_bar_window", lambda *args: bars)
    monkeypatch.setattr(market_analyst, "_read_mbp_window", lambda *args: pd.DataFrame())
    set_config({"data_vendors": {"core_stock_apis": "databento"}})

    llm = MagicMock()
    llm.openai_api_base = "https://aicode.cat"
    node = create_market_analyst(llm)
    result = node({"trade_date": "2026-04-27", "company_of_interest": "NQM6", "messages": []})

    assert "# Databento Market Report for NQM6" in result["market_report"]
    assert "one-minute records" in result["market_report"]
    assert result["messages"][-1].content == result["market_report"]
    assert result["messages"][-1].tool_calls == []
    llm.bind_tools.assert_not_called()
