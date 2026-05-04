"""Execution adapters and paper-trading safety gates."""

from .ibkr import (
    IBKRConnectionConfig,
    IBKRContractSpec,
    IBKRMarketSnapshot,
    IBKROrderIntent,
    IBKRPaperBroker,
    IBKRPaperRiskConfig,
    IBKRPaperTradingSession,
    build_nq_future_contract,
    submit_ibkr_paper_order,
)
from .live_signal import LIVE_SIGNAL_COLUMNS, LiveSignalConfig, build_live_signal_row, write_live_signal
from .live_strategy import (
    BEST_MEAN_REVERSION_ALIAS,
    BEST_MEAN_REVERSION_STRATEGY_ID,
    LiveStrategySignalConfig,
    LiveStrategySpec,
    build_strategy_live_signal_row,
    evaluate_mean_reversion_signal,
)
from .agent_gate import (
    AgentGateConfig,
    AgentStrategyGate,
    PaperTradeOutcome,
    build_candidate_trade_context,
    load_strategy_evidence,
    outcome_metrics,
    record_agent_gate_outcome,
)
from .gate_backtest import GateReplayConfig, replay_gate_on_trades
from .paper_report import PaperValidationGateConfig, evaluate_paper_validation_gate, paper_summary_frame, summarize_paper_audits
from .paper_runner import PaperDaemonConfig, PaperRunnerConfig, run_adaptive_portfolio_paper_daemon, run_adaptive_portfolio_paper_once
from .live_paper_trader import LivePaperTraderConfig, LivePaperTraderDaemonConfig, run_live_paper_trader_daemon, run_live_paper_trader_once
from .paper_validation import build_paper_intent_from_trade, load_trade_samples, select_trade_sample
from .tick_recorder import IBKRTickRecorderConfig, record_ibkr_ticks
from .tick_replay import TickReplayDatasetConfig, build_tick_replay_dataset
from .walk_forward import WalkForwardConfig, walk_forward_gate_replay

__all__ = [
    "IBKRConnectionConfig",
    "IBKRContractSpec",
    "IBKRMarketSnapshot",
    "IBKROrderIntent",
    "IBKRPaperBroker",
    "IBKRPaperRiskConfig",
    "IBKRPaperTradingSession",
    "AgentGateConfig",
    "AgentStrategyGate",
    "GateReplayConfig",
    "WalkForwardConfig",
    "PaperTradeOutcome",
    "PaperValidationGateConfig",
    "PaperRunnerConfig",
    "PaperDaemonConfig",
    "LiveSignalConfig",
    "LivePaperTraderConfig",
    "LivePaperTraderDaemonConfig",
    "IBKRTickRecorderConfig",
    "TickReplayDatasetConfig",
    "LiveStrategySignalConfig",
    "LiveStrategySpec",
    "BEST_MEAN_REVERSION_ALIAS",
    "BEST_MEAN_REVERSION_STRATEGY_ID",
    "build_nq_future_contract",
    "build_live_signal_row",
    "build_strategy_live_signal_row",
    "build_candidate_trade_context",
    "build_paper_intent_from_trade",
    "load_trade_samples",
    "load_strategy_evidence",
    "outcome_metrics",
    "select_trade_sample",
    "record_agent_gate_outcome",
    "replay_gate_on_trades",
    "evaluate_paper_validation_gate",
    "summarize_paper_audits",
    "paper_summary_frame",
    "run_adaptive_portfolio_paper_once",
    "run_adaptive_portfolio_paper_daemon",
    "run_live_paper_trader_once",
    "run_live_paper_trader_daemon",
    "record_ibkr_ticks",
    "build_tick_replay_dataset",
    "write_live_signal",
    "submit_ibkr_paper_order",
    "walk_forward_gate_replay",
    "evaluate_mean_reversion_signal",
    "LIVE_SIGNAL_COLUMNS",
]
