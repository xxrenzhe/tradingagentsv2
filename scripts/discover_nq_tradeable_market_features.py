from __future__ import annotations

import argparse
import hashlib
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

from tradingagents.config.env import load_project_env
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.evolution.features import prepare_evolution_features
from tradingagents.evolution.memory import EvolutionMemory, utc_now
from tradingagents.evolution.nq_data import load_continuous_nq_bars
from tradingagents.execution.llm_debate_delayed_strategy import extract_json_object, invoke_aicode_streaming_json
from tradingagents.llm_clients.factory import create_llm_client


@dataclass(frozen=True)
class MarketFeature:
    feature_id: str
    family: str
    direction_hint: str
    description: str
    signal: pd.Series


def load_or_prepare_features(args: argparse.Namespace) -> pd.DataFrame:
    cache_path = Path(args.features_cache)
    if cache_path.exists() and not args.rebuild_features:
        cached = pd.read_pickle(cache_path)
        features = cached["features"] if isinstance(cached, dict) and "features" in cached else cached
        frame = features.copy()
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        return frame

    bars = load_continuous_nq_bars(
        start_date=args.start_date,
        end_date=args.end_date,
        cache_path=args.bars_cache,
        source_csv=Path(args.source_csv) if args.source_csv else None,
        source_zip=Path(args.source_zip) if args.source_zip else None,
        min_volume=args.min_volume,
    )
    features = prepare_evolution_features(bars)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"features": features, "created_at": utc_now()}, cache_path)
    return features


def build_market_features(data: pd.DataFrame) -> list[MarketFeature]:
    close = pd.to_numeric(data["Close"], errors="coerce")
    open_price = pd.to_numeric(data["Open"], errors="coerce")
    high = pd.to_numeric(data["High"], errors="coerce")
    low = pd.to_numeric(data["Low"], errors="coerce")
    volume = pd.to_numeric(data["Volume"], errors="coerce").fillna(0.0)
    atr = pd.to_numeric(data["atr_30"], errors="coerce").replace(0, np.nan)
    minute = pd.to_numeric(data["minute_of_day"], errors="coerce")
    rth = (minute >= 13 * 60 + 30) & (minute < 20 * 60)
    us_late = (minute >= 20 * 60) & (minute < 23 * 60)
    ldn_ny = (minute >= 7 * 60) & (minute < 20 * 60)
    range_points = high - low
    body_share = pd.to_numeric(data["body_share"], errors="coerce")
    volume_z = pd.to_numeric(data["volume_z_60"], errors="coerce").fillna(0.0)
    momentum_15_atr = close.diff(15) / atr
    momentum_30_atr = close.diff(30) / atr
    wick_lower = pd.to_numeric(data["lower_wick_points"], errors="coerce") / range_points.replace(0, np.nan)
    wick_upper = pd.to_numeric(data["upper_wick_points"], errors="coerce") / range_points.replace(0, np.nan)
    prior_low_60 = low.rolling(60, min_periods=30).min().shift(1)
    prior_high_60 = high.rolling(60, min_periods=30).max().shift(1)
    prior_low_120 = low.rolling(120, min_periods=60).min().shift(1)
    prior_high_120 = high.rolling(120, min_periods=60).max().shift(1)
    near_prior_low = (low <= prior_low_60 + 0.15 * atr) & (close > prior_low_60)
    near_prior_high = (high >= prior_high_60 - 0.15 * atr) & (close < prior_high_60)
    donch = pd.to_numeric(data.get("donchian_20_position", np.nan), errors="coerce")
    adx = pd.to_numeric(data.get("adx_14", np.nan), errors="coerce")
    di_spread = pd.to_numeric(data.get("di_spread_14", np.nan), errors="coerce")
    cmf = pd.to_numeric(data.get("cmf_20", np.nan), errors="coerce")
    obv_slope = pd.to_numeric(data.get("obv_slope_20", np.nan), errors="coerce")
    mfi = pd.to_numeric(data.get("mfi_14", np.nan), errors="coerce")
    vfi = pd.to_numeric(data.get("vfi_130", np.nan), errors="coerce")
    boll_pos = pd.to_numeric(data.get("boll_position", np.nan), errors="coerce")
    range_pos = pd.to_numeric(data.get("range_100_position", np.nan), errors="coerce")
    session_vwap_atr = pd.to_numeric(data.get("session_vwap_distance_atr", np.nan), errors="coerce")

    features = [
        MarketFeature(
            "trend_start_long_displacement",
            "trend_start",
            "long",
            "Compression resolves upward with a displacement candle, expanding volume, DI confirmation, and Donchian upper-half location.",
            (data["displacement_candle"].eq(1))
            & (close > open_price)
            & (volume_z >= 0.5)
            & (adx >= 18)
            & (di_spread > 0)
            & (donch > 0.6),
        ),
        MarketFeature(
            "trend_start_short_displacement",
            "trend_start",
            "short",
            "Compression resolves downward with a displacement candle, expanding volume, DI confirmation, and Donchian lower-half location.",
            (data["displacement_candle"].eq(1))
            & (close < open_price)
            & (volume_z >= 0.5)
            & (adx >= 18)
            & (di_spread < 0)
            & (donch < 0.4),
        ),
        MarketFeature(
            "fast_selloff_rebound",
            "exhaustion_reversal",
            "long",
            "Fast 15-minute selloff reaches prior support or discount, prints a lower wick, and closes back above the bar midpoint.",
            (momentum_15_atr <= -1.5)
            & (near_prior_low | (range_pos <= 0.25))
            & (wick_lower >= 0.45)
            & (close > (high + low) / 2),
        ),
        MarketFeature(
            "fast_rally_fade",
            "exhaustion_reversal",
            "short",
            "Fast 15-minute rally reaches prior resistance or premium, prints an upper wick, and closes back below the bar midpoint.",
            (momentum_15_atr >= 1.5)
            & (near_prior_high | (range_pos >= 0.75))
            & (wick_upper >= 0.45)
            & (close < (high + low) / 2),
        ),
        MarketFeature(
            "sell_pressure_absorbed_rebound",
            "absorption",
            "long",
            "Price probes a prior low but selling fails to extend; CMF/OBV or MFI shows accumulation against weak price.",
            (near_prior_low | (low <= prior_low_120 + 0.20 * atr))
            & ((cmf > 0) | (obv_slope > 0) | (mfi > 45))
            & (close >= open_price),
        ),
        MarketFeature(
            "buy_pressure_absorbed_fade",
            "absorption",
            "short",
            "Price probes a prior high but buying fails to extend; CMF/OBV or MFI shows distribution against strong price.",
            (near_prior_high | (high >= prior_high_120 - 0.20 * atr))
            & ((cmf < 0) | (obv_slope < 0) | (mfi < 55))
            & (close <= open_price),
        ),
        MarketFeature(
            "w_bottom_reclaim",
            "double_bottom",
            "long",
            "A second low near the prior swing low rejects and reclaims the midpoint/VWAP area with improving money flow.",
            (low.sub(prior_low_60).abs() <= 0.25 * atr)
            & (close > open_price)
            & (session_vwap_atr > -0.25)
            & ((cmf > 0) | (vfi > 0) | (mfi > 50)),
        ),
        MarketFeature(
            "m_top_reject",
            "double_top",
            "short",
            "A second high near the prior swing high rejects and loses the midpoint/VWAP area with weakening money flow.",
            (high.sub(prior_high_60).abs() <= 0.25 * atr)
            & (close < open_price)
            & (session_vwap_atr < 0.25)
            & ((cmf < 0) | (vfi < 0) | (mfi < 50)),
        ),
        MarketFeature(
            "volume_price_bullish_mismatch",
            "volume_price_mismatch",
            "long",
            "Price is weak or at discount while OBV/CMF/VFI diverges upward, suggesting hidden accumulation.",
            ((close < close.shift(20)) | (range_pos <= 0.35) | (boll_pos <= -0.75))
            & ((data["bullish_volume_divergence"].eq(1)) | ((cmf > 0) & (obv_slope > 0)) | (vfi > vfi.shift(20))),
        ),
        MarketFeature(
            "volume_price_bearish_mismatch",
            "volume_price_mismatch",
            "short",
            "Price is strong or at premium while OBV/CMF/VFI diverges downward, suggesting hidden distribution.",
            ((close > close.shift(20)) | (range_pos >= 0.65) | (boll_pos >= 0.75))
            & ((data["bearish_volume_divergence"].eq(1)) | ((cmf < 0) & (obv_slope < 0)) | (vfi < vfi.shift(20))),
        ),
        MarketFeature(
            "low_volume_pullback_trend_long",
            "trend_pullback",
            "long",
            "An uptrend pauses on lower volume without losing trend stack; pullback may offer continuation entry.",
            (data["low_volume_pullback"].eq(1))
            & (data["ema_10"] > data["ema_20"])
            & (data["ema_20"] > data["ema_50"])
            & (session_vwap_atr >= -0.25)
            & (momentum_30_atr > 0),
        ),
        MarketFeature(
            "low_volume_pullback_trend_short",
            "trend_pullback",
            "short",
            "A downtrend pauses on lower volume without regaining trend stack; pullback may offer continuation entry.",
            (data["low_volume_pullback"].eq(1))
            & (data["ema_10"] < data["ema_20"])
            & (data["ema_20"] < data["ema_50"])
            & (session_vwap_atr <= 0.25)
            & (momentum_30_atr < 0),
        ),
        MarketFeature(
            "vwap_reclaim_after_selloff",
            "reclaim",
            "long",
            "After a selloff, price reclaims session VWAP with improving volume-price state.",
            (data["session_vwap_reclaim_up"].eq(1))
            & (momentum_30_atr < 0)
            & ((volume_z > 0) | (cmf > 0) | (mfi > 50)),
        ),
        MarketFeature(
            "vwap_loss_after_rally",
            "reclaim",
            "short",
            "After a rally, price loses session VWAP with weakening volume-price state.",
            (data["session_vwap_reclaim_down"].eq(1))
            & (momentum_30_atr > 0)
            & ((volume_z > 0) | (cmf < 0) | (mfi < 50)),
        ),
    ]
    session_features: list[MarketFeature] = []
    for base in features:
        session_features.append(base)
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_us_rth",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to US RTH.",
                base.signal & rth,
            )
        )
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_us_late",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to US late session.",
                base.signal & us_late,
            )
        )
        session_features.append(
            MarketFeature(
                f"{base.feature_id}_ldn_ny",
                base.family,
                base.direction_hint,
                f"{base.description} Session-filtered to London/New York overlap.",
                base.signal & ldn_ny,
            )
        )
    return session_features


def event_path_rows(
    data: pd.DataFrame,
    market_features: list[MarketFeature],
    *,
    horizons: list[int],
    min_gap_minutes: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    close = pd.to_numeric(data["Close"], errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(data["High"], errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(data["Low"], errors="coerce").to_numpy(dtype=float)
    timestamps = pd.to_datetime(data["ts"], utc=True)
    symbols = data["symbol"].astype(str).to_numpy() if "symbol" in data.columns else np.asarray(["NQ"] * len(data))
    max_horizon = max(horizons)
    for feature in market_features:
        indexes = np.flatnonzero(feature.signal.fillna(False).to_numpy(dtype=bool))
        indexes = _dedupe_indexes(indexes, min_gap_minutes)
        indexes = indexes[indexes + max_horizon < len(data)]
        if len(indexes) == 0:
            continue
        for index in indexes:
            if symbols[index + max_horizon] != symbols[index]:
                continue
            event_close = close[index]
            if not np.isfinite(event_close):
                continue
            row: dict[str, Any] = {
                "feature_id": feature.feature_id,
                "family": feature.family,
                "direction_hint": feature.direction_hint,
                "description": feature.description,
                "event_index": int(index),
                "event_ts": str(timestamps.iloc[index]),
                "symbol": str(symbols[index]),
                "event_close": float(event_close),
            }
            direction = 1 if feature.direction_hint == "long" else -1 if feature.direction_hint == "short" else 0
            for horizon in horizons:
                end = index + horizon
                forward_close = close[end]
                window_high = np.nanmax(high[index + 1 : end + 1])
                window_low = np.nanmin(low[index + 1 : end + 1])
                if direction >= 0:
                    mfe = window_high - event_close
                    mae = event_close - window_low
                    signed_close = forward_close - event_close
                else:
                    mfe = event_close - window_low
                    mae = window_high - event_close
                    signed_close = event_close - forward_close
                row[f"close_move_{horizon}m"] = float(signed_close)
                row[f"mfe_{horizon}m"] = float(mfe)
                row[f"mae_{horizon}m"] = float(mae)
            rows.append(row)
    return pd.DataFrame(rows)


def _dedupe_indexes(indexes: np.ndarray, min_gap: int) -> np.ndarray:
    if len(indexes) == 0:
        return indexes
    selected = [int(indexes[0])]
    next_allowed = int(indexes[0]) + min_gap
    for index in indexes[1:]:
        value = int(index)
        if value >= next_allowed:
            selected.append(value)
            next_allowed = value + min_gap
    return np.asarray(selected, dtype=int)


def summarize_events(events: pd.DataFrame, *, horizons: list[int], min_events: int) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for feature_id, group in events.groupby("feature_id", sort=False):
        if len(group) < min_events:
            continue
        base = group.iloc[0]
        row: dict[str, Any] = {
            "feature_id": feature_id,
            "family": base["family"],
            "direction_hint": base["direction_hint"],
            "description": base["description"],
            "events": int(len(group)),
            "first_ts": str(group["event_ts"].min()),
            "last_ts": str(group["event_ts"].max()),
        }
        score_parts = []
        for horizon in horizons:
            close_move = pd.to_numeric(group[f"close_move_{horizon}m"], errors="coerce").dropna()
            mfe = pd.to_numeric(group[f"mfe_{horizon}m"], errors="coerce").dropna()
            mae = pd.to_numeric(group[f"mae_{horizon}m"], errors="coerce").dropna()
            if close_move.empty:
                continue
            median_close = float(close_move.median())
            mean_close = float(close_move.mean())
            hit_10 = float((mfe >= 10.0).mean()) if len(mfe) else 0.0
            hit_20 = float((mfe >= 20.0).mean()) if len(mfe) else 0.0
            adverse_10 = float((mae >= 10.0).mean()) if len(mae) else 0.0
            favorable_share = float((close_move > 0).mean())
            payoff_path = float(mfe.median() / max(mae.median(), 1.0)) if len(mfe) and len(mae) else 0.0
            row[f"mean_close_move_{horizon}m"] = mean_close
            row[f"median_close_move_{horizon}m"] = median_close
            row[f"favorable_close_rate_{horizon}m"] = favorable_share
            row[f"median_mfe_{horizon}m"] = float(mfe.median()) if len(mfe) else 0.0
            row[f"median_mae_{horizon}m"] = float(mae.median()) if len(mae) else 0.0
            row[f"hit_10pt_rate_{horizon}m"] = hit_10
            row[f"hit_20pt_rate_{horizon}m"] = hit_20
            row[f"adverse_10pt_rate_{horizon}m"] = adverse_10
            row[f"path_payoff_{horizon}m"] = payoff_path
            score_parts.append(
                favorable_share * 3.0
                + min(max(mean_close, -20.0), 20.0) / 10.0
                + hit_10 * 2.0
                + hit_20 * 2.0
                + min(payoff_path, 3.0)
                - adverse_10
            )
        row["opportunity_score"] = float(np.mean(score_parts)) if score_parts else 0.0
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(
        ["opportunity_score", "events"],
        ascending=[False, False],
    ).reset_index(drop=True)


def invoke_feature_llm(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    memory_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    if args.no_llm or summary.empty:
        return fallback_feature_analysis(summary, args, memory_notes=memory_notes)
    load_project_env()
    provider = args.provider or DEFAULT_CONFIG["llm_provider"]
    model = args.model or DEFAULT_CONFIG["deep_think_llm"]
    base_url = args.backend_url or DEFAULT_CONFIG.get("backend_url")
    prompt = build_feature_prompt(summary.head(args.llm_top_n), args, memory_notes=memory_notes)
    try:
        if provider.lower() == "aicode":
            content = invoke_aicode_streaming_json(prompt, model=model, base_url=base_url, timeout=args.llm_timeout)
        else:
            llm = create_llm_client(provider, model, base_url=base_url, timeout=args.llm_timeout, streaming=False).get_llm()
            response = llm.invoke(prompt)
            content = str(getattr(response, "content", response))
        payload = extract_json_object(content)
        payload.setdefault("provider", provider)
        payload.setdefault("model", model)
        payload.setdefault("status", "parsed")
        payload["raw_response"] = content
        return payload
    except Exception as exc:
        payload = fallback_feature_analysis(summary, args, memory_notes=memory_notes)
        payload["status"] = "fallback_after_error"
        payload["error"] = str(exc) or exc.__class__.__name__
        return payload


def build_feature_prompt(summary: pd.DataFrame, args: argparse.Namespace, *, memory_notes: list[dict[str, Any]]) -> str:
    payload = summary.replace([np.inf, -np.inf], np.nan).where(pd.notna(summary), None).to_dict(orient="records")
    return (
        "你是NQ 1分钟行情结构研究员。现在不要先追求胜率>53%或盈亏比>1，"
        "任务是从2020年之后的1分钟bar事件统计里识别哪些行情特征值得交易研究。"
        "请重点判断趋势起点、快速下杀反抽、快速上涨回落、跌不动反弹、涨不动下跌、W底、M顶、量价不匹配等结构。"
        "先描述可交易现象，再建议适配的策略类型、入场确认、止损位置、出场逻辑、失效条件和下一步回测优先级。"
        "不要编造统计表之外的结果。\n\n"
        "Return ONLY JSON with keys: feature_rankings, strategy_hypotheses, risk_principles, next_research_steps, summary. "
        "feature_rankings must be a list of objects with feature_id, tradeability, reason, preferred_strategy, confirmation, invalidation. "
        "strategy_hypotheses must include setup, direction, entry_logic, stop_logic, exit_logic, filters_to_test. "
        "risk_principles must be short actionable rules.\n\n"
        f"CONFIG: {json.dumps(vars(args), ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"MEMORY_NOTES: {json.dumps(memory_notes, ensure_ascii=False, sort_keys=True, default=str)}\n\n"
        f"EVENT_SUMMARY_ROWS: {json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)}"
    )


def fallback_feature_analysis(
    summary: pd.DataFrame,
    args: argparse.Namespace,
    *,
    memory_notes: list[dict[str, Any]],
) -> dict[str, Any]:
    rankings = []
    for _, row in summary.head(args.llm_top_n).iterrows():
        feature_id = str(row["feature_id"])
        family = str(row["family"])
        direction = str(row["direction_hint"])
        rankings.append(
            {
                "feature_id": feature_id,
                "tradeability": "research",
                "reason": (
                    f"{family} {direction} event has {int(row['events'])} samples and opportunity_score "
                    f"{float(row['opportunity_score']):.3f}; use as a hypothesis source, not as a complete strategy."
                ),
                "preferred_strategy": strategy_for_family(family),
                "confirmation": confirmation_for_family(family, direction),
                "invalidation": invalidation_for_family(family, direction),
            }
        )
    return {
        "provider": "rule",
        "model": "feature_fallback",
        "status": "fallback",
        "feature_rankings": rankings,
        "strategy_hypotheses": [
            {
                "setup": item["feature_id"],
                "direction": summary.loc[summary["feature_id"].eq(item["feature_id"]), "direction_hint"].iloc[0],
                "entry_logic": item["confirmation"],
                "stop_logic": item["invalidation"],
                "exit_logic": "Compare fixed R, structure target, and time stop variants after event-level opportunity is confirmed.",
                "filters_to_test": ["session", "relative_volume_20", "session_vwap_distance_atr", "adx_14", "cmf_20", "mfi_14"],
            }
            for item in rankings[:8]
        ],
        "risk_principles": [
            "先验证事件后的路径分布，再为该事件选择趋势跟随、反转或回归执行策略。",
            "每个结构都必须定义失效条件，失效时不补仓、不扩大止损。",
            "量价不匹配必须等待价格确认，不能只凭背离逆势入场。",
            "趋势起点优先用结构止损，快速反抽/回落优先用极值失效止损。",
        ],
        "next_research_steps": [
            "For top features, run bracket and time-stop strategy grids separately by family.",
            "Validate whether MFE arrives before MAE enough to support realistic entries.",
            "Split event statistics by session and volatility regime before promoting a setup.",
        ],
        "summary": "Fallback analysis ranked event families by path opportunity; LLM unavailable or disabled.",
        "memory_note_count": len(memory_notes),
    }


def strategy_for_family(family: str) -> str:
    if family in {"trend_start", "trend_pullback"}:
        return "breakout/continuation with structure stop and trailing/time exit"
    if family in {"exhaustion_reversal", "absorption", "double_bottom", "double_top", "reclaim"}:
        return "confirmation reversal with extreme-based stop and VWAP/range target"
    if family == "volume_price_mismatch":
        return "confirmation-first reversal or failed-continuation strategy"
    return "family-specific bracket and time-stop comparison"


def confirmation_for_family(family: str, direction: str) -> str:
    side = "above" if direction == "long" else "below"
    if family == "trend_start":
        return f"Enter only after the next bar holds {side} the displacement midpoint or breaks continuation in the hinted direction."
    if family == "volume_price_mismatch":
        return "Wait for price to reclaim/lose VWAP or break the prior micro swing in the hinted direction."
    if family in {"double_bottom", "double_top"}:
        return "Require neckline or midpoint reclaim/reject; avoid entering directly at the second touch without confirmation."
    return "Require follow-through close or failed retest in the hinted direction."


def invalidation_for_family(family: str, direction: str) -> str:
    if family in {"trend_start", "trend_pullback"}:
        return "Invalidate if price closes back through the breakout/displacement origin or volume expansion reverses against the trade."
    if direction == "long":
        return "Invalidate below the event low or if rebound cannot reclaim VWAP/midpoint within the chosen time window."
    return "Invalidate above the event high or if fade cannot lose VWAP/midpoint within the chosen time window."


def load_memory_notes(memory_db: Path, limit: int) -> list[dict[str, Any]]:
    if not memory_db.exists():
        return []
    memory = EvolutionMemory(memory_db)
    try:
        return memory.active_notes(limit)
    finally:
        memory.close()


def record_feature_memory(memory_db: Path, summary: pd.DataFrame, llm_payload: dict[str, Any], args: argparse.Namespace) -> None:
    memory = EvolutionMemory(memory_db)
    try:
        now = utc_now()
        rankings = llm_payload.get("feature_rankings", [])
        ranking_by_feature = {
            str(item.get("feature_id")): item
            for item in rankings
            if isinstance(item, dict) and item.get("feature_id")
        }
        for _, row in summary.head(args.memory_top_n).iterrows():
            feature_id = str(row["feature_id"])
            ranking = ranking_by_feature.get(feature_id, {})
            signature = "mfeat_" + hashlib.sha1(feature_id.encode("utf-8")).hexdigest()[:16]
            note_id = f"note_{signature}_market_feature_{int(row['events'])}"
            lesson = (
                f"Market feature {feature_id}: family={row['family']}, direction={row['direction_hint']}, "
                f"events={int(row['events'])}, opportunity_score={float(row['opportunity_score']):.3f}. "
                f"LLM/readout tradeability={ranking.get('tradeability', 'research')}; "
                f"preferred_strategy={ranking.get('preferred_strategy', strategy_for_family(str(row['family'])))}."
            )
            memory.connection.execute(
                """
                INSERT OR REPLACE INTO experience_notes (
                    note_id, rule_signature, note_type, regime, applies_when, avoid_when,
                    lesson, evidence_summary, confidence, status, supersedes_note_id,
                    created_at, last_used_at, use_count
                ) VALUES (?, ?, 'market_feature', NULL, ?, ?, ?, ?, ?, 'active', NULL, ?, NULL, 0)
                """,
                (
                    note_id,
                    signature,
                    str(row["description"]),
                    str(ranking.get("invalidation", invalidation_for_family(str(row["family"]), str(row["direction_hint"])))),
                    lesson,
                    json.dumps(row.replace([np.inf, -np.inf], np.nan).dropna().to_dict(), sort_keys=True, default=str),
                    min(1.0, max(0.05, float(row["events"]) / 1000.0)),
                    now,
                ),
            )
        memory.limit_active_notes()
        memory.connection.commit()
    finally:
        memory.close()


def write_html_report(
    path: Path,
    summary: pd.DataFrame,
    llm_payload: dict[str, Any],
    args: argparse.Namespace,
    *,
    feature_rows: int,
    event_rows: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_rows = summary.head(args.top_n).copy()
    ranking_html = _html_table(top_rows)
    llm_html = _json_block(llm_payload)
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>NQ 2020+ Tradeable Market Feature Discovery</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #172026; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 22px 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; position: sticky; top: 0; }}
    .metric {{ display: inline-block; margin: 0 14px 10px 0; padding: 8px 10px; background: #f6f8fa; border: 1px solid #d8dee4; border-radius: 6px; }}
    pre {{ white-space: pre-wrap; background: #0f1720; color: #e6edf3; padding: 14px; border-radius: 6px; overflow: auto; }}
    .muted {{ color: #59636e; }}
  </style>
</head>
<body>
  <h1>NQ 2020+ 可交易行情特征发现</h1>
  <p class="muted">先发现行情结构与路径机会，再为结构匹配策略。当前不使用 53% 胜率或盈亏比硬门槛作为筛选条件。</p>
  <section>
    <span class="metric">Features rows: {feature_rows:,}</span>
    <span class="metric">Event rows: {event_rows:,}</span>
    <span class="metric">Summary rows: {len(summary):,}</span>
    <span class="metric">Window: {args.start_date} to {args.end_date}</span>
  </section>
  <section>
    <h2>Top Event Path Statistics</h2>
    {ranking_html}
  </section>
  <section>
    <h2>LLM / Rule Analysis</h2>
    {llm_html}
  </section>
</body>
</html>
""",
        encoding="utf-8",
    )


def _html_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>No rows.</p>"
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display.to_html(index=False, escape=True)


def _json_block(payload: dict[str, Any]) -> str:
    return "<pre>" + json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "</pre>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover tradeable NQ 1-minute market features from 2020+ bars.")
    parser.add_argument("--start-date", default="2020-01-01")
    parser.add_argument("--end-date", default="2026-04-28")
    parser.add_argument("--bars-cache", default=".tmp/nq-market-feature-bars-2020-cache.pkl")
    parser.add_argument("--features-cache", default=".tmp/nq-market-feature-features-2020-cache.pkl")
    parser.add_argument("--source-csv")
    parser.add_argument("--source-zip")
    parser.add_argument("--min-volume", type=float, default=1.0)
    parser.add_argument("--rebuild-features", action="store_true")
    parser.add_argument("--horizons", type=int, nargs="+", default=[5, 15, 30, 60, 120])
    parser.add_argument("--min-gap-minutes", type=int, default=15)
    parser.add_argument("--min-events", type=int, default=30)
    parser.add_argument("--events-output", default=".tmp/nq-market-feature-events-2020.csv")
    parser.add_argument("--summary-output", default=".tmp/nq-market-feature-summary-2020.csv")
    parser.add_argument("--llm-output", default=".tmp/nq-market-feature-llm-analysis-2020.json")
    parser.add_argument("--report", default="reports/NQ-market-feature-discovery-2020.html")
    parser.add_argument("--memory-db", default=".tmp/nq-trading-evolution.sqlite")
    parser.add_argument("--record-memory", action="store_true")
    parser.add_argument("--memory-top-n", type=int, default=30)
    parser.add_argument("--memory-note-limit", type=int, default=20)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--backend-url")
    parser.add_argument("--llm-timeout", type=float, default=90.0)
    parser.add_argument("--llm-top-n", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=50)
    args = parser.parse_args()

    features = load_or_prepare_features(args)
    market_features = build_market_features(features)
    events = event_path_rows(
        features,
        market_features,
        horizons=args.horizons,
        min_gap_minutes=args.min_gap_minutes,
    )
    summary = summarize_events(events, horizons=args.horizons, min_events=args.min_events)
    memory_db = Path(args.memory_db)
    memory_notes = load_memory_notes(memory_db, args.memory_note_limit)
    llm_payload = invoke_feature_llm(summary, args, memory_notes=memory_notes)

    for output, frame in [(Path(args.events_output), events), (Path(args.summary_output), summary)]:
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output, index=False)
    llm_output = Path(args.llm_output)
    llm_output.parent.mkdir(parents=True, exist_ok=True)
    llm_output.write_text(json.dumps(llm_payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    write_html_report(Path(args.report), summary, llm_payload, args, feature_rows=len(features), event_rows=len(events))
    if args.record_memory:
        record_feature_memory(memory_db, summary, llm_payload, args)

    result = {
        "feature_rows": int(len(features)),
        "market_features": int(len(market_features)),
        "event_rows": int(len(events)),
        "summary_rows": int(len(summary)),
        "events_output": args.events_output,
        "summary_output": args.summary_output,
        "llm_output": args.llm_output,
        "report": args.report,
        "memory_db": args.memory_db if args.record_memory else "",
        "top_feature": summary.iloc[0].to_dict() if not summary.empty else None,
        "llm_status": llm_payload.get("status", "unknown"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
