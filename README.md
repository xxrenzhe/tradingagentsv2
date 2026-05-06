<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Analyzes social media and public sentiment using sentiment scoring algorithms to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

Optional IBKR paper-trading support:
```bash
pip install ".[ibkr]"
```

The IBKR adapter lives under `tradingagents.execution.ibkr`. It is guarded for paper trading by default: paper-only mode accepts TWS paper port `7497` or IB Gateway paper port `4002`, rejects non-paper ports, enforces account/symbol/quantity checks, requires brackets for entry orders, and writes audit events to `.tmp/ibkr-paper-audit.jsonl`.

Copy `.env.example` to `.env` and configure the `TRADINGAGENTS_IBKR_*` values there. Scripts load `.env` automatically; do not pass IBKR account settings via ad-hoc shell exports.

Minimal dry-run:
```python
from tradingagents.execution import IBKROrderIntent, IBKRPaperBroker

intent = IBKROrderIntent(
    action="BUY",
    quantity=1,
    symbol="NQ",
    last_trade_date_or_contract_month="202606",
    stop_loss_price=18000.0,
    take_profit_price=18100.0,
    account="DU123456",
    strategy_id="adaptive_mbp_portfolio",
)

result = IBKRPaperBroker().submit(intent, dry_run=True)
```

Or from the command line:

```bash
python scripts/submit_ibkr_paper_order.py --intent examples/ibkr_paper_order_intent.example.json
```

Use `dry_run=False` only after TWS/IB Gateway paper trading is running and account, port, bracket, and risk settings have been verified. The paper session adds a preflight similar to the `tradingllmagent` IBKR gateway: socket check, paper-account verification, contract metadata validation, quote readiness, spread cap, current-position risk, and JSONL audit output.

Run readiness before submitting:

```bash
.venv/bin/python scripts/check_ibkr_paper_ready.py
```

To validate the adaptive portfolio against paper trading inputs:

```bash
.venv/bin/python scripts/validate_mbp_adaptive_portfolio_paper.py --trades .tmp/mbp-adaptive-portfolio-trades.csv --preflight
```

To run the selected best MBP strategy through the same guarded IBKR paper path:

```bash
.venv/bin/python scripts/run_mbp_best_strategy_paper_trader.py --record-ticks
```

This locks the paper runner to `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3` from `.tmp/mbp-best-strategy-trades.csv` and defaults to dry-run. Add `--daemon --max-iterations 0` for continuous monitoring. Add `--submit` only after readiness and paper-validation gates pass.

To run the guarded automation supervisor for that strategy:

```bash
.venv/bin/python scripts/automate_mbp_best_strategy_paper_trading.py --daemon --max-iterations 0 --record-ticks
```

The supervisor defaults to dry-run automation. With `--submit`, it first checks IBKR paper readiness and the paper-validation gate for `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`; if either gate is blocked, it exits without submitting.

To run the guarded live best-strategy paper loop in dry-run mode:

```bash
.venv/bin/python scripts/run_ibkr_live_paper_trader.py --record-ticks
```

The default signal mode now evaluates `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3` instead of using a fixed BUY/SELL direction. It appends live market snapshots to `.tmp/mbp-live-market-history.jsonl` and blocks with `signal_blocked` unless the strategy has enough minute bars, crosses the mean-reversion z-score threshold, and has aligned bid/ask size imbalance. Paper trading defaults to `--strategy-session all`; pass `--strategy-session europe` to restore the original Europe-only window. For continuous monitoring, add `--daemon --max-iterations 0`. Add `--submit` only after `scripts/check_paper_automation_status.py` reports `paper_submit_status: ready`; without `--submit`, the live loop writes a fresh signal only when the strategy triggers, builds the bracket intent, runs risk checks, records audit/tick evidence, and does not place orders. IBKR paper preflight accepts live, frozen, and delayed market data (`market_data_type` `1`, `2`, or `3`) and blocks unknown/frozen-delayed data with `market_data_not_paper_tradeable`. Only disable this for diagnostics with `TRADINGAGENTS_IBKR_REQUIRE_PAPER_TRADEABLE_MARKET_DATA=false`.

When the only paper-validation blocker is insufficient outcome count, use explicit accrual mode to continue collecting IBKR paper outcomes without treating the strategy as fully validated:

```bash
.venv/bin/python scripts/check_paper_automation_status.py \
  --strategy-id adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3 \
  --paper-validation-accrual-mode

.venv/bin/python scripts/run_ibkr_live_paper_trader.py \
  --daemon --max-iterations 0 --submit --paper-validation-accrual-mode
```

Accrual mode still blocks if readiness, net points, win rate, or consecutive-loss gates fail. It only bypasses `paper_outcomes_below_min:*` so the paper account can collect the remaining validation samples. Omit `--paper-validation-accrual-mode` for fully validated real-time paper execution.

In status output, `live_candidate_status` / `strict_live_candidate_status` remain `blocked` until the full validation gate passes. `paper_validation_accrual_status` is the separate field to use when intentionally collecting the remaining paper-validation samples.

Manual top-of-book signals are still available for diagnostics only:

```bash
.venv/bin/python scripts/run_ibkr_live_paper_trader.py --signal-mode manual --direction buy
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

This project routes AI business calls to aicode.cat. Prefer `gpt-5.5` when it is available; the current validated fallback is `gpt-5.4`. Configure these values in `.env`:

```bash
AICODE_API_KEY=...
AICODE_BASE_URL=https://aicode.cat
LLM_PROVIDER=aicode
DEEP_THINK_LLM=gpt-5.4
QUICK_THINK_LLM=gpt-5.4
```

TradingAgents still supports multiple LLM providers. If you intentionally switch providers, set the API key for your chosen provider in `.env`:

```bash
OPENAI_API_KEY=...          # OpenAI (GPT)
GOOGLE_API_KEY=...          # Google (Gemini)
ANTHROPIC_API_KEY=...       # Anthropic (Claude)
XAI_API_KEY=...             # xAI (Grok)
DEEPSEEK_API_KEY=...        # DeepSeek
DASHSCOPE_API_KEY=...       # Qwen (Alibaba DashScope)
ZHIPU_API_KEY=...           # GLM (Zhipu)
OPENROUTER_API_KEY=...      # OpenRouter
ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For enterprise providers (e.g. Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For local models, configure Ollama with `llm_provider: "ollama"` in your config.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope), GLM (Zhipu), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "aicode"      # default AI provider for this project
config["deep_think_llm"] = "gpt-5.4"   # Validated aicode.cat fallback when gpt-5.5 is unavailable
config["quick_think_llm"] = "gpt-5.4"  # Validated aicode.cat fallback when gpt-5.5 is unavailable
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

Past contributions, including code, design feedback, and bug reports, are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
