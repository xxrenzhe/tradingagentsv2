from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tradingagents.config.env import load_project_env
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.execution.llm_debate_delayed_strategy import extract_json_object, invoke_aicode_streaming_json
from tradingagents.llm_clients.factory import create_llm_client

from .memory import estimate_tokens, utc_now
from .rules import TradingRule, parse_rule_payload, rule_signature, rule_to_dict
from .segmentation import Segment


@dataclass(frozen=True)
class LLMResult:
    analysis_event: dict[str, Any]
    rule: TradingRule | None
    signature: str | None
    error: str = ""


class RuleGenerator:
    provider: str = "unknown"
    model: str = "unknown"

    def generate(self, *, segment: Segment, memory_packet: dict[str, Any]) -> LLMResult:
        raise NotImplementedError


class MockRuleGenerator(RuleGenerator):
    provider = "mock"
    model = "fixture"

    def __init__(self, fixture_path: Path | str):
        self.fixture_path = Path(fixture_path)
        self.payloads = [json.loads(line) for line in self.fixture_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not self.payloads:
            raise ValueError(f"No mock payloads found in {self.fixture_path}")
        self.index = 0

    def generate(self, *, segment: Segment, memory_packet: dict[str, Any]) -> LLMResult:
        payload = self.payloads[self.index % len(self.payloads)]
        self.index += 1
        raw = json.dumps(payload, sort_keys=True, default=str)
        return _result_from_payload(
            payload=payload,
            raw_response=raw,
            segment=segment,
            memory_packet=memory_packet,
            provider=self.provider,
            model=self.model,
        )


class FallbackRuleGenerator(RuleGenerator):
    provider = "rule"
    model = "fallback"

    def generate(self, *, segment: Segment, memory_packet: dict[str, Any]) -> LLMResult:
        features = json.loads(segment.feature_json)
        direction = "short" if float(features.get("net_points", 0.0) or 0.0) > 0 else "long"
        condition = {"feature": "z_30", "operator": ">=", "value": 1.0} if direction == "short" else {"feature": "z_30", "operator": "<=", "value": -1.0}
        payload = {
            "pattern_name": f"fallback_{direction}_mean_reversion",
            "hypothesis": "Fallback rule fades statistically stretched moves when LLM analysis is unavailable.",
            "new_or_existing": "new",
            "memory_used": [],
            "why_not_reuse_existing": "Fallback mode does not create variants from memory.",
            "market_regime": segment.regime,
            "direction": direction,
            "entry_conditions": [condition],
            "entry_timing": "next_open",
            "stop_points": 12.0,
            "target_points": 18.0,
            "max_hold_bars": 30,
            "validation_bars": 100,
            "max_trades_per_validation": 3,
            "confidence": 0.25,
            "expected_failure_modes": ["Trend continuation can overwhelm mean reversion."],
            "invalid_if": ["ATR expands and price keeps closing beyond the extreme."],
        }
        raw = json.dumps(payload, sort_keys=True)
        return _result_from_payload(payload=payload, raw_response=raw, segment=segment, memory_packet=memory_packet, provider=self.provider, model=self.model)


class RealLLMRuleGenerator(RuleGenerator):
    def __init__(self, provider: str | None = None, model: str | None = None, base_url: str | None = None, timeout: float = 60.0, fallback_on_error: bool = True):
        load_project_env()
        self.provider = provider or DEFAULT_CONFIG["llm_provider"]
        self.model = model or DEFAULT_CONFIG["deep_think_llm"]
        self.base_url = base_url or DEFAULT_CONFIG.get("backend_url")
        self.timeout = timeout
        self.fallback_on_error = fallback_on_error

    def generate(self, *, segment: Segment, memory_packet: dict[str, Any]) -> LLMResult:
        prompt = build_rule_prompt(segment=segment, memory_packet=memory_packet)
        try:
            if self.provider.lower() == "aicode":
                content = invoke_aicode_streaming_json(prompt, model=self.model, base_url=self.base_url, timeout=self.timeout)
            else:
                llm = create_llm_client(self.provider, self.model, base_url=self.base_url, timeout=self.timeout, streaming=False).get_llm()
                response = llm.invoke(prompt)
                content = str(getattr(response, "content", response))
            payload = extract_json_object(content)
            return _result_from_payload(payload=payload, raw_response=content, segment=segment, memory_packet=memory_packet, provider=self.provider, model=self.model, prompt=prompt)
        except Exception as exc:
            analysis_id = _analysis_id(segment.segment_id, str(exc), self.provider, self.model)
            fallback_result = FallbackRuleGenerator().generate(segment=segment, memory_packet=memory_packet) if self.fallback_on_error else None
            return LLMResult(
                analysis_event={
                    "analysis_id": analysis_id,
                    "segment_id": segment.segment_id,
                    "provider": self.provider,
                    "model": self.model,
                    "prompt_hash": _hash_text(prompt if "prompt" in locals() else ""),
                    "memory_packet_hash": _hash_text(json.dumps(memory_packet, sort_keys=True, default=str)),
                    "raw_response": None,
                    "parsed_json": None,
                    "status": "error",
                    "error": str(exc) or exc.__class__.__name__,
                    "prompt_tokens": estimate_tokens(prompt if "prompt" in locals() else ""),
                    "completion_tokens": 0,
                    "created_at": utc_now(),
                },
                rule=fallback_result.rule if fallback_result else None,
                signature=fallback_result.signature if fallback_result else None,
                error=str(exc) or exc.__class__.__name__,
            )


def build_rule_prompt(*, segment: Segment, memory_packet: dict[str, Any]) -> str:
    return (
        "You are an NQ 1-minute trading research agent. "
        "Generate exactly one mechanically testable rule for the next validation segment. "
        "Do not provide prose outside JSON. Use only whitelisted features visible in SEGMENT_FEATURES. "
        "Prefer price-volume features when useful, including relative_volume_20, obv_slope_20, cmf_20, "
        "mfi_14, price_volume_corr_20, volume_price_trend_slope_20, volume_breakout_signal, "
        "low_volume_pullback, bullish_volume_divergence, and bearish_volume_divergence. "
        "If evidence is weak, lower confidence instead of inventing history.\n\n"
        "Return ONLY JSON with keys: pattern_name, hypothesis, new_or_existing, memory_used, "
        "why_not_reuse_existing, market_regime, direction, entry_conditions, entry_timing, "
        "stop_points, target_points, max_hold_bars, validation_bars, max_trades_per_validation, "
        "confidence, expected_failure_modes, invalid_if. "
        "entry_timing must be exactly one of next_open, close_confirmation, retest. "
        "memory_used, expected_failure_modes, and invalid_if must be JSON arrays.\n\n"
        f"SEGMENT:\n{json.dumps(segment.to_dict(), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"MEMORY_PACKET:\n{json.dumps(memory_packet, ensure_ascii=False, sort_keys=True, default=str)}"
    )


def _result_from_payload(
    *,
    payload: dict[str, Any],
    raw_response: str,
    segment: Segment,
    memory_packet: dict[str, Any],
    provider: str,
    model: str,
    prompt: str = "",
) -> LLMResult:
    try:
        rule = parse_rule_payload(payload)
        signature = rule_signature(rule)
        status = "parsed"
        error = None
        parsed = rule_to_dict(rule)
    except Exception as exc:
        rule = None
        signature = None
        status = "parse_error"
        error = str(exc) or exc.__class__.__name__
        parsed = payload
    analysis_id = _analysis_id(segment.segment_id, raw_response, provider, model)
    event = {
        "analysis_id": analysis_id,
        "segment_id": segment.segment_id,
        "provider": provider,
        "model": model,
        "prompt_hash": _hash_text(prompt),
        "memory_packet_hash": _hash_text(json.dumps(memory_packet, sort_keys=True, default=str)),
        "raw_response": raw_response,
        "parsed_json": parsed,
        "status": status,
        "error": error,
        "prompt_tokens": estimate_tokens(prompt),
        "completion_tokens": estimate_tokens(raw_response),
        "created_at": utc_now(),
    }
    return LLMResult(analysis_event=event, rule=rule, signature=signature, error=error or "")


def _analysis_id(segment_id: str, raw: str, provider: str, model: str) -> str:
    return "ana_" + hashlib.sha1(f"{segment_id}|{provider}|{model}|{raw}".encode("utf-8")).hexdigest()[:16]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
