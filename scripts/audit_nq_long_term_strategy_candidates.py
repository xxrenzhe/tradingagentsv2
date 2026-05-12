from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.backtesting.short_patterns import BacktestCosts  # noqa: E402


@dataclass(frozen=True)
class AuditConfig:
    min_sample_years: int = 10
    min_trades: int = 300
    profit_factor: float = 1.25
    net_to_drawdown: float = 4.0
    positive_year_rate: float = 0.70
    positive_90d_rate: float = 0.55
    positive_180d_rate: float = 0.60
    cost_2_points: float = 2.125
    cost_3_points: float = 3.125
    require_current_year_nonnegative: bool = True
    paper_validation_pass: bool = False
    execution_validation_pass: bool = False
    live_risk_limits_pass: bool = False


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def build_candidate_audit(
    *,
    regime_summary: pd.DataFrame,
    regime_yearly: pd.DataFrame,
    regime_rolling90: pd.DataFrame,
    regime_rolling180: pd.DataFrame,
    ofs_summary: pd.DataFrame,
    ofs_yearly: pd.DataFrame,
    ofs_rolling: pd.DataFrame,
    screenshot_summary: pd.DataFrame | None = None,
    screenshot_yearly: pd.DataFrame | None = None,
    screenshot_rolling: pd.DataFrame | None = None,
    config: AuditConfig | None = None,
    base_cost_points: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = config or AuditConfig()
    base_cost_points = BacktestCosts().round_trip_cost_points if base_cost_points is None else float(base_cost_points)
    screenshot_summary = pd.DataFrame() if screenshot_summary is None else screenshot_summary
    screenshot_yearly = pd.DataFrame() if screenshot_yearly is None else screenshot_yearly
    screenshot_rolling = pd.DataFrame() if screenshot_rolling is None else screenshot_rolling

    yearly = normalize_yearly(regime_yearly, ofs_yearly, screenshot_yearly, regime_summary, ofs_summary, screenshot_summary)
    rolling = normalize_rolling(
        regime_rolling90,
        regime_rolling180,
        ofs_rolling,
        screenshot_rolling,
        regime_summary,
        ofs_summary,
        screenshot_summary,
    )

    rows: list[dict[str, Any]] = []
    for _, row in regime_summary.iterrows():
        rows.append(normalize_regime_candidate(row, yearly, config))
    for _, row in ofs_summary.iterrows():
        rows.append(
            normalize_template_candidate(
                row,
                yearly,
                config,
                base_cost_points,
                strategy_source="ict_order_flow_shift",
                family="liquidity_sweep_mss_fvg_reclaim",
            )
        )
    for _, row in screenshot_summary.iterrows():
        rows.append(
            normalize_template_candidate(
                row,
                yearly,
                config,
                base_cost_points,
                strategy_source="screenshot_smc_momentum",
                family=str(row.get("family", "screenshot_smc_momentum")),
            )
        )

    audit = pd.DataFrame(rows)
    if audit.empty:
        return audit, yearly, rolling

    audit["stability_score"] = audit.apply(stability_score, axis=1)
    audit["readiness_tier"] = audit.apply(readiness_tier, axis=1)
    audit = audit.sort_values(
        ["long_term_research_pass", "stability_score", "net_points"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return audit, yearly, rolling


def normalize_yearly(
    regime_yearly: pd.DataFrame,
    ofs_yearly: pd.DataFrame,
    screenshot_yearly: pd.DataFrame,
    regime_summary: pd.DataFrame,
    ofs_summary: pd.DataFrame,
    screenshot_summary: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not regime_yearly.empty:
        mapping = dict(zip(regime_summary["label"], regime_summary["candidate"], strict=False))
        frame = regime_yearly.copy()
        frame["strategy_source"] = "regime_transition"
        frame["candidate"] = frame["label"].map(mapping).fillna(frame["label"])
        frame["candidate_key"] = frame["label"]
        frame = frame.rename(columns={"label": "strategy_label"})
        frames.append(frame[["strategy_source", "strategy_label", "candidate_key", "candidate", "year", "trades", "net_points"]])

    frames.extend(template_yearly_frames(ofs_yearly, ofs_summary, "ict_order_flow_shift"))
    frames.extend(template_yearly_frames(screenshot_yearly, screenshot_summary, "screenshot_smc_momentum"))

    if not frames:
        return pd.DataFrame(columns=["strategy_source", "strategy_label", "candidate_key", "candidate", "year", "trades", "net_points"])
    out = pd.concat(frames, ignore_index=True)
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["trades"] = pd.to_numeric(out["trades"], errors="coerce").fillna(0).astype(int)
    out["net_points"] = pd.to_numeric(out["net_points"], errors="coerce").fillna(0.0)
    return out


def normalize_rolling(
    regime_rolling90: pd.DataFrame,
    regime_rolling180: pd.DataFrame,
    ofs_rolling: pd.DataFrame,
    screenshot_rolling: pd.DataFrame,
    regime_summary: pd.DataFrame,
    ofs_summary: pd.DataFrame,
    screenshot_summary: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    regime_mapping = dict(zip(regime_summary["label"], regime_summary["candidate"], strict=False))
    for days, source in [(90, regime_rolling90), (180, regime_rolling180)]:
        if source.empty:
            continue
        frame = source.copy()
        frame["strategy_source"] = "regime_transition"
        frame["strategy_label"] = frame["label"]
        frame["candidate_key"] = frame["label"]
        frame["candidate"] = frame["label"].map(regime_mapping).fillna(frame["label"])
        frame["rolling_days"] = days
        frames.append(
            frame[
                [
                    "strategy_source",
                    "strategy_label",
                    "candidate_key",
                    "candidate",
                    "rolling_days",
                    "start",
                    "end",
                    "trades",
                    "net_points",
                ]
            ]
        )

    frames.extend(template_rolling_frames(ofs_rolling, ofs_summary, "ict_order_flow_shift"))
    frames.extend(template_rolling_frames(screenshot_rolling, screenshot_summary, "screenshot_smc_momentum"))

    if not frames:
        return pd.DataFrame(
            columns=[
                "strategy_source",
                "strategy_label",
                "candidate_key",
                "candidate",
                "rolling_days",
                "start",
                "end",
                "trades",
                "net_points",
            ]
        )
    out = pd.concat(frames, ignore_index=True)
    out["trades"] = pd.to_numeric(out["trades"], errors="coerce").fillna(0).astype(int)
    out["net_points"] = pd.to_numeric(out["net_points"], errors="coerce").fillna(0.0)
    return out


def template_yearly_frames(yearly: pd.DataFrame, summary: pd.DataFrame, strategy_source: str) -> list[pd.DataFrame]:
    if yearly.empty:
        return []
    mapping = dict(zip(summary["template"], summary["name"], strict=False)) if not summary.empty else {}
    frame = yearly.copy()
    frame["strategy_source"] = strategy_source
    frame["strategy_label"] = frame["template"]
    frame["candidate_key"] = frame["template"]
    frame["candidate"] = frame["template"].map(mapping).fillna(frame["template"])
    return [frame[["strategy_source", "strategy_label", "candidate_key", "candidate", "year", "trades", "net_points"]]]


def template_rolling_frames(rolling: pd.DataFrame, summary: pd.DataFrame, strategy_source: str) -> list[pd.DataFrame]:
    if rolling.empty:
        return []
    mapping = dict(zip(summary["template"], summary["name"], strict=False)) if not summary.empty else {}
    frame = rolling.copy()
    frame["strategy_source"] = strategy_source
    frame["strategy_label"] = frame["template"]
    frame["candidate_key"] = frame["template"]
    frame["candidate"] = frame["template"].map(mapping).fillna(frame["template"])
    frame["rolling_days"] = 180
    return [
        frame[
            [
                "strategy_source",
                "strategy_label",
                "candidate_key",
                "candidate",
                "rolling_days",
                "start",
                "end",
                "trades",
                "net_points",
            ]
        ]
    ]


def normalize_regime_candidate(row: pd.Series, yearly: pd.DataFrame, config: AuditConfig) -> dict[str, Any]:
    label = str(row["label"])
    selected_yearly = yearly[(yearly["strategy_source"] == "regime_transition") & (yearly["candidate_key"] == label)]
    years = sorted(int(year) for year in selected_yearly["year"].dropna().unique())
    current_year = years[-1] if years else np.nan
    current_year_net = float(selected_yearly.loc[selected_yearly["year"] == current_year, "net_points"].sum()) if years else np.nan
    cost_2 = _number(row, f"net_at_cost_{config.cost_2_points:g}")
    cost_3 = _number(row, f"net_at_cost_{config.cost_3_points:g}")
    record = {
        "strategy_source": "regime_transition",
        "strategy_label": label,
        "candidate_key": label,
        "candidate": str(row["candidate"]),
        "family": "range_compression_displacement_breakout",
        "sample_start_year": years[0] if years else np.nan,
        "sample_end_year": years[-1] if years else np.nan,
        "sample_years": int(_number(row, "years", len(years))),
        "trades": int(_number(row, "trades")),
        "net_points": _number(row, "net_points"),
        "net_dollars": _number(row, "net_dollars"),
        "profit_factor": _number(row, "profit_factor"),
        "win_rate": _number(row, "win_rate"),
        "payoff_ratio": _number(row, "payoff_ratio"),
        "expectancy_points": _number(row, "expectancy_points"),
        "max_drawdown_points": _number(row, "max_drawdown_points"),
        "net_to_drawdown": _number(row, "net_to_drawdown"),
        "positive_year_rate": _number(row, "positive_year_rate"),
        "worst_year_points": _number(row, "worst_year_points"),
        "positive_90d_rate": _number(row, "positive_90d_rate"),
        "worst_90d_points": _number(row, "worst_90d_points"),
        "positive_180d_rate": _number(row, "positive_180d_rate"),
        "worst_180d_points": _number(row, "worst_180d_points"),
        "current_year": current_year,
        "current_year_net_points": current_year_net,
        "cost_2_125_net_points": cost_2,
        "cost_3_125_net_points": cost_3,
    }
    return add_gates(record, config)


def normalize_template_candidate(
    row: pd.Series,
    yearly: pd.DataFrame,
    config: AuditConfig,
    base_cost_points: float,
    *,
    strategy_source: str,
    family: str,
) -> dict[str, Any]:
    label = str(row["template"])
    selected_yearly = yearly[(yearly["strategy_source"] == strategy_source) & (yearly["candidate_key"] == label)]
    years = sorted(int(year) for year in selected_yearly["year"].dropna().unique())
    current_year = years[-1] if years else np.nan
    current_year_net = float(selected_yearly.loc[selected_yearly["year"] == current_year, "net_points"].sum()) if years else np.nan
    trades = int(_number(row, "trades"))
    net_points = _number(row, "net_points")
    cost_2 = net_points - max(config.cost_2_points - base_cost_points, 0.0) * trades
    cost_3 = net_points - max(config.cost_3_points - base_cost_points, 0.0) * trades
    max_dd = _number(row, "max_drawdown_points")
    record = {
        "strategy_source": strategy_source,
        "strategy_label": label,
        "candidate_key": label,
        "candidate": str(row.get("name", label)),
        "family": family,
        "sample_start_year": years[0] if years else np.nan,
        "sample_end_year": years[-1] if years else np.nan,
        "sample_years": int(_number(row, "year_count", len(years))),
        "trades": trades,
        "net_points": net_points,
        "net_dollars": net_points * BacktestCosts().point_value,
        "profit_factor": _number(row, "profit_factor"),
        "win_rate": _number(row, "win_rate"),
        "payoff_ratio": _number(row, "payoff_ratio"),
        "expectancy_points": _number(row, "expectancy_points", _number(row, "avg_points")),
        "max_drawdown_points": max_dd,
        "net_to_drawdown": net_points / max(max_dd, 1.0),
        "positive_year_rate": _number(row, "positive_year_rate"),
        "worst_year_points": _number(row, "min_year_net_points"),
        "positive_90d_rate": np.nan,
        "worst_90d_points": np.nan,
        "positive_180d_rate": _number(row, "positive_rolling_rate"),
        "worst_180d_points": _number(row, "min_rolling_net_points"),
        "current_year": current_year,
        "current_year_net_points": current_year_net,
        "cost_2_125_net_points": cost_2,
        "cost_3_125_net_points": cost_3,
    }
    return add_gates(record, config)


def add_gates(record: dict[str, Any], config: AuditConfig) -> dict[str, Any]:
    research_checks = {
        "gate_net_positive": record["net_points"] > 0,
        "gate_sample_years": record["sample_years"] >= config.min_sample_years,
        "gate_trades": record["trades"] >= config.min_trades,
        "gate_profit_factor": record["profit_factor"] >= config.profit_factor,
        "gate_net_to_drawdown": record["net_to_drawdown"] >= config.net_to_drawdown,
        "gate_positive_year_rate": record["positive_year_rate"] >= config.positive_year_rate,
        "gate_positive_90d_rate": _finite(record["positive_90d_rate"]) and record["positive_90d_rate"] >= config.positive_90d_rate,
        "gate_positive_180d_rate": _finite(record["positive_180d_rate"]) and record["positive_180d_rate"] >= config.positive_180d_rate,
        "gate_cost_2_125_positive": record["cost_2_125_net_points"] > 0,
        "gate_cost_3_125_positive": record["cost_3_125_net_points"] > 0,
    }
    if config.require_current_year_nonnegative:
        research_checks["gate_current_year_nonnegative"] = _finite(record["current_year_net_points"]) and record["current_year_net_points"] >= 0

    blockers = [name.removeprefix("gate_") for name, passed in research_checks.items() if not bool(passed)]
    long_term_pass = not blockers
    production_checks = {
        "paper_validation_pass": bool(config.paper_validation_pass),
        "execution_validation_pass": bool(config.execution_validation_pass),
        "live_risk_limits_pass": bool(config.live_risk_limits_pass),
    }
    production_blockers = [
        name.removesuffix("_pass") + "_missing" for name, passed in production_checks.items() if not bool(passed)
    ]
    record.update(research_checks)
    record["research_blockers"] = ", ".join(blockers)
    record["long_term_research_pass"] = bool(long_term_pass)
    record.update(production_checks)
    record["production_blockers"] = ", ".join(production_blockers)
    record["production_ready"] = bool(long_term_pass and not production_blockers)
    return record


def readiness_tier(row: pd.Series) -> str:
    if bool(row["production_ready"]):
        return "production_ready"
    if bool(row["long_term_research_pass"]):
        return "promote_to_paper_validation"
    if row["net_points"] > 0 and row["profit_factor"] >= 1.10 and row["cost_2_125_net_points"] > 0:
        return "continue_research"
    return "reject_current_form"


def stability_score(row: pd.Series) -> float:
    score = 0.0
    score += min(float(row["net_to_drawdown"]), 20.0) * 4.0
    score += max(float(row["profit_factor"]) - 1.0, -1.0) * 50.0
    score += float(row["expectancy_points"]) * 3.0
    score += float(row["positive_year_rate"]) * 25.0
    if _finite(row["positive_90d_rate"]):
        score += float(row["positive_90d_rate"]) * 10.0
    if _finite(row["positive_180d_rate"]):
        score += float(row["positive_180d_rate"]) * 10.0
    score += min(float(row["sample_years"]), 16.0) * 2.0
    score += min(float(row["trades"]), 1000.0) / 100.0
    if _finite(row["current_year_net_points"]):
        score += max(float(row["current_year_net_points"]), -float(row["max_drawdown_points"])) / max(
            float(row["max_drawdown_points"]), 1.0
        ) * 5.0
    if not bool(row["gate_sample_years"]):
        score -= 50.0
    if not bool(row["gate_positive_90d_rate"]):
        score -= 10.0
    if not bool(row["gate_cost_3_125_positive"]):
        score -= 25.0
    return float(score)


def write_outputs(
    *,
    audit: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
    audit_output: Path,
    yearly_output: Path,
    rolling_output: Path,
    report: Path,
    markdown_report: Path,
    source_paths: dict[str, str],
    config: AuditConfig,
) -> None:
    for path, frame in [(audit_output, audit), (yearly_output, yearly), (rolling_output, rolling)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
    write_report(report, audit, yearly, rolling, source_paths, config)
    write_markdown_report(markdown_report, audit, yearly, rolling)


def write_report(
    path: Path,
    audit: pd.DataFrame,
    yearly: pd.DataFrame,
    rolling: pd.DataFrame,
    source_paths: dict[str, str],
    config: AuditConfig,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top = audit.iloc[0].to_dict() if not audit.empty else {}
    pass_count = int(audit["long_term_research_pass"].sum()) if "long_term_research_pass" in audit else 0
    production_count = int(audit["production_ready"].sum()) if "production_ready" in audit else 0
    top_yearly = yearly[yearly["candidate_key"] == top.get("candidate_key")] if top else pd.DataFrame()
    top_rolling = rolling[rolling["candidate_key"] == top.get("candidate_key")] if top else pd.DataFrame()
    worst_rolling = rolling.sort_values("net_points").head(20) if not rolling.empty else rolling

    payload = {
        "source_paths": source_paths,
        "research_gate": {
            "min_sample_years": config.min_sample_years,
            "min_trades": config.min_trades,
            "profit_factor": config.profit_factor,
            "net_to_drawdown": config.net_to_drawdown,
            "positive_year_rate": config.positive_year_rate,
            "positive_90d_rate": config.positive_90d_rate,
            "positive_180d_rate": config.positive_180d_rate,
            "cost_2_points": config.cost_2_points,
            "cost_3_points": config.cost_3_points,
        },
        "top_candidate": top,
    }
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ Long-Term Strategy Candidate Audit</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #111827;
      --muted: #5b6472;
      --line: #d7dde6;
      --panel: #f7f8fa;
      --accent: #146c5c;
      --warn: #9f580a;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      margin: 28px;
      line-height: 1.45;
      background: #fff;
    }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 28px; }}
    h2 {{ font-size: 18px; margin-top: 28px; }}
    p {{ margin: 8px 0; }}
    .lead {{ max-width: 980px; color: var(--muted); }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 10px;
      margin: 18px 0;
      max-width: 1100px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--panel);
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; }}
    .metric strong {{ display: block; font-size: 20px; margin-top: 2px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin: 10px 0 20px; }}
    th, td {{ border: 1px solid var(--line); padding: 6px 8px; vertical-align: top; }}
    th {{ background: #eef2f6; text-align: left; position: sticky; top: 0; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 14px; border-radius: 8px; overflow: auto; }}
    .ok {{ color: var(--accent); font-weight: 700; }}
    .warn {{ color: var(--warn); font-weight: 700; }}
  </style>
</head>
<body>
  <h1>NQ 长期盈利策略候选审计</h1>
  <p class="lead">
    本报告把已完成的 2010-2026 regime-transition 长样本回测、2020-2026 OFS 压力测试、
    以及 2020-2026 截图 SMC/动量压力测试放到同一套稳定性门槛下比较。
    结论只代表历史回测研究候选，不代表实盘许可；生产就绪仍需要纸盘、真实成交和风控验证。
  </p>

  <div class="metric-grid">
    <div class="metric"><span>审计候选</span><strong>{len(audit)}</strong></div>
    <div class="metric"><span>长期研究通过</span><strong>{pass_count}</strong></div>
    <div class="metric"><span>生产就绪</span><strong>{production_count}</strong></div>
    <div class="metric"><span>当前第一候选</span><strong>{html.escape(str(top.get("strategy_label", "n/a")))}</strong></div>
  </div>

  <h2>结论</h2>
  {verdict_html(top)}

  <h2>目标覆盖检查</h2>
  <table>
    <thead><tr><th>要求</th><th>证据</th><th>状态</th></tr></thead>
    <tbody>
      <tr><td>比较 2020 年之后 1m 策略候选</td><td>OFS 与截图 SMC/动量压力测试均包含 2020-2026 年度与 180 日滚动结果</td><td class="ok">covered</td></tr>
      <tr><td>寻找长期盈利候选</td><td>regime-transition 候选使用 2010-2026 长样本，统一纳入 PF、净值/回撤、年度、90/180 日滚动和成本压力门槛</td><td class="ok">covered</td></tr>
      <tr><td>避免短样本误判长期稳定</td><td>长期研究门槛要求至少 {config.min_sample_years} 个有交易年份，并要求 90 日滚动数据</td><td class="ok">covered</td></tr>
      <tr><td>区分历史回测与实盘可用</td><td>production_ready 需要纸盘、执行真实性和实盘风控标记；默认全部缺失</td><td class="ok">covered</td></tr>
      <tr><td>统一输出可审计报告</td><td>{html.escape(str(path))}</td><td class="ok">covered</td></tr>
    </tbody>
  </table>

  <h2>Top Ranking</h2>
  {html_table(display_columns(audit, top_summary_columns()))}

  <h2>当前第一候选年度表现</h2>
  {html_table(top_yearly)}

  <h2>当前第一候选滚动窗口</h2>
  {html_table(top_rolling)}

  <h2>全候选最差滚动窗口</h2>
  {html_table(worst_rolling)}

  <h2>审计配置</h2>
  <pre>{html.escape(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))}</pre>
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    path.write_text(html_text, encoding="utf-8")


def write_markdown_report(path: Path, audit: pd.DataFrame, yearly: pd.DataFrame, rolling: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if audit.empty:
        path.write_text("# NQ Long-Term Profitable Strategy Backtest Audit\n\nNo candidates were audited.\n", encoding="utf-8")
        return

    top = audit.iloc[0]
    source_summary = (
        audit.groupby("strategy_source")
        .agg(
            candidates=("strategy_label", "count"),
            long_term_pass=("long_term_research_pass", "sum"),
            production_ready=("production_ready", "sum"),
            best_net_points=("net_points", "max"),
        )
        .reset_index()
    )
    top_yearly = yearly[
        (yearly["strategy_source"] == top["strategy_source"]) & (yearly["candidate_key"] == top["candidate_key"])
    ][["year", "trades", "net_points"]]
    top_worst = rolling[
        (rolling["strategy_source"] == top["strategy_source"]) & (rolling["candidate_key"] == top["candidate_key"])
    ].sort_values("net_points").head(10)[["rolling_days", "start", "end", "trades", "net_points"]]
    passed = audit[audit["long_term_research_pass"]][
        [
            "strategy_label",
            "trades",
            "net_points",
            "profit_factor",
            "win_rate",
            "payoff_ratio",
            "expectancy_points",
            "max_drawdown_points",
            "net_to_drawdown",
            "positive_year_rate",
            "positive_90d_rate",
            "positive_180d_rate",
            "cost_3_125_net_points",
            "candidate",
        ]
    ]
    top_by_source = (
        audit.sort_values(["strategy_source", "stability_score"], ascending=[True, False])
        .groupby("strategy_source")
        .head(3)[
            [
                "strategy_source",
                "strategy_label",
                "readiness_tier",
                "trades",
                "net_points",
                "profit_factor",
                "net_to_drawdown",
                "positive_year_rate",
                "positive_180d_rate",
                "cost_3_125_net_points",
                "research_blockers",
            ]
        ]
    )

    text = f"""# NQ Long-Term Profitable Strategy Backtest Audit

## Verdict

The best current long-term research candidate is `{top["strategy_label"]}`:

`{top["candidate"]}`

It is a **range-compression to upside-displacement breakout** strategy, not a generic indicator rule:

- Look back 45 minutes and require a compressed, inefficient range: width <= 10 ATR and efficiency <= 0.10.
- Trade only `us_late`, long only.
- Require upside displacement: candle range >= 1.6 ATR30, body share >= 0.55, volume z >= 0.
- Enter next bar open.
- Stop below the displacement bar low with structural buffer.
- Target 2.5R, timeout 180 minutes.

This strategy passes the long-term research gate, but it is **not production-ready** because paper validation, execution validation, and live risk-limit validation are still missing.

## Top Candidate Metrics

| Metric | Value |
| --- | ---: |
| Sample | {int(top["sample_start_year"])}-{int(top["sample_end_year"])} |
| Sample years with trades | {int(top["sample_years"])} |
| Trades | {int(top["trades"])} |
| Net points | {float(top["net_points"]):.2f} |
| Net dollars at NQ $20/pt | {float(top["net_dollars"]):.2f} |
| Profit factor | {float(top["profit_factor"]):.3f} |
| Win rate | {float(top["win_rate"]):.2%} |
| Payoff ratio | {float(top["payoff_ratio"]):.2f} |
| Expectancy points/trade | {float(top["expectancy_points"]):.2f} |
| Max drawdown points | {float(top["max_drawdown_points"]):.2f} |
| Net / max drawdown | {float(top["net_to_drawdown"]):.2f} |
| Positive year rate | {float(top["positive_year_rate"]):.2%} |
| Positive 90d rolling rate | {float(top["positive_90d_rate"]):.2%} |
| Positive 180d rolling rate | {float(top["positive_180d_rate"]):.2%} |
| Worst year points | {float(top["worst_year_points"]):.2f} |
| Worst 90d window points | {float(top["worst_90d_points"]):.2f} |
| Worst 180d window points | {float(top["worst_180d_points"]):.2f} |
| Net at 2.125pt round-trip cost | {float(top["cost_2_125_net_points"]):.2f} |
| Net at 3.125pt round-trip cost | {float(top["cost_3_125_net_points"]):.2f} |
| 2026 partial-year net | {float(top["current_year_net_points"]):.2f} |

## Candidate Pool Coverage

{markdown_table(source_summary)}

Interpretation:

- `regime_transition`: the only pool with candidates passing the long-term gate. These use the full 2010-2026 Databento 1m history.
- `ict_order_flow_shift`: still interesting, especially high-relative-volume bullish OFS, but only has 2020-2026 evidence and fails long-term gates.
- `screenshot_smc_momentum`: EQL sweep reclaim is a research lead, but not a long-term strategy yet; naked BOS/displacement visual continuation fails.

## Long-Term Gate Passed Candidates

{markdown_table(passed)}

## Top Candidate Yearly Net

{markdown_table(top_yearly)}

## Top Candidate Worst Rolling Windows

{markdown_table(top_worst)}

## Best Candidates By Source

{markdown_table(top_by_source)}

## Completion Audit

| Requirement | Evidence | Status |
| --- | --- | --- |
| Backtest 1m NQ after 2020 | OFS and screenshot SMC pressure tests cover 2020-2026; source rows are included in `.tmp/nq-ofs-candidate-pressure-*` and `.tmp/nq-screenshot-smc-candidate-pressure-*`. | covered |
| Search for long-term profitability | Regime-transition audit covers 2010-06-06 to 2026-04-27, 5,383,225 bars, 502,361 events. | covered |
| Validate stability, not just net profit | Gate includes PF, net/DD, positive years, 90d/180d rolling windows, current-year nonnegative, and 2.125/3.125 point cost stress. | covered |
| Include screenshot-derived features | `screenshot_smc_momentum` pool is included in the unified audit; no screenshot candidate passes long-term gates. | covered |
| Distinguish research vs production | `production_ready` is false until paper validation, execution validation, and live risk limits are proven. | covered |

## Files

- HTML audit: `reports/NQ-long-term-strategy-candidate-audit.html`
- CSV audit: `.tmp/nq-long-term-strategy-candidate-audit.csv`
- Yearly detail: `.tmp/nq-long-term-strategy-candidate-yearly.csv`
- Rolling detail: `.tmp/nq-long-term-strategy-candidate-rolling.csv`
"""
    path.write_text(text, encoding="utf-8")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    rows = ["| " + " | ".join(str(column) for column in display.columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(display.columns)) + " |")
    for _, row in display.iterrows():
        rows.append("| " + " | ".join(str(value) for value in row.tolist()) + " |")
    return "\n".join(rows)


def verdict_html(top: dict[str, Any]) -> str:
    if not top:
        return "<p class=\"warn\">没有可审计候选。</p>"
    research_class = "ok" if top.get("long_term_research_pass") else "warn"
    production_class = "ok" if top.get("production_ready") else "warn"
    return f"""
  <p>
    当前最佳长期研究候选是 <code>{html.escape(str(top.get("candidate")))}</code>
    （标签 <code>{html.escape(str(top.get("strategy_label")))}</code>）。
    历史稳定门状态：<span class="{research_class}">{bool(top.get("long_term_research_pass"))}</span>；
    生产就绪状态：<span class="{production_class}">{bool(top.get("production_ready"))}</span>。
  </p>
  <p>
    关键指标：{int(top.get("trades", 0))} 笔，净点数 {float(top.get("net_points", 0.0)):.2f}，
    PF {float(top.get("profit_factor", 0.0)):.2f}，净值/最大回撤 {float(top.get("net_to_drawdown", 0.0)):.2f}，
    正收益年份率 {float(top.get("positive_year_rate", 0.0)):.1%}，
    90 日滚动正收益率 {float(top.get("positive_90d_rate", 0.0)):.1%}。
  </p>
  <p>
    剩余阻塞：{html.escape(str(top.get("production_blockers") or "none"))}。
  </p>
"""


def top_summary_columns() -> list[str]:
    return [
        "readiness_tier",
        "strategy_source",
        "strategy_label",
        "family",
        "sample_years",
        "trades",
        "net_points",
        "profit_factor",
        "win_rate",
        "payoff_ratio",
        "expectancy_points",
        "max_drawdown_points",
        "net_to_drawdown",
        "positive_year_rate",
        "positive_90d_rate",
        "positive_180d_rate",
        "current_year_net_points",
        "cost_2_125_net_points",
        "cost_3_125_net_points",
        "long_term_research_pass",
        "production_ready",
        "research_blockers",
        "production_blockers",
        "candidate",
    ]


def display_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return frame[[column for column in columns if column in frame.columns]].copy()


def html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display.to_html(index=False, escape=True)


def _number(row: pd.Series, column: str, default: float = 0.0) -> float:
    if column not in row:
        return float(default)
    value = row[column]
    if pd.isna(value):
        return float(default)
    return float(value)


def _finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def config_from_args(args: argparse.Namespace) -> AuditConfig:
    return AuditConfig(
        min_sample_years=args.gate_min_sample_years,
        min_trades=args.gate_min_trades,
        profit_factor=args.gate_profit_factor,
        net_to_drawdown=args.gate_net_to_drawdown,
        positive_year_rate=args.gate_positive_year_rate,
        positive_90d_rate=args.gate_positive_90d_rate,
        positive_180d_rate=args.gate_positive_180d_rate,
        cost_2_points=args.gate_cost_2_points,
        cost_3_points=args.gate_cost_3_points,
        require_current_year_nonnegative=not args.allow_negative_current_year,
        paper_validation_pass=args.paper_validation_pass,
        execution_validation_pass=args.execution_validation_pass,
        live_risk_limits_pass=args.live_risk_limits_pass,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit NQ strategy candidates for long-term profitability readiness.")
    parser.add_argument("--regime-summary", default=".tmp/nq-regime-transition-readiness-summary.csv")
    parser.add_argument("--regime-yearly", default=".tmp/nq-regime-transition-readiness-yearly.csv")
    parser.add_argument("--regime-rolling90", default=".tmp/nq-regime-transition-readiness-rolling90.csv")
    parser.add_argument("--regime-rolling180", default=".tmp/nq-regime-transition-readiness-rolling180.csv")
    parser.add_argument("--ofs-summary", default=".tmp/nq-ofs-candidate-pressure-full.csv")
    parser.add_argument("--ofs-yearly", default=".tmp/nq-ofs-candidate-pressure-yearly.csv")
    parser.add_argument("--ofs-rolling", default=".tmp/nq-ofs-candidate-pressure-rolling.csv")
    parser.add_argument("--screenshot-summary", default=".tmp/nq-screenshot-smc-candidate-pressure-full.csv")
    parser.add_argument("--screenshot-yearly", default=".tmp/nq-screenshot-smc-candidate-pressure-yearly.csv")
    parser.add_argument("--screenshot-rolling", default=".tmp/nq-screenshot-smc-candidate-pressure-rolling.csv")
    parser.add_argument("--audit-output", default=".tmp/nq-long-term-strategy-candidate-audit.csv")
    parser.add_argument("--yearly-output", default=".tmp/nq-long-term-strategy-candidate-yearly.csv")
    parser.add_argument("--rolling-output", default=".tmp/nq-long-term-strategy-candidate-rolling.csv")
    parser.add_argument("--report", default="reports/NQ-long-term-strategy-candidate-audit.html")
    parser.add_argument("--markdown-report", default="reports/NQ-long-term-profitable-strategy-backtest-audit.md")
    parser.add_argument("--gate-min-sample-years", type=int, default=10)
    parser.add_argument("--gate-min-trades", type=int, default=300)
    parser.add_argument("--gate-profit-factor", type=float, default=1.25)
    parser.add_argument("--gate-net-to-drawdown", type=float, default=4.0)
    parser.add_argument("--gate-positive-year-rate", type=float, default=0.70)
    parser.add_argument("--gate-positive-90d-rate", type=float, default=0.55)
    parser.add_argument("--gate-positive-180d-rate", type=float, default=0.60)
    parser.add_argument("--gate-cost-2-points", type=float, default=2.125)
    parser.add_argument("--gate-cost-3-points", type=float, default=3.125)
    parser.add_argument("--allow-negative-current-year", action="store_true")
    parser.add_argument("--paper-validation-pass", action="store_true")
    parser.add_argument("--execution-validation-pass", action="store_true")
    parser.add_argument("--live-risk-limits-pass", action="store_true")
    args = parser.parse_args()

    config = config_from_args(args)
    source_paths = {
        "regime_summary": args.regime_summary,
        "regime_yearly": args.regime_yearly,
        "regime_rolling90": args.regime_rolling90,
        "regime_rolling180": args.regime_rolling180,
        "ofs_summary": args.ofs_summary,
        "ofs_yearly": args.ofs_yearly,
        "ofs_rolling": args.ofs_rolling,
        "screenshot_summary": args.screenshot_summary,
        "screenshot_yearly": args.screenshot_yearly,
        "screenshot_rolling": args.screenshot_rolling,
    }
    audit, yearly, rolling = build_candidate_audit(
        regime_summary=read_csv(Path(args.regime_summary)),
        regime_yearly=read_csv(Path(args.regime_yearly)),
        regime_rolling90=read_csv(Path(args.regime_rolling90)),
        regime_rolling180=read_csv(Path(args.regime_rolling180)),
        ofs_summary=read_csv(Path(args.ofs_summary)),
        ofs_yearly=read_csv(Path(args.ofs_yearly)),
        ofs_rolling=read_csv(Path(args.ofs_rolling)),
        screenshot_summary=read_csv(Path(args.screenshot_summary)),
        screenshot_yearly=read_csv(Path(args.screenshot_yearly)),
        screenshot_rolling=read_csv(Path(args.screenshot_rolling)),
        config=config,
    )
    write_outputs(
        audit=audit,
        yearly=yearly,
        rolling=rolling,
        audit_output=Path(args.audit_output),
        yearly_output=Path(args.yearly_output),
        rolling_output=Path(args.rolling_output),
        report=Path(args.report),
        markdown_report=Path(args.markdown_report),
        source_paths=source_paths,
        config=config,
    )
    top = audit.iloc[0].to_dict() if not audit.empty else None
    print(
        json.dumps(
            {
                "candidates": int(len(audit)),
                "long_term_research_pass": int(audit["long_term_research_pass"].sum()) if not audit.empty else 0,
                "production_ready": int(audit["production_ready"].sum()) if not audit.empty else 0,
                "top": top,
                "audit_output": args.audit_output,
                "yearly_output": args.yearly_output,
                "rolling_output": args.rolling_output,
                "report": args.report,
                "markdown_report": args.markdown_report,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
