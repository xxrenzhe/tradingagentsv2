# NQ Regime Transition Search

## Model

The model is explicitly `range -> expansion -> trend start`: a prior rolling box must be narrow and inefficient, then the current candle must close outside the box with displacement. Entries are next-bar open; exits use structural or ATR stops plus fixed R targets, with same-bar stop/target ambiguity resolved stop-first.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `5,383,225`.
- Breakout events: `171,520`.
- Costs: `0.625` NQ points round trip.

## Search

- Candidates: `768`.
- Lookbacks: `60, 120`.
- Sessions: `ldn_ny, us_rth, us_late`.
- Stops: `break_bar`; R targets: `2.0, 3.0`.
- Walk-forward train/purge/test/step days: `730` / `5` / `180` / `90`.

## Verdict

Best stable candidate: `regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240` with `963.55` selected OOS points, `100.00%` positive selected folds, PF `1.979`, and expectancy `11.170` points/trade.

## Top Walk-Forward Rows

| stable_candidate | candidate | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | avg_test_payoff_ratio | avg_test_expectancy_points | avg_test_target_exit_share | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 4 | 1.0000 | 1.0000 | 100 | 963.5542 | 6.0132 | 1.9787 | 0.4668 | 2.1980 | 11.1703 | 0.4061 | 116.5092 |
| True | regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 4 | 1.0000 | 1.0000 | 100 | 963.5542 | 6.0132 | 1.9787 | 0.4668 | 2.1980 | 11.1703 | 0.4061 | 116.5092 |
| True | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 4 | 1.0000 | 1.0000 | 100 | 765.2642 | 4.7757 | 1.9306 | 0.4807 | 1.9469 | 9.0089 | 0.3315 | 101.9558 |
| True | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 3 | 1.0000 | 1.0000 | 88 | 662.7150 | 4.1357 | 1.7336 | 0.4503 | 2.0335 | 9.1825 | 0.4051 | 85.3075 |
| True | regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 3 | 1.0000 | 1.0000 | 88 | 662.7150 | 4.1357 | 1.7336 | 0.4503 | 2.0335 | 9.1825 | 0.4051 | 85.3075 |
| True | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 8 | 0.8750 | 0.8750 | 201 | 763.6217 | 3.9277 | 1.4403 | 0.3221 | 2.9380 | 4.0871 | 0.2528 | -123.6175 |
| True | regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 8 | 0.8750 | 0.8750 | 201 | 763.6217 | 3.9277 | 1.4403 | 0.3221 | 2.9380 | 4.0871 | 0.2528 | -123.6175 |
| True | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 5 | 0.8000 | 0.8000 | 124 | 783.8292 | 7.9782 | 1.7140 | 0.4392 | 2.0755 | 7.0962 | 0.3959 | -6.6625 |
| True | regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 5 | 0.8000 | 0.8000 | 124 | 783.8292 | 7.9782 | 1.7140 | 0.4392 | 2.0755 | 7.0962 | 0.3959 | -6.6625 |
| True | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 4 | 0.7500 | 0.7500 | 140 | 483.0717 | 2.1357 | 1.3478 | 0.3342 | 2.6917 | 2.5285 | 0.1846 | -10.9000 |
| True | regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 4 | 0.7500 | 0.7500 | 140 | 483.0717 | 2.1357 | 1.3478 | 0.3342 | 2.6917 | 2.5285 | 0.1846 | -10.9000 |
| False | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | 2 | 1.0000 | 1.0000 | 115 | 1398.2242 | 17.8156 | 2.3669 | 0.4078 | 3.4679 | 12.1639 | 0.2338 | 692.8433 |
| False | regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | 2 | 1.0000 | 1.0000 | 115 | 1398.2242 | 17.8156 | 2.3669 | 0.4078 | 3.4679 | 12.1639 | 0.2338 | 692.8433 |
| False | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 2 | 1.0000 | 1.0000 | 42 | 488.6883 | 5.4774 | 1.9697 | 0.4977 | 1.9367 | 10.8159 | 0.4497 | 41.9992 |
| False | regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 2 | 1.0000 | 1.0000 | 42 | 488.6883 | 5.4774 | 1.9697 | 0.4977 | 1.9367 | 10.8159 | 0.4497 | 41.9992 |
| False | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h120 | 1 | 1.0000 | 1.0000 | 23 | 215.7350 | 1.4118 | 1.9186 | 0.4783 | 2.0930 | 9.3798 | 0.1739 | 215.7350 |
| False | regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h120 | 1 | 1.0000 | 1.0000 | 23 | 215.7350 | 1.4118 | 1.9186 | 0.4783 | 2.0930 | 9.3798 | 0.1739 | 215.7350 |
| False | regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 2 | 1.0000 | 1.0000 | 142 | 558.8292 | 4.3150 | 1.4064 | 0.4013 | 2.0366 | 3.3442 | 0.3748 | 6.6883 |
| False | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 2 | 1.0000 | 1.0000 | 62 | 345.4392 | 2.0203 | 1.5693 | 0.4349 | 2.0452 | 5.5934 | 0.3340 | 162.9317 |
| False | regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 2 | 1.0000 | 1.0000 | 62 | 345.4392 | 2.0203 | 1.5693 | 0.4349 | 2.0452 | 5.5934 | 0.3340 | 162.9317 |
| False | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 2 | 1.0000 | 1.0000 | 123 | 573.1967 | 2.7432 | 1.3694 | 0.3964 | 2.0337 | 4.4154 | 0.3724 | 6.6883 |
| False | regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 2 | 1.0000 | 1.0000 | 51 | 259.8975 | 1.6219 | 1.4994 | 0.4138 | 2.1020 | 5.2542 | 0.2911 | 101.9558 |
| False | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h120 | 1 | 1.0000 | 1.0000 | 10 | 36.9467 | 0.6701 | 1.3375 | 0.3000 | 3.1208 | 3.6947 | 0.1000 | 36.9467 |
| False | regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h120 | 1 | 1.0000 | 1.0000 | 10 | 36.9467 | 0.6701 | 1.3375 | 0.3000 | 3.1208 | 3.6947 | 0.1000 | 36.9467 |
| False | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h120 | 3 | 1.0000 | 1.0000 | 61 | 55.0192 | 0.4082 | 1.1611 | 0.3875 | 1.8318 | 0.7911 | 0.0631 | 1.4750 |
| False | regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h120 | 3 | 1.0000 | 1.0000 | 61 | 55.0192 | 0.4082 | 1.1611 | 0.3875 | 1.8318 | 0.7911 | 0.0631 | 1.4750 |
| False | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 1 | 1.0000 | 1.0000 | 31 | 70.7542 | 0.4415 | 1.1578 | 0.3548 | 2.1051 | 2.2824 | 0.2903 | 70.7542 |
| False | regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 1 | 1.0000 | 1.0000 | 31 | 70.7542 | 0.4415 | 1.1578 | 0.3548 | 2.1051 | 2.2824 | 0.2903 | 70.7542 |
| False | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 1 | 1.0000 | 1.0000 | 76 | 113.6142 | 0.5460 | 1.1492 | 0.4079 | 1.6682 | 1.4949 | 0.3158 | 113.6142 |
| False | regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 1 | 1.0000 | 1.0000 | 76 | 113.6142 | 0.5460 | 1.1492 | 0.4079 | 1.6682 | 1.4949 | 0.3158 | 113.6142 |

## Full Sample Sanity

| candidate | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | avg_r_multiple | target_exit_share | stop_exit_share | max_drawdown_points | positive_years | years | positive_90d_rate | worst_90d_net | first_half_points | second_half_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 462 | 1685.1617 | 1.4208 | 0.4199 | 1.9628 | 3.6475 | 0.1287 | 0.3485 | 0.5476 | 266.3983 | 12 | 17 | 0.6032 | -141.8550 | 388.0175 | 1297.1442 |
| regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 462 | 1685.1617 | 1.4208 | 0.4199 | 1.9628 | 3.6475 | 0.1287 | 0.3485 | 0.5476 | 266.3983 | 12 | 17 | 0.6032 | -141.8550 | 388.0175 | 1297.1442 |
| regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 462 | 1473.0092 | 1.4028 | 0.4307 | 1.8540 | 3.1883 | 0.1069 | 0.2944 | 0.5065 | 184.2742 | 13 | 17 | 0.5873 | -108.8550 | 285.6067 | 1187.4025 |
| regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 507 | 1574.2025 | 1.3621 | 0.4083 | 1.9740 | 3.1049 | 0.1002 | 0.3432 | 0.5621 | 334.7908 | 12 | 17 | 0.5873 | -144.0425 | 374.6358 | 1199.5667 |
| regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol0_us_late_long_break_bar_rr2_h240 | 507 | 1574.2025 | 1.3621 | 0.4083 | 1.9740 | 3.1049 | 0.1002 | 0.3432 | 0.5621 | 334.7908 | 12 | 17 | 0.5873 | -144.0425 | 374.6358 | 1199.5667 |
| regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 558 | 2106.2667 | 1.4314 | 0.3495 | 2.6646 | 3.7747 | 0.1340 | 0.2276 | 0.6201 | 288.6150 | 12 | 17 | 0.5873 | -154.2483 | 974.3550 | 1131.9117 |
| regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 558 | 2106.2667 | 1.4314 | 0.3495 | 2.6646 | 3.7747 | 0.1340 | 0.2276 | 0.6201 | 288.6150 | 12 | 17 | 0.5873 | -154.2483 | 974.3550 | 1131.9117 |
| regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 529 | 1893.7175 | 1.4313 | 0.4140 | 2.0260 | 3.5798 | 0.1173 | 0.3497 | 0.5539 | 277.2717 | 11 | 17 | 0.5556 | -115.2625 | 624.8133 | 1268.9042 |
| regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 529 | 1893.7175 | 1.4313 | 0.4140 | 2.0260 | 3.5798 | 0.1173 | 0.3497 | 0.5539 | 277.2717 | 11 | 17 | 0.5556 | -115.2625 | 624.8133 | 1268.9042 |
| regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 1105 | 3371.1583 | 1.3473 | 0.3267 | 2.7768 | 3.0508 | 0.0780 | 0.2271 | 0.6462 | 555.5117 | 13 | 17 | 0.5873 | -177.8725 | 1063.6475 | 2307.5108 |
| regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | 1108 | 3348.3917 | 1.3442 | 0.3258 | 2.7814 | 3.0220 | 0.0751 | 0.2265 | 0.6471 | 571.8750 | 13 | 17 | 0.5873 | -177.8725 | 1049.7058 | 2298.6858 |
| regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | 942 | 3500.0942 | 1.4143 | 0.3386 | 2.7620 | 3.7156 | 0.1099 | 0.2282 | 0.6327 | 406.0883 | 14 | 17 | 0.6349 | -210.5892 | 958.7650 | 2541.3292 |
| regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | 944 | 3482.9183 | 1.4114 | 0.3379 | 2.7653 | 3.6895 | 0.1075 | 0.2278 | 0.6335 | 412.6033 | 14 | 17 | 0.6190 | -210.5892 | 948.1042 | 2534.8142 |
| regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 587 | 1819.8208 | 1.3792 | 0.4072 | 2.0082 | 3.1002 | 0.1016 | 0.3492 | 0.5639 | 364.5892 | 11 | 17 | 0.5079 | -134.0742 | 601.5675 | 1218.2533 |
| regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 587 | 1819.8208 | 1.3792 | 0.4072 | 2.0082 | 3.1002 | 0.1016 | 0.3492 | 0.5639 | 364.5892 | 11 | 17 | 0.5079 | -134.0742 | 601.5675 | 1218.2533 |
| regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h120 | 558 | 1326.1092 | 1.2924 | 0.3620 | 2.2777 | 2.3765 | 0.0740 | 0.1864 | 0.5806 | 276.7450 | 11 | 17 | 0.5079 | -144.4983 | 479.3075 | 846.8017 |
| regime_breakout_lb120_w12_eff0.35_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h120 | 558 | 1326.1092 | 1.2924 | 0.3620 | 2.2777 | 2.3765 | 0.0740 | 0.1864 | 0.5806 | 276.7450 | 11 | 17 | 0.5079 | -144.4983 | 479.3075 | 846.8017 |
| regime_breakout_lb60_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h240 | 1190 | 2898.8267 | 1.3051 | 0.3941 | 2.0063 | 2.4360 | 0.0717 | 0.3454 | 0.5798 | 522.8633 | 12 | 17 | 0.5238 | -120.8433 | 808.4767 | 2090.3500 |
| regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 529 | 1563.1750 | 1.3882 | 0.4253 | 1.8757 | 2.9550 | 0.0954 | 0.2987 | 0.5142 | 194.1058 | 12 | 17 | 0.5079 | -105.5125 | 404.0125 | 1159.1625 |
| regime_breakout_lb120_w12_eff0.35_disp1.2_body0.55_vol-0.5_us_late_long_break_bar_rr2_h120 | 529 | 1563.1750 | 1.3882 | 0.4253 | 1.8757 | 2.9550 | 0.0954 | 0.2987 | 0.5142 | 194.1058 | 12 | 17 | 0.5079 | -105.5125 | 404.0125 | 1159.1625 |
