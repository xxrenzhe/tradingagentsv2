# NQ 1m Feature Discovery Ranking

This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.

- Source aggregate: `.tmp/nq-bar-5y-broader-walkforward-aggregate.csv`
- Candidates ranked: `46`
- Balanced candidates: `0`

## Verdict

Best research candidate: `bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late`

No candidate passed the risk-control gate; use these rows for research and LLM debate only, not automatic submission.

## Trading Rule

- Signal: go long when close is more than 0.0002 above cumulative VWAP and 30m momentum is positive; go short when close is more than 0.0002 below cumulative VWAP and 30m momentum is negative.
- Session: `us_late` UTC window `20:00-23:00`.
- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.
- Exit rule: time exit after `30` minutes unless a stop/target is configured.
- Readiness: `research_only`; live_ready=`False`.

## Directional Evidence

```csv
direction,trades,net_points,profit_factor,win_rate,avg_points
long,592,4037.0,1.2651995401543767,0.5236486486486487,6.819256756756757
short,22,-30.5,0.9248999692212989,0.6818181818181818,-1.3863636363636365
```

## Best Candidate

```csv
candidate,family,lookback,threshold,holding_minutes,session,selected_folds,positive_test_folds,pass_folds,test_trades,test_net_points,test_max_drawdown_points,avg_test_profit_factor,avg_test_win_rate,avg_test_stability,min_test_net_points,train_net_points,avg_train_score,positive_test_fold_rate,pass_fold_rate,net_to_drawdown,stable_candidate,long_history_score,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,full_win_rate,full_stability,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score,live_ready,name,source,candidate_universe,risk_denominator,stress_to_drawdown,fold_count_pass,risk_control_pass,stability_pass,selection_tier
bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late,vwap_reclaim,30,0.0002,30,us_late,5,4,4,614,4006.5,1367.125,1.3541911143943977,0.5291021011970645,0.1892055640761017,-276.375,17670.5,2.412836780698689,0.8,0.8,2.9306025418304835,True,5.174786741562668,614,4006.5,1367.125,1.3541911143943977,0.5291021011970645,0.1892055640761017,0.8,0.8,-276.375,-276.375,5.174786741562668,False,bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late,walkforward,walkforward_5y_1m,1367.125,-0.20215781292859103,True,False,False,research_only
```

## Top Candidates

```csv
name,candidate_universe,selection_tier,family,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score
bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,614,4006.5,1367.125,1.3541911143943977,0.8,0.8,-276.375,-276.375,5.174786741562668
bar_best_mean_reversion_lb30_thr1.4_hold60_us_late,walkforward_5y_1m,research_only,mean_reversion,306,2155.25,2409.625,1.1286651219837984,0.6666666666666666,0.6666666666666666,-1961.0,-1961.0,2.3415937929606105
bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,372,1681.75,677.875,1.2305783367085843,0.6666666666666666,0.6666666666666666,-276.375,-276.375,2.157108966955429
bar_best_vwap_reclaim_lb30_thr0.001_hold30_us_late,walkforward_5y_1m,research_only,vwap_reclaim,372,1578.0,677.875,1.215134177577923,0.6666666666666666,0.6666666666666666,-276.375,-276.375,2.035160878170141
bar_best_vwap_reclaim_lb60_thr0.0002_hold15_us_late,walkforward_5y_1m,research_only,vwap_reclaim,186,1219.0,1682.75,5.2292064688901565,0.5,0.5,-778.375,-778.375,1.2975414200363653
bar_best_vwap_reclaim_lb60_thr0.0005_hold15_us_late,walkforward_5y_1m,research_only,vwap_reclaim,186,1219.0,1682.75,5.2292064688901565,0.5,0.5,-778.375,-778.375,1.2975414200363653
bar_best_mean_reversion_lb60_thr2_hold60_us_late,walkforward_5y_1m,research_only,mean_reversion,71,643.375,1257.875,1.1365614221278857,1.0,1.0,643.375,643.375,0.6953219529464375
bar_best_mean_reversion_lb15_thr2_hold30_us_rth,walkforward_5y_1m,research_only,mean_reversion,1111,354.625,3046.0,0.9935896799555968,0.5,0.5,-1093.5,-1093.5,0.3659944509705352
bar_best_mean_reversion_lb15_thr2_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,340,328.0,3432.75,1.0199062343534266,1.0,0.0,328.0,328.0,0.3377043186949239
bar_best_vwap_reclaim_lb30_thr0.0002_hold15_us_late,walkforward_5y_1m,research_only,vwap_reclaim,340,289.5,1316.5,1.1473340693077807,0.5,0.5,-1122.0,-1122.0,0.3129497963052117
```

## LLM Debate Pack

```json
{
  "candidates": [
    {
      "bear_case": [
        "full_max_drawdown_points=1367.1250",
        "min_window_net_points=-276.3750",
        "stress_net_points=-276.3750",
        "full_trades=614"
      ],
      "best_strategy_score": 5.174786741562668,
      "bull_case": [
        "positive_fold_rate=0.8000",
        "positive_window_rate=0.8000",
        "full_profit_factor=1.3542",
        "full_stability=0.1892",
        "net_to_drawdown=2.9306"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 6.819256756756757,
          "direction": "long",
          "net_points": 4037.0,
          "profit_factor": 1.2651995401543767,
          "trades": 592,
          "win_rate": 0.5236486486486487
        },
        {
          "avg_points": -1.3863636363636365,
          "direction": "short",
          "net_points": -30.5,
          "profit_factor": 0.9248999692212989,
          "trades": 22,
          "win_rate": 0.6818181818181818
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "vwap_reclaim",
      "full_net_points": 4006.5,
      "full_profit_factor": 1.3541911143943977,
      "full_stability": 0.1892055640761017,
      "name": "bar_best_vwap_reclaim_lb30_thr0.0002_hold30_us_late",
      "positive_fold_rate": 0.8,
      "positive_window_rate": 0.8,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is more than 0.0002 above cumulative VWAP and 30m momentum is positive; go short when close is more than 0.0002 below cumulative VWAP and 30m momentum is negative"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=2409.6250",
        "min_window_net_points=-1961.0000",
        "stress_net_points=-1961.0000",
        "full_trades=306"
      ],
      "best_strategy_score": 2.3415937929606105,
      "bull_case": [
        "positive_fold_rate=0.6667",
        "positive_window_rate=0.6667",
        "full_profit_factor=1.1287",
        "full_stability=0.3334",
        "net_to_drawdown=0.8944"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 13.609375,
          "direction": "long",
          "net_points": 1959.75,
          "profit_factor": 1.2726419031719534,
          "trades": 144,
          "win_rate": 0.5833333333333334
        },
        {
          "avg_points": 1.2067901234567902,
          "direction": "short",
          "net_points": 195.5,
          "profit_factor": 1.0264430392587833,
          "trades": 162,
          "win_rate": 0.48148148148148145
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 60 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 2155.25,
      "full_profit_factor": 1.1286651219837984,
      "full_stability": 0.3333945453211335,
      "name": "bar_best_mean_reversion_lb30_thr1.4_hold60_us_late",
      "positive_fold_rate": 0.6666666666666666,
      "positive_window_rate": 0.6666666666666666,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is below its 30m mean by more than 1.4 rolling standard deviations; go short when it is above its 30m mean by more than 1.4 rolling standard deviations"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=677.8750",
        "min_window_net_points=-276.3750",
        "stress_net_points=-276.3750",
        "full_trades=372"
      ],
      "best_strategy_score": 2.157108966955429,
      "bull_case": [
        "positive_fold_rate=0.6667",
        "positive_window_rate=0.6667",
        "full_profit_factor=1.2306",
        "full_stability=0.0657",
        "net_to_drawdown=2.4809"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 4.892142857142857,
          "direction": "long",
          "net_points": 1712.25,
          "profit_factor": 1.1994728488008037,
          "trades": 350,
          "win_rate": 0.5228571428571429
        },
        {
          "avg_points": -1.3863636363636365,
          "direction": "short",
          "net_points": -30.5,
          "profit_factor": 0.9248999692212989,
          "trades": 22,
          "win_rate": 0.6818181818181818
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "vwap_reclaim",
      "full_net_points": 1681.75,
      "full_profit_factor": 1.2305783367085843,
      "full_stability": 0.0657014155484365,
      "name": "bar_best_vwap_reclaim_lb30_thr0.0005_hold30_us_late",
      "positive_fold_rate": 0.6666666666666666,
      "positive_window_rate": 0.6666666666666666,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is more than 0.0005 above cumulative VWAP and 30m momentum is positive; go short when close is more than 0.0005 below cumulative VWAP and 30m momentum is negative"
    }
  ]
}
```
