from unittest.mock import MagicMock, patch

from tradingagents.graph.trading_graph import TradingAgentsGraph


def test_deterministic_decision_mode_skips_graph_invoke(tmp_path):
    mock_graph = MagicMock()
    mock_graph.config = {
        "deterministic_decision_mode": True,
        "checkpoint_enabled": False,
        "memory_log_enabled": False,
        "results_dir": str(tmp_path),
    }
    mock_graph.debug = False
    mock_graph.log_states_dict = {}
    mock_graph.quick_thinking_llm = MagicMock()
    mock_graph.graph.invoke = MagicMock()
    mock_graph.propagator.create_initial_state.return_value = {
        "messages": [],
        "company_of_interest": "NQM6",
        "trade_date": "2026-04-27",
        "past_context": "",
        "investment_debate_state": {},
        "risk_debate_state": {},
        "market_report": "",
        "sentiment_report": "",
        "news_report": "",
        "fundamentals_report": "",
    }
    mock_graph.propagator.get_graph_args.return_value = {}
    mock_graph.process_signal.return_value = "Hold"
    mock_graph.memory_log = MagicMock()
    mock_graph._memory_enabled = lambda: False
    mock_graph._run_deterministic_decision = MagicMock(
        return_value={
            "company_of_interest": "NQM6",
            "trade_date": "2026-04-27",
            "market_report": "market evidence",
            "sentiment_report": "",
            "news_report": "",
            "fundamentals_report": "",
            "investment_debate_state": {"bull_history": "", "bear_history": "", "history": "", "current_response": "", "judge_decision": ""},
            "risk_debate_state": {"aggressive_history": "", "conservative_history": "", "neutral_history": "", "history": "", "judge_decision": ""},
            "investment_plan": "plan",
            "trader_investment_plan": "trader",
            "final_trade_decision": "**Rating**: Hold",
        }
    )
    mock_graph._log_state = MagicMock()

    with patch.object(TradingAgentsGraph, "_memory_enabled", mock_graph._memory_enabled):
        state, decision = TradingAgentsGraph._run_graph(mock_graph, "NQM6", "2026-04-27")

    assert state["final_trade_decision"] == "**Rating**: Hold"
    assert decision == "Hold"
    mock_graph.graph.invoke.assert_not_called()
