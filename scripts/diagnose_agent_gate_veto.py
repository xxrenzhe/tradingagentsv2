from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tradingagents.config.env import load_project_env
from tradingagents.execution.agent_gate import BULLISH_RATINGS, BEARISH_RATINGS


EXECUTION_RISK_TOKENS = [
    "execution risk",
    "preflight",
    "market_data",
    "not_connected",
    "行情缺失",
    "连接问题",
    "执行风险",
]
THIN_EVIDENCE_TOKENS = [
    "evidence is too thin",
    "market evidence is too thin",
    "缺少",
    "证据",
    "太薄",
    "证据不足",
    "单一模型信号",
]


def main() -> int:
    load_project_env()
    parser = argparse.ArgumentParser(description="Diagnose why the most recent agent-gate event rejected a candidate.")
    parser.add_argument("--audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--strategy-id", default=None)
    args = parser.parse_args()

    event = _latest_gate_event(Path(args.audit), strategy_id=args.strategy_id)
    if event is None:
        print(json.dumps({"status": "missing", "reason": "no_agent_gate_event"}, indent=2, sort_keys=True))
        return 2
    diagnosis = diagnose_event(event)
    print(json.dumps(diagnosis, indent=2, sort_keys=True, default=str))
    return 0 if diagnosis["status"] == "agent_approved" else 2


def diagnose_event(event: dict) -> dict:
    intent = event.get("intent") if isinstance(event.get("intent"), dict) else {}
    action = str(intent.get("action", "")).upper()
    rating = str(event.get("rating", ""))
    final_decision = str(event.get("final_trade_decision", ""))
    context = str(event.get("candidate_trade_context", ""))
    reasons = list(event.get("reasons", []))
    direction_aligned = _direction_aligned(action, rating)
    veto_text = _has_veto_text(final_decision)
    execution_risk_matches = _matched_tokens(final_decision + "\n" + context, EXECUTION_RISK_TOKENS)
    thin_evidence_matches = _matched_tokens(final_decision + "\n" + context, THIN_EVIDENCE_TOKENS)
    primary_causes = []
    if "agent_vetoed_candidate" in reasons or veto_text:
        primary_causes.append("explicit_veto")
    if not direction_aligned:
        primary_causes.append("rating_direction_mismatch")
    if execution_risk_matches:
        primary_causes.append("execution_risk_context")
    if thin_evidence_matches:
        primary_causes.append("thin_market_evidence")
    return {
        "status": event.get("status", "unknown"),
        "passed": bool(event.get("passed")),
        "created_at": event.get("created_at"),
        "analysis_symbol": event.get("analysis_symbol"),
        "strategy_id": intent.get("strategy_id"),
        "action": action,
        "rating": rating,
        "direction_aligned": direction_aligned,
        "reasons": reasons,
        "primary_causes": primary_causes,
        "veto_text_detected": veto_text,
        "execution_risk_matches": execution_risk_matches,
        "thin_evidence_matches": thin_evidence_matches,
        "performance_guard": event.get("performance_guard", {}),
        "candidate_context_excerpt": _excerpt(context),
        "final_decision_excerpt": _excerpt(final_decision, limit=1200),
    }


def _latest_gate_event(path: Path, *, strategy_id: str | None) -> dict | None:
    if not path.exists():
        return None
    latest = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event_type") != "agent_strategy_gate":
                continue
            intent = event.get("intent") if isinstance(event.get("intent"), dict) else {}
            if strategy_id and intent.get("strategy_id") != strategy_id:
                continue
            latest = event
    return latest


def _direction_aligned(action: str, rating: str) -> bool:
    if action == "BUY":
        return rating in BULLISH_RATINGS
    if action == "SELL":
        return rating in BEARISH_RATINGS
    return False


def _has_veto_text(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ["veto", "reject", "do not trade", "do not submit", "avoid entry", "否决", "拒绝", "不应下单"])


def _matched_tokens(text: str, tokens: list[str]) -> list[str]:
    lower = text.lower()
    return [token for token in tokens if token.lower() in lower]


def _excerpt(text: str, *, limit: int = 800) -> str:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return normalized[:limit]


if __name__ == "__main__":
    raise SystemExit(main())
