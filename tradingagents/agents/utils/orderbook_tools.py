from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.databento import get_orderbook_microstructure as get_databento_orderbook_microstructure


@tool
def get_orderbook_microstructure(
    symbol: Annotated[str, "Databento futures symbol, e.g. NQM6"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    bucket: Annotated[str, "Aggregation bucket such as 1min, 5min, or 15min"] = "5min",
) -> str:
    """
    Retrieve short-horizon top-of-book microstructure features from Databento MBP-1 data.
    Use this for intraday futures analysis: spread, mid-price movement, displayed depth,
    and bid/ask size imbalance.
    """
    return get_databento_orderbook_microstructure(symbol, start_date, end_date, bucket)
