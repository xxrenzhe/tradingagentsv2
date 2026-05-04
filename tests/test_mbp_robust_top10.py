import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "optimize_mbp_robust_top10.py"
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location("optimize_mbp_robust_top10", SCRIPT_PATH)
robust_top10 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["optimize_mbp_robust_top10"] = robust_top10
SPEC.loader.exec_module(robust_top10)

_markdown_table = robust_top10._markdown_table
deduplicate_ranked_results = robust_top10.deduplicate_ranked_results
_rolling_window_masks = robust_top10._rolling_window_masks
_advanced_neighbors = robust_top10._advanced_neighbors
AdvancedStrategySpec = robust_top10.AdvancedStrategySpec

REPORT_PATH = SCRIPTS_DIR / "generate_mbp_live_ready_report.py"
REPORT_SPEC = importlib.util.spec_from_file_location("generate_mbp_live_ready_report", REPORT_PATH)
live_ready_report = importlib.util.module_from_spec(REPORT_SPEC)
assert REPORT_SPEC.loader is not None
sys.modules["generate_mbp_live_ready_report"] = live_ready_report
REPORT_SPEC.loader.exec_module(live_ready_report)

_advanced_spec_from_row = live_ready_report._advanced_spec_from_row

REFINE_PATH = SCRIPTS_DIR / "refine_mbp_top_mean_reversion.py"
REFINE_SPEC = importlib.util.spec_from_file_location("refine_mbp_top_mean_reversion", REFINE_PATH)
refine_top_mean_reversion = importlib.util.module_from_spec(REFINE_SPEC)
assert REFINE_SPEC.loader is not None
sys.modules["refine_mbp_top_mean_reversion"] = refine_top_mean_reversion
REFINE_SPEC.loader.exec_module(refine_top_mean_reversion)

generate_refined_specs = refine_top_mean_reversion.generate_refined_specs

ASSESS_PATH = SCRIPTS_DIR / "assess_mbp_top10_enhancements.py"
ASSESS_SPEC = importlib.util.spec_from_file_location("assess_mbp_top10_enhancements", ASSESS_PATH)
assess_top10 = importlib.util.module_from_spec(ASSESS_SPEC)
assert ASSESS_SPEC.loader is not None
sys.modules["assess_mbp_top10_enhancements"] = assess_top10
ASSESS_SPEC.loader.exec_module(assess_top10)

_passes_live_ready = assess_top10._passes_live_ready

ENHANCED_REPORT_PATH = SCRIPTS_DIR / "generate_mbp_enhanced_top10_report.py"
ENHANCED_REPORT_SPEC = importlib.util.spec_from_file_location("generate_mbp_enhanced_top10_report", ENHANCED_REPORT_PATH)
enhanced_top10_report = importlib.util.module_from_spec(ENHANCED_REPORT_SPEC)
assert ENHANCED_REPORT_SPEC.loader is not None
sys.modules["generate_mbp_enhanced_top10_report"] = enhanced_top10_report
ENHANCED_REPORT_SPEC.loader.exec_module(enhanced_top10_report)

_load_candidates = enhanced_top10_report._load_candidates
_load_benchmark = enhanced_top10_report._load_benchmark


def test_markdown_table_formats_without_optional_dependencies():
    table = _markdown_table(pd.DataFrame([{"name": "strategy", "score": 1.23456}]))

    assert "| name | score |" in table
    assert "| strategy | 1.2346 |" in table


def test_deduplicate_ranked_results_keeps_best_profile():
    rows = pd.DataFrame(
        [
            {
                "name": "base",
                "source": "base",
                "family": "momentum",
                "full_trades": 10,
                "full_net_points": 100.0,
                "full_max_drawdown_points": 20.0,
                "full_profit_factor": 1.5,
                "full_score": 4.0,
                "robust_score": 3.0,
            },
            {
                "name": "advanced_duplicate",
                "source": "advanced",
                "family": "momentum",
                "full_trades": 10,
                "full_net_points": 100.0,
                "full_max_drawdown_points": 20.0,
                "full_profit_factor": 1.5,
                "full_score": 4.0,
                "robust_score": 3.0,
            },
            {
                "name": "other",
                "source": "advanced",
                "family": "vwap_reclaim",
                "full_trades": 11,
                "full_net_points": 120.0,
                "full_max_drawdown_points": 25.0,
                "full_profit_factor": 1.6,
                "full_score": 3.5,
                "robust_score": 2.0,
            },
        ]
    )

    deduped = deduplicate_ranked_results(rows)

    assert deduped["name"].tolist() == ["advanced_duplicate", "other"]


def test_rolling_window_masks_use_trade_dates():
    frame = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(
                [
                    "2026-03-01",
                    "2026-03-02",
                    "2026-03-03",
                    "2026-03-04",
                    "2026-03-05",
                    "2026-03-06",
                ]
            ).date
        }
    )

    masks = _rolling_window_masks(frame, window_days=3, step_days=2)

    assert len(masks) == 2
    assert masks[0].sum() == 3
    assert masks[1].sum() == 3


def test_advanced_neighbors_create_bounded_one_step_variants():
    seed = AdvancedStrategySpec(
        name="seed",
        family="mean_reversion",
        lookback=3,
        threshold=0.6,
        min_hold=1,
        max_hold=10,
        exit_mode="reverse_vwap",
        session="europe",
        volatility_filter="not_low",
        imbalance_threshold=0.35,
        max_spread_quantile=0.75,
        min_depth_quantile=0.25,
        stop_loss_points=None,
        take_profit_points=None,
    )

    neighbors = list(_advanced_neighbors(seed))

    assert neighbors
    assert all(spec.name.startswith("adv_local_mean_reversion_") for spec in neighbors)
    assert len({spec.name for spec in neighbors}) == len(neighbors)
    assert len(neighbors) < 30


def test_live_ready_report_rebuilds_local_advanced_spec_from_row():
    row = pd.Series(
        {
            "name": "adv_local_mean_reversion_lb5_thr0.6_min1_max5_reverse_vwap_europe_not_low_imb0.35",
            "family": "mean_reversion",
            "lookback": 5,
            "threshold": 0.6,
            "min_hold": 1,
            "max_hold": 5,
            "exit_mode": "reverse_vwap",
            "session": "europe",
            "volatility_filter": "not_low",
            "imbalance_threshold": 0.35,
            "max_spread_quantile": 0.75,
            "min_depth_quantile": 0.25,
            "stop_loss_points": pd.NA,
            "take_profit_points": pd.NA,
        }
    )

    spec = _advanced_spec_from_row(row)

    assert spec.name.startswith("adv_local_mean_reversion")
    assert spec.lookback == 5
    assert spec.exit_mode == "reverse_vwap"
    assert spec.stop_loss_points is None


def test_refined_specs_stay_focused_on_top_mean_reversion_edge():
    specs = generate_refined_specs()

    assert len(specs) == 576
    assert {spec.family for spec in specs} == {"mean_reversion"}
    assert {spec.session for spec in specs} == {"europe"}
    assert all(spec.name.startswith("adv_refined_mean_reversion_") for spec in specs)


def test_top10_enhancement_live_ready_gate_requires_window_and_cost_strength():
    row = {
        "worst_cost_net_points": 10.0,
        "positive_fold_rate": 0.80,
        "positive_window_rate": 0.70,
        "min_window_trades": 5,
        "full_trades": 200,
        "full_profit_factor": 1.25,
    }

    assert _passes_live_ready(row)

    row["min_window_trades"] = 4
    assert not _passes_live_ready(row)


def test_enhanced_top10_ranking_prioritizes_core_edge(tmp_path):
    frame = pd.DataFrame(
        [
            {
                "name": "high_net_weak_edge",
                "family": "momentum",
                "lookback": 10,
                "threshold": 0.1,
                "min_hold": 1,
                "max_hold": 5,
                "exit_mode": "time",
                "session": "all",
                "volatility_filter": "all",
                "imbalance_threshold": 0.35,
                "stop_loss_points": pd.NA,
                "take_profit_points": pd.NA,
                "live_ready": True,
                "preserves_core_edge": False,
                "full_trades": 300,
                "full_profit_factor": 1.5,
                "full_net_points": 5000.0,
                "worst_cost_net_points": 1000.0,
                "min_window_net_points": -200.0,
                "full_max_drawdown_points": 500.0,
            },
            {
                "name": "lower_net_core_edge",
                "family": "momentum",
                "lookback": 11,
                "threshold": 0.1,
                "min_hold": 1,
                "max_hold": 5,
                "exit_mode": "time",
                "session": "all",
                "volatility_filter": "all",
                "imbalance_threshold": 0.35,
                "stop_loss_points": pd.NA,
                "take_profit_points": pd.NA,
                "live_ready": True,
                "preserves_core_edge": True,
                "full_trades": 300,
                "full_profit_factor": 1.5,
                "full_net_points": 1000.0,
                "worst_cost_net_points": 800.0,
                "min_window_net_points": 50.0,
                "full_max_drawdown_points": 200.0,
            },
        ]
    )
    path = tmp_path / "candidates.csv"
    frame.to_csv(path, index=False)

    ranked = _load_candidates([path])

    assert ranked.iloc[0]["name"] == "lower_net_core_edge"


def test_enhanced_report_loads_strict_benchmark(tmp_path):
    benchmark_name = "adv_refined_mean_reversion_lb7_thr0.65_min1_max6_reverse_europe_not_low_imb0.3"
    frame = pd.DataFrame(
        [
            {
                "name": benchmark_name,
                "family": "mean_reversion",
                "lookback": 7,
                "threshold": 0.65,
                "min_hold": 1,
                "max_hold": 6,
                "exit_mode": "reverse",
                "session": "europe",
                "volatility_filter": "not_low",
                "imbalance_threshold": 0.3,
                "stop_loss_points": pd.NA,
                "take_profit_points": pd.NA,
                "live_ready_strict": True,
                "full_net_points": 1979.75,
                "worst_cost_net_points": 1397.75,
                "min_window_net_points": 55.75,
                "full_max_drawdown_points": 215.375,
            }
        ]
    )
    path = tmp_path / "refined.csv"
    frame.to_csv(path, index=False)

    benchmark = _load_benchmark([path], benchmark_name)

    assert benchmark["name"] == benchmark_name
    assert benchmark["live_ready"]
    assert benchmark["preserves_core_edge"]
