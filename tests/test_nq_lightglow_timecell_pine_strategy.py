from pathlib import Path


SCRIPT_PATH = Path("pine_scripts/nq_lightglow_timecell_composite_paper_readiness.pine")


def test_nq_lightglow_timecell_pine_names_correct_boundary_strategy() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'strategy("NQ Range Boundary Lightglow Strategy"' in script
    assert 'shorttitle="NQ Boundary LG"' in script
    assert "Boundary executable" in script
    assert "Converts the Lightglow paper-readiness research into an explicit range-boundary strategy" in script
    assert "Timecell is shown as shadow-only" in script
    assert "shadow-only 0.05x" in script
    assert "strategy.entry(\"LG Stable Long\", strategy.long)" in script
    assert "strategy.entry(\"LG Stable Short\", strategy.short)" in script
    assert "timecellShadowSignal" in script
    assert "strategy.entry(\"TC" not in script


def test_nq_lightglow_timecell_pine_freezes_stable_month_dow_action_map() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "stableLightglowAction(int monthValue, int dowValue)" in script
    assert 'timeCellMode = input.string("Off"' in script
    assert 'options=["Off", "Filter Only", "Native/Reverse Research"]' in script
    assert 'tradePdFallback = input.bool(false, "Trade P/D Fallback Signals"' in script
    assert "timeCellAllowsTrade" in script
    assert "useStableActionMap" not in script
    assert "TradingView: Sunday=1 ... Saturday=7. Python pandas dayofweek: Monday=0 ... Sunday=6." in script
    assert "tvToPythonDow" in script
    for cell in [
        "monthValue == 1 and dowValue == 4",
        "monthValue == 1 and dowValue == 6",
        "monthValue == 2 and dowValue == 6",
        "monthValue == 3 and dowValue == 3",
        "monthValue == 3 and dowValue == 6",
        "monthValue == 4 and dowValue == 2",
        "monthValue == 5 and dowValue == 1",
        "monthValue == 5 and dowValue == 6",
        "monthValue == 8 and dowValue == 3",
        "monthValue == 8 and dowValue == 6",
        "monthValue == 9 and dowValue == 0",
        "monthValue == 9 and dowValue == 4",
        "monthValue == 9 and dowValue == 6",
        "monthValue == 11 and dowValue == 2",
        "monthValue == 11 and dowValue == 6",
        "monthValue == 12 and dowValue == 0",
        "monthValue == 12 and dowValue == 4",
        "monthValue == 12 and dowValue == 6",
    ]:
        assert cell in script
    assert "stableActionText" in script


def test_nq_lightglow_timecell_pine_uses_structure_bracket_exits_and_manual_review_visuals() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "process_orders_on_close=false" in script
    assert 'exitMode = input.string("Structure Bracket"' in script
    assert 'options=["Structure Bracket", "Fixed Time"]' in script
    assert "barsHeldFromEntry = strategy.opentrades > 0 ? bar_index - strategy.opentrades.entry_bar_index(0) : 0" in script
    assert 'strategy.exit("LG Long Bracket", from_entry="LG Stable Long", stop=longProtectiveStop, limit=longTargetForExit)' in script
    assert 'strategy.exit("LG Short Bracket", from_entry="LG Stable Short", stop=shortProtectiveStop, limit=shortTargetForExit)' in script
    assert "activeInitialStop" in script
    assert "activeTarget" in script
    assert "activeTargetPlan" in script
    assert "activeRiskPoints" in script
    assert "minRiskAtr = input.float(0.80" in script
    assert 'targetMode = input.string("Signal Adaptive"' in script
    assert 'options=["Signal Adaptive", "Fixed R", "Structure Capped"]' in script
    assert "minTargetR = input.float(1.00" in script
    assert "maxTargetR = input.float(3.00" in script
    assert "reversalTargetRangeRatio = input.float(0.50" in script
    assert "continuationTargetRangeMult = input.float(0.75" in script
    assert "minHoldBarsBeforeTargetExit = input.int(2" in script
    assert "cooldownBars = input.int(5" in script
    assert "targetExitArmed = barsHeldFromEntry >= minHoldBarsBeforeTargetExit" in script
    assert "longTargetForExit = targetExitArmed ? activeTarget : na" in script
    assert "shortTargetForExit = targetExitArmed ? activeTarget : na" in script
    assert "bracketExitArmed" not in script
    assert "longProtectiveStop" in script
    assert "shortProtectiveStop" in script
    assert "useBreakeven" in script
    assert "useAtrTrail" in script
    assert "maxHoldExitCondition" in script
    assert 'strategy.close_all(timeExitCondition ? "LG Fixed Time Exit" : "LG Max Hold Exit")' in script
    assert "Long Structure Stop" in script
    assert "Short Structure Stop" in script
    assert "Adaptive Structure Target" in script
    assert "line.style_dashed" in script
    assert "strategy.closedtrades.profit" in script
    assert "pointsPnl" in script
    assert "pnlLabelHorizontalOffsetBars = input.int(3" in script
    assert "pnlLabelVerticalAtrOffset = input.float(2.00" in script
    assert "labelX = exitBar + pnlLabelHorizontalOffsetBars" in script
    assert "labelY = isWin ? high + atr * pnlLabelVerticalAtrOffset : low - atr * pnlLabelVerticalAtrOffset" in script
    assert "label.new" in script
    assert "size=size.tiny" in script
    assert "label.new(exitBar, labelY" not in script
    assert "location.absolute" not in script


def test_nq_lightglow_timecell_pine_has_adaptive_profit_targets() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "fixedRTarget" in script
    assert "minRTarget" in script
    assert "maxRTarget" in script
    assert "activeRangeWidth = activeRangeHigh - activeRangeLow" in script
    assert 'activeSignalType == "bottom_reclaim_long"' in script
    assert 'structureTargetCandidate := activeRangeLow + activeRangeWidth * reversalTargetRangeRatio' in script
    assert 'activeSignalType == "top_reject_short"' in script
    assert 'structureTargetCandidate := activeRangeHigh - activeRangeWidth * reversalTargetRangeRatio' in script
    assert 'activeSignalType == "top_breakout_long"' in script
    assert 'structureTargetCandidate := activeRangeHigh + activeRangeWidth * continuationTargetRangeMult' in script
    assert 'activeSignalType == "bottom_breakdown_short"' in script
    assert 'structureTargetCandidate := activeRangeLow - activeRangeWidth * continuationTargetRangeMult' in script
    assert "structureTargetDistance" in script
    assert "structureTargetValid" in script
    assert "cappedStructureTarget" in script
    assert "structureCappedFixedTarget" in script
    assert 'activeTargetPlan := targetMode == "Fixed R" or not structureTargetValid ? "fixed_r"' in script
    assert "lastTradeTargetPlan := activeTargetPlan" in script


def test_nq_lightglow_timecell_pine_has_trend_ignition_entry_family() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert 'groupTrendIgnition = "Trend Ignition"' in script
    assert 'tradeBottomBreakdown = input.bool(false, "Trade Bottom Breakdown Continuation"' in script
    assert 'tradeTopBreakout = input.bool(true, "Trade Top Breakout Continuation"' in script
    assert 'tradeBottomReclaim = input.bool(false, "Trade Bottom Reclaim Bounce"' in script
    assert 'tradeTopReject = input.bool(false, "Trade Top Reject Short"' in script
    assert 'tradeTrendIgnition = input.bool(true, "Trade Compression Reclaim Ignition"' in script
    assert 'tradeTrendContinuation = input.bool(false, "Trade Trend Pullback Continuation"' in script
    assert 'tradeTrendTransition = input.bool(false, "Trade EMA Transition Trend Start"' in script
    assert 'tradeReversalImpulse = input.bool(false, "Trade Liquidity Reversal Impulse"' in script
    assert 'tradeTopBreakoutOnlyRth = input.bool(true, "Trade Top Breakout Only In US RTH"' in script
    assert 'tradeReversalImpulseLateOnly = input.bool(true, "Trade Reversal Impulse Only In US Late"' in script
    assert 'tradeTrendIgnitionEuropeOnly = input.bool(true, "Trade Trend Ignition Only In Europe"' in script
    assert "ignitionBreakoutLength = input.int(14" in script
    assert "ignitionBaseLength = input.int(45" in script
    assert "microBreakoutHigh = ta.highest(high, ignitionBreakoutLength)[1]" in script
    assert "microBreakdownLow = ta.lowest(low, ignitionBreakoutLength)[1]" in script
    assert "compressionHigh = ta.highest(high, ignitionBaseLength)[1]" in script
    assert "compressionLow = ta.lowest(low, ignitionBaseLength)[1]" in script
    assert "compressedBase" in script
    assert "emaReclaimLong" in script
    assert "emaRejectShort" in script
    assert "trendIgnitionLongCandidate" in script
    assert "trendIgnitionShortCandidate" in script
    assert "trendIgnitionLongSignal" in script
    assert "trendIgnitionShortSignal" in script
    assert "trendIgnitionLongSignal ? 1" in script
    assert "trendIgnitionShortSignal = false" in script
    assert '"trend_ignition_long"' in script
    assert '"trend_ignition_short"' in script
    assert "trend_range_target" in script
    assert "Compression Reclaim Trend Ignition Long" in script
    assert "Trend Ignition Long Candidate" in script


def test_nq_lightglow_timecell_pine_has_trend_pullback_continuation_family() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "trendSlopeLookback = input.int(20" in script
    assert "pullbackLookback = input.int(12" in script
    assert "pullbackAtrMax = input.float(2.50" in script
    assert "pullbackEmaAtrBuffer = input.float(0.35" in script
    assert "continuationVolumeZMin = input.float(-0.75" in script
    assert "trendUpEstablished = ema20 > ema60 and ema60 > ema200" in script
    assert "trendDownEstablished = ema20 < ema60 and ema60 < ema200" in script
    assert "pullbackDepthLongAtr" in script
    assert "pullbackDepthShortAtr" in script
    assert "longPullbackHeld" in script
    assert "shortPullbackHeld" in script
    assert "trendContinuationLongCandidate" in script
    assert "trendContinuationShortCandidate" in script
    assert "trendContinuationLongSignal" in script
    assert "trendContinuationShortSignal" in script
    assert "trendContinuationLongSignal ? 1" in script
    assert "trendContinuationShortSignal ? -1" in script
    assert '"trend_pullback_long"' in script
    assert '"trend_pullback_short"' in script
    assert "trend_pullback_extension" in script
    assert "Trend Pullback Continuation Long" in script
    assert "Trend Pullback Long Candidate" in script


def test_nq_lightglow_timecell_pine_has_trend_transition_and_reversal_impulse() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "transitionLookback = input.int(20" in script
    assert "transitionBodyAtrMin = input.float(0.40" in script
    assert "transitionVolumeZMin = input.float(-0.50" in script
    assert "reversalImpulseBodyAtrMin = input.float(0.80" in script
    assert "reversalImpulseVolumeZMin = input.float(-0.25" in script
    assert "reversalImpulseCloseRatio = input.float(0.70" in script
    assert "emaBearTransition" in script
    assert "emaBullTransition" in script
    assert "trendTransitionShortCandidate" in script
    assert "trendTransitionLongCandidate" in script
    assert "bullishReversalImpulseCandidate" in script
    assert "bearishReversalImpulseCandidate" in script
    assert "trendTransitionLongSignal" in script
    assert "trendTransitionShortSignal" in script
    assert "reversalImpulseLongSignal" in script
    assert "reversalImpulseShortSignal" in script
    assert "isUsRthSession" in script
    assert "isUsLateSession" in script
    assert "trendTransitionLongSignal ? 1" in script
    assert "trendTransitionShortSignal ? -1" in script
    assert "reversalImpulseLongSignal ? 1" in script
    assert "reversalImpulseShortSignal ? -1" in script
    assert '"trend_transition_long"' in script
    assert '"trend_transition_short"' in script
    assert '"reversal_impulse_long"' in script
    assert '"reversal_impulse_short"' in script
    assert "EMA Transition Trend Start Long" in script
    assert "Liquidity Reversal Impulse Long" in script
    assert "Trend Transition Long Candidate" in script
    assert "Reversal Impulse Long Candidate" in script


def test_nq_lightglow_timecell_pine_has_bottom_breakdown_vs_reclaim_diagnostics() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Range Boundary Breakdown vs Reclaim" in script
    assert "Range Boundary Breakdown / Breakout vs Reclaim Diagnostics" in script
    assert "acceptedBelowRange" in script
    assert "acceptedAboveRange" in script
    assert "sweepBelowRange" in script
    assert "sweepAboveRange" in script
    assert "discountReclaimBounceCandidate" in script
    assert "breakdownContinuationCandidate" in script
    assert "premiumRejectShortCandidate" in script
    assert "breakoutContinuationCandidate" in script
    assert "weakBottomNoTrade" in script
    assert "weakTopNoTrade" in script
    assert "bottomFilterBlocksLong" in script
    assert "Filter Longs During Accepted Range Breakdown" in script
    assert "math.sum(belowRangeLow ? 1 : 0, acceptBars)" in script
    assert "math.sum(aboveRangeHigh ? 1 : 0, acceptBars)" in script
    assert "ta.sum(" not in script
    assert "bottomBreakdownSignal ? -1" in script
    assert "topBreakoutSignal ? 1" in script
    assert "bottomReclaimSignal ? 1" in script
    assert "topRejectSignal ? -1" in script
    assert "trendIgnitionLongSignal ? 1" in script
    assert "trendIgnitionShortSignal = false" in script
    assert "trendContinuationLongSignal ? 1" in script
    assert "trendContinuationShortSignal ? -1" in script
    assert "trendTransitionLongSignal ? 1" in script
    assert "trendTransitionShortSignal ? -1" in script
    assert "reversalImpulseLongSignal ? 1" in script
    assert "reversalImpulseShortSignal ? -1" in script
    assert "pdFallbackSignal = tradePdFallback and nativeDirection != 0" in script
    assert "pdFallbackSignal ? nativeDirection : 0" in script
    assert "boundaryEvent" in script
    assert "lightglowSignal = (boundaryEvent or pdFallbackSignal) and mappedDirection != 0 and timeCellAllowsTrade and dateFilterPassed" in script
    assert 'timeCellMode == "Native/Reverse Research" ? boundaryDirection * stableAction : boundaryDirection' in script
    assert 'tradeTopBreakoutOnlyRth = input.bool(true, "Trade Top Breakout Only In US RTH"' in script
    assert 'tradeReversalImpulseLateOnly = input.bool(true, "Trade Reversal Impulse Only In US Late"' in script
    assert 'tradeTrendIgnitionEuropeOnly = input.bool(true, "Trade Trend Ignition Only In Europe"' in script
    assert 'maxHoldBars = input.int(120, "Max Hold Bars"' in script
    assert 'breakevenTriggerR = input.float(1.50, "Breakeven Trigger R"' in script
    assert 'trailAtrMult = input.float(2.00, "Trailing ATR Mult"' in script
    assert "ema20 < ema60" in script
    assert "ema60 <= ema200" in script
    assert "ema20 > ema60" in script
    assert "ema60 >= ema200" in script
    assert "volumeZ" in script
    assert "bodyAtr" in script
    assert "Range Bottom Breakdown Candidate" in script
    assert "Range Bottom Reclaim Candidate" in script
    assert "Range Top Breakout Candidate" in script
    assert "Range Top Reject Candidate" in script
    assert "Range Top Breakout Continuation" in script
    assert "Range Top Sweep Reject Short" in script
