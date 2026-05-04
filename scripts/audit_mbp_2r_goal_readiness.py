from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from tradingagents.config.env import load_project_env
from tradingagents.execution import PaperValidationGateConfig, summarize_paper_audits


def _csv_summary(path: Path, pass_column: str) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "rows": 0, "passes": 0}
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return {"path": str(path), "exists": True, "rows": 0, "passes": 0}
    passes = int(frame[pass_column].sum()) if pass_column in frame.columns and not frame.empty else 0
    return {"path": str(path), "exists": True, "rows": int(len(frame)), "passes": passes}


def _date_span_from_feature_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "rows": 0, "start": None, "end": None, "calendar_days": 0}
    cache = pd.read_pickle(path)
    frames = [frame for frame in cache.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return {"path": str(path), "exists": True, "rows": 0, "start": None, "end": None, "calendar_days": 0}
    features = pd.concat(frames, ignore_index=True)
    timestamps = pd.to_datetime(features["ts"], utc=True)
    start = timestamps.min()
    end = timestamps.max()
    return {
        "path": str(path),
        "exists": True,
        "rows": int(len(features)),
        "start": str(start),
        "end": str(end),
        "calendar_days": int((end.date() - start.date()).days) + 1,
    }


def audit_goal(args: argparse.Namespace) -> dict[str, Any]:
    load_project_env()
    blackbox = _csv_summary(Path(args.blackbox_csv), "blackbox_pass")
    expanded = _csv_summary(Path(args.expanded_csv), "blackbox_pass")
    label_rules = _csv_summary(Path(args.label_rules_csv), "blackbox_pass")
    purged = _csv_summary(Path(args.purged_csv), "blackbox_pass")
    feasibility = _csv_summary(Path(args.feasibility_bins_csv), "oracle_60wr_2r_pass")
    pair_feasibility = _csv_summary(Path(args.pair_feasibility_bins_csv), "oracle_60wr_2r_pass")
    closest = _csv_summary(Path(args.closest_walkforward_csv), "blackbox_pass")
    model_walkforward = _csv_summary(Path(args.model_walkforward_csv), "blackbox_pass")
    state_walkforward = _csv_summary(Path(args.state_walkforward_csv), "blackbox_pass")
    bar_walkforward = _csv_summary(Path(args.bar_walkforward_csv), "blackbox_pass")
    data_span = _date_span_from_feature_cache(Path(args.features_cache))
    paper = summarize_paper_audits(
        agent_audit_path=args.agent_audit,
        ibkr_audit_path=args.ibkr_audit,
        gate_config=PaperValidationGateConfig(
            min_ibkr_ready=args.min_ibkr_ready,
            min_ibkr_submitted=args.min_ibkr_submitted,
            min_paper_outcomes=args.min_paper_outcomes,
            min_paper_net_points=args.min_paper_net_points,
            min_paper_win_rate=args.min_paper_win_rate,
            max_consecutive_losses=args.max_consecutive_losses,
            max_allowed_blocker_count=args.max_allowed_blocker_count,
        ),
    )
    checks = {
        "strict_2r_blackbox": blackbox,
        "expanded_2r_blackbox": expanded,
        "label_rule_2r_blackbox": label_rules,
        "purged_walkforward_2r": purged,
        "single_feature_feasibility": feasibility,
        "pair_feature_feasibility": pair_feasibility,
        "closest_pair_neighborhood": closest,
        "model_walkforward_2r": model_walkforward,
        "state_walkforward_2r": state_walkforward,
        "bar_only_walkforward_2r": bar_walkforward,
    }
    total_passes = sum(int(value["passes"]) for value in checks.values())
    blockers = []
    if total_passes <= 0:
        blockers.append("no_60wr_2r_blackbox_candidate")
    if data_span["calendar_days"] < args.min_history_days:
        blockers.append(f"history_span_below_min:{data_span['calendar_days']}<{args.min_history_days}")
    if not os.getenv("DATABENTO_API_KEY"):
        blockers.append("databento_api_key_missing")
    if not os.getenv("IBKR_ACCOUNT"):
        blockers.append("ibkr_account_missing")
    paper_gate = paper["validation_gate"]
    if paper_gate["status"] != "pass":
        blockers.extend(f"paper_validation:{reason}" for reason in paper_gate["blockers"])
    checklist = [
        {
            "requirement": ">=60% win rate with fixed 2R",
            "evidence": checks,
            "status": "pass" if total_passes > 0 else "blocked",
        },
        {
            "requirement": "black-box / purged validation",
            "evidence": {
                "strict_split_rows": blackbox["rows"],
                "purged_rows": purged["rows"],
                "closest_followup_rows": closest["rows"],
                "model_walkforward_rows": model_walkforward["rows"],
                "state_walkforward_rows": state_walkforward["rows"],
                "bar_only_walkforward_rows": bar_walkforward["rows"],
            },
            "status": "pass" if total_passes > 0 and (purged["passes"] > 0 or closest["passes"] > 0 or blackbox["passes"] > 0) else "blocked",
        },
        {
            "requirement": "long-term evidence",
            "evidence": data_span,
            "status": "pass" if data_span["calendar_days"] >= args.min_history_days else "blocked",
        },
        {
            "requirement": "direct live/paper readiness",
            "evidence": {
                "databento_api_key_present": bool(os.getenv("DATABENTO_API_KEY")),
                "ibkr_account_present": bool(os.getenv("IBKR_ACCOUNT")),
                "paper_gate": paper_gate,
            },
            "status": "pass" if paper_gate["status"] == "pass" and os.getenv("IBKR_ACCOUNT") else "blocked",
        },
    ]
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "total_2r_passes": total_passes,
        "checklist": checklist,
        "data_span": data_span,
        "paper_summary": paper,
        "checks": checks,
    }


def _write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NQM6 60% 2R Goal Readiness Audit",
        "",
        f"Status: `{result['status']}`",
        "",
        "## Blockers",
        "",
    ]
    if result["blockers"]:
        lines.extend(f"- `{blocker}`" for blocker in result["blockers"])
    else:
        lines.append("_No blockers._")
    lines.extend(["", "## Checklist", ""])
    for item in result["checklist"]:
        lines.extend(
            [
                f"### {item['requirement']}",
                "",
                f"Status: `{item['status']}`",
                "",
                "```json",
                json.dumps(item["evidence"], indent=2, sort_keys=True, default=str),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Raw Summary",
            "",
            "```json",
            json.dumps(
                {
                    "total_2r_passes": result["total_2r_passes"],
                    "data_span": result["data_span"],
                    "paper_validation_gate": result["paper_summary"]["validation_gate"],
                    "checks": result["checks"],
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit readiness for the explicit 60% win-rate fixed-2R live strategy goal.")
    parser.add_argument("--features-cache", default=".tmp/mbp-history-features-cache.pkl")
    parser.add_argument("--blackbox-csv", default=".tmp/mbp-2r-blackbox.csv")
    parser.add_argument("--expanded-csv", default=".tmp/mbp-2r-expanded-diagnostics-merged.csv")
    parser.add_argument("--label-rules-csv", default=".tmp/mbp-2r-label-rules-merged.csv")
    parser.add_argument("--purged-csv", default=".tmp/mbp-2r-purged-walkforward-all-core.csv")
    parser.add_argument("--feasibility-bins-csv", default=".tmp/mbp-2r-feasibility-representative-feature-bins.csv")
    parser.add_argument("--pair-feasibility-bins-csv", default=".tmp/mbp-2r-feasibility-pair-representative-bins.csv")
    parser.add_argument("--closest-walkforward-csv", default=".tmp/mbp-2r-purged-walkforward-us-late-pair-neighborhood.csv")
    parser.add_argument("--model-walkforward-csv", default=".tmp/mbp-2r-model-walkforward.csv")
    parser.add_argument("--state-walkforward-csv", default=".tmp/mbp-2r-state-walkforward-focused.csv")
    parser.add_argument("--bar-walkforward-csv", default=".tmp/nq-bar-2r-walkforward-discovery-small.csv")
    parser.add_argument("--agent-audit", default=".tmp/agent-gate-audit.jsonl")
    parser.add_argument("--ibkr-audit", default=".tmp/ibkr-paper-audit.jsonl")
    parser.add_argument("--output", default=".tmp/mbp-2r-goal-readiness-audit.json")
    parser.add_argument("--report", default="reports/NQM6-mbp-2r-goal-readiness-audit.md")
    parser.add_argument("--min-history-days", type=int, default=365)
    parser.add_argument("--min-ibkr-ready", type=int, default=1)
    parser.add_argument("--min-ibkr-submitted", type=int, default=1)
    parser.add_argument("--min-paper-outcomes", type=int, default=20)
    parser.add_argument("--min-paper-net-points", type=float, default=0.0)
    parser.add_argument("--min-paper-win-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=4)
    parser.add_argument("--max-allowed-blocker-count", type=int, default=0)
    args = parser.parse_args()

    result = audit_goal(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(Path(args.report), result)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
