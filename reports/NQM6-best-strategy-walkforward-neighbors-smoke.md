# NQM6 Best-Strategy Walk-Forward Neighbor Search

## Verdict

Best train-selected neighbor: `adv_wf_best_mean_reversion_lb4_thr0.7_min1_max5_reverse_europe_not_low_imb0.3`.

- Search is centered on the current best non-2R mean-reversion strategy.
- Each fold ranks parameters on the training window, then evaluates the selected neighbors on future test dates.
- This is still research evidence; live readiness remains blocked by history span and paper outcomes.

## Run Metadata

- Feature rows: 60,503
- Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
- Neighbor specs: 8
- Fold candidate rows: 8

## Top Candidates

| name | folds_selected | wf_positive_fold_rate | wf_test_trades | wf_test_net_points | full_trades | full_net_points | full_max_drawdown_points | full_profit_factor | full_win_rate | full_stability | full_positive_window_rate | full_min_window_net_points | stress_net_points | best_walkforward_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adv_wf_best_mean_reversion_lb4_thr0.7_min1_max5_reverse_europe_not_low_imb0.3 | 3 | 1.0000 | 146 | 383.0000 | 637 | 1965.6250 | 321.3750 | 1.5481 | 0.5620 | 0.8871 | 0.8889 | -163.3750 | 1328.6250 | 3733.4399 |
| adv_wf_best_mean_reversion_lb4_thr0.7_min1_max5_reverse_europe_not_low_imb0.25 | 3 | 1.0000 | 146 | 357.7500 | 638 | 1935.5000 | 321.3750 | 1.5352 | 0.5611 | 0.8582 | 0.8889 | -163.3750 | 1297.5000 | 3672.6112 |
| adv_wf_best_mean_reversion_lb4_thr0.7_min1_max5_reverse_europe_not_low_imb0.35 | 2 | 0.5000 | 43 | 134.8750 | 231 | 768.1250 | 159.8750 | 1.5043 | 0.6061 | 0.6896 | 0.7778 | -46.0000 | 537.1250 | 2823.2032 |
