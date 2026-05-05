# NQ 1m Feature Discovery Ranking

This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.

- Source aggregate: `.tmp/nq-bar-5y-walkforward-aggregate.csv`
- Candidates ranked: `13`
- Balanced candidates: `0`

## Verdict

Best research candidate: `bar_best_mean_reversion_lb30_thr1_hold30_us_rth`

No candidate passed the risk-control gate; use these rows for research and LLM debate only, not automatic submission.

## Trading Rule

- Signal: go long when close is below its 30m mean by more than 1 rolling standard deviations; go short when it is above its 30m mean by more than 1 rolling standard deviations.
- Session: `us_rth` UTC window `13:30-20:00`.
- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.
- Exit rule: time exit after `30` minutes unless a stop/target is configured.
- Readiness: `research_only`; live_ready=`False`.

## Best Candidate

```csv
candidate,family,lookback,threshold,holding_minutes,session,selected_folds,positive_test_folds,pass_folds,test_trades,test_net_points,test_max_drawdown_points,avg_test_profit_factor,avg_test_win_rate,avg_test_stability,min_test_net_points,train_net_points,avg_train_score,positive_test_fold_rate,pass_fold_rate,net_to_drawdown,stable_candidate,long_history_score,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,full_win_rate,full_stability,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score,live_ready,name,source,candidate_universe,risk_denominator,stress_to_drawdown,fold_count_pass,risk_control_pass,stability_pass,selection_tier
bar_best_mean_reversion_lb30_thr1_hold30_us_rth,mean_reversion,30,1.0,30,us_rth,5,4,3,3137,10694.375,4022.75,1.138392097676696,0.5157157595626982,0.2016574452512564,-1821.5,32503.875,2.7504694537560708,0.8,0.6,2.6584736809396556,True,11.758315256698122,3137,10694.375,4022.75,1.138392097676696,0.5157157595626982,0.2016574452512564,0.8,0.6,-1821.5,-1821.5,11.758315256698122,False,bar_best_mean_reversion_lb30_thr1_hold30_us_rth,walkforward,walkforward_5y_1m,4022.75,-0.4527997016966006,True,False,False,research_only
```

## Top Candidates

```csv
name,candidate_universe,selection_tier,family,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score
bar_best_mean_reversion_lb30_thr1_hold30_us_rth,walkforward_5y_1m,research_only,mean_reversion,3137,10694.375,4022.75,1.138392097676696,0.8,0.6,-1821.5,-1821.5,11.758315256698122
bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth,walkforward_5y_1m,research_only,mean_reversion,598,5359.25,1812.75,1.3602524136424363,1.0,1.0,5359.25,5359.25,5.6403435194349045
bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth,walkforward_5y_1m,research_only,mean_reversion,2033,3335.125,2870.5,1.040146433570073,0.5,0.25,-1017.875,-1017.875,3.560889125698179
bar_best_mean_reversion_lb30_thr1.4_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,693,2751.875,2028.875,1.1154455249944148,1.0,1.0,291.5,291.5,3.0562946217831293
bar_best_mean_reversion_lb30_thr1_hold15_us_rth,walkforward_5y_1m,research_only,mean_reversion,989,904.125,1855.75,1.047002326397463,1.0,1.0,904.125,904.125,0.9609771503701084
bar_best_mean_reversion_lb60_thr1_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,643,694.625,2525.5,1.025900677833378,1.0,1.0,335.5,335.5,0.7504934233320135
bar_best_mean_reversion_lb15_thr1.4_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,2558,443.25,3143.0,0.9994691628571352,0.7142857142857143,0.4285714285714285,-2156.0,-2156.0,0.5133309481533617
bar_best_mean_reversion_lb15_thr0.6_hold15_us_rth,walkforward_5y_1m,research_only,mean_reversion,1178,166.25,977.375,1.01280459039752,1.0,0.0,166.25,166.25,0.1835256266786034
bar_best_mean_reversion_lb15_thr0.6_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,372,-171.0,2806.875,0.9848065838136808,0.0,0.0,-171.0,-171.0,0.0
bar_best_mean_reversion_lb30_thr1_hold60_us_rth,walkforward_5y_1m,research_only,mean_reversion,714,-280.0,3231.375,0.9800140883974164,0.5,0.0,-441.875,-441.875,0.0
```

## LLM Debate Pack

```json
{
  "candidates": [
    {
      "bear_case": [
        "full_max_drawdown_points=4022.7500",
        "min_window_net_points=-1821.5000",
        "stress_net_points=-1821.5000",
        "full_trades=3137"
      ],
      "best_strategy_score": 11.758315256698122,
      "bull_case": [
        "positive_fold_rate=0.8000",
        "positive_window_rate=0.6000",
        "full_profit_factor=1.1384",
        "full_stability=0.2017",
        "net_to_drawdown=2.6585"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 10694.375,
      "full_profit_factor": 1.138392097676696,
      "full_stability": 0.2016574452512564,
      "name": "bar_best_mean_reversion_lb30_thr1_hold30_us_rth",
      "positive_fold_rate": 0.8,
      "positive_window_rate": 0.6,
      "selection_tier": "research_only",
      "session_window_utc": "13:30-20:00",
      "signal_rule": "go long when close is below its 30m mean by more than 1 rolling standard deviations; go short when it is above its 30m mean by more than 1 rolling standard deviations"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=1812.7500",
        "min_window_net_points=5359.2500",
        "stress_net_points=5359.2500",
        "full_trades=598"
      ],
      "best_strategy_score": 5.6403435194349045,
      "bull_case": [
        "positive_fold_rate=1.0000",
        "positive_window_rate=1.0000",
        "full_profit_factor=1.3603",
        "full_stability=0.0425",
        "net_to_drawdown=2.9564"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 5359.25,
      "full_profit_factor": 1.3602524136424363,
      "full_stability": 0.0425288753799392,
      "name": "bar_best_mean_reversion_lb30_thr0.6_hold30_us_rth",
      "positive_fold_rate": 1.0,
      "positive_window_rate": 1.0,
      "selection_tier": "research_only",
      "session_window_utc": "13:30-20:00",
      "signal_rule": "go long when close is below its 30m mean by more than 0.6 rolling standard deviations; go short when it is above its 30m mean by more than 0.6 rolling standard deviations"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=2870.5000",
        "min_window_net_points=-1017.8750",
        "stress_net_points=-1017.8750",
        "full_trades=2033"
      ],
      "best_strategy_score": 3.560889125698179,
      "bull_case": [
        "positive_fold_rate=0.5000",
        "positive_window_rate=0.2500",
        "full_profit_factor=1.0401",
        "full_stability=0.1090",
        "net_to_drawdown=1.1619"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 3335.125,
      "full_profit_factor": 1.040146433570073,
      "full_stability": 0.1089973434476828,
      "name": "bar_best_mean_reversion_lb60_thr1.4_hold30_us_rth",
      "positive_fold_rate": 0.5,
      "positive_window_rate": 0.25,
      "selection_tier": "research_only",
      "session_window_utc": "13:30-20:00",
      "signal_rule": "go long when close is below its 60m mean by more than 1.4 rolling standard deviations; go short when it is above its 60m mean by more than 1.4 rolling standard deviations"
    }
  ]
}
```
