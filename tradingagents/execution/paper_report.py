from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .agent_gate import outcome_metrics


@dataclass(frozen=True)
class PaperValidationGateConfig:
    min_ibkr_ready: int = 1
    min_ibkr_submitted: int = 1
    min_paper_outcomes: int = 20
    min_paper_net_points: float = 0.0
    min_paper_win_rate: float = 45.0
    max_consecutive_losses: int = 4
    max_allowed_blocker_count: int = 0


def summarize_paper_audits(
    *,
    agent_audit_path: Path | str = ".tmp/agent-gate-audit.jsonl",
    ibkr_audit_path: Path | str = ".tmp/ibkr-paper-audit.jsonl",
    gate_config: PaperValidationGateConfig | None = None,
    strategy_id: str | None = None,
) -> dict[str, Any]:
    agent_events = _read_jsonl(Path(agent_audit_path))
    ibkr_events = _read_jsonl(Path(ibkr_audit_path))
    gate_reviews = [
        event
        for event in agent_events
        if event.get("event_type") == "agent_strategy_gate" and _matches_strategy(event, strategy_id)
    ]
    outcomes = [
        event
        for event in agent_events
        if event.get("event_type") == "agent_gate_paper_outcome" and _matches_strategy(event, strategy_id)
    ]
    preflights = [event for event in ibkr_events if event.get("event_type") == "ibkr_paper_preflight"]
    submitted = [
        event
        for event in ibkr_events
        if event.get("status") == "submitted" and _matches_strategy(event, strategy_id)
    ]
    blocked = [
        event
        for event in ibkr_events
        if (str(event.get("status", "")).endswith("blocked") or event.get("status") == "risk_rejected")
        and _matches_strategy(event, strategy_id)
    ]
    latest_preflight = preflights[-1] if preflights else {}
    current_missing_requirements = latest_preflight.get("readiness", {}).get("missing_requirements", [])
    latest_account = latest_preflight.get("account", {}) if isinstance(latest_preflight.get("account", {}), dict) else {}
    readiness_reasons = _top_counts(
        reason
        for event in preflights
        for reason in event.get("readiness", {}).get("missing_requirements", [])
    )
    gate_reasons = _top_counts(
        reason
        for event in gate_reviews
        for reason in event.get("reasons", [])
    )
    metrics = outcome_metrics(outcomes)
    summary = {
        "agent_reviews": len(gate_reviews),
        "agent_approved": sum(1 for event in gate_reviews if event.get("passed") is True),
        "agent_rejected": sum(1 for event in gate_reviews if event.get("passed") is False),
        "agent_rejection_reasons": gate_reasons,
        "paper_outcomes": metrics,
        "ibkr_preflights": len(preflights),
        "ibkr_ready": sum(1 for event in preflights if event.get("readiness", {}).get("status") == "ready"),
        "ibkr_blocked": len(blocked),
        "ibkr_submitted": len(submitted),
        "ibkr_readiness_reasons": readiness_reasons,
        "ibkr_current_ready": 1 if latest_preflight.get("readiness", {}).get("status") == "ready" else 0,
        "ibkr_current_readiness_reasons": _top_counts(current_missing_requirements),
        "ibkr_current_account": latest_account.get("account"),
        "ibkr_current_account_paper": bool(latest_account.get("paper")),
        "strategy_id_filter": strategy_id,
    }
    summary["validation_gate"] = evaluate_paper_validation_gate(summary, config=gate_config)
    return summary


def evaluate_paper_validation_gate(
    summary: dict[str, Any],
    *,
    config: PaperValidationGateConfig | None = None,
) -> dict[str, Any]:
    config = config or PaperValidationGateConfig()
    outcomes = summary.get("paper_outcomes", {}) or {}
    readiness_counts = _parse_counts(str(summary.get("ibkr_current_readiness_reasons", "") or ""))
    submitted = int(summary.get("ibkr_submitted", 0) or 0)
    ready = int(summary.get("ibkr_current_ready", summary.get("ibkr_ready", 0)) or 0)
    paper_trades = int(outcomes.get("trades", 0) or 0)
    paper_net = float(outcomes.get("net_points", 0.0) or 0.0)
    paper_win_rate = float(outcomes.get("win_rate", 0.0) or 0.0)
    consecutive_losses = int(outcomes.get("consecutive_losses", 0) or 0)
    blocker_count = sum(readiness_counts.values())
    blockers = []
    warnings = []
    if ready < config.min_ibkr_ready:
        blockers.append(f"ibkr_ready_below_min:{ready}<{config.min_ibkr_ready}")
    if submitted < config.min_ibkr_submitted:
        blockers.append(f"ibkr_submitted_below_min:{submitted}<{config.min_ibkr_submitted}")
    if paper_trades < config.min_paper_outcomes:
        blockers.append(f"paper_outcomes_below_min:{paper_trades}<{config.min_paper_outcomes}")
    if paper_net < config.min_paper_net_points:
        blockers.append(f"paper_net_points_below_min:{paper_net:.4f}<{config.min_paper_net_points:.4f}")
    if paper_trades > 0 and paper_win_rate < config.min_paper_win_rate:
        blockers.append(f"paper_win_rate_below_min:{paper_win_rate:.2f}<{config.min_paper_win_rate:.2f}")
    if consecutive_losses > config.max_consecutive_losses:
        blockers.append(f"consecutive_losses_above_max:{consecutive_losses}>{config.max_consecutive_losses}")
    if blocker_count > config.max_allowed_blocker_count:
        blockers.append(f"readiness_blockers_above_max:{blocker_count}>{config.max_allowed_blocker_count}")
    if "market_data_not_ready" in readiness_counts:
        warnings.append("market_data_not_ready:IBKR market data is not order-ready")
    if "not_connected" in readiness_counts:
        warnings.append("not_connected:IBKR socket/API connection is not consistently available")
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "metrics": {
            "ibkr_ready": ready,
            "ibkr_submitted": submitted,
            "paper_outcomes": paper_trades,
            "paper_net_points": paper_net,
            "paper_win_rate": paper_win_rate,
            "consecutive_losses": consecutive_losses,
            "readiness_blocker_count": blocker_count,
        },
        "thresholds": {
            "min_ibkr_ready": config.min_ibkr_ready,
            "min_ibkr_submitted": config.min_ibkr_submitted,
            "min_paper_outcomes": config.min_paper_outcomes,
            "min_paper_net_points": config.min_paper_net_points,
            "min_paper_win_rate": config.min_paper_win_rate,
            "max_consecutive_losses": config.max_consecutive_losses,
            "max_allowed_blocker_count": config.max_allowed_blocker_count,
        },
    }


def paper_summary_frame(summary: dict[str, Any]) -> pd.DataFrame:
    flat = {}
    for key, value in summary.items():
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                if isinstance(child_value, dict):
                    for grandchild_key, grandchild_value in child_value.items():
                        flat[f"{key}_{child_key}_{grandchild_key}"] = _csv_value(grandchild_value)
                else:
                    flat[f"{key}_{child_key}"] = _csv_value(child_value)
        else:
            flat[key] = _csv_value(value)
    return pd.DataFrame([flat])


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _top_counts(values) -> str:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        if not key or key == "None":
            continue
        counts[key] = counts.get(key, 0) + 1
    return ", ".join(f"{key}={count}" for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8])


def _parse_counts(value: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in value.split(","):
        text = item.strip()
        if not text or "=" not in text:
            continue
        key, count = text.rsplit("=", 1)
        try:
            counts[key.strip()] = int(count)
        except ValueError:
            continue
    return counts


def _event_strategy_id(event: dict[str, Any]) -> str | None:
    strategy_id = event.get("strategy_id")
    if strategy_id:
        return str(strategy_id)
    intent = event.get("intent")
    if isinstance(intent, dict) and intent.get("strategy_id"):
        return str(intent["strategy_id"])
    return None


def _matches_strategy(event: dict[str, Any], strategy_id: str | None) -> bool:
    if strategy_id is None:
        return True
    return _event_strategy_id(event) == strategy_id


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return value
