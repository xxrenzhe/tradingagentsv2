from unittest.mock import MagicMock

from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup


def _tool_nodes():
    return {
        "market": MagicMock(),
        "social": MagicMock(),
        "news": MagicMock(),
        "fundamentals": MagicMock(),
    }


def test_fast_graph_mode_routes_directly_to_managers():
    setup = GraphSetup(
        quick_thinking_llm=MagicMock(),
        deep_thinking_llm=MagicMock(),
        tool_nodes=_tool_nodes(),
        conditional_logic=ConditionalLogic(),
        fast_mode=True,
    )

    graph = setup.setup_graph(["market"]).compile()
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}

    assert ("Msg Clear Market", "Research Manager") in edges
    assert ("Research Manager", "Trader") in edges
    assert ("Trader", "Portfolio Manager") in edges
    assert not any(target in {"Bull Researcher", "Aggressive Analyst"} for _, target in edges)
