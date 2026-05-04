# NQM6 Best-Strategy Walk-Forward Neighbor Search

## Verdict

Best train-selected neighbor: `adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3`.

- Search is centered on the current best non-2R mean-reversion strategy.
- Each fold ranks parameters on the training window, then evaluates the selected neighbors on future test dates.
- This is still research evidence; live readiness remains blocked by history span and paper outcomes.

## Run Metadata

- Feature rows: 60,503
- Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
- Neighbor specs: 50
- Fold candidate rows: 20

## Top Candidates

| name | folds_selected | wf_positive_fold_rate | wf_test_trades | wf_test_net_points | full_trades | full_net_points | full_max_drawdown_points | full_profit_factor | full_win_rate | full_stability | full_positive_window_rate | full_min_window_net_points | stress_net_points | best_walkforward_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.3 | 4 | 1.0000 | 329 | 1444.3750 | 942 | 3318.0000 | 190.8750 | 1.6891 | 0.5488 | 0.8476 | 1.0000 | 28.3750 | 2376.0000 | 6483.9120 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.3 | 1 | 1.0000 | 53 | 169.8750 | 544 | 2276.7500 | 128.0000 | 1.8446 | 0.5515 | 0.7860 | 1.0000 | 128.6250 | 1732.7500 | 6097.1313 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_not_low_imb0.25 | 1 | 1.0000 | 53 | 169.8750 | 544 | 2276.7500 | 128.0000 | 1.8446 | 0.5515 | 0.7860 | 1.0000 | 128.6250 | 1732.7500 | 6097.1313 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_europe_all_imb0.25 | 1 | 1.0000 | 80 | 156.2500 | 943 | 3203.3750 | 190.8750 | 1.6504 | 0.5483 | 0.8842 | 1.0000 | 28.3750 | 2260.3750 | 5986.8467 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max5_reverse_europe_not_low_imb0.3 | 2 | 1.0000 | 99 | 402.3750 | 569 | 1799.3750 | 180.8750 | 1.5845 | 0.5308 | 0.7098 | 1.0000 | 10.7500 | 1230.3750 | 4443.8016 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max5_reverse_europe_not_low_imb0.25 | 1 | 1.0000 | 43 | 371.8750 | 569 | 1799.3750 | 180.8750 | 1.5845 | 0.5308 | 0.7098 | 1.0000 | 10.7500 | 1230.3750 | 4434.6516 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_vwap_europe_not_low_imb0.3 | 1 | 1.0000 | 75 | 512.6250 | 659 | 1658.3750 | 160.8750 | 1.6524 | 0.4947 | 0.5180 | 0.8889 | -92.1250 | 999.3750 | 4243.3568 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_vwap_europe_not_low_imb0.25 | 1 | 1.0000 | 75 | 512.6250 | 659 | 1658.3750 | 160.8750 | 1.6524 | 0.4947 | 0.5180 | 0.8889 | -92.1250 | 999.3750 | 4243.3568 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_vwap_europe_all_imb0.25 | 2 | 1.0000 | 208 | 897.7500 | 1159 | 2285.1250 | 280.7500 | 1.4833 | 0.4978 | 0.6727 | 0.8889 | -92.2500 | 1126.1250 | 4036.9509 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max6_reverse_vwap_europe_all_imb0.3 | 2 | 1.0000 | 207 | 886.3750 | 1158 | 2273.7500 | 280.7500 | 1.4809 | 0.4974 | 0.6788 | 0.8889 | -92.2500 | 1115.7500 | 4028.9023 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max7_reverse_europe_not_low_imb0.3 | 2 | 1.0000 | 77 | 495.1250 | 512 | 1373.5000 | 707.2500 | 1.3971 | 0.5449 | 0.4500 | 0.6667 | -226.2500 | 861.5000 | 2179.0602 |
| adv_wf_best_mean_reversion_lb6_thr0.8_min1_max7_reverse_europe_not_low_imb0.25 | 2 | 1.0000 | 77 | 495.1250 | 512 | 1373.5000 | 707.2500 | 1.3971 | 0.5449 | 0.4500 | 0.6667 | -226.2500 | 861.5000 | 2179.0602 |
