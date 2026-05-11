# NQ ICT 2022 Event System Search

## Model

This search mechanizes the bar-computable parts of `docs/Strategy/ICT2022-2.md`: liquidity sweep, MSS/CHoCH confirmation, displacement, optional FVG, premium/discount context, kill-zone style sessions, and PBL-style structural stops. Entries are either next-bar open after MSS or a later FVG retracement limit fill. Fixed-R targets are used so probability and payoff are explicit.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `5,383,225`.
- Setup events: `13,911`.
- Costs: `0.625` NQ points round trip.

## Search

- Candidates: `1,536`.
- Sweep sources: `rolling, prev_day`.
- Sessions: `ldn_ny, us_rth, ict_am, ict_silver`.
- Entry modes: `mss_open, fvg50`; stop modes: `pbl`.
- R targets: `2.0, 3.0`.
- Walk-forward train/purge/test/step days: `730` / `5` / `180` / `90`.

## Verdict

Best stable candidate: `ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr2_h120` with `159.88` selected OOS points, `100.00%` positive selected folds, PF `4.246`, and expectancy `4.634` points/trade.

## Top Walk-Forward Rows

| stable_candidate | candidate | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | avg_test_payoff_ratio | avg_test_expectancy_points | avg_test_target_exit_share | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr2_h120 | 7 | 1.0000 | 0.7143 | 34 | 159.8825 | 4.5365 | 4.2464 | 0.5595 | 2.2882 | 4.6344 | 0.5000 | 0.7450 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr2_h240 | 6 | 1.0000 | 0.6667 | 29 | 163.0417 | 4.6262 | 4.8184 | 0.5861 | 2.3561 | 5.5309 | 0.5861 | 5.2750 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr3_h240 | 7 | 0.8571 | 0.8571 | 46 | 177.2225 | 3.9418 | 1.8353 | 0.4034 | 2.6925 | 3.3612 | 0.2207 | -6.1833 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr3_h120 | 6 | 0.8333 | 0.3333 | 28 | 111.0192 | 4.7802 | 3.0235 | 0.4667 | 2.6869 | 4.1472 | 0.2472 | -1.7250 |
| True | ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h120 | 10 | 0.8000 | 0.8000 | 108 | 143.9483 | 1.3143 | 1.6988 | 0.4334 | 2.0119 | 1.2492 | 0.4334 | -25.6250 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr2_h240 | 12 | 0.7500 | 0.7500 | 92 | 253.4375 | 1.9946 | 3.6668 | 0.5075 | 2.1538 | 3.4172 | 0.4916 | -101.3308 |
| True | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ict_am_short_mss_open_pbl_rr3_h120 | 4 | 0.7500 | 0.7500 | 34 | 192.7533 | 1.4294 | 1.3056 | 0.3587 | 2.2183 | 6.4512 | 0.2358 | -126.3700 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ldn_ny_long_mss_open_pbl_rr3_h120 | 4 | 0.7500 | 0.7500 | 36 | 119.5908 | 3.1304 | 2.0865 | 0.3639 | 3.3561 | 2.7390 | 0.2153 | -4.2425 |
| True | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr2_h120 | 11 | 0.7273 | 0.7273 | 82 | 226.7042 | 1.7842 | 3.8445 | 0.5173 | 2.1330 | 3.4023 | 0.4779 | -101.3308 |
| True | ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h240 | 11 | 0.7273 | 0.7273 | 118 | 126.0500 | 1.1509 | 1.6146 | 0.4274 | 1.9185 | 0.9575 | 0.4121 | -28.3983 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ldn_ny_long_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 12 | 276.2850 | 2.2620 | 2.3162 | 0.5833 | 1.6545 | 23.0237 | 0.3333 | 276.2850 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ict_am_long_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 5 | 120.2592 | 0.7355 | 1.7355 | 0.2000 | 6.9419 | 24.0518 | 0.2000 | 120.2592 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_ict_am_long_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 5 | 114.2592 | 0.6740 | 1.6740 | 0.2000 | 6.6962 | 22.8518 | 0.2000 | 114.2592 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_us_rth_long_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 8 | 84.1925 | 0.4830 | 1.3902 | 0.3750 | 2.3169 | 10.5241 | 0.1250 | 84.1925 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_us_rth_long_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 8 | 84.1925 | 0.4830 | 1.3902 | 0.3750 | 2.3169 | 10.5241 | 0.1250 | 84.1925 |
| False | ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_short_mss_open_pbl_rr3_h120 | 1 | 1.0000 | 1.0000 | 6 | 43.0517 | 0.5592 | 1.3777 | 0.1667 | 6.8883 | 7.1753 | 0.1667 | 43.0517 |
| False | ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_short_mss_open_pbl_rr3_h240 | 1 | 1.0000 | 1.0000 | 6 | 43.0517 | 0.5592 | 1.3777 | 0.1667 | 6.8883 | 7.1753 | 0.1667 | 43.0517 |
| False | ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol0_any_ict_silver_short_mss_open_pbl_rr3_h120 | 1 | 1.0000 | 1.0000 | 6 | 43.0517 | 0.5592 | 1.3777 | 0.1667 | 6.8883 | 7.1753 | 0.1667 | 43.0517 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ldn_ny_long_mss_open_pbl_rr3_h240 | 2 | 1.0000 | 1.0000 | 22 | 100.3708 | 1.7355 | 2.0904 | 0.3750 | 3.7123 | 4.6975 | 0.2750 | 38.5300 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_long_mss_open_pbl_rr3_h120 | 1 | 1.0000 | 1.0000 | 7 | 32.6800 | 2.0571 | 2.3861 | 0.4286 | 3.1814 | 4.6686 | 0.2857 | 32.6800 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_ldn_ny_long_mss_open_pbl_rr3_h240 | 2 | 1.0000 | 1.0000 | 19 | 51.1175 | 1.8628 | 1.6267 | 0.3222 | 3.5732 | 2.8057 | 0.2667 | 6.1517 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ict_am_long_mss_open_pbl_rr2_h240 | 1 | 1.0000 | 1.0000 | 5 | 25.4600 | 0.1557 | 1.1557 | 0.2000 | 4.6228 | 5.0920 | 0.2000 | 25.4600 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_ict_am_long_mss_open_pbl_rr2_h240 | 1 | 1.0000 | 1.0000 | 5 | 19.4600 | 0.1148 | 1.1148 | 0.2000 | 4.4592 | 3.8920 | 0.2000 | 19.4600 |
| False | ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_short_mss_open_pbl_rr2_h240 | 1 | 1.0000 | 1.0000 | 17 | 53.5408 | 0.6127 | 1.4852 | 0.3529 | 2.7228 | 3.1495 | 0.3529 | 53.5408 |
| False | ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_short_mss_open_pbl_rr2_h120 | 2 | 1.0000 | 1.0000 | 22 | 58.4158 | 0.6684 | 1.4500 | 0.4765 | 1.8330 | 2.0622 | 0.4765 | 4.8750 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_short_mss_open_pbl_rr2_h120 | 1 | 1.0000 | 1.0000 | 10 | 16.9433 | 0.3202 | 1.2794 | 0.4000 | 1.9191 | 1.6943 | 0.4000 | 16.9433 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_short_mss_open_pbl_rr2_h240 | 1 | 1.0000 | 1.0000 | 9 | 2.0450 | 0.1042 | 1.0621 | 0.4444 | 1.3276 | 0.2272 | 0.3333 | 2.0450 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h240 | 1 | 1.0000 | 1.0000 | 12 | 1.4242 | 0.0919 | 1.0337 | 0.4167 | 1.4472 | 0.1187 | 0.3333 | 1.4242 |
| False | ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h120 | 1 | 1.0000 | 1.0000 | 12 | 0.4242 | 0.0274 | 1.0100 | 0.4167 | 1.4141 | 0.0353 | 0.3333 | 0.4242 |
| False | ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_ict_silver_long_mss_open_pbl_rr2_h240 | 2 | 1.0000 | 0.5000 | 12 | 46.6050 | 0.4905 | 1.4410 | 0.3889 | 2.4254 | 4.9180 | 0.3333 | 20.9592 |

## Full Sample Sanity

| candidate | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | avg_r_multiple | target_exit_share | stop_exit_share | max_drawdown_points | positive_years | years | positive_90d_rate | worst_90d_net | first_half_points | second_half_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr2_h120 | 224 | -84.8158 | 0.9734 | 0.4107 | 1.3967 | -0.3786 | 0.0946 | 0.3571 | 0.5759 | 759.6442 | 11 | 17 | 0.4688 | -242.3083 | 353.1733 | -437.9892 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr2_h240 | 224 | -186.0325 | 0.9438 | 0.3884 | 1.4862 | -0.8305 | 0.0878 | 0.3705 | 0.5938 | 784.5208 | 11 | 17 | 0.4375 | -242.3083 | 236.5383 | -422.5708 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr3_h240 | 264 | -490.6258 | 0.8836 | 0.3030 | 2.0324 | -1.8584 | 0.0735 | 0.2462 | 0.6818 | 920.6617 | 8 | 17 | 0.4375 | -212.9225 | 73.2367 | -563.8625 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol0_any_us_rth_long_mss_open_pbl_rr3_h120 | 222 | -157.3600 | 0.9538 | 0.3604 | 1.6929 | -0.7088 | 0.1258 | 0.2027 | 0.6171 | 764.1108 | 10 | 17 | 0.4531 | -242.3083 | 368.1300 | -525.4900 |
| ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h120 | 460 | -9.1367 | 0.9981 | 0.3717 | 1.6869 | -0.0199 | 0.0038 | 0.3370 | 0.6043 | 1024.4242 | 9 | 17 | 0.4688 | -240.4925 | -149.9950 | 140.8583 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr2_h240 | 268 | -221.1667 | 0.9421 | 0.3881 | 1.4856 | -0.8252 | 0.0877 | 0.3731 | 0.5970 | 782.9558 | 11 | 17 | 0.4531 | -248.7742 | 255.1908 | -476.3575 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ict_am_short_mss_open_pbl_rr3_h120 | 140 | 501.3225 | 1.2002 | 0.3214 | 2.5337 | 3.5809 | -0.0293 | 0.1714 | 0.6143 | 695.7883 | 8 | 17 | 0.3651 | -205.1975 | -578.7825 | 1080.1050 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ldn_ny_long_mss_open_pbl_rr3_h120 | 362 | -322.8342 | 0.9333 | 0.3260 | 1.9299 | -0.8918 | 0.0353 | 0.1989 | 0.6602 | 764.1608 | 9 | 17 | 0.4375 | -239.6108 | 74.5650 | -397.3992 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_long_mss_open_pbl_rr2_h120 | 268 | -119.9500 | 0.9676 | 0.4067 | 1.4115 | -0.4476 | 0.0934 | 0.3619 | 0.5821 | 793.2708 | 11 | 17 | 0.4688 | -248.7742 | 371.8258 | -491.7758 |
| ict2022_prev_day_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_us_rth_short_mss_open_pbl_rr2_h240 | 460 | -151.8092 | 0.9704 | 0.3652 | 1.6866 | -0.3300 | 0.0004 | 0.3478 | 0.6283 | 1140.3208 | 8 | 17 | 0.4688 | -240.4925 | -131.7383 | -20.0708 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ldn_ny_long_mss_open_pbl_rr3_h240 | 278 | 207.4750 | 1.0436 | 0.2986 | 2.4519 | 0.7463 | -0.0100 | 0.2014 | 0.6691 | 929.7950 | 8 | 17 | 0.4219 | -227.5817 | -643.9683 | 851.4433 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_ict_am_long_mss_open_pbl_rr3_h240 | 97 | 440.3300 | 1.2571 | 0.3093 | 2.8075 | 4.5395 | 0.0520 | 0.2165 | 0.6598 | 483.9717 | 8 | 17 | 0.2500 | -216.9942 | -128.5642 | 568.8942 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_ict_am_long_mss_open_pbl_rr3_h240 | 101 | 417.5800 | 1.2410 | 0.2970 | 2.9371 | 4.1345 | 0.0102 | 0.2079 | 0.6733 | 487.0967 | 8 | 17 | 0.2500 | -216.9942 | -111.3950 | 528.9750 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol-0.5_required_us_rth_long_mss_open_pbl_rr3_h240 | 162 | -86.3875 | 0.9729 | 0.2901 | 2.3805 | -0.5333 | -0.0888 | 0.1667 | 0.6605 | 896.3000 | 7 | 17 | 0.3594 | -213.2275 | -428.6008 | 342.2133 |
| ict2022_roll60_pd120_mss10w5_half_sw0.1_rec0_disp1_body0.55_vol0_required_us_rth_long_mss_open_pbl_rr3_h240 | 154 | -100.0075 | 0.9676 | 0.2987 | 2.2718 | -0.6494 | -0.0671 | 0.1688 | 0.6494 | 867.1858 | 8 | 17 | 0.3906 | -213.2275 | -310.5442 | 210.5367 |
| ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_short_mss_open_pbl_rr3_h120 | 138 | -57.0142 | 0.9700 | 0.2899 | 2.3764 | -0.4131 | -0.1461 | 0.1377 | 0.6522 | 378.6067 | 5 | 17 | 0.2188 | -104.3983 | -164.9758 | 107.9617 |
| ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_short_mss_open_pbl_rr3_h240 | 138 | 179.1783 | 1.0904 | 0.2536 | 3.2088 | 1.2984 | -0.1141 | 0.1884 | 0.7029 | 401.5883 | 5 | 17 | 0.2500 | -107.8817 | -195.1242 | 374.3025 |
| ict2022_roll60_pd120_mss10w5_extreme_sw0.1_rec0_disp1_body0.55_vol0_any_ict_silver_short_mss_open_pbl_rr3_h120 | 122 | 20.7317 | 1.0120 | 0.3033 | 2.3248 | 0.1699 | -0.1162 | 0.1475 | 0.6475 | 352.5825 | 5 | 17 | 0.2344 | -138.2583 | -172.9100 | 193.6417 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ldn_ny_long_mss_open_pbl_rr3_h240 | 360 | -483.0308 | 0.9054 | 0.2917 | 2.1988 | -1.3418 | 0.0317 | 0.2417 | 0.6972 | 836.3817 | 7 | 17 | 0.4219 | -239.6108 | -145.7083 | -337.3225 |
| ict2022_prev_day_pd120_mss10w3_half_sw0.1_rec0_disp1_body0.55_vol-0.5_any_ict_silver_long_mss_open_pbl_rr3_h120 | 186 | 264.2608 | 1.1016 | 0.3925 | 1.7052 | 1.4208 | 0.1964 | 0.2043 | 0.5968 | 475.0558 | 11 | 17 | 0.4688 | -247.1075 | 130.3392 | 133.9217 |
