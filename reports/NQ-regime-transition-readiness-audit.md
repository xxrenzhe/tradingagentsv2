# NQ Regime Transition Readiness Audit

## Objective Audit

| Requirement | Evidence | Status |
| --- | --- | --- |
| NQ 1m bars under `data/raw/databento` | `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`, `5,383,225` rows, `2010-06-06 22:00:00+00:00` to `2026-04-27 23:59:00+00:00` | covered |
| Trend strategy, not simple indicator-only | Range compression followed by displacement breakout; direction is long after upside range break | covered |
| Bar-computable factors only | OHLCV-derived range width, efficiency, ATR, candle body, volume z, session, structural bar stop | covered |
| Profitability and payoff tested | Full trade export plus PF, win rate, payoff, expectancy, R target, cost stress | covered |
| Stability tested | Yearly, monthly, rolling 90/180-day, first/second half, net/DD gates | covered |
| Conservative exits | Same-bar ambiguity resolves stop-first in source backtest; stop below displacement bar low | covered |

## Historical Stability Gates

- PF >= `1.25`.
- Net/DD >= `4.0`.
- Positive years >= `70%`.
- Positive 90-day windows >= `55%`.
- First and second half both positive.
- Net remains positive at `2.125` NQ points round trip.

## Verdict

Best audited candidate `regime_breakout_lb45_w10_eff0.1_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.5_h180` passes the historical stability gate. It is a historical stable trend candidate, not a production approval.

## Candidate Summary

| label | candidate | historical_stable_pass | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | max_drawdown_points | net_to_drawdown | positive_year_rate | positive_90d_rate | first_half_points | second_half_points | net_at_cost_2.125 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| defensive45_2r5_loweff | regime_breakout_lb45_w10_eff0.1_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | True | 593 | 3398.3338 | 1.7051 | 0.3912 | 2.6532 | 5.7307 | 230.0867 | 14.7698 | 0.8750 | 0.6333 | 806.3058 | 2592.0279 | 2508.8338 |
| defensive45_2r5_lossfilter | regime_breakout_lb45_w10_eff0.25_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 | True | 653 | 3626.2421 | 1.6606 | 0.3997 | 2.4941 | 5.5532 | 254.1508 | 14.2681 | 0.7059 | 0.6667 | 1122.0646 | 2504.1775 | 2646.7421 |
| short45_2r25_netdd | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h240 | True | 1166 | 4118.2479 | 1.4229 | 0.3842 | 2.2805 | 3.5319 | 333.1319 | 12.3622 | 0.7059 | 0.6190 | 1142.5602 | 2975.6877 | 2369.2479 |
| short45_2r5_balanced | regime_breakout_lb45_w12_eff0.15_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | True | 995 | 3734.2675 | 1.4490 | 0.3779 | 2.3854 | 3.7530 | 319.1054 | 11.7023 | 0.7059 | 0.6984 | 1148.6979 | 2585.5696 | 2241.7675 |
| highest_fullsample_3r_neighbor | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | True | 956 | 3306.4750 | 1.3851 | 0.3337 | 2.7659 | 3.4587 | 448.8033 | 7.3673 | 0.8235 | 0.6349 | 783.2550 | 2523.2200 | 1872.4750 |
| best_wf_3r | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | True | 569 | 1975.3075 | 1.3954 | 0.3409 | 2.6974 | 3.4715 | 301.6825 | 6.5476 | 0.7059 | 0.5873 | 941.9283 | 1033.3792 | 1121.8075 |
| best_wf_2r | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | True | 469 | 1608.0125 | 1.3949 | 0.4115 | 1.9947 | 3.4286 | 258.3542 | 6.2241 | 0.7647 | 0.5873 | 361.2808 | 1246.7317 | 904.5125 |
| short35_2r25_lowr_probe | regime_breakout_lb35_w10_eff0.25_disp1.4_body0.55_vol0_us_late_long_break_bar_rr2.25_h180 | False | 1108 | 3410.2073 | 1.3674 | 0.3872 | 2.1642 | 3.0778 | 376.2954 | 9.0626 | 0.5882 | 0.6508 | 826.2108 | 2583.9965 | 1748.2073 |
| short45_2r5_maxnet | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h240 | False | 1148 | 4214.8742 | 1.4268 | 0.3632 | 2.5012 | 3.6715 | 484.4575 | 8.7002 | 0.6471 | 0.6349 | 1197.9354 | 3016.9388 | 2492.8742 |

## Gate Detail

| label | gate_net_positive | gate_profit_factor | gate_net_to_drawdown | gate_positive_year_rate | gate_positive_90d_rate | gate_first_half_positive | gate_second_half_positive | gate_cost_stress_positive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| defensive45_2r5_loweff | True | True | True | True | True | True | True | True |
| defensive45_2r5_lossfilter | True | True | True | True | True | True | True | True |
| short45_2r25_netdd | True | True | True | True | True | True | True | True |
| short45_2r5_balanced | True | True | True | True | True | True | True | True |
| highest_fullsample_3r_neighbor | True | True | True | True | True | True | True | True |
| best_wf_3r | True | True | True | True | True | True | True | True |
| best_wf_2r | True | True | True | True | True | True | True | True |
| short35_2r25_lowr_probe | True | True | True | False | True | True | True | True |
| short45_2r5_maxnet | True | True | True | False | True | True | True | True |

## Yearly Net Points

| label | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| best_wf_2r | 9.1250 | -34.3950 | 10.0000 | -5.9358 | 17.4617 | 10.5808 | -24.5150 | 72.3367 | 66.5508 | -54.4858 | 227.3592 | 0.6758 | 24.1592 | 154.3767 | 449.3450 | 542.4725 | 142.9008 |
| best_wf_3r | 3.6250 | -44.2700 | 10.0000 | -5.9358 | 0.5867 | 38.3600 | 7.4442 | 79.2858 | 185.7675 | -39.4942 | 689.1417 | -75.7342 | 63.6775 | -33.4208 | 447.7500 | 477.1908 | 171.3333 |
| defensive45_2r5_lossfilter | 21.1250 | -47.0250 | 3.2500 | 8.0079 | -19.4600 | 36.8454 | -26.1900 | 68.6771 | 275.1871 | -83.3175 | 897.3787 | 74.4958 | 425.0104 | -57.0254 | 670.5042 | 771.4096 | 607.3688 |
| defensive45_2r5_loweff | nan | -32.2750 | 8.6250 | 3.6225 | 3.9150 | 41.1421 | 3.9921 | 40.5850 | 89.4496 | -78.5283 | 772.0379 | 82.5392 | 302.0125 | 84.6442 | 505.1408 | 798.1387 | 773.2925 |
| highest_fullsample_3r_neighbor | 18.2500 | -45.6450 | 4.6250 | 2.0767 | -29.6467 | 48.5767 | 0.5683 | 83.6608 | 255.0175 | -111.0817 | 396.8300 | 296.9783 | 67.7583 | 42.2067 | 427.2575 | 1311.2258 | 537.8167 |
| short35_2r25_lowr_probe | 19.6875 | -60.4000 | -1.8750 | 4.8194 | -7.6842 | 96.8896 | -58.9325 | 68.4202 | 286.0548 | -192.5085 | 863.3533 | -165.3408 | 600.7525 | -100.2858 | 539.7596 | 826.2137 | 691.2835 |
| short45_2r25_netdd | 21.4375 | -64.0583 | 7.6250 | -3.3283 | -19.9442 | 63.3898 | -54.6438 | 73.0310 | 237.4477 | -145.4125 | 846.0321 | 153.6862 | 459.7635 | 108.4692 | 578.3498 | 1396.0258 | 460.3773 |
| short45_2r5_balanced | 21.1250 | -40.5250 | 11.0000 | 3.5746 | -23.3192 | 58.3392 | -7.7629 | 84.0588 | 235.9096 | -94.9337 | 804.9762 | 41.3496 | 265.6183 | -92.1746 | 558.9104 | 1324.6771 | 583.4442 |
| short45_2r5_maxnet | 22.8750 | -64.0583 | 7.6250 | -11.8004 | -26.4442 | 54.5225 | -11.1050 | 75.9338 | 202.5725 | -119.8337 | 814.3571 | 198.3854 | 351.1371 | -21.9225 | 631.0988 | 1509.1221 | 602.4092 |

## Worst Rolling 90-Day Windows

| start | end | trades | net_points | label |
| --- | --- | --- | --- | --- |
| 2022-12-26 | 2023-03-26 | 42 | -228.4604 | short35_2r25_lowr_probe |
| 2022-12-26 | 2023-03-26 | 40 | -210.5892 | highest_fullsample_3r_neighbor |
| 2021-01-05 | 2021-04-05 | 37 | -183.6529 | short35_2r25_lowr_probe |
| 2022-12-26 | 2023-03-26 | 46 | -166.6333 | short45_2r5_maxnet |
| 2023-06-24 | 2023-09-22 | 27 | -162.4054 | short45_2r5_balanced |
| 2023-06-15 | 2023-09-13 | 12 | -154.2483 | best_wf_3r |
| 2023-06-24 | 2023-09-22 | 32 | -154.0596 | short35_2r25_lowr_probe |
| 2023-06-24 | 2023-09-22 | 34 | -150.4898 | short45_2r25_netdd |
| 2022-11-10 | 2023-02-08 | 23 | -141.8550 | best_wf_2r |
| 2022-03-22 | 2022-06-20 | 8 | -134.0742 | best_wf_3r |
| 2021-01-05 | 2021-04-05 | 39 | -127.9646 | short45_2r25_netdd |
| 2023-06-24 | 2023-09-22 | 33 | -125.2021 | short45_2r5_maxnet |
| 2022-12-26 | 2023-03-26 | 40 | -122.8392 | short45_2r5_balanced |
| 2021-08-25 | 2021-11-23 | 16 | -122.1983 | defensive45_2r5_loweff |
| 2019-01-16 | 2019-04-16 | 25 | -119.8542 | highest_fullsample_3r_neighbor |
| 2022-12-26 | 2023-03-26 | 20 | -119.1346 | defensive45_2r5_lossfilter |
| 2023-06-24 | 2023-09-22 | 25 | -118.2950 | highest_fullsample_3r_neighbor |
| 2022-11-18 | 2023-02-16 | 21 | -117.8129 | defensive45_2r5_loweff |
| 2018-12-09 | 2019-03-09 | 25 | -116.3300 | defensive45_2r5_loweff |
| 2021-01-05 | 2021-04-05 | 39 | -114.9408 | short45_2r5_maxnet |

## Interpretation

- Passing this audit means the candidate is historically stable under the defined gates.
- It still needs paper trading and execution validation before live deployment.
- The edge remains concentrated in the `us_late` long-side NQ behavior, so regime drift is the main residual risk.
