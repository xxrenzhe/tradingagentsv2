# NQ 1m Feature Discovery Ranking

This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.

- Source aggregate: `.tmp/nq-bar-5y-directional-walkforward-aggregate.csv`
- Candidates ranked: `181`
- Balanced candidates: `0`

## Verdict

Best research candidate: `bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late`

No candidate passed the risk-control gate; use these rows for research and LLM debate only, not automatic submission.

## Trading Rule

- Signal: go long when close is below its 30m mean by more than 1.4 rolling standard deviations; go short when it is above its 30m mean by more than 1.4 rolling standard deviations. Only take long signals.
- Session: `us_late` UTC window `20:00-23:00`.
- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.
- Exit rule: time exit after `60` minutes unless a stop/target is configured.
- Readiness: `research_only`; live_ready=`False`.

## Directional Evidence

```csv
direction,trades,net_points,profit_factor,win_rate,avg_points
long,398,6205.25,1.3767493397286057,0.5577889447236181,15.59108040201005
```

## Best Candidate

```csv
candidate,family,lookback,threshold,holding_minutes,session,selected_folds,positive_test_folds,pass_folds,test_trades,test_net_points,test_max_drawdown_points,avg_test_profit_factor,avg_test_win_rate,avg_test_stability,min_test_net_points,train_net_points,avg_train_score,positive_test_fold_rate,pass_fold_rate,net_to_drawdown,stable_candidate,long_history_score,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,full_win_rate,full_stability,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score,live_ready,name,source,direction_filter,candidate_universe,risk_denominator,stress_to_drawdown,fold_count_pass,risk_control_pass,stability_pass,selection_tier
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,mean_reversion,30,1.4,60,us_late,5,4,4,398,6205.25,2705.625,1.7309329326889002,0.5591245103228217,0.342217309814106,-1128.375,25717.875,4.898930555939054,0.8,0.8,2.2934626934626934,True,7.163406339187987,398,6205.25,2705.625,1.7309329326889002,0.5591245103228217,0.342217309814106,0.8,0.8,-1128.375,-1128.375,7.163406339187987,False,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,walkforward,long,walkforward_5y_1m,2705.625,-0.41704781704781707,True,False,False,research_only
```

## Top Candidates

```csv
name,candidate_universe,selection_tier,family,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score
bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,walkforward_5y_1m,research_only,mean_reversion,398,6205.25,2705.625,1.7309329326889002,0.8,0.8,-1128.375,-1128.375,7.163406339187987
bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,walkforward_5y_1m,research_only,momentum,372,4563.75,891.25,1.7966706070775698,0.8,0.8,-8.875,-8.875,6.725639949164089
bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,walkforward_5y_1m,research_only,mean_reversion,369,4483.875,1011.125,1.5586179740256,1.0,1.0,1157.625,1157.625,5.452278875763782
bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,walkforward_5y_1m,research_only,mean_reversion,500,4569.25,3072.625,1.627265716265255,0.75,0.75,-512.875,-512.875,5.044551488863399
bar_best_momentum_lb60_thr0.0006_hold60_long_us_late,walkforward_5y_1m,research_only,momentum,103,3588.375,587.75,1.7467835282870707,1.0,1.0,1486.875,1486.875,4.925894880595523
bar_best_support_reclaim_lb15_thr0.0002_hold30_long_us_late,walkforward_5y_1m,research_only,support_reclaim,496,3576.75,1176.0,1.3422795966381815,0.75,0.75,-67.375,-67.375,4.6044170275921
bar_best_support_reclaim_lb15_thr0.0005_hold30_long_us_late,walkforward_5y_1m,research_only,support_reclaim,496,3576.75,1176.0,1.3422795966381815,0.75,0.75,-67.375,-67.375,4.6044170275921
bar_best_support_reclaim_lb15_thr0.001_hold30_long_us_late,walkforward_5y_1m,research_only,support_reclaim,496,3576.75,1176.0,1.3422795966381815,0.75,0.75,-67.375,-67.375,4.6044170275921
bar_best_momentum_lb60_thr0.0006_hold15_long_us_late,walkforward_5y_1m,research_only,momentum,444,2939.5,1528.75,1.6399470799115463,0.6,0.6,-974.125,-974.125,3.5231485638874576
bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,walkforward_5y_1m,research_only,support_reclaim,173,2602.875,1484.5,1.3121434778538044,1.0,1.0,952.75,952.75,2.9777977985811424
```

## LLM Debate Pack

```json
{
  "candidates": [
    {
      "bear_case": [
        "full_max_drawdown_points=2705.6250",
        "min_window_net_points=-1128.3750",
        "stress_net_points=-1128.3750",
        "full_trades=398"
      ],
      "best_strategy_score": 7.163406339187987,
      "bull_case": [
        "positive_fold_rate=0.8000",
        "positive_window_rate=0.8000",
        "full_profit_factor=1.7309",
        "full_stability=0.3422",
        "net_to_drawdown=2.2935"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_filter": "long",
      "direction_stats": [
        {
          "avg_points": 15.59108040201005,
          "direction": "long",
          "net_points": 6205.25,
          "profit_factor": 1.3767493397286057,
          "trades": 398,
          "win_rate": 0.5577889447236181
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 60 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 6205.25,
      "full_profit_factor": 1.7309329326889002,
      "full_stability": 0.342217309814106,
      "name": "bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late",
      "positive_fold_rate": 0.8,
      "positive_window_rate": 0.8,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is below its 30m mean by more than 1.4 rolling standard deviations; go short when it is above its 30m mean by more than 1.4 rolling standard deviations. Only take long signals"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=891.2500",
        "min_window_net_points=-8.8750",
        "stress_net_points=-8.8750",
        "full_trades=372"
      ],
      "best_strategy_score": 6.725639949164089,
      "bull_case": [
        "positive_fold_rate=0.8000",
        "positive_window_rate=0.8000",
        "full_profit_factor=1.7967",
        "full_stability=0.3775",
        "net_to_drawdown=5.1206"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_filter": "long",
      "direction_stats": [
        {
          "avg_points": 12.268145161290322,
          "direction": "long",
          "net_points": 4563.75,
          "profit_factor": 1.607245026944315,
          "trades": 372,
          "win_rate": 0.5376344086021505
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "momentum",
      "full_net_points": 4563.75,
      "full_profit_factor": 1.7966706070775698,
      "full_stability": 0.3775459518027829,
      "name": "bar_best_momentum_lb60_thr0.0006_hold30_long_us_late",
      "positive_fold_rate": 0.8,
      "positive_window_rate": 0.8,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when 60m close-to-close return is above 0.0006; go short when it is below -0.0006. Only take long signals"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=1011.1250",
        "min_window_net_points=1157.6250",
        "stress_net_points=1157.6250",
        "full_trades=369"
      ],
      "best_strategy_score": 5.452278875763782,
      "bull_case": [
        "positive_fold_rate=1.0000",
        "positive_window_rate=1.0000",
        "full_profit_factor=1.5586",
        "full_stability=0.4940",
        "net_to_drawdown=4.4345"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_filter": "long",
      "direction_stats": [
        {
          "avg_points": 12.151422764227643,
          "direction": "long",
          "net_points": 4483.875,
          "profit_factor": 1.595290251916758,
          "trades": 369,
          "win_rate": 0.5284552845528455
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "mean_reversion",
      "full_net_points": 4483.875,
      "full_profit_factor": 1.5586179740256,
      "full_stability": 0.4940398432397126,
      "name": "bar_best_mean_reversion_lb10_thr1_hold30_long_us_late",
      "positive_fold_rate": 1.0,
      "positive_window_rate": 1.0,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when close is below its 10m mean by more than 1 rolling standard deviations; go short when it is above its 10m mean by more than 1 rolling standard deviations. Only take long signals"
    }
  ]
}
```
