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
