from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def evaluate_parity(record: dict[str, Any], *, strategy_id: str, max_mismatch_rate: float, min_checked_signals: int) -> dict[str, Any]:
    if not record:
        return {
            "status": "blocked",
            "blockers": ["parity_file_missing_or_invalid"],
            "strategy_id": strategy_id,
        }
    record_strategy = str(record.get("strategy_id") or record.get("selected_alias") or "")
    checked = int(record.get("checked_signals") or record.get("signals_checked") or 0)
    mismatches = int(record.get("mismatches") or record.get("mismatch_count") or 0)
    mismatch_rate = float(record.get("mismatch_rate", mismatches / checked if checked else 1.0))
    explicit_status = str(record.get("status") or "").lower()
    blockers: list[str] = []
    if record_strategy and record_strategy != strategy_id:
        blockers.append(f"strategy_mismatch:{record_strategy}!={strategy_id}")
    if checked < min_checked_signals:
        blockers.append(f"checked_signals_below_min:{checked}<{min_checked_signals}")
    if mismatch_rate > max_mismatch_rate:
        blockers.append(f"mismatch_rate_above_max:{mismatch_rate:.4f}>{max_mismatch_rate:.4f}")
    if explicit_status and explicit_status not in {"pass", "passed", "ok"}:
        blockers.append(f"explicit_status_not_pass:{explicit_status}")
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "strategy_id": strategy_id,
        "record_strategy_id": record_strategy,
        "checked_signals": checked,
        "mismatches": mismatches,
        "mismatch_rate": mismatch_rate,
        "max_mismatch_rate": max_mismatch_rate,
        "min_checked_signals": min_checked_signals,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check dry-run parity before allowing NQ regime-transition IBKR submit.")
    parser.add_argument("--parity-file", default=".tmp/nq-regime-transition-parity.json")
    parser.add_argument("--strategy-id", default="optimized50_2r5_quality")
    parser.add_argument("--max-mismatch-rate", type=float, default=0.0)
    parser.add_argument("--min-checked-signals", type=int, default=1)
    args = parser.parse_args()

    result = evaluate_parity(
        load_json(Path(args.parity_file)),
        strategy_id=args.strategy_id,
        max_mismatch_rate=args.max_mismatch_rate,
        min_checked_signals=args.min_checked_signals,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
