"""Tests for structured-output agents (Trader and Research Manager).

The Portfolio Manager has its own coverage in tests/test_memory_log.py
(which exercises the full memory-log → PM injection cycle).  This file
covers the parallel schemas, render functions, and graceful-fallback
behavior we added for the Trader and Research Manager so all three
decision-making agents share the same shape.
"""

from unittest.mock import MagicMock

import pytest

from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_conservative_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.schemas import (
    PortfolioRating,
    ResearchPlan,
    TraderAction,
    TraderProposal,
    render_research_plan,
    render_trader_proposal,
)
from tradingagents.agents.trader.trader import create_trader
from tradingagents.agents.utils.structured import normalize_freetext_output


# ---------------------------------------------------------------------------
# Render functions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRenderTraderProposal:
    def test_minimal_required_fields(self):
        p = TraderProposal(action=TraderAction.HOLD, reasoning="Balanced setup; no edge.")
        md = render_trader_proposal(p)
        assert "**Action**: Hold" in md
        assert "**Reasoning**: Balanced setup; no edge." in md
        # The trailing FINAL TRANSACTION PROPOSAL line is preserved for the
        # analyst stop-signal text and any external code that greps for it.
        assert "FINAL TRANSACTION PROPOSAL: **HOLD**" in md

    def test_optional_fields_included_when_present(self):
        p = TraderProposal(
            action=TraderAction.BUY,
            reasoning="Strong technicals + fundamentals.",
            entry_price=189.5,
            stop_loss=178.0,
            position_sizing="6% of portfolio",
        )
        md = render_trader_proposal(p)
        assert "**Action**: Buy" in md
        assert "**Entry Price**: 189.5" in md
        assert "**Stop Loss**: 178.0" in md
        assert "**Position Sizing**: 6% of portfolio" in md
        assert "FINAL TRANSACTION PROPOSAL: **BUY**" in md

    def test_optional_fields_omitted_when_absent(self):
        p = TraderProposal(action=TraderAction.SELL, reasoning="Guidance cut.")
        md = render_trader_proposal(p)
        assert "Entry Price" not in md
        assert "Stop Loss" not in md
        assert "Position Sizing" not in md
        assert "FINAL TRANSACTION PROPOSAL: **SELL**" in md


@pytest.mark.unit
class TestRenderResearchPlan:
    def test_required_fields(self):
        p = ResearchPlan(
            recommendation=PortfolioRating.OVERWEIGHT,
            rationale="Bull case carried; tailwinds intact.",
            strategic_actions="Build position over two weeks; cap at 5%.",
        )
        md = render_research_plan(p)
        assert "**Recommendation**: Overweight" in md
        assert "**Rationale**: Bull case carried" in md
        assert "**Strategic Actions**: Build position" in md

    def test_all_5_tier_ratings_render(self):
        for rating in PortfolioRating:
            p = ResearchPlan(
                recommendation=rating,
                rationale="r",
                strategic_actions="s",
            )
            md = render_research_plan(p)
            assert f"**Recommendation**: {rating.value}" in md


# ---------------------------------------------------------------------------
# Trader agent: structured happy path + fallback
# ---------------------------------------------------------------------------


def _make_trader_state(**overrides):
    state = {
        "company_of_interest": "NVDA",
        "investment_plan": "**Recommendation**: Buy\n**Rationale**: ...\n**Strategic Actions**: ...",
    }
    state.update(overrides)
    return state


def _structured_trader_llm(captured: dict, proposal: TraderProposal | None = None):
    """Build a MagicMock LLM whose with_structured_output binding captures the
    prompt and returns a real TraderProposal so render_trader_proposal works.
    """
    if proposal is None:
        proposal = TraderProposal(
            action=TraderAction.BUY,
            reasoning="Strong setup.",
        )
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or proposal
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.unit
class TestTraderAgent:
    def test_structured_path_produces_rendered_markdown(self):
        captured = {}
        proposal = TraderProposal(
            action=TraderAction.BUY,
            reasoning="AI capex cycle intact; institutional flows constructive.",
            entry_price=189.5,
            stop_loss=178.0,
            position_sizing="6% of portfolio",
        )
        llm = _structured_trader_llm(captured, proposal)
        trader = create_trader(llm)
        result = trader(_make_trader_state())
        plan = result["trader_investment_plan"]
        assert "**Action**: Buy" in plan
        assert "**Entry Price**: 189.5" in plan
        assert "FINAL TRANSACTION PROPOSAL: **BUY**" in plan
        # The same rendered markdown is also added to messages for downstream agents.
        assert plan in result["messages"][0].content

    def test_prompt_includes_investment_plan(self):
        captured = {}
        llm = _structured_trader_llm(captured)
        trader = create_trader(llm)
        trader(_make_trader_state())
        # The investment plan is in the user message of the captured prompt.
        prompt = captured["prompt"]
        assert any("Proposed Investment Plan" in m["content"] for m in prompt)

    def test_prompt_includes_memory_and_candidate_context(self):
        captured = {}
        llm = _structured_trader_llm(captured)
        trader = create_trader(llm)
        trader(
            _make_trader_state(
                past_context="Prior NQ long failed when spread widened after entry.",
                candidate_trade_context="Candidate action: BUY 1 NQ 202606\nStrategy ID: adaptive_defensive_mr",
            )
        )
        user_prompt = next(m["content"] for m in captured["prompt"] if m["role"] == "user")
        assert "Lessons from prior decisions and outcomes" in user_prompt
        assert "Prior NQ long failed" in user_prompt
        assert "Concrete strategy candidate under review" in user_prompt
        assert "adaptive_defensive_mr" in user_prompt

    def test_falls_back_to_freetext_when_structured_unavailable(self):
        plain_response = (
            "**Action**: Sell\n\nGuidance cut hits margins.\n\n"
            "FINAL TRANSACTION PROPOSAL: **SELL**"
        )
        llm = MagicMock()
        llm.with_structured_output.side_effect = NotImplementedError("provider unsupported")
        llm.invoke.return_value = MagicMock(content=plain_response)
        trader = create_trader(llm)
        result = trader(_make_trader_state())
        assert result["trader_investment_plan"] == plain_response

    def test_aicode_skips_structured_binding(self):
        plain_response = "**Action**: Hold\n\nNo clean edge.\n\nFINAL TRANSACTION PROPOSAL: **HOLD**"
        llm = MagicMock()
        llm.openai_api_base = "https://aicode.cat"
        llm.invoke.return_value = MagicMock(content=plain_response)
        trader = create_trader(llm)
        result = trader(_make_trader_state())
        assert result["trader_investment_plan"] == plain_response
        llm.with_structured_output.assert_not_called()


def test_normalize_freetext_output_adds_required_trader_markers():
    normalized = normalize_freetext_output("Buy gradually on pullbacks.", "Trader")
    assert "**Action**: Buy" in normalized
    assert "FINAL TRANSACTION PROPOSAL: **BUY**" in normalized


# ---------------------------------------------------------------------------
# Research Manager agent: structured happy path + fallback
# ---------------------------------------------------------------------------


def _make_rm_state(**overrides):
    state = {
        "company_of_interest": "NVDA",
        "investment_debate_state": {
            "history": "Bull and bear arguments here.",
            "bull_history": "Bull says...",
            "bear_history": "Bear says...",
            "current_response": "",
            "judge_decision": "",
            "count": 1,
        },
    }
    state.update(overrides)
    return state


def _structured_rm_llm(captured: dict, plan: ResearchPlan | None = None):
    if plan is None:
        plan = ResearchPlan(
            recommendation=PortfolioRating.HOLD,
            rationale="Balanced view across both sides.",
            strategic_actions="Hold current position; reassess after earnings.",
        )
    structured = MagicMock()
    structured.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or plan
    )
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.unit
class TestResearchManagerAgent:
    def test_structured_path_produces_rendered_markdown(self):
        captured = {}
        plan = ResearchPlan(
            recommendation=PortfolioRating.OVERWEIGHT,
            rationale="Bull case is stronger; AI tailwind intact.",
            strategic_actions="Build position gradually over two weeks.",
        )
        llm = _structured_rm_llm(captured, plan)
        rm = create_research_manager(llm)
        result = rm(_make_rm_state())
        ip = result["investment_plan"]
        assert "**Recommendation**: Overweight" in ip
        assert "**Rationale**: Bull case" in ip
        assert "**Strategic Actions**: Build position" in ip

    def test_prompt_uses_5_tier_rating_scale(self):
        """The RM prompt must list all five tiers so the schema enum matches user expectations."""
        captured = {}
        llm = _structured_rm_llm(captured)
        rm = create_research_manager(llm)
        rm(_make_rm_state())
        prompt = captured["prompt"]
        for tier in ("Buy", "Overweight", "Hold", "Underweight", "Sell"):
            assert f"**{tier}**" in prompt, f"missing {tier} in prompt"

    def test_prompt_includes_past_decision_memory(self):
        captured = {}
        llm = _structured_rm_llm(captured)
        rm = create_research_manager(llm)
        rm(_make_rm_state(past_context="Past analyses of NVDA: Buy worked after volume confirmation."))
        prompt = captured["prompt"]
        assert "Lessons from prior decisions and outcomes" in prompt
        assert "Buy worked after volume confirmation" in prompt

    def test_falls_back_to_freetext_when_structured_unavailable(self):
        plain_response = "**Recommendation**: Sell\n\n**Rationale**: ...\n\n**Strategic Actions**: ..."
        llm = MagicMock()
        llm.with_structured_output.side_effect = NotImplementedError("provider unsupported")
        llm.invoke.return_value = MagicMock(content=plain_response)
        rm = create_research_manager(llm)
        result = rm(_make_rm_state())
        assert result["investment_plan"] == plain_response


# ---------------------------------------------------------------------------
# Bull/Bear research debate agents: shared memory + candidate context
# ---------------------------------------------------------------------------


def _make_researcher_state():
    return {
        "market_report": "M1 reclaim after liquidity sweep.",
        "sentiment_report": "Sentiment neutral.",
        "news_report": "No macro shock.",
        "fundamentals_report": "Futures contract; fundamentals not applicable.",
        "past_context": "Prior NQ long failed when spread widened after entry.",
        "candidate_trade_context": (
            "Candidate action: BUY 1 NQ 202606\n"
            "Strategy ID: adaptive_defensive_mr"
        ),
        "investment_debate_state": {
            "history": "Existing investment debate.",
            "bull_history": "",
            "bear_history": "",
            "current_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }


def _plain_llm(captured: dict):
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or MagicMock(content="Research argument.")
    )
    return llm


@pytest.mark.unit
@pytest.mark.parametrize(
    "factory,expected_prefix",
    [
        (create_bull_researcher, "Bull Analyst:"),
        (create_bear_researcher, "Bear Analyst:"),
    ],
)
def test_research_debators_include_memory_and_candidate_context(factory, expected_prefix):
    captured = {}
    researcher = factory(_plain_llm(captured))
    result = researcher(_make_researcher_state())
    prompt = captured["prompt"]
    assert "Lessons from prior decisions and outcomes" in prompt
    assert "Prior NQ long failed" in prompt
    assert "Concrete strategy candidate under review" in prompt
    assert "adaptive_defensive_mr" in prompt
    assert expected_prefix in result["investment_debate_state"]["current_response"]


# ---------------------------------------------------------------------------
# Risk debate agents: shared memory + candidate context
# ---------------------------------------------------------------------------


def _make_risk_state():
    return {
        "market_report": "M1 trend shifted higher.",
        "sentiment_report": "Sentiment neutral.",
        "news_report": "No macro shock.",
        "fundamentals_report": "Futures contract; fundamentals not applicable.",
        "trader_investment_plan": "**Action**: Buy\n**Reasoning**: Candidate setup.",
        "past_context": "Prior NQ breakout failed when M3 divergence appeared.",
        "candidate_trade_context": (
            "Candidate action: BUY 1 NQ 202606\n"
            "Strategy ID: adaptive_defensive_mr\n"
            "full_profit_factor=1.6891"
        ),
        "risk_debate_state": {
            "history": "Existing risk debate.",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "latest_speaker": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "judge_decision": "",
            "count": 0,
        },
    }


def _risk_llm(captured: dict):
    llm = MagicMock()
    llm.invoke.side_effect = lambda prompt: (
        captured.__setitem__("prompt", prompt) or MagicMock(content="Risk argument.")
    )
    return llm


@pytest.mark.unit
@pytest.mark.parametrize(
    "factory,expected_speaker",
    [
        (create_aggressive_debator, "Aggressive"),
        (create_conservative_debator, "Conservative"),
        (create_neutral_debator, "Neutral"),
    ],
)
def test_risk_debators_include_memory_and_candidate_context(factory, expected_speaker):
    captured = {}
    debator = factory(_risk_llm(captured))
    result = debator(_make_risk_state())
    prompt = captured["prompt"]
    assert "Lessons from prior decisions and outcomes" in prompt
    assert "Prior NQ breakout failed" in prompt
    assert "Concrete strategy candidate under review" in prompt
    assert "adaptive_defensive_mr" in prompt
    assert "full_profit_factor=1.6891" in prompt
    assert result["risk_debate_state"]["latest_speaker"] == expected_speaker
