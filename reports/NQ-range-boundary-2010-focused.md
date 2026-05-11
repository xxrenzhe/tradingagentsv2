# NQ Range Boundary Reversion Search

## Model

This tests the box-trading idea: after a mechanically defined sideways range, buy near the lower boundary if price rejects the low, or short near the upper boundary if price rejects the high. Stop is placed beyond a recent prior low/high and is honored immediately; no averaging or holding through failure.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Span: `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `5,383,225`.
- Boundary events: `199,234`.
- Costs: `0.625` NQ points round trip.

## Verdict

Best stable boundary candidate: `range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl5_opposite_edge_rr2_h120` with `62.50` selected OOS points, `100.00%` positive selected folds, PF `1.890`, and expectancy `3.293` points/trade.

## Top Walk-Forward Rows

| stable_candidate | candidate | selected_folds | positive_test_fold_rate | pass_fold_rate | test_trades | test_net_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | avg_test_payoff_ratio | avg_test_expectancy_points | avg_test_target_exit_share | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl5_opposite_edge_rr2_h120 | 3 | 1.0000 | 1.0000 | 22 | 62.5000 | 2.5641 | 1.8901 | 0.4361 | 2.3301 | 3.2928 | 0.0787 | 9.8750 |
| True | range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.1_us_late_short_sl5_opposite_edge_rr2_h120 | 3 | 1.0000 | 1.0000 | 22 | 62.5000 | 2.5641 | 1.8901 | 0.4361 | 2.3301 | 3.2928 | 0.0787 | 9.8750 |
| True | range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl10_opposite_edge_rr2_h120 | 3 | 1.0000 | 1.0000 | 24 | 62.7500 | 2.5744 | 1.9036 | 0.4806 | 1.9511 | 2.9618 | 0.0750 | 10.0000 |
| True | range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.1_us_late_short_sl10_opposite_edge_rr2_h120 | 3 | 1.0000 | 1.0000 | 24 | 62.7500 | 2.5744 | 1.9036 | 0.4806 | 1.9511 | 2.9618 | 0.0750 | 10.0000 |
| True | range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 4 | 0.7500 | 0.7500 | 85 | 357.8750 | 4.1857 | 1.9077 | 0.3912 | 3.0913 | 3.8866 | 0.3912 | -12.2500 |
| True | range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 4 | 0.7500 | 0.7500 | 85 | 357.8750 | 4.1857 | 1.9077 | 0.3912 | 3.0913 | 3.8866 | 0.3912 | -12.2500 |
| True | range_boundary_lb120_w8_eff0.25_band0.1_reclaim0.05_ldn_ny_long_sl5_opposite_edge_rr2_h120 | 4 | 0.7500 | 0.7500 | 93 | 171.3750 | 2.0191 | 1.3001 | 0.1435 | 8.1194 | 1.3176 | 0.0970 | -42.3750 |
| True | range_boundary_lb120_w8_eff0.35_band0.1_reclaim0.05_ldn_ny_long_sl5_opposite_edge_rr2_h120 | 4 | 0.7500 | 0.7500 | 93 | 171.3750 | 2.0191 | 1.3001 | 0.1435 | 8.1194 | 1.3176 | 0.0970 | -42.3750 |
| True | range_boundary_lb120_w8_eff0.25_band0.1_reclaim0.05_ldn_ny_long_sl10_opposite_edge_rr2_h120 | 4 | 0.7500 | 0.7500 | 94 | 165.5000 | 1.9442 | 1.2909 | 0.1414 | 8.1128 | 1.2725 | 0.0960 | -47.7500 |
| True | range_boundary_lb120_w8_eff0.35_band0.1_reclaim0.05_ldn_ny_long_sl10_opposite_edge_rr2_h120 | 4 | 0.7500 | 0.7500 | 94 | 165.5000 | 1.9442 | 1.2909 | 0.1414 | 8.1128 | 1.2725 | 0.0960 | -47.7500 |
| False | range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_short_sl5_opposite_edge_rr2_h120 | 2 | 1.0000 | 1.0000 | 12 | 28.7500 | 1.4286 | 1.8737 | 0.1714 | 8.5938 | 2.8071 | 0.1714 | 2.3750 |
| False | range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_short_sl5_opposite_edge_rr2_h120 | 2 | 1.0000 | 1.0000 | 12 | 28.7500 | 1.4286 | 1.8737 | 0.1714 | 8.5938 | 2.8071 | 0.1714 | 2.3750 |
| False | range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 1 | 1.0000 | 1.0000 | 32 | 29.5000 | 0.8773 | 1.2658 | 0.3750 | 2.1096 | 0.9219 | 0.3750 | 29.5000 |
| False | range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 1 | 1.0000 | 1.0000 | 32 | 29.5000 | 0.8773 | 1.2658 | 0.3750 | 2.1096 | 0.9219 | 0.3750 | 29.5000 |
| False | range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_long_sl10_opposite_edge_rr2_h120 | 12 | 0.6667 | 0.6667 | 402 | 475.5000 | 2.7645 | 1.2945 | 0.1706 | 6.1508 | 1.4193 | 0.0215 | -123.2500 |
| False | range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_long_sl10_opposite_edge_rr2_h120 | 12 | 0.6667 | 0.6667 | 402 | 475.5000 | 2.7645 | 1.2945 | 0.1706 | 6.1508 | 1.4193 | 0.0215 | -123.2500 |
| False | range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 3 | 0.6667 | 0.6667 | 133 | -52.1250 | -0.4376 | 0.9572 | 0.3266 | 1.9681 | -0.3251 | 0.3100 | -62.5000 |
| False | range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 3 | 0.6667 | 0.6667 | 133 | -52.1250 | -0.4376 | 0.9572 | 0.3266 | 1.9681 | -0.3251 | 0.3100 | -62.5000 |
| False | range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_long_sl5_opposite_edge_rr2_h120 | 8 | 0.6250 | 0.6250 | 268 | 103.2500 | 0.3824 | 1.2491 | 0.1816 | 5.5534 | 0.7025 | 0.0103 | -122.1250 |
| False | range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_long_sl5_opposite_edge_rr2_h120 | 8 | 0.6250 | 0.6250 | 268 | 103.2500 | 0.3824 | 1.2491 | 0.1816 | 5.5534 | 0.7025 | 0.0103 | -122.1250 |
| False | range_boundary_lb120_w12_eff0.25_band0.2_reclaim0.1_us_late_short_sl10_fixed_r_rr2_h120 | 10 | 0.6000 | 0.6000 | 411 | 171.1250 | 0.5227 | 1.0069 | 0.3779 | 1.6113 | 0.0616 | 0.2768 | -89.3750 |
| False | range_boundary_lb120_w12_eff0.35_band0.2_reclaim0.1_us_late_short_sl10_fixed_r_rr2_h120 | 10 | 0.6000 | 0.6000 | 411 | 171.1250 | 0.5227 | 1.0069 | 0.3779 | 1.6113 | 0.0616 | 0.2768 | -89.3750 |
| False | range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 2 | 0.5000 | 0.5000 | 38 | 132.5000 | 4.0000 | 1.9340 | 0.4058 | 2.4906 | 2.7572 | 0.4058 | -10.6250 |
| False | range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 2 | 0.5000 | 0.5000 | 38 | 132.5000 | 4.0000 | 1.9340 | 0.4058 | 2.4906 | 2.7572 | 0.4058 | -10.6250 |
| False | range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl10_fixed_r_rr2_h120 | 2 | 0.5000 | 0.5000 | 13 | -30.8750 | -0.8636 | 0.9048 | 0.3333 | 0.4524 | -2.0536 | 0.1667 | -43.6250 |
| False | range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.1_us_late_short_sl10_fixed_r_rr2_h120 | 2 | 0.5000 | 0.5000 | 13 | -30.8750 | -0.8636 | 0.9048 | 0.3333 | 0.4524 | -2.0536 | 0.1667 | -43.6250 |
| False | range_boundary_lb120_w12_eff0.25_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 9 | 0.4444 | 0.4444 | 436 | 192.5000 | 0.8527 | 0.8994 | 0.3498 | 1.6754 | -0.1732 | 0.2580 | -12.0000 |
| False | range_boundary_lb120_w12_eff0.35_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 9 | 0.4444 | 0.4444 | 436 | 192.5000 | 0.8527 | 0.8994 | 0.3498 | 1.6754 | -0.1732 | 0.2580 | -12.0000 |
| False | range_boundary_lb120_w12_eff0.25_band0.2_reclaim0.1_us_late_long_sl5_fixed_r_rr2_h120 | 3 | 0.3333 | 0.3333 | 108 | -164.7500 | -0.8553 | 0.7979 | 0.3205 | 1.6302 | -1.3042 | 0.3094 | -128.3750 |
| False | range_boundary_lb120_w12_eff0.35_band0.2_reclaim0.1_us_late_long_sl5_fixed_r_rr2_h120 | 3 | 0.3333 | 0.3333 | 108 | -164.7500 | -0.8553 | 0.7979 | 0.3205 | 1.6302 | -1.3042 | 0.3094 | -128.3750 |

## Full Sample Sanity

| candidate | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | avg_r_multiple | target_exit_share | stop_exit_share | max_drawdown_points | positive_years | years | positive_90d_rate | worst_90d_net | first_half_points | second_half_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl5_opposite_edge_rr2_h120 | 159 | 412.6250 | 1.4326 | 0.2013 | 5.6855 | 2.5951 | 0.0928 | 0.1132 | 0.7987 | 199.3750 | 9 | 13 | 0.3191 | -57.8750 | 248.2500 | 164.3750 |
| range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.1_us_late_short_sl5_opposite_edge_rr2_h120 | 159 | 412.6250 | 1.4326 | 0.2013 | 5.6855 | 2.5951 | 0.0928 | 0.1132 | 0.7987 | 199.3750 | 9 | 13 | 0.3191 | -57.8750 | 248.2500 | 164.3750 |
| range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.1_us_late_short_sl10_opposite_edge_rr2_h120 | 165 | 372.6250 | 1.3743 | 0.2000 | 5.4972 | 2.2583 | 0.0401 | 0.1091 | 0.8000 | 196.1250 | 9 | 13 | 0.2857 | -58.1250 | 228.3750 | 144.2500 |
| range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.1_us_late_short_sl10_opposite_edge_rr2_h120 | 165 | 372.6250 | 1.3743 | 0.2000 | 5.4972 | 2.2583 | 0.0401 | 0.1091 | 0.8000 | 196.1250 | 9 | 13 | 0.2857 | -58.1250 | 228.3750 | 144.2500 |
| range_boundary_lb120_w8_eff0.25_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 223 | 300.6250 | 1.3142 | 0.3632 | 2.3039 | 1.3481 | -0.0373 | 0.3453 | 0.6368 | 161.8750 | 9 | 14 | 0.3962 | -44.5000 | -21.2500 | 321.8750 |
| range_boundary_lb120_w8_eff0.35_band0.2_reclaim0.05_us_late_short_sl10_fixed_r_rr2_h120 | 223 | 300.6250 | 1.3142 | 0.3632 | 2.3039 | 1.3481 | -0.0373 | 0.3453 | 0.6368 | 161.8750 | 9 | 14 | 0.3962 | -44.5000 | -21.2500 | 321.8750 |
| range_boundary_lb120_w8_eff0.25_band0.1_reclaim0.05_ldn_ny_long_sl5_opposite_edge_rr2_h120 | 354 | -651.0000 | 0.7142 | 0.0819 | 8.0037 | -1.8390 | -0.1697 | 0.0621 | 0.9181 | 982.0000 | 5 | 11 | 0.2203 | -294.2500 | -114.1250 | -536.8750 |
| range_boundary_lb120_w8_eff0.35_band0.1_reclaim0.05_ldn_ny_long_sl5_opposite_edge_rr2_h120 | 354 | -651.0000 | 0.7142 | 0.0819 | 8.0037 | -1.8390 | -0.1697 | 0.0621 | 0.9181 | 982.0000 | 5 | 11 | 0.2203 | -294.2500 | -114.1250 | -536.8750 |
| range_boundary_lb120_w8_eff0.25_band0.1_reclaim0.05_ldn_ny_long_sl10_opposite_edge_rr2_h120 | 359 | -601.8750 | 0.7396 | 0.0836 | 8.1110 | -1.6765 | -0.1727 | 0.0613 | 0.9164 | 923.8750 | 5 | 12 | 0.2373 | -286.6250 | -132.0000 | -469.8750 |
| range_boundary_lb120_w8_eff0.35_band0.1_reclaim0.05_ldn_ny_long_sl10_opposite_edge_rr2_h120 | 359 | -601.8750 | 0.7396 | 0.0836 | 8.1110 | -1.6765 | -0.1727 | 0.0613 | 0.9164 | 923.8750 | 5 | 12 | 0.2373 | -286.6250 | -132.0000 | -469.8750 |
| range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_short_sl5_opposite_edge_rr2_h120 | 526 | -694.5000 | 0.7692 | 0.1369 | 4.8503 | -1.3203 | -0.1541 | 0.0323 | 0.8574 | 939.6250 | 5 | 13 | 0.2500 | -153.2500 | -294.8750 | -399.6250 |
| range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_short_sl5_opposite_edge_rr2_h120 | 526 | -694.5000 | 0.7692 | 0.1369 | 4.8503 | -1.3203 | -0.1541 | 0.0323 | 0.8574 | 939.6250 | 5 | 13 | 0.2500 | -153.2500 | -294.8750 | -399.6250 |
| range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 542 | -88.7500 | 0.9618 | 0.3395 | 1.8713 | -0.1637 | -0.0970 | 0.3321 | 0.6587 | 383.5000 | 7 | 13 | 0.3750 | -79.1250 | -172.6250 | 83.8750 |
| range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_short_sl5_fixed_r_rr2_h120 | 542 | -88.7500 | 0.9618 | 0.3395 | 1.8713 | -0.1637 | -0.0970 | 0.3321 | 0.6587 | 383.5000 | 7 | 13 | 0.3750 | -79.1250 | -172.6250 | 83.8750 |
| range_boundary_lb120_w12_eff0.25_band0.1_reclaim0.05_us_late_long_sl10_opposite_edge_rr2_h120 | 510 | 504.5000 | 1.1627 | 0.1686 | 5.7323 | 0.9892 | 0.1754 | 0.0353 | 0.8275 | 334.7500 | 7 | 14 | 0.3621 | -161.6250 | 698.8750 | -194.3750 |
| range_boundary_lb120_w12_eff0.35_band0.1_reclaim0.05_us_late_long_sl10_opposite_edge_rr2_h120 | 510 | 504.5000 | 1.1627 | 0.1686 | 5.7323 | 0.9892 | 0.1754 | 0.0353 | 0.8275 | 334.7500 | 7 | 14 | 0.3621 | -161.6250 | 698.8750 | -194.3750 |
