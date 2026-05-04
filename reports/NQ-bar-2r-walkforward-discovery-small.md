# NQ Bar-Only 60% Fixed-2R Walk-Forward Search

## Verdict

No long-horizon bar-only NQ candidate passed the fixed-2R black-box gate.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Continuous construction: one NQ futures row per minute, selected by highest reported volume.
- Feature span: `2024-01-01 23:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Feature rows: `819,917`.
- Distinct symbols selected: `10`.

## Gates

- Train days: `120`; purge days: `5`; test days: `60`; step days: `90`.
- Minimum train/test trades: `20` / `8`.
- Train win/PF: `0.45` / `0.7`.
- Test win/PF: `0.6` / `1.0`.
- Minimum bracket exit share: `0.35`.

## Summary

- Rows tested: `289`.
- Black-box passes: `0`.
- Test trades exported: `456,440`.

## Top Rows

| blackbox_pass | candidate | fold | train_trades | train_win_rate | train_net_points | train_profit_factor | test_trades | test_win_rate | test_net_points | test_profit_factor | test_bracket_exit_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | bar2r_short_sl32_tp64_h60_us_rth_range_mean_30<=7.81 | 1 | 415 | 0.4747 | 1532.1250 | 1.2800 | 62 | 0.5000 | 562.7500 | 1.8026 | 0.4355 |
| False | bar2r_short_sl24_tp48_h30_us_rth_range_mean_30<=7.82 | 1 | 416 | 0.4591 | 674.5000 | 1.1735 | 62 | 0.5000 | 203.5000 | 1.4165 | 0.3387 |
| False | bar2r_long_sl32_tp64_h30_all_z_30<=-1.20309 | 4 | 1492 | 0.4578 | -770.5000 | 0.9569 | 833 | 0.4970 | 1367.8750 | 1.1339 | 0.4238 |
| False | bar2r_long_sl32_tp64_h30_all_volume_z_60<=-0.614913 | 2 | 2247 | 0.4530 | -1244.3750 | 0.9556 | 1074 | 0.4926 | 192.0000 | 1.0241 | 0.1480 |
| False | bar2r_long_sl24_tp48_h60_all_range_mean_30<=8.875 | 3 | 6020 | 0.4666 | -3732.5000 | 0.9345 | 2327 | 0.4916 | 1549.1250 | 1.0655 | 0.4658 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_15<=0.00051638 | 2 | 5242 | 0.4542 | -5814.2500 | 0.9127 | 3350 | 0.4887 | -2193.0000 | 0.9163 | 0.1615 |
| False | bar2r_long_sl24_tp48_h60_all_vol_30<=0.000209922 | 3 | 5267 | 0.4733 | -2777.3750 | 0.9416 | 2131 | 0.4876 | 664.1250 | 1.0306 | 0.4566 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_5>=-0.000501245 | 2 | 5991 | 0.4550 | -4090.3750 | 0.9443 | 3699 | 0.4845 | -2660.6250 | 0.9094 | 0.1590 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_60<=0.00184113 | 2 | 5991 | 0.4523 | -7899.6250 | 0.8969 | 3711 | 0.4842 | -3085.8750 | 0.8968 | 0.1663 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_15>=-0.000907244 | 2 | 5991 | 0.4515 | -5863.1250 | 0.9212 | 3737 | 0.4841 | -2943.3750 | 0.8999 | 0.1549 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_5<=-0.000155984 | 4 | 2237 | 0.4609 | -1745.3750 | 0.9370 | 1283 | 0.4840 | 1784.3750 | 1.1088 | 0.4505 |
| False | bar2r_long_sl32_tp64_h30_all_momentum_5>=-0.000269571 | 2 | 5242 | 0.4525 | -4317.2500 | 0.9328 | 3328 | 0.4826 | -2379.7500 | 0.9080 | 0.1523 |
| False | bar2r_long_sl12_tp24_h30_all_vol_120<=0.00011026 | 4 | 1497 | 0.4522 | -825.3750 | 0.8917 | 399 | 0.4812 | 162.1250 | 1.0746 | 0.5063 |
| False | bar2r_long_sl24_tp48_h60_all_range_mean_30<=5.11167 | 2 | 1494 | 0.4598 | -1166.7500 | 0.9218 | 2309 | 0.4799 | -1288.8750 | 0.9299 | 0.2728 |
| False | bar2r_long_sl32_tp64_h30_us_rth_vol_30<=0.000526745 | 1 | 1453 | 0.4529 | -780.1250 | 0.9617 | 572 | 0.4790 | 866.2500 | 1.1064 | 0.5227 |
| False | bar2r_long_sl24_tp48_h60_all_vol_30<=0.000167234 | 2 | 1494 | 0.4565 | -1060.7500 | 0.9293 | 2609 | 0.4718 | -2127.6250 | 0.9038 | 0.3078 |
| False | bar2r_short_sl24_tp48_h30_us_rth_vol_30<=0.000255547 | 0 | 640 | 0.4562 | 639.7500 | 1.1009 | 289 | 0.4706 | 742.6250 | 1.2576 | 0.4948 |
| False | bar2r_long_sl32_tp64_h30_us_rth_momentum_5>=0.000442414 | 2 | 645 | 0.4512 | 2173.8750 | 1.2052 | 236 | 0.4703 | 273.7500 | 1.0874 | 0.4322 |
| False | bar2r_long_sl32_tp64_h60_all_z_30<=-1.18451 | 0 | 1469 | 0.4772 | 824.3750 | 1.0445 | 804 | 0.4701 | -71.7500 | 0.9936 | 0.4826 |
| False | bar2r_long_sl24_tp48_h60_all_vol_120<=0.000289977 | 3 | 6019 | 0.4652 | -3118.3750 | 0.9458 | 2667 | 0.4676 | -174.6250 | 0.9940 | 0.5193 |
