# NQ Feature Promotion Shortlist

This report combines directional 5-year walk-forward results, post-filter state mining, and past-fold selected validation.

- Directional ranking: `.tmp/nq-bar-5y-directional-strategy-ranking.csv`
- State-filter mining: `.tmp/nq-bar-5y-state-filtered-features.csv`
- Past-fold validation: `.tmp/nq-state-filter-past-fold-validation-aggregate.csv`
- Shortlist rows: `439`

## promote_to_strict_gate

```csv
tier,candidate,filter,evidence_type,trades,net_points,profit_factor,positive_fold_rate,stress_points,baseline_net_points,net_improvement,selected_folds,promotion_score,next_action
promote_to_strict_gate,bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,none,directional_walkforward,369,4483.875,1.5586179740256,1.0,1157.625,4483.875,0.0,2,3256.13953441536,integrate_into_strict_gate_and_recent_oos
promote_to_strict_gate,bar_best_momentum_lb60_thr0.0006_hold60_long_us_late,none,directional_walkforward,103,3588.375,1.7467835282870707,1.0,1486.875,3588.375,0.0,2,3145.1638669722424,integrate_into_strict_gate_and_recent_oos
```

## paper_watchlist

```csv
tier,candidate,filter,evidence_type,trades,net_points,profit_factor,positive_fold_rate,stress_points,baseline_net_points,net_improvement,selected_folds,promotion_score,next_action
paper_watchlist,bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,none,directional_walkforward,372,4563.75,1.7966706070775698,0.8,-8.875,4563.75,0.0,5,3170.064864246542,paper_trade_and_tighten_state_filter
paper_watchlist,bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,none,directional_walkforward,173,2602.875,1.3121434778538044,1.0,952.75,2602.875,0.0,2,2638.0048367122827,paper_trade_and_tighten_state_filter
paper_watchlist,bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late,none,directional_walkforward,173,2602.875,1.3121434778538044,1.0,952.75,2602.875,0.0,2,2638.0048367122827,paper_trade_and_tighten_state_filter
paper_watchlist,bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late,none,directional_walkforward,173,2602.875,1.3121434778538044,1.0,952.75,2602.875,0.0,2,2638.0048367122827,paper_trade_and_tighten_state_filter
paper_watchlist,bar_best_mean_reversion_lb30_thr1_hold30_long_us_late,z_30_negative,past_fold_selected,238,1230.75,3.8341968911917097,0.5,-434.25,1155.875,74.875,2,2510.447506476684,paper_trade_and_expand_oos
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,none,directional_walkforward,398,6205.25,1.7309329326889002,0.8,-1128.375,6205.25,0.0,5,2421.4972596133402,paper_trade_and_tighten_state_filter
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,return_1m_negative,past_fold_selected,154,758.75,1.8299152310637137,0.5,-914.25,585.75,173.0,2,1064.4660924254854,paper_trade_and_expand_oos
paper_watchlist,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,z_30_negative,past_fold_selected,156,611.75,1.5861779853874716,0.5,-1043.625,585.75,26.0,2,742.0461941549888,paper_trade_and_expand_oos
```

## validate_next

```csv
tier,candidate,filter,evidence_type,trades,net_points,profit_factor,positive_fold_rate,stress_points,baseline_net_points,net_improvement,selected_folds,promotion_score,next_action
validate_next,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below,past_fold_selected,39,784.875,inf,1.0,784.875,1159.875,-375.0,1,inf,seek_more_repeat_folds
validate_next,bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,range_30_low_mid,past_fold_selected,35,136.875,inf,1.0,136.875,-8.875,145.75,1,inf,seek_more_repeat_folds
validate_next,bar_best_mean_reversion_lb30_thr0.6_hold15_long_us_late,none,directional_walkforward,173,2148.375,2.198034295273944,1.0,2148.375,2148.375,0.0,1,3055.914327164366,keep_as_research_context
validate_next,bar_best_mean_reversion_lb30_thr1.4_hold60_long_us_late,vwap_below,post_filter_mining,203,5847.125,1.74103352132311,1.0,776.875,6205.25,-358.125,5,3004.1292606615552,validate_with_past_fold_selection
validate_next,bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,range_30_low_mid,post_filter_mining,251,4736.625,1.8605200408765752,1.0,136.875,4563.75,172.875,5,2894.8725204382877,validate_with_past_fold_selection
validate_next,bar_best_mean_reversion_lb15_thr1.4_hold30_long_us_late,none,directional_walkforward,146,1780.0,1.8997283123775823,1.0,1780.0,1780.0,0.0,1,2784.836987426549,keep_as_research_context
validate_next,bar_best_momentum_lb60_thr0.001_hold15_long_us_late,trend_120_down,post_filter_mining,90,1789.75,2.78417445482866,1.0,208.25,1989.75,-200.0,5,2730.03722741433,validate_with_past_fold_selection
validate_next,bar_best_momentum_lb60_thr0.0006_hold30_long_us_late,return_1m_negative,post_filter_mining,109,2543.125,2.8243364418938306,1.0,97.375,4563.75,-2020.625,5,2718.7307209469154,validate_with_past_fold_selection
validate_next,bar_best_support_reclaim_lb10_thr0.0002_hold30_long_us_late,none,directional_walkforward,143,1922.625,1.722791353383459,1.0,1922.625,1922.625,0.0,1,2714.3310620300754,keep_as_research_context
validate_next,bar_best_support_reclaim_lb10_thr0.0005_hold30_long_us_late,none,directional_walkforward,143,1922.625,1.722791353383459,1.0,1922.625,1922.625,0.0,1,2714.3310620300754,keep_as_research_context
validate_next,bar_best_support_reclaim_lb10_thr0.001_hold30_long_us_late,none,directional_walkforward,143,1922.625,1.722791353383459,1.0,1922.625,1922.625,0.0,1,2714.3310620300754,keep_as_research_context
validate_next,bar_best_mean_reversion_lb10_thr1_hold15_long_us_late,none,directional_walkforward,290,2272.75,1.5489568551674164,1.0,2272.75,2272.75,0.0,1,2697.56161310045,keep_as_research_context
```

## research_only

```csv
tier,candidate,filter,evidence_type,trades,net_points,profit_factor,positive_fold_rate,stress_points,baseline_net_points,net_improvement,selected_folds,promotion_score,next_action
research_only,bar_best_breakout_retest_lb30_thr0.0002_hold60_long_us_late,none,directional_walkforward,35,1293.625,3.877919911012236,1.0,1293.625,1293.625,0.0,1,3850.158196607342,keep_as_research_context
research_only,bar_best_breakout_retest_lb30_thr0.0005_hold60_long_us_late,none,directional_walkforward,35,1293.625,3.877919911012236,1.0,1293.625,1293.625,0.0,1,3850.158196607342,keep_as_research_context
research_only,bar_best_breakout_retest_lb30_thr0.001_hold60_long_us_late,none,directional_walkforward,34,1289.0,3.867630700778643,1.0,1289.0,1289.0,0.0,1,3842.828420467186,keep_as_research_context
research_only,bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,return_1m_positive,post_filter_mining,98,4135.5,2.0945543571759413,1.0,806.0,2602.875,1532.625,2,3027.6396785879706,validate_with_past_fold_selection
research_only,bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late,return_1m_positive,post_filter_mining,98,4135.5,2.0945543571759413,1.0,806.0,2602.875,1532.625,2,3027.6396785879706,validate_with_past_fold_selection
research_only,bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late,return_1m_positive,post_filter_mining,98,4135.5,2.0945543571759413,1.0,806.0,2602.875,1532.625,2,3027.6396785879706,validate_with_past_fold_selection
research_only,bar_best_support_reclaim_lb15_thr0.0002_hold60_short_us_late,entry_candle_up,post_filter_mining,94,3769.25,2.044402881684677,1.0,134.875,2602.875,1166.375,2,2892.6889408423385,validate_with_past_fold_selection
research_only,bar_best_support_reclaim_lb15_thr0.0005_hold60_short_us_late,entry_candle_up,post_filter_mining,94,3769.25,2.044402881684677,1.0,134.875,2602.875,1166.375,2,2892.6889408423385,validate_with_past_fold_selection
research_only,bar_best_support_reclaim_lb15_thr0.001_hold60_short_us_late,entry_candle_up,post_filter_mining,94,3769.25,2.044402881684677,1.0,134.875,2602.875,1166.375,2,2892.6889408423385,validate_with_past_fold_selection
research_only,bar_best_mean_reversion_lb30_thr1.4_hold30_long_us_late,vwap_below,post_filter_mining,194,3497.75,1.6885504072442727,1.0,835.625,1797.375,1700.375,3,2713.8627036221365,validate_with_past_fold_selection
research_only,bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,entry_candle_down,post_filter_mining,348,4476.0,1.6239740707825814,1.0,944.125,4483.875,-7.875,2,2706.399535391291,validate_with_past_fold_selection
research_only,bar_best_mean_reversion_lb10_thr1_hold30_long_us_late,minute_bucket_30_45,post_filter_mining,84,4035.75,1.865878188108456,1.0,836.75,4483.875,-448.125,2,2695.276594054228,validate_with_past_fold_selection
```

## Decision

- Stop broad feature mining for now; it is producing many post-filter edges that do not survive strict past-fold validation.
- Promote only the small set of stable base features and past-fold-positive state filters into stricter recent OOS / paper validation.
- Continue optimization on validation gates, execution realism, and recency checks rather than adding more raw feature families.
