import os

from tradingagents.config.env import load_project_env

load_project_env()

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    "memory_log_enabled": os.getenv("TRADINGAGENTS_MEMORY_LOG_ENABLED", "true").lower() not in ("0", "false", "no"),
    # LLM settings
    "llm_provider": os.getenv("LLM_PROVIDER", "aicode"),
    "deep_think_llm": os.getenv("DEEP_THINK_LLM", "gpt-5.5"),
    "quick_think_llm": os.getenv("QUICK_THINK_LLM", "gpt-5.5"),
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": os.getenv("LLM_BACKEND_URL") or os.getenv("AICODE_BASE_URL", "https://aicode.cat"),
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    "fast_graph_mode": os.getenv("TRADINGAGENTS_FAST_GRAPH_MODE", "false").lower() in ("1", "true", "yes"),
    "deterministic_decision_mode": os.getenv("TRADINGAGENTS_DETERMINISTIC_DECISION_MODE", "false").lower() in ("1", "true", "yes"),
    "market_report_use_mbp": os.getenv("TRADINGAGENTS_MARKET_REPORT_USE_MBP", "false").lower() in ("1", "true", "yes"),
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": os.getenv("CORE_STOCK_VENDOR", "yfinance"),       # Options: alpha_vantage, yfinance, databento
        "technical_indicators": os.getenv("TECHNICAL_INDICATORS_VENDOR", "yfinance"),  # Options: alpha_vantage, yfinance, databento
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    "execution": {
        "ibkr": {
            "host": os.getenv("TRADINGAGENTS_IBKR_HOST", "127.0.0.1"),
            "port": int(os.getenv("TRADINGAGENTS_IBKR_PORT", "7497")),
            "client_id": int(os.getenv("TRADINGAGENTS_IBKR_CLIENT_ID", "26")),
            "account": os.getenv("TRADINGAGENTS_IBKR_ACCOUNT"),
            "paper_only": os.getenv("TRADINGAGENTS_IBKR_PAPER_ONLY", "true").lower() not in ("0", "false", "no"),
            "max_quantity": int(os.getenv("TRADINGAGENTS_IBKR_MAX_QTY", "1")),
            "max_position": int(os.getenv("TRADINGAGENTS_IBKR_MAX_POSITION", "1")),
            "kill_switch": os.getenv("TRADINGAGENTS_IBKR_KILL_SWITCH", "false").lower() in ("1", "true", "yes"),
        }
    },
}
