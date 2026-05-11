from __future__ import annotations

import json
import sqlite3
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .backtest import ValidationResult
from .rules import TradingRule, rule_to_dict
from .segmentation import Segment


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class EvolutionMemory:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.initialize_schema()

    def close(self) -> None:
        self.connection.close()

    def initialize_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS segments (
              segment_id TEXT PRIMARY KEY,
              start_ts TEXT NOT NULL,
              end_ts TEXT NOT NULL,
              bars INTEGER NOT NULL,
              symbol_start TEXT,
              symbol_end TEXT,
              regime TEXT NOT NULL,
              split_reason TEXT NOT NULL,
              high_info_score REAL NOT NULL,
              feature_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS llm_analyses (
              analysis_id TEXT PRIMARY KEY,
              segment_id TEXT NOT NULL,
              provider TEXT NOT NULL,
              model TEXT NOT NULL,
              prompt_hash TEXT NOT NULL,
              memory_packet_hash TEXT NOT NULL,
              raw_response TEXT,
              parsed_json TEXT,
              status TEXT NOT NULL,
              error TEXT,
              prompt_tokens INTEGER,
              completion_tokens INTEGER,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pattern_rules (
              rule_id TEXT PRIMARY KEY,
              rule_signature TEXT NOT NULL,
              parent_signature TEXT,
              analysis_id TEXT NOT NULL,
              segment_id TEXT NOT NULL,
              pattern_name TEXT NOT NULL,
              hypothesis TEXT NOT NULL,
              rule_json TEXT NOT NULL,
              market_regime TEXT NOT NULL,
              direction TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pattern_rules_signature ON pattern_rules(rule_signature);
            CREATE TABLE IF NOT EXISTS validations (
              validation_id TEXT PRIMARY KEY,
              rule_id TEXT NOT NULL,
              rule_signature TEXT NOT NULL,
              analysis_segment_id TEXT NOT NULL,
              validation_segment_id TEXT NOT NULL,
              trades INTEGER NOT NULL,
              net_points REAL NOT NULL,
              gross_points REAL NOT NULL,
              max_drawdown_points REAL NOT NULL,
              profit_factor REAL NOT NULL,
              win_rate REAL NOT NULL,
              avg_win_points REAL NOT NULL DEFAULT 0,
              avg_loss_points REAL NOT NULL DEFAULT 0,
              expectancy_points REAL NOT NULL,
              exit_reason_json TEXT NOT NULL DEFAULT '{}',
              validation_status TEXT NOT NULL,
              failure_reason TEXT,
              created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_validations_signature ON validations(rule_signature);
            CREATE TABLE IF NOT EXISTS validation_trades (
              trade_id TEXT PRIMARY KEY,
              validation_id TEXT NOT NULL,
              rule_signature TEXT NOT NULL,
              entry_ts TEXT NOT NULL,
              exit_ts TEXT NOT NULL,
              direction INTEGER NOT NULL,
              entry_price REAL NOT NULL,
              exit_price REAL NOT NULL,
              gross_points REAL NOT NULL,
              net_points REAL NOT NULL,
              exit_reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pattern_stats (
              rule_signature TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              validations INTEGER NOT NULL,
              trades INTEGER NOT NULL,
              net_points REAL NOT NULL,
              max_drawdown_points REAL NOT NULL,
              profit_factor REAL NOT NULL,
              win_rate REAL NOT NULL,
              positive_validation_rate REAL NOT NULL,
              recent_net_points REAL NOT NULL,
              recent_profit_factor REAL NOT NULL,
              consecutive_losing_validations INTEGER NOT NULL,
              edge_score REAL NOT NULL,
              last_promoted_at TEXT,
              last_validated_at TEXT,
              retired_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS experience_notes (
              note_id TEXT PRIMARY KEY,
              rule_signature TEXT,
              note_type TEXT NOT NULL,
              regime TEXT,
              applies_when TEXT NOT NULL,
              avoid_when TEXT NOT NULL,
              lesson TEXT NOT NULL,
              evidence_summary TEXT NOT NULL,
              confidence REAL NOT NULL,
              status TEXT NOT NULL,
              supersedes_note_id TEXT,
              created_at TEXT NOT NULL,
              last_used_at TEXT,
              use_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_experience_active ON experience_notes(status, rule_signature, regime, note_type);
            CREATE TABLE IF NOT EXISTS memory_packets (
              packet_id TEXT PRIMARY KEY,
              segment_id TEXT NOT NULL,
              packet_json TEXT NOT NULL,
              token_estimate INTEGER NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column("validations", "avg_win_points", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("validations", "avg_loss_points", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("validations", "exit_reason_json", "TEXT NOT NULL DEFAULT '{}'")
        self.connection.commit()

    def upsert_segment(self, segment: Segment) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO segments (
                segment_id, start_ts, end_ts, bars, symbol_start, symbol_end,
                regime, split_reason, high_info_score, feature_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                segment.segment_id,
                segment.start_ts,
                segment.end_ts,
                segment.bars,
                segment.symbol_start,
                segment.symbol_end,
                segment.regime,
                segment.split_reason,
                segment.high_info_score,
                segment.feature_json,
                utc_now(),
            ),
        )
        self.connection.commit()

    def record_llm_analysis(self, event: dict[str, Any]) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO llm_analyses (
                analysis_id, segment_id, provider, model, prompt_hash, memory_packet_hash,
                raw_response, parsed_json, status, error, prompt_tokens, completion_tokens, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["analysis_id"],
                event["segment_id"],
                event.get("provider", "unknown"),
                event.get("model", "unknown"),
                event.get("prompt_hash", ""),
                event.get("memory_packet_hash", ""),
                event.get("raw_response"),
                json.dumps(event.get("parsed_json"), sort_keys=True, default=str) if event.get("parsed_json") is not None else None,
                event.get("status", "unknown"),
                event.get("error"),
                event.get("prompt_tokens"),
                event.get("completion_tokens"),
                event.get("created_at", utc_now()),
            ),
        )
        self.connection.commit()

    def record_rule(
        self,
        *,
        rule_id: str,
        signature: str,
        rule: TradingRule,
        analysis_id: str,
        segment_id: str,
        status: str = "new",
        parent_signature: str | None = None,
    ) -> None:
        payload = rule_to_dict(rule)
        self.connection.execute(
            """
            INSERT OR REPLACE INTO pattern_rules (
                rule_id, rule_signature, parent_signature, analysis_id, segment_id,
                pattern_name, hypothesis, rule_json, market_regime, direction, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule_id,
                signature,
                parent_signature,
                analysis_id,
                segment_id,
                rule.pattern_name,
                rule.hypothesis,
                json.dumps(payload, sort_keys=True, default=str),
                rule.market_regime,
                rule.direction,
                status,
                utc_now(),
            ),
        )
        self.connection.commit()

    def record_validation(self, result: ValidationResult) -> None:
        data = result.to_dict()
        self.connection.execute(
            """
            INSERT OR REPLACE INTO validations (
                validation_id, rule_id, rule_signature, analysis_segment_id,
                validation_segment_id, trades, net_points, gross_points,
                max_drawdown_points, profit_factor, win_rate, avg_win_points,
                avg_loss_points, expectancy_points, exit_reason_json,
                validation_status, failure_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["validation_id"],
                data["rule_id"],
                data["rule_signature"],
                data["analysis_segment_id"],
                data["validation_segment_id"],
                data["trades"],
                data["net_points"],
                data["gross_points"],
                data["max_drawdown_points"],
                data["profit_factor"],
                data["win_rate"],
                data["avg_win_points"],
                data["avg_loss_points"],
                data["expectancy_points"],
                data["exit_reason_json"],
                data["validation_status"],
                data["failure_reason"],
                utc_now(),
            ),
        )
        for row in result.trade_rows:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO validation_trades (
                    trade_id, validation_id, rule_signature, entry_ts, exit_ts,
                    direction, entry_price, exit_price, gross_points, net_points, exit_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["trade_id"],
                    row["validation_id"],
                    row["rule_signature"],
                    row["entry_ts"],
                    row["exit_ts"],
                    row["direction"],
                    row["entry_price"],
                    row["exit_price"],
                    row["gross_points"],
                    row["net_points"],
                    row["exit_reason"],
                ),
            )
        self.connection.commit()
        self.update_pattern_stats(result.rule_signature)

    def update_pattern_stats(self, signature: str) -> dict[str, Any]:
        rows = self.connection.execute(
            "SELECT * FROM validations WHERE rule_signature = ? ORDER BY created_at, validation_id",
            (signature,),
        ).fetchall()
        if not rows:
            return {}
        validations = len(rows)
        trades = sum(int(row["trades"]) for row in rows)
        net_points = sum(float(row["net_points"]) for row in rows)
        max_drawdown = max(float(row["max_drawdown_points"]) for row in rows)
        positive_rate = sum(1 for row in rows if float(row["net_points"]) > 0) / validations
        trade_rows = self.connection.execute(
            "SELECT net_points FROM validation_trades WHERE rule_signature = ?",
            (signature,),
        ).fetchall()
        net_values = [float(row["net_points"]) for row in trade_rows]
        wins = sum(value for value in net_values if value > 0)
        losses = -sum(value for value in net_values if value < 0)
        profit_factor = wins / losses if losses else (999.0 if wins > 0 else 0.0)
        win_rate = sum(1 for value in net_values if value > 0) / len(net_values) if net_values else 0.0
        recent = rows[-20:]
        recent_net = sum(float(row["net_points"]) for row in recent)
        recent_values = [
            float(row["net_points"])
            for row in self.connection.execute(
                """
                SELECT net_points FROM validation_trades
                WHERE rule_signature = ?
                ORDER BY entry_ts DESC LIMIT 60
                """,
                (signature,),
            ).fetchall()
        ]
        recent_wins = sum(value for value in recent_values if value > 0)
        recent_losses = -sum(value for value in recent_values if value < 0)
        recent_pf = recent_wins / recent_losses if recent_losses else (999.0 if recent_wins > 0 else 0.0)
        consecutive_losses = 0
        for row in reversed(rows):
            if float(row["net_points"]) < 0:
                consecutive_losses += 1
            else:
                break
        status, retired_reason = _status_for(
            validations=validations,
            trades=trades,
            net_points=net_points,
            profit_factor=profit_factor,
            positive_rate=positive_rate,
            recent_pf=recent_pf,
            consecutive_losses=consecutive_losses,
        )
        edge_score = _edge_score(
            trades=trades,
            validations=validations,
            net_points=net_points,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            positive_rate=positive_rate,
            recent_pf=recent_pf,
        )
        now = utc_now()
        self.connection.execute(
            """
            INSERT OR REPLACE INTO pattern_stats (
                rule_signature, status, validations, trades, net_points,
                max_drawdown_points, profit_factor, win_rate, positive_validation_rate,
                recent_net_points, recent_profit_factor, consecutive_losing_validations,
                edge_score, last_promoted_at, last_validated_at, retired_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signature,
                status,
                validations,
                trades,
                net_points,
                max_drawdown,
                profit_factor,
                win_rate,
                positive_rate,
                recent_net,
                recent_pf,
                consecutive_losses,
                edge_score,
                now if status in {"research", "candidate", "stable"} else None,
                now,
                retired_reason,
            ),
        )
        self._upsert_experience_note(signature, status, validations, trades, net_points, profit_factor, positive_rate, retired_reason)
        self.limit_active_notes()
        self.connection.commit()
        return self.pattern_stats(signature) or {}

    def pattern_stats(self, signature: str) -> dict[str, Any] | None:
        row = self.connection.execute("SELECT * FROM pattern_stats WHERE rule_signature = ?", (signature,)).fetchone()
        return dict(row) if row else None

    def build_memory_packet(self, *, segment: Segment, token_budget: int = 2500) -> dict[str, Any]:
        stable = self._ranked_rule_stats(segment.regime, ("stable", "candidate", "research"), limit=5)
        failures = self._ranked_rule_stats(segment.regime, ("retired", "watch"), limit=3, recent_first=True)
        notes = self._rows(
            """
            SELECT * FROM experience_notes
            WHERE status = 'active' AND (regime = ? OR regime IS NULL)
            ORDER BY confidence DESC, use_count DESC LIMIT 5
            """,
            (segment.regime,),
        )
        packet = {
            "segment_id": segment.segment_id,
            "regime": segment.regime,
            "top_rules": stable,
            "recent_failures": failures,
            "experience_notes": notes,
        }
        packet["token_estimate"] = estimate_tokens(packet)
        while packet["token_estimate"] > token_budget and (
            packet["experience_notes"] or packet["recent_failures"] or packet["top_rules"]
        ):
            if len(packet["experience_notes"]) > 1:
                packet["experience_notes"] = packet["experience_notes"][:-1]
            elif len(packet["recent_failures"]) > 1:
                packet["recent_failures"] = packet["recent_failures"][:-1]
            elif len(packet["top_rules"]) > 1:
                packet["top_rules"] = packet["top_rules"][:-1]
            elif packet["experience_notes"]:
                packet["experience_notes"] = []
            elif packet["recent_failures"]:
                packet["recent_failures"] = []
            else:
                packet["top_rules"] = []
            packet["token_estimate"] = estimate_tokens(packet)
        self.record_memory_packet(segment.segment_id, packet)
        self.mark_notes_used(note["note_id"] for note in packet.get("experience_notes", []) if note.get("note_id"))
        return packet

    def record_memory_packet(self, segment_id: str, packet: dict[str, Any]) -> str:
        payload = json.dumps(packet, sort_keys=True, default=str)
        packet_id = "mem_" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        self.connection.execute(
            """
            INSERT OR REPLACE INTO memory_packets (packet_id, segment_id, packet_json, token_estimate, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (packet_id, segment_id, payload, int(packet.get("token_estimate", estimate_tokens(packet))), utc_now()),
        )
        self.connection.commit()
        return packet_id

    def mark_notes_used(self, note_ids: list[str] | tuple[str, ...] | Any) -> None:
        ids = [str(note_id) for note_id in note_ids if note_id]
        if not ids:
            return
        now = utc_now()
        for note_id in ids:
            self.connection.execute(
                """
                UPDATE experience_notes
                SET last_used_at = ?, use_count = use_count + 1
                WHERE note_id = ?
                """,
                (now, note_id),
            )
        self.connection.commit()

    def prune_raw_responses(self, keep_latest: int = 5000) -> None:
        rows = self.connection.execute(
            "SELECT analysis_id FROM llm_analyses ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (keep_latest,),
        ).fetchall()
        for row in rows:
            self.connection.execute("UPDATE llm_analyses SET raw_response = NULL WHERE analysis_id = ?", (row["analysis_id"],))
        self.connection.commit()

    def prune_memory_packets(self, keep_latest: int = 10000) -> None:
        rows = self.connection.execute(
            "SELECT packet_id FROM memory_packets ORDER BY created_at DESC LIMIT -1 OFFSET ?",
            (keep_latest,),
        ).fetchall()
        for row in rows:
            self.connection.execute("DELETE FROM memory_packets WHERE packet_id = ?", (row["packet_id"],))
        self.connection.commit()

    def limit_active_notes(self, max_per_key: int = 3) -> None:
        groups = self.connection.execute(
            """
            SELECT COALESCE(rule_signature, ''), COALESCE(regime, ''), note_type
            FROM experience_notes
            WHERE status = 'active'
            GROUP BY COALESCE(rule_signature, ''), COALESCE(regime, ''), note_type
            """
        ).fetchall()
        for rule_signature, regime, note_type in groups:
            rows = self.connection.execute(
                """
                SELECT note_id FROM experience_notes
                WHERE status = 'active'
                  AND COALESCE(rule_signature, '') = ?
                  AND COALESCE(regime, '') = ?
                  AND note_type = ?
                ORDER BY confidence DESC, created_at DESC
                """,
                (rule_signature, regime, note_type),
            ).fetchall()
            for row in rows[max_per_key:]:
                self.connection.execute("UPDATE experience_notes SET status = 'superseded' WHERE note_id = ?", (row["note_id"],))
        self.connection.execute(
            """
            UPDATE experience_notes
            SET status = 'archived'
            WHERE status = 'active'
              AND confidence < 0.10
              AND use_count = 0
              AND created_at < datetime('now', '-180 days')
            """
        )

    def counts(self) -> dict[str, int]:
        result = {}
        for table in ["segments", "llm_analyses", "pattern_rules", "validations", "validation_trades", "pattern_stats", "experience_notes", "memory_packets"]:
            result[table] = int(self.connection.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
        return result

    def top_pattern_stats(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pattern_stats ORDER BY edge_score DESC LIMIT ?", (limit,))

    def all_pattern_stats(self, limit: int = 1000) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM pattern_stats ORDER BY edge_score DESC LIMIT ?", (limit,))

    def active_notes(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT * FROM experience_notes
            WHERE status = 'active'
            ORDER BY confidence DESC, use_count DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def retired_patterns(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._rows(
            """
            SELECT * FROM pattern_stats
            WHERE status = 'retired' OR retired_reason IS NOT NULL
            ORDER BY last_validated_at DESC LIMIT ?
            """,
            (limit,),
        )

    def memory_token_total(self) -> int:
        row = self.connection.execute("SELECT COALESCE(SUM(token_estimate), 0) AS n FROM memory_packets").fetchone()
        return int(row["n"]) if row else 0

    def recent_validations(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._rows("SELECT * FROM validations ORDER BY created_at DESC LIMIT ?", (limit,))

    def _ranked_rule_stats(
        self,
        regime: str,
        statuses: tuple[str, ...],
        *,
        limit: int,
        recent_first: bool = False,
    ) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in statuses)
        joined_order_by = "ps.last_validated_at DESC" if recent_first else "ps.edge_score DESC"
        global_order_by = "last_validated_at DESC" if recent_first else "edge_score DESC"
        regime_rows = self._rows(
            f"""
            SELECT DISTINCT ps.*
            FROM pattern_stats ps
            JOIN pattern_rules pr ON pr.rule_signature = ps.rule_signature
            WHERE ps.status IN ({placeholders})
              AND pr.market_regime = ?
            ORDER BY {joined_order_by}
            LIMIT ?
            """,
            (*statuses, regime, limit),
        )
        if len(regime_rows) >= limit:
            return regime_rows
        seen = {row["rule_signature"] for row in regime_rows}
        global_rows = self._rows(
            f"""
            SELECT * FROM pattern_stats
            WHERE status IN ({placeholders})
            ORDER BY {global_order_by}
            LIMIT ?
            """,
            (*statuses, limit * 2),
        )
        for row in global_rows:
            if row["rule_signature"] not in seen:
                regime_rows.append(row)
                seen.add(row["rule_signature"])
            if len(regime_rows) >= limit:
                break
        return regime_rows

    def _upsert_experience_note(
        self,
        signature: str,
        status: str,
        validations: int,
        trades: int,
        net_points: float,
        profit_factor: float,
        positive_rate: float,
        retired_reason: str | None,
    ) -> None:
        if validations < 1:
            return
        note_type = "failure_mode" if status == "retired" else "effective_feature"
        note_id = f"note_{signature}_{note_type}_{validations}"
        lesson = (
            f"Rule {signature} is {status}: {trades} trades, {net_points:.2f} net points, "
            f"PF {profit_factor:.2f}, positive validation rate {positive_rate:.1%}."
        )
        avoid_when = retired_reason or "Avoid when current regime no longer matches the original rule evidence."
        self.connection.execute(
            """
            INSERT OR REPLACE INTO experience_notes (
                note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                lesson, evidence_summary, confidence, status, supersedes_note_id,
                created_at, last_used_at, use_count
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
            """,
            (
                note_id,
                signature,
                note_type,
                f"Use when current features match rule {signature}.",
                avoid_when,
                lesson,
                f"validations={validations}; trades={trades}; net_points={net_points:.2f}; profit_factor={profit_factor:.2f}",
                min(1.0, max(0.05, validations / 80.0)),
                utc_now(),
            ),
        )

    def _rows(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute(query, params).fetchall()]

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        existing = {
            str(row["name"])
            for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def estimate_tokens(value: Any) -> int:
    return max(1, len(json.dumps(value, sort_keys=True, default=str)) // 4)


def _status_for(
    *,
    validations: int,
    trades: int,
    net_points: float,
    profit_factor: float,
    positive_rate: float,
    recent_pf: float,
    consecutive_losses: int,
) -> tuple[str, str | None]:
    if validations >= 30 and (recent_pf < 1.0 or consecutive_losses >= 6):
        return "retired", "recent_performance_decay"
    if validations >= 80 and trades >= 150 and profit_factor > 1.25 and positive_rate > 0.62 and recent_pf >= 1.0:
        return "stable", None
    if validations >= 30 and trades >= 60 and profit_factor > 1.20 and positive_rate > 0.58:
        return "candidate", None
    if validations >= 10 and trades >= 20 and profit_factor > 1.10 and net_points > 0:
        return "research", None
    if validations >= 20 and net_points < 0:
        return "retired", "negative_research_sample"
    return "new", None


def _edge_score(
    *,
    trades: int,
    validations: int,
    net_points: float,
    max_drawdown: float,
    profit_factor: float,
    positive_rate: float,
    recent_pf: float,
) -> float:
    sample_confidence = min(1.0, (max(trades, 1) / 150.0) ** 0.5 * (max(validations, 1) / 80.0) ** 0.5)
    drawdown_control = 1.0 / max(max_drawdown / max(abs(net_points), 1.0), 1.0)
    stability = 0.35 * positive_rate + 0.25 * min(recent_pf / 2.0, 1.0) + 0.20 * min(profit_factor / 2.0, 1.0) + 0.20 * drawdown_control
    return float((net_points / max(max_drawdown, 1.0)) * stability * sample_confidence)
