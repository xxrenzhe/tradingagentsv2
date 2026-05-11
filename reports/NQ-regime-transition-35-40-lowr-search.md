# NQ Regime Transition Search

## Model

The model is explicitly `range -> expansion -> trend start`: a prior rolling box must be narrow and inefficient, then the current candle must close outside the box with displacement. Entries are next-bar open; exits use structural or ATR stops plus fixed R targets, with same-bar stop/target ambiguity resolved stop-first.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `5,383,225`.
- Breakout events: `276,306`.
- Costs: `0.625` NQ points round trip.

## Search

- Candidates: `6,144`.
- Lookbacks: `35, 40`.
- Sessions: `us_late`.
- Stops: `break_bar`; R targets: `1.25, 1.5, 1.75, 2.0, 2.25, 2.5`.
- Walk-forward train/purge/test/step days: `730` / `5` / `180` / `90`.

## Verdict

Best stable candidate: `regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180` with `874.76` selected OOS points, `100.00%` positive selected folds, PF `3.042`, and expectancy `13.622` points/trade.

## Top Walk-Forward Rows

| stable_candidate | candidate | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | avg_test_payoff_ratio | avg_test_expectancy_points | avg_test_target_exit_share | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 3 | 1.0000 | 1.0000 | 63 | 874.7633 | 14.4982 | 3.0424 | 0.4890 | 2.9842 | 13.6219 | 0.4247 | 152.7004 |
| True | regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2_h180 | 4 | 1.0000 | 1.0000 | 86 | 876.6925 | 7.9393 | 2.3886 | 0.5303 | 2.2336 | 9.7355 | 0.5051 | 17.1492 |
| True | regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.25_h180 | 3 | 1.0000 | 1.0000 | 64 | 705.8317 | 5.5600 | 2.5648 | 0.5144 | 2.1689 | 10.8559 | 0.4668 | 29.8283 |
| True | regime_breakout_lb35_w10_eff0.1_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | 3 | 1.0000 | 1.0000 | 118 | 799.0742 | 8.5375 | 2.0817 | 0.4391 | 2.4838 | 7.7042 | 0.3872 | 25.3096 |
| True | regime_breakout_lb35_w10_eff0.1_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h180 | 3 | 1.0000 | 1.0000 | 97 | 822.0117 | 8.1917 | 2.1998 | 0.5449 | 2.0289 | 8.0016 | 0.5215 | 103.5433 |
| True | regime_breakout_lb40_w10_eff0.25_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 4 | 1.0000 | 1.0000 | 134 | 848.1321 | 8.4772 | 1.9609 | 0.4802 | 1.8846 | 6.5636 | 0.2781 | 6.9333 |
| True | regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.25_h90 | 3 | 1.0000 | 1.0000 | 142 | 832.6163 | 8.6329 | 1.7577 | 0.4349 | 2.2675 | 5.1452 | 0.2755 | 13.4777 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 5 | 1.0000 | 1.0000 | 154 | 572.6325 | 7.3701 | 1.9314 | 0.5112 | 1.8504 | 3.3736 | 0.3324 | 29.1875 |
| True | regime_breakout_lb40_w10_eff0.1_disp1.2_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 3 | 1.0000 | 1.0000 | 109 | 668.8671 | 5.2280 | 1.7878 | 0.3405 | 3.3941 | 6.9947 | 0.2797 | 58.4071 |
| True | regime_breakout_lb35_w12_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 3 | 1.0000 | 1.0000 | 62 | 248.9133 | 7.6489 | 2.1141 | 0.5149 | 1.8542 | 4.1135 | 0.2530 | 10.3808 |
| True | regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | 4 | 1.0000 | 1.0000 | 97 | 331.5338 | 7.5036 | 1.7682 | 0.4878 | 1.8015 | 2.8446 | 0.2845 | 15.0058 |
| True | regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h120 | 3 | 1.0000 | 1.0000 | 79 | 253.4258 | 7.9152 | 1.7719 | 0.5208 | 1.6038 | 2.7289 | 0.2368 | 13.5058 |
| True | regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.5_h90 | 4 | 1.0000 | 1.0000 | 169 | 606.6021 | 5.0494 | 1.5022 | 0.5260 | 1.3951 | 3.5068 | 0.4259 | 1.8488 |
| True | regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h120 | 4 | 1.0000 | 1.0000 | 199 | 643.1121 | 4.6008 | 1.4742 | 0.5184 | 1.3949 | 3.2135 | 0.4231 | 30.2833 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.75_h120 | 4 | 1.0000 | 1.0000 | 167 | 601.1519 | 4.3103 | 1.4384 | 0.5152 | 1.3708 | 3.3486 | 0.4024 | 62.0017 |
| True | regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h90 | 4 | 1.0000 | 1.0000 | 199 | 601.6846 | 4.3044 | 1.4444 | 0.4982 | 1.4777 | 3.0137 | 0.3882 | 28.8658 |
| True | regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 3 | 1.0000 | 1.0000 | 79 | 207.4321 | 6.0933 | 1.6225 | 0.4615 | 1.8630 | 2.2519 | 0.2071 | 11.7558 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h120 | 4 | 1.0000 | 1.0000 | 213 | 575.3821 | 3.9690 | 1.3903 | 0.4940 | 1.4542 | 2.6666 | 0.4045 | 26.0771 |
| True | regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.75_h120 | 3 | 1.0000 | 1.0000 | 133 | 534.4588 | 3.8321 | 1.5225 | 0.5376 | 1.3294 | 3.7079 | 0.4102 | 62.0017 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 4 | 1.0000 | 1.0000 | 130 | 220.3417 | 4.3631 | 1.7575 | 0.4866 | 1.8069 | 2.1679 | 0.3203 | 35.9542 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h90 | 4 | 1.0000 | 1.0000 | 213 | 531.9546 | 3.6694 | 1.3586 | 0.4750 | 1.5287 | 2.4716 | 0.3717 | 24.6596 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h120 | 4 | 1.0000 | 1.0000 | 193 | 523.4056 | 3.2894 | 1.3406 | 0.4725 | 1.5013 | 2.5225 | 0.3656 | 49.0215 |
| True | regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h120 | 3 | 1.0000 | 1.0000 | 155 | 498.0092 | 3.1298 | 1.4336 | 0.4962 | 1.4609 | 3.0474 | 0.3741 | 62.4883 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h90 | 4 | 1.0000 | 1.0000 | 113 | 174.9242 | 3.6004 | 1.6708 | 0.4421 | 2.0555 | 1.8898 | 0.2685 | 10.3858 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h120 | 4 | 1.0000 | 1.0000 | 108 | 173.5875 | 3.3181 | 1.7588 | 0.4723 | 1.8807 | 2.1060 | 0.2813 | 8.7800 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h90 | 3 | 1.0000 | 1.0000 | 154 | 478.0421 | 3.0043 | 1.4214 | 0.4734 | 1.5906 | 2.9878 | 0.3704 | 73.9883 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2_h180 | 3 | 1.0000 | 1.0000 | 68 | 164.4342 | 3.6874 | 1.7299 | 0.4995 | 1.7483 | 2.4443 | 0.3246 | 20.2500 |
| True | regime_breakout_lb35_w8_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 3 | 1.0000 | 1.0000 | 93 | 157.9767 | 3.8581 | 1.5176 | 0.4808 | 1.6127 | 1.8419 | 0.3744 | 29.7092 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.25_h180 | 3 | 1.0000 | 1.0000 | 83 | 145.5854 | 3.5561 | 1.5346 | 0.4635 | 1.7386 | 1.9920 | 0.3481 | 18.1535 |
| True | regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h180 | 4 | 1.0000 | 1.0000 | 108 | 142.0875 | 2.7160 | 1.4451 | 0.4203 | 1.9754 | 1.5812 | 0.2813 | 12.0300 |

## Full Sample Sanity

| candidate | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | avg_r_multiple | target_exit_share | stop_exit_share | max_drawdown_points | positive_years | years | positive_90d_rate | worst_90d_net | first_half_points | second_half_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 427 | 2566.7329 | 1.7157 | 0.4215 | 2.3543 | 6.0111 | 0.2076 | 0.2670 | 0.5199 | 509.9567 | 12 | 17 | 0.6508 | -177.6862 | 1197.2471 | 1369.4858 |
| regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2_h180 | 432 | 2228.2183 | 1.6434 | 0.4583 | 1.9422 | 5.1579 | 0.1969 | 0.3449 | 0.4884 | 501.0283 | 12 | 17 | 0.6190 | -152.9292 | 1036.4692 | 1191.7492 |
| regime_breakout_lb35_w10_eff0.1_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.25_h180 | 429 | 2538.3531 | 1.7225 | 0.4429 | 2.1667 | 5.9169 | 0.2208 | 0.3170 | 0.5035 | 504.1998 | 12 | 17 | 0.6190 | -151.6625 | 1139.1800 | 1399.1731 |
| regime_breakout_lb35_w10_eff0.1_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | 769 | 2905.8246 | 1.4523 | 0.3862 | 2.3080 | 3.7787 | 0.1321 | 0.2783 | 0.5787 | 631.1571 | 11 | 17 | 0.6190 | -220.0621 | 1092.0662 | 1813.7583 |
| regime_breakout_lb35_w10_eff0.1_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h180 | 781 | 2561.1958 | 1.4168 | 0.4251 | 1.9161 | 3.2794 | 0.1244 | 0.3457 | 0.5416 | 694.0858 | 12 | 17 | 0.6032 | -187.4783 | 933.2158 | 1627.9800 |
| regime_breakout_lb40_w10_eff0.25_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 680 | 2889.0496 | 1.5442 | 0.4250 | 2.0892 | 4.2486 | 0.1359 | 0.2059 | 0.4868 | 258.0150 | 12 | 17 | 0.6349 | -160.8846 | 1022.2029 | 1866.8467 |
| regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.25_h90 | 987 | 2890.9656 | 1.3744 | 0.4063 | 2.0085 | 2.9290 | 0.0739 | 0.2421 | 0.5177 | 263.0448 | 11 | 17 | 0.5873 | -115.2835 | 644.9033 | 2246.0623 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 970 | 2779.5708 | 1.3668 | 0.4196 | 1.8907 | 2.8655 | 0.0857 | 0.3000 | 0.5206 | 261.4575 | 12 | 17 | 0.6667 | -140.3150 | 549.3000 | 2230.2708 |
| regime_breakout_lb40_w10_eff0.1_disp1.2_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 688 | 3246.4883 | 1.5792 | 0.3910 | 2.4599 | 4.7187 | 0.1617 | 0.2805 | 0.5669 | 299.0087 | 13 | 17 | 0.5714 | -136.0362 | 862.4954 | 2383.9929 |
| regime_breakout_lb35_w12_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 795 | 3137.6708 | 1.4490 | 0.3912 | 2.2550 | 3.9468 | 0.1521 | 0.2767 | 0.5648 | 515.3458 | 12 | 17 | 0.6190 | -232.1392 | 981.5708 | 2156.1000 |
| regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | 856 | 3519.6063 | 1.4782 | 0.3879 | 2.3331 | 4.1117 | 0.1428 | 0.2804 | 0.5748 | 569.4542 | 13 | 17 | 0.6825 | -264.3787 | 1133.9604 | 2385.6458 |
| regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h120 | 749 | 2761.3892 | 1.4418 | 0.3979 | 2.1820 | 3.6868 | 0.1386 | 0.2563 | 0.5447 | 486.0521 | 13 | 17 | 0.6349 | -254.2096 | 759.2662 | 2002.1229 |
| regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.5_h90 | 811 | 2427.4142 | 1.4297 | 0.4834 | 1.5281 | 2.9931 | 0.0997 | 0.4007 | 0.4575 | 189.4492 | 13 | 17 | 0.6349 | -81.8879 | 565.8983 | 1861.5158 |
| regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h120 | 926 | 2345.2050 | 1.3515 | 0.4622 | 1.5726 | 2.5326 | 0.0646 | 0.3963 | 0.4849 | 238.6396 | 14 | 17 | 0.6667 | -75.8879 | 589.2558 | 1755.9492 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.75_h120 | 872 | 2649.4844 | 1.3974 | 0.4507 | 1.7032 | 3.0384 | 0.1109 | 0.3578 | 0.4908 | 264.9608 | 13 | 17 | 0.6667 | -147.8385 | 487.5585 | 2161.9258 |
| regime_breakout_lb35_w8_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h90 | 929 | 2415.4425 | 1.3722 | 0.4693 | 1.5516 | 2.6000 | 0.0696 | 0.3864 | 0.4693 | 213.6354 | 13 | 17 | 0.6349 | -81.8879 | 640.2900 | 1775.1525 |
| regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 753 | 2614.9613 | 1.4304 | 0.4104 | 2.0553 | 3.4727 | 0.1356 | 0.2351 | 0.5259 | 447.8925 | 13 | 17 | 0.6349 | -245.9596 | 812.2500 | 1802.7113 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h120 | 1011 | 2108.9658 | 1.2829 | 0.4590 | 1.5124 | 2.0860 | 0.0564 | 0.3907 | 0.4847 | 280.1200 | 13 | 17 | 0.6825 | -89.4321 | 198.1346 | 1910.8313 |
| regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr1.75_h120 | 902 | 2650.0812 | 1.3819 | 0.4479 | 1.7034 | 2.9380 | 0.1022 | 0.3548 | 0.4956 | 265.2302 | 12 | 17 | 0.6190 | -121.4056 | 489.8819 | 2160.1994 |
| regime_breakout_lb35_w10_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 1270 | 3057.9967 | 1.3142 | 0.4134 | 1.8649 | 2.4079 | 0.0837 | 0.3173 | 0.5394 | 325.2575 | 13 | 17 | 0.6508 | -165.6108 | 780.5783 | 2277.4183 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.5_h90 | 1014 | 2185.6967 | 1.3011 | 0.4645 | 1.5001 | 2.1555 | 0.0610 | 0.3817 | 0.4684 | 255.6500 | 13 | 17 | 0.6349 | -95.4321 | 239.0371 | 1946.6596 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h120 | 990 | 2433.6985 | 1.3198 | 0.4343 | 1.7189 | 2.4583 | 0.0671 | 0.3404 | 0.5081 | 278.3521 | 13 | 17 | 0.6349 | -147.8385 | 342.7315 | 2090.9671 |
| regime_breakout_lb35_w12_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h120 | 1020 | 2434.2954 | 1.3088 | 0.4324 | 1.7184 | 2.3866 | 0.0607 | 0.3382 | 0.5118 | 290.8606 | 12 | 17 | 0.6190 | -121.4056 | 351.6577 | 2082.6377 |
| regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h90 | 1106 | 3037.3804 | 1.3516 | 0.4014 | 2.0153 | 2.7463 | 0.0796 | 0.2559 | 0.5289 | 347.5321 | 11 | 17 | 0.6032 | -219.6638 | 696.3392 | 2341.0413 |
| regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h120 | 1100 | 3133.2398 | 1.3549 | 0.3973 | 2.0556 | 2.8484 | 0.0853 | 0.2718 | 0.5482 | 353.2821 | 11 | 17 | 0.6825 | -226.1638 | 662.4073 | 2470.8325 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr1.75_h90 | 994 | 2433.0719 | 1.3281 | 0.4396 | 1.6928 | 2.4478 | 0.0701 | 0.3320 | 0.4899 | 260.9113 | 13 | 17 | 0.5873 | -153.8385 | 385.8135 | 2047.2583 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2_h180 | 969 | 3079.6300 | 1.3893 | 0.4159 | 1.9512 | 3.1782 | 0.1002 | 0.3302 | 0.5418 | 284.1008 | 12 | 17 | 0.6508 | -139.3617 | 778.0883 | 2301.5417 |
| regime_breakout_lb35_w8_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2_h120 | 1032 | 2953.2058 | 1.3699 | 0.4157 | 1.9255 | 2.8616 | 0.0864 | 0.3130 | 0.5349 | 321.3683 | 12 | 17 | 0.6349 | -225.3217 | 783.4300 | 2169.7758 |
| regime_breakout_lb35_w10_eff0.25_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.25_h180 | 951 | 3457.4035 | 1.4360 | 0.3975 | 2.1768 | 3.6355 | 0.1095 | 0.2965 | 0.5573 | 306.8967 | 12 | 17 | 0.6508 | -157.2348 | 854.4910 | 2602.9125 |
| regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h180 | 1100 | 3675.2827 | 1.4011 | 0.3936 | 2.1583 | 3.3412 | 0.1081 | 0.3036 | 0.5673 | 376.2954 | 11 | 17 | 0.6508 | -228.4604 | 898.6350 | 2776.6477 |
| regime_breakout_lb35_w10_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h90 | 1243 | 3407.5992 | 1.3622 | 0.4031 | 2.0174 | 2.7414 | 0.0953 | 0.2695 | 0.5326 | 288.4681 | 12 | 17 | 0.6032 | -145.2796 | 1024.4983 | 2383.1008 |
| regime_breakout_lb35_w8_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 749 | 3265.7808 | 1.5023 | 0.3952 | 2.2992 | 4.3602 | 0.1696 | 0.2870 | 0.5648 | 577.9437 | 13 | 17 | 0.6508 | -264.3787 | 995.8246 | 2269.9563 |
| regime_breakout_lb35_w10_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 784 | 3299.4296 | 1.4850 | 0.3941 | 2.2828 | 4.2085 | 0.1624 | 0.2793 | 0.5612 | 445.3717 | 13 | 17 | 0.6508 | -232.1392 | 984.1512 | 2315.2783 |
| regime_breakout_lb35_w10_eff0.15_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 689 | 3341.1446 | 1.5685 | 0.4020 | 2.3329 | 4.8493 | 0.1767 | 0.2743 | 0.5472 | 313.0196 | 13 | 17 | 0.6667 | -186.3396 | 1130.3275 | 2210.8171 |
| regime_breakout_lb35_w12_eff0.15_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | 698 | 3194.0208 | 1.5281 | 0.3997 | 2.2949 | 4.5760 | 0.1680 | 0.2722 | 0.5501 | 382.9937 | 12 | 17 | 0.6508 | -186.3396 | 1097.5071 | 2096.5138 |
| regime_breakout_lb35_w12_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2_h180 | 810 | 2900.9292 | 1.4320 | 0.4284 | 1.9106 | 3.5814 | 0.1455 | 0.3506 | 0.5309 | 375.4350 | 11 | 17 | 0.5873 | -173.7808 | 883.9542 | 2016.9750 |
| regime_breakout_lb35_w10_eff0.15_disp1.4_body0.55_vol0_us_late_long_break_bar_rr1.5_h180 | 938 | 2426.1217 | 1.3408 | 0.4691 | 1.5176 | 2.5865 | 0.0847 | 0.4254 | 0.4957 | 364.8633 | 14 | 17 | 0.6508 | -152.2917 | 646.1008 | 1780.0208 |
| regime_breakout_lb35_w10_eff0.15_disp1.4_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 788 | 2586.6100 | 1.4060 | 0.4099 | 2.0241 | 3.2825 | 0.1279 | 0.2297 | 0.5228 | 347.6158 | 13 | 17 | 0.6508 | -213.7200 | 826.0767 | 1760.5333 |
| regime_breakout_lb35_w10_eff0.15_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 694 | 2676.5354 | 1.4925 | 0.4222 | 2.0426 | 3.8567 | 0.1417 | 0.2205 | 0.5029 | 260.5613 | 13 | 17 | 0.6667 | -168.9204 | 991.1000 | 1685.4354 |
| regime_breakout_lb35_w12_eff0.15_disp1.6_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h90 | 703 | 2519.9096 | 1.4496 | 0.4196 | 2.0048 | 3.5845 | 0.1316 | 0.2176 | 0.5064 | 274.6608 | 12 | 17 | 0.6667 | -168.9204 | 966.6733 | 1553.2363 |
