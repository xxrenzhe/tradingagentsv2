from pathlib import Path


def test_lightglow_paper_validation_pine_contains_manual_trade_review_features():
    script = Path("pine_scripts/lightglow_paper_executable_validation.pine").read_text(encoding="utf-8")

    assert "strategy(\"Lightglow Paper Validation\"" in script
    assert "line.style_dashed" in script
    assert "strategy.closedtrades.profit" in script
    assert "pointsPnl" in script
    assert "label.new" in script
    assert "location.absolute" not in script
    assert 'plotshape(showSignalMarkers and fixedTimeExitCondition, "Time Exit", shape.xcross, location.abovebar' in script
    assert 'exitMode = input.string("Trend Hold"' in script
    assert "holdBars = input.int(2" in script
    assert "maxHoldBars = input.int(120" in script
    assert "atrLength = input.int(14" in script
    assert "initialStopAtr = input.float(1.8" in script
    assert "trailStopAtr = input.float(2.4" in script
    assert "breakevenTriggerAtr = input.float(1.2" in script
    assert "avoidLongBelowEma60Trend" in script
    assert "reverseLightglowSignal = input.bool(true" in script
    assert 'signalMode = input.string("Armed Zone Trigger"' in script
    assert 'rearmMode = input.string("Rearm At Equilibrium"' in script
    assert "cooldownBars = input.int(10" in script
    assert "var bool premiumArmed = true" in script
    assert "var bool discountArmed = true" in script
    assert "lastExitBar" in script
    assert "cooldownPassed" in script
    assert "cooldownBlockedSignal" in script
    assert "premiumThreshold = input.float(0.90" in script
    assert "discountThreshold = input.float(0.10" in script
    assert "strategy.opentrades.entry_bar_index(0)" in script
    assert 'strategy.exit("LG Long Risk", from_entry="LG Long", stop=longProtectiveStop)' in script
    assert 'strategy.exit("LG Short Risk", from_entry="LG Short", stop=shortProtectiveStop)' in script
    assert "var float entryAtr = na" in script
    assert "var float bestFavorablePrice = na" in script
    assert "longProtectiveStop" in script
    assert "shortProtectiveStop" in script
    assert "trendBreakExitCondition" in script
    assert "var int entryBar" not in script
    assert "showRawSignals = input.bool(false" in script
