from pathlib import Path


def test_lightglow_paper_validation_pine_contains_manual_trade_review_features():
    script = Path("pine_scripts/lightglow_paper_executable_validation.pine").read_text(encoding="utf-8")

    assert "strategy(\"Lightglow Paper Validation\"" in script
    assert "line.style_dashed" in script
    assert "strategy.closedtrades.profit" in script
    assert "pointsPnl" in script
    assert "label.new" in script
    assert "location.absolute" not in script
    assert 'plotshape(showSignalMarkers and exitCondition, "Time Exit", shape.xcross, location.abovebar' in script
    assert "holdBars = input.int(2" in script
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
    assert "var int entryBar" not in script
    assert "showRawSignals = input.bool(false" in script
