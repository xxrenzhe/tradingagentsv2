import pandas as pd
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_indicators,
    get_language_instruction,
    get_orderbook_microstructure,
    get_stock_data,
)
from tradingagents.dataflows.config import get_config
from tradingagents.backtesting.short_patterns import evaluate_strategies, prepare_minute_features
from tradingagents.dataflows.databento import _read_bar_window, _read_mbp_window


def _is_aicode_llm(llm) -> bool:
    return "aicode.cat" in str(getattr(llm, "openai_api_base", "") or getattr(llm, "base_url", ""))


def _databento_market_report(symbol: str, current_date: str, use_mbp: bool = False) -> str:
    start_date = current_date
    end_date = (pd.Timestamp(current_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    bars = _read_bar_window(symbol, start_date, end_date)
    if bars.empty:
        return f"No Databento market data found for {symbol} on {current_date}."

    microstructure = _read_mbp_window(symbol, start_date, end_date) if use_mbp else pd.DataFrame()
    features = prepare_minute_features(bars, microstructure if len(microstructure) > 10 else None)
    results, _ = evaluate_strategies(features, min_trades=5)

    first_close = float(bars["Close"].iloc[0])
    last_close = float(bars["Close"].iloc[-1])
    high = float(bars["High"].max())
    low = float(bars["Low"].min())
    volume = int(bars["Volume"].sum())
    net_change = last_close - first_close
    net_change_pct = net_change / first_close * 100

    lines = [
        f"# Databento Market Report for {symbol.upper()} on {current_date}",
        "",
        f"- Bars: {len(bars)} one-minute records.",
        f"- Close change: {net_change:.2f} points ({net_change_pct:.2f}%).",
        f"- Intraday range: {low:.2f} to {high:.2f}.",
        f"- Total volume: {volume:,}.",
    ]
    if len(microstructure) > 10:
        lines.append(f"- MBP rows available: {len(microstructure):,}; order-book filters can be applied.")
    else:
        lines.append("- MBP rows were unavailable or insufficient for robust order-book filtering in this run.")

    if not results.empty:
        top = results.head(5)
        lines.extend([
            "",
            "## Best Short-Term Patterns",
            "",
            top[[
                "name",
                "family",
                "trades",
                "net_points",
                "max_drawdown_points",
                "profit_factor",
                "win_rate",
                "score",
            ]].to_csv(index=False),
            "",
            "Use these as hypotheses only; they are in-sample on the available day and require walk-forward validation.",
        ])

    return "\n".join(lines)


def create_market_analyst(llm):

    def market_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])
        data_vendor = get_config().get("data_vendors", {}).get("core_stock_apis")
        if _is_aicode_llm(llm) and data_vendor == "databento":
            report = _databento_market_report(
                state["company_of_interest"],
                current_date,
                use_mbp=bool(get_config().get("market_report_use_mbp", False)),
            )
            return {
                "messages": [AIMessage(content=report)],
                "market_report": report,
            }

        tools = [
            get_stock_data,
            get_indicators,
            get_orderbook_microstructure,
        ]

        system_message = (
            """You are a trading assistant tasked with analyzing financial markets. Your role is to select the **most relevant indicators** for a given market condition or trading strategy from the following list. The goal is to choose up to **8 indicators** that provide complementary insights without redundancy. Categories and each category's indicators are:

Moving Averages:
- close_50_sma: 50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance. Tips: It lags price; combine with faster indicators for timely signals.
- close_200_sma: 200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups. Tips: It reacts slowly; best for strategic trend confirmation rather than frequent trading entries.
- close_10_ema: 10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points. Tips: Prone to noise in choppy markets; use alongside longer averages for filtering false signals.

MACD Related:
- macd: MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes. Tips: Confirm with other indicators in low-volatility or sideways markets.
- macds: MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades. Tips: Should be part of a broader strategy to avoid false positives.
- macdh: MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early. Tips: Can be volatile; complement with additional filters in fast-moving markets.

Momentum Indicators:
- rsi: RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals. Tips: In strong trends, RSI may remain extreme; always cross-check with trend analysis.

Volatility Indicators:
- boll: Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement. Tips: Combine with the upper and lower bands to effectively spot breakouts or reversals.
- boll_ub: Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones. Tips: Confirm signals with other tools; prices may ride the band in strong trends.
- boll_lb: Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions. Tips: Use additional analysis to avoid false reversal signals.
- atr: ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility. Tips: It's a reactive measure, so use it as part of a broader risk management strategy.

Volume-Based Indicators:
- vwma: VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data. Tips: Watch for skewed results from volume spikes; use in combination with other volume analyses.

- For short-term futures/order-book analysis, call get_orderbook_microstructure for the relevant date window and use spread, mid-price movement, displayed depth, and bid/ask imbalance to assess execution risk, liquidity, and near-term pressure.

- Select indicators that provide diverse and complementary information. Avoid redundancy (e.g., do not select both rsi and stochrsi). Also briefly explain why they are suitable for the given market context. When you tool call, please use the exact name of the indicators provided above as they are defined parameters, otherwise your call will fail. Please make sure to call get_stock_data first to retrieve the CSV that is needed to generate indicators. Then use get_indicators with the specific indicator names. Write a very detailed and nuanced report of the trends you observe. Provide specific, actionable insights with supporting evidence to help traders make informed decisions."""
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "market_report": report,
        }

    return market_analyst_node
