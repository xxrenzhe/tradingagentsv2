# NQ 1m Feature Discovery Ranking

This ranking converts the 5-year NQ 1m walk-forward aggregate into strategy evidence and an LLM debate pack.

- Source aggregate: `.tmp/nq-bar-5y-price-action-walkforward-aggregate.csv`
- Candidates ranked: `116`
- Balanced candidates: `0`

## Verdict

Best risk-controlled candidate: `bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late`

No balanced candidate passed the stability tier; this remains a paper-validation candidate.

## Trading Rule

- Signal: go long when the prior bar breaks the 10m high, the current bar retests that level, then closes back above by 0.0002 of the prior range; go short when the prior bar breaks the 10m low, the current bar retests that level, then closes back below by 0.0002 of the prior range.
- Session: `us_late` UTC window `20:00-23:00`.
- Entry point: enter on the next minute open after the signal bar; long/short follows the signal sign.
- Exit rule: time exit after `15` minutes unless a stop/target is configured.
- Readiness: `risk_controlled`; live_ready=`False`.

## Directional Evidence

```csv
direction,trades,net_points,profit_factor,win_rate,avg_points
long,267,43.875,1.0138477926381821,0.449438202247191,0.16432584269662923
short,214,1530.5,1.5293558149589277,0.4392523364485981,7.151869158878505
```

## Best Candidate

```csv
candidate,family,lookback,threshold,holding_minutes,session,selected_folds,positive_test_folds,pass_folds,test_trades,test_net_points,test_max_drawdown_points,avg_test_profit_factor,avg_test_win_rate,avg_test_stability,min_test_net_points,train_net_points,avg_train_score,positive_test_fold_rate,pass_fold_rate,net_to_drawdown,stable_candidate,long_history_score,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,full_win_rate,full_stability,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score,live_ready,name,source,candidate_universe,risk_denominator,stress_to_drawdown,fold_count_pass,risk_control_pass,stability_pass,selection_tier
bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late,breakout_retest,10,0.0002,15,us_late,3,3,3,481,1574.375,671.0,1.2759264525967218,0.4451019066403681,0.1844849789874354,290.125,6156.5,2.1286444772176973,1.0,1.0,2.346311475409836,True,2.274855654637669,481,1574.375,671.0,1.2759264525967218,0.4451019066403681,0.1844849789874354,1.0,1.0,290.125,290.125,2.274855654637669,False,bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late,walkforward,walkforward_5y_1m,671.0,0.4323770491803279,True,True,False,risk_controlled
```

## Top Candidates

```csv
name,candidate_universe,selection_tier,family,full_trades,full_net_points,full_max_drawdown_points,full_profit_factor,positive_fold_rate,positive_window_rate,min_window_net_points,stress_net_points,best_strategy_score
bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late,walkforward_5y_1m,risk_controlled,breakout_retest,481,1574.375,671.0,1.2759264525967218,1.0,1.0,290.125,290.125,2.274855654637669
bar_best_support_reclaim_lb60_thr0.001_hold15_us_late,walkforward_5y_1m,risk_controlled,support_reclaim,386,782.0,367.125,1.2801534798224836,1.0,1.0,76.5,76.5,1.431323513072774
bar_best_support_reclaim_lb15_thr0.001_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,2292,9505.75,2567.625,1.1899017751634835,0.7692307692307693,0.7692307692307693,-1207.5,-1207.5,11.804124715720205
bar_best_support_reclaim_lb15_thr0.0002_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,2293,8914.875,2567.625,1.179659735498706,0.7692307692307693,0.7692307692307693,-1207.5,-1207.5,11.02653597929162
bar_best_support_reclaim_lb15_thr0.0005_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,2293,8914.875,2567.625,1.179659735498706,0.7692307692307693,0.7692307692307693,-1207.5,-1207.5,11.02653597929162
bar_best_support_reclaim_lb60_thr0.0002_hold60_us_rth,walkforward_5y_1m,research_only,support_reclaim,1447,8765.125,3109.5,1.156186666334842,0.8,0.8,-382.0,-382.0,9.896906756278314
bar_best_support_reclaim_lb30_thr0.001_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,972,3268.25,2077.125,1.1801711131155197,0.7142857142857143,0.7142857142857143,-354.75,-354.75,4.045522333449268
bar_best_support_reclaim_lb30_thr0.0002_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,973,3234.375,2074.125,1.1779350490812948,0.7142857142857143,0.7142857142857143,-354.75,-354.75,4.004703592205759
bar_best_support_reclaim_lb30_thr0.0005_hold30_us_late,walkforward_5y_1m,research_only,support_reclaim,973,3234.375,2074.125,1.1779350490812948,0.7142857142857143,0.7142857142857143,-354.75,-354.75,4.004703592205759
bar_best_support_reclaim_lb60_thr0.0005_hold60_us_rth,walkforward_5y_1m,research_only,support_reclaim,1143,2672.375,3109.5,1.0772665191019477,0.75,0.75,-382.0,-382.0,2.9307092478008454
```

## LLM Debate Pack

```json
{
  "candidates": [
    {
      "bear_case": [
        "full_max_drawdown_points=671.0000",
        "min_window_net_points=290.1250",
        "stress_net_points=290.1250",
        "full_trades=481"
      ],
      "best_strategy_score": 2.274855654637669,
      "bull_case": [
        "positive_fold_rate=1.0000",
        "positive_window_rate=1.0000",
        "full_profit_factor=1.2759",
        "full_stability=0.1845",
        "net_to_drawdown=2.3463"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 0.16432584269662923,
          "direction": "long",
          "net_points": 43.875,
          "profit_factor": 1.0138477926381821,
          "trades": 267,
          "win_rate": 0.449438202247191
        },
        {
          "avg_points": 7.151869158878505,
          "direction": "short",
          "net_points": 1530.5,
          "profit_factor": 1.5293558149589277,
          "trades": 214,
          "win_rate": 0.4392523364485981
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 15 minutes unless a strategy-specific stop/target is configured",
      "family": "breakout_retest",
      "full_net_points": 1574.375,
      "full_profit_factor": 1.2759264525967218,
      "full_stability": 0.1844849789874354,
      "name": "bar_best_breakout_retest_lb10_thr0.0002_hold15_us_late",
      "positive_fold_rate": 1.0,
      "positive_window_rate": 1.0,
      "selection_tier": "risk_controlled",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when the prior bar breaks the 10m high, the current bar retests that level, then closes back above by 0.0002 of the prior range; go short when the prior bar breaks the 10m low, the current bar retests that level, then closes back below by 0.0002 of the prior range"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=367.1250",
        "min_window_net_points=76.5000",
        "stress_net_points=76.5000",
        "full_trades=386"
      ],
      "best_strategy_score": 1.431323513072774,
      "bull_case": [
        "positive_fold_rate=1.0000",
        "positive_window_rate=1.0000",
        "full_profit_factor=1.2802",
        "full_stability=0.2516",
        "net_to_drawdown=2.1301"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 5.847972972972973,
          "direction": "long",
          "net_points": 1081.875,
          "profit_factor": 1.9774138904573688,
          "trades": 185,
          "win_rate": 0.5621621621621622
        },
        {
          "avg_points": -1.4919154228855722,
          "direction": "short",
          "net_points": -299.875,
          "profit_factor": 0.8550715882317405,
          "trades": 201,
          "win_rate": 0.4577114427860697
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 15 minutes unless a strategy-specific stop/target is configured",
      "family": "support_reclaim",
      "full_net_points": 782.0,
      "full_profit_factor": 1.2801534798224836,
      "full_stability": 0.2515995872033024,
      "name": "bar_best_support_reclaim_lb60_thr0.001_hold15_us_late",
      "positive_fold_rate": 1.0,
      "positive_window_rate": 1.0,
      "selection_tier": "risk_controlled",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when price sweeps below the prior 60m low then closes back above that support by 0.001 of the prior range; go short when price sweeps above the prior 60m high then closes back below that resistance by 0.001 of the prior range"
    },
    {
      "bear_case": [
        "full_max_drawdown_points=2567.6250",
        "min_window_net_points=-1207.5000",
        "stress_net_points=-1207.5000",
        "full_trades=2292"
      ],
      "best_strategy_score": 11.804124715720205,
      "bull_case": [
        "positive_fold_rate=0.7692",
        "positive_window_rate=0.7692",
        "full_profit_factor=1.1899",
        "full_stability=0.2283",
        "net_to_drawdown=3.7022"
      ],
      "candidate_universe": "walkforward_5y_1m",
      "decision_hint": "use as LLM debate seed; confirm current live features before taking direction",
      "direction_stats": [
        {
          "avg_points": 9.295765027322405,
          "direction": "long",
          "net_points": 10206.75,
          "profit_factor": 1.429245059849548,
          "trades": 1098,
          "win_rate": 0.529143897996357
        },
        {
          "avg_points": -0.5871021775544388,
          "direction": "short",
          "net_points": -701.0,
          "profit_factor": 0.9783738758888769,
          "trades": 1194,
          "win_rate": 0.47571189279731996
        }
      ],
      "entry_point": "enter on the next minute open after the signal bar; direction is the signal sign",
      "exit_rule": "time exit after 30 minutes unless a strategy-specific stop/target is configured",
      "family": "support_reclaim",
      "full_net_points": 9505.75,
      "full_profit_factor": 1.1899017751634835,
      "full_stability": 0.228266551628818,
      "name": "bar_best_support_reclaim_lb15_thr0.001_hold30_us_late",
      "positive_fold_rate": 0.7692307692307693,
      "positive_window_rate": 0.7692307692307693,
      "selection_tier": "research_only",
      "session_window_utc": "20:00-23:00",
      "signal_rule": "go long when price sweeps below the prior 15m low then closes back above that support by 0.001 of the prior range; go short when price sweeps above the prior 15m high then closes back below that resistance by 0.001 of the prior range"
    }
  ]
}
```
