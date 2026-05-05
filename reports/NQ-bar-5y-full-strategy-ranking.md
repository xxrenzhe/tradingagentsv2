# NQ 1m Feature Discovery Ranking

This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.

- Source aggregate: `.tmp/nq-bar-5y-full-walkforward-aggregate.csv`
- Candidates ranked: `142`
- Balanced candidates: `0`

## Verdict

Best research candidate: `bar_best_momentum_lb10_thr0.0003_hold60_us_late`

No candidate passed the risk-control gate; use these rows for research and LLM debate only, not automatic submission.

## Trading Rule

- Signal: go long when 10m close-to-close return is above 0.0003; go short when it is below -0.0003.
- Session: `us_late` UTC window `20:00-23:00`.
- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.
- Exit rule: time exit after `60` minutes unless a stop/target is configured.
- Readiness: `research_only`; live_ready=`False`.

## Best Candidate

```csv
candidate,family,lookback,threshold,holding_minutes,session,selected_folds,positive_test_folds,pass_folds,test_trades,test_net_points,test_max_drawdown_points,avg_test_profit_factor,avg_test_win_rate,avg_test_stability,min_test_net_points,train_net_points,avg_train_score,positive_test_fold_rate,pass_fold_rate,net_to_drawdown,stable_candidate,long_history_score,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,full_win_rate,full_stability,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score,live_ready,name,source,candidate_universe,risk_denominator,stress_to_drawdown,fold_count_pass,risk_control_pass,stability_pass,selection_tier
bar_best_momentum_lb10_thr0.0003_hold60_us_late,momentum,10,0.0003,60,us_late,5,3,3,533,4652.875,1806.75,1.150553051985165,0.5380354125238496,0.2695501730103806,-1211.625,40309.375,5.329243042166195,0.6,0.6,2.5752732807527328,True,5.442248612559448,533,4652.875,1806.75,1.150553051985165,0.5380354125238496,0.2695501730103806,0.6,0.6,-1211.625,-1211.625,5.442248612559448,False,bar_best_momentum_lb10_thr0.0003_hold60_us_late,walkforward,walkforward_5y_1m,1806.75,-0.6706102117061021,True,False,False,research_only
```

## Top Candidates

```csv
name,candidate_universe,selection_tier,family,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score
bar_best_momentum_lb10_thr0.0003_hold60_us_late,walkforward_5y_1m,research_only,momentum,533,4652.875,1806.75,1.150553051985165,0.6,0.6,-1211.625,-1211.625,5.442248612559448
bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,495,3745.375,677.875,1.5078834360243776,0.75,0.75,-276.375,-276.375,5.413572302599924
bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,495,3745.375,677.875,1.5078834360243776,0.75,0.75,-276.375,-276.375,5.413572302599924
bar_best_vwap_reclaim_lb30_thr0.001_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,495,3641.625,677.875,1.4963003166763815,0.75,0.75,-276.375,-276.375,5.292501523315332
bar_best_mean_reversion_lb30_thr1_hold60_all,walkforward_5y_1m,research_only,mean_reversion,2484,3482.5,3406.875,1.0718796071140944,1.0,0.5,339.625,339.625,3.684017310150158
bar_best_momentum_lb15_thr0.0003_hold30_us_rth,walkforward_5y_1m,research_only,momentum,2442,2214.0,1646.0,1.0550187973830858,0.5,0.5,-1113.5,-1113.5,2.5024041944454116
bar_best_mean_reversion_lb15_thr0.6_hold30_europe,walkforward_5y_1m,research_only,mean_reversion,673,2205.375,810.25,1.2076673179688788,1.0,1.0,2205.375,2205.375,2.473515813474151
bar_best_mean_reversion_lb30_thr1.4_hold60_us_late,walkforward_5y_1m,research_only,mean_reversion,306,2155.25,2409.625,1.1286651219837984,0.6666666666666666,0.6666666666666666,-1961.0,-1961.0,2.3415937929606105
bar_best_breakout_lb5_thr0_hold60_us_late,walkforward_5y_1m,research_only,breakout,224,2094.25,2470.0,1.1120239839443726,0.5,0.0,-1229.5,-1229.5,2.1770595907058268
bar_best_momentum_lb5_thr0.001_hold60_us_late,walkforward_5y_1m,research_only,momentum,77,1761.875,851.25,1.510300133956048,1.0,1.0,1761.875,1761.875,1.9804903561399847
```

## LLM Debate Pack

```json
{
  "candidates": [
    {
      "bear_case": [
        "full_max_drawdown_points=1806.7500",
        "min_window_net_points=-1211.6250",
        "stress_net_points=-1211.6250",
        "full_trades=533"
      ],
      "best_strategy_score": 5.442248612559448,
      "bull_case": [
        "positive_fold_rate=0.6000",
        "positive_window_rate=0.6000",
        "full_profit_factor=1.1506",
        "full_stability=0.2696",
        "net_to_drawdown=2.5753"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 60 minutes unless a strategy-specific stop/target is configured",
      "family": "momentum",
      "full_net_points": 4652.875,
      "full_profit_factor": 1.150553051985165,
      "full_stability": 0.2695501730103806,
      "name": "bar_best_momentum_lb10_thr0.0003_hold60_us_late",
      "positive_fold_rate": 0.6,
      "positive_window_rate": 0.6,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when 10m close-to-close return is above 0.0003; go short when it is below -0.0003"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=677.8750",
        "min_window_net_points=-276.3750",
        "stress_net_points=-276.3750",
        "full_trades=495"
      ],
      "best_strategy_score": 5.413572302599924,
      "bull_case": [
        "positive_fold_rate=0.7500",
        "positive_window_rate=0.7500",
        "full_profit_factor=1.5079",
        "full_stability=0.2206",
        "net_to_drawdown=5.5252"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "vwap_reclaim",
      "full_net_points": 3745.375,
      "full_profit_factor": 1.5078834360243776,
      "full_stability": 0.220552983167911,
      "name": "bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late",
      "positive_fold_rate": 0.75,
      "positive_window_rate": 0.75,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is more than 0.0002 above cumulative VWAP and 30m momentum is positive; go short when close is more than 0.0002 below cumulative VWAP and 30m momentum is negative"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=677.8750",
        "min_window_net_points=-276.3750",
        "stress_net_points=-276.3750",
        "full_trades=495"
      ],
      "best_strategy_score": 5.413572302599924,
      "bull_case": [
        "positive_fold_rate=0.7500",
        "positive_window_rate=0.7500",
        "full_profit_factor=1.5079",
        "full_stability=0.2206",
        "net_to_drawdown=5.5252"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "vwap_reclaim",
      "full_net_points": 3745.375,
      "full_profit_factor": 1.5078834360243776,
      "full_stability": 0.220552983167911,
      "name": "bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late",
      "positive_fold_rate": 0.75,
      "positive_window_rate": 0.75,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is more than 0.0005 above cumulative VWAP and 30m momentum is positive; go short when close is more than 0.0005 below cumulative VWAP and 30m momentum is negative"
    }
  ]
}
```
