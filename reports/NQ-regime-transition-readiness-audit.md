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

Best audited candidate `regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h240` passes the historical stability gate. It is a historical stable trend candidate, not a production approval.

## Candidate Summary

| label | candidate | historical_stable_pass | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | max_drawdown_points | net_to_drawdown | positive_year_rate | positive_90d_rate | first_half_points | second_half_points | net_at_cost_2.125 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| short45_2r25_netdd | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h240 | True | 1156 | 4362.1504 | 1.4531 | 0.3893 | 2.2798 | 3.7735 | 303.2383 | 14.3852 | 0.7059 | 0.6032 | 1214.4121 | 3147.7383 | 2628.1504 |
| short45_2r5_balanced | regime_breakout_lb45_w12_eff0.15_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 | True | 986 | 3941.8079 | 1.4803 | 0.3834 | 2.3810 | 3.9978 | 311.3529 | 12.6603 | 0.7059 | 0.6667 | 1156.8629 | 2784.9450 | 2462.8079 |
| short45_2r5_maxnet | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h240 | True | 1138 | 4390.3883 | 1.4489 | 0.3673 | 2.4957 | 3.8580 | 441.7425 | 9.9388 | 0.7059 | 0.6032 | 1205.9087 | 3184.4796 | 2683.3883 |
| highest_fullsample_3r_neighbor | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | True | 942 | 3500.0942 | 1.4143 | 0.3386 | 2.7620 | 3.7156 | 406.0883 | 8.6190 | 0.8235 | 0.6349 | 958.7650 | 2541.3292 | 2087.0942 |
| best_wf_3r | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | True | 558 | 2106.2667 | 1.4314 | 0.3495 | 2.6646 | 3.7747 | 288.6150 | 7.2978 | 0.7059 | 0.5873 | 974.3550 | 1131.9117 | 1269.2667 |
| best_wf_2r | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | True | 462 | 1685.1617 | 1.4208 | 0.4199 | 1.9628 | 3.6475 | 266.3983 | 6.3257 | 0.7059 | 0.6032 | 388.0175 | 1297.1442 | 992.1617 |

## Gate Detail

| label | gate_net_positive | gate_profit_factor | gate_net_to_drawdown | gate_positive_year_rate | gate_positive_90d_rate | gate_first_half_positive | gate_second_half_positive | gate_cost_stress_positive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| short45_2r25_netdd | True | True | True | True | True | True | True | True |
| short45_2r5_balanced | True | True | True | True | True | True | True | True |
| short45_2r5_maxnet | True | True | True | True | True | True | True | True |
| highest_fullsample_3r_neighbor | True | True | True | True | True | True | True | True |
| best_wf_3r | True | True | True | True | True | True | True | True |
| best_wf_2r | True | True | True | True | True | True | True | True |

## Yearly Net Points

| label | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| best_wf_2r | 9.1250 | -34.3950 | 10.7500 | -5.9358 | 17.4617 | 10.5808 | -19.8583 | 78.9983 | 73.6758 | -36.7325 | 227.3592 | 17.7633 | -24.2333 | 169.2017 | 467.8625 | 580.6375 | 142.9008 |
| best_wf_3r | 3.6250 | -44.2700 | 10.7500 | -5.9358 | 0.5867 | 38.3600 | 12.1008 | 85.9475 | 192.8925 | -15.5775 | 700.6933 | -52.0192 | 76.7450 | -18.5958 | 472.4400 | 477.1908 | 171.3333 |
| highest_fullsample_3r_neighbor | 18.2500 | -45.6450 | 10.7500 | 2.0767 | -29.6467 | 48.5767 | 6.9700 | 75.1975 | 262.1425 | -137.7925 | 427.9550 | 314.0658 | 110.4733 | 77.5050 | 451.9475 | 1369.4517 | 537.8167 |
| short45_2r25_netdd | 21.4375 | -64.0583 | 13.7500 | -12.8640 | -19.9442 | 51.5148 | -48.2421 | 89.3802 | 244.5727 | -184.9983 | 877.1571 | 170.7737 | 469.1400 | 160.5462 | 661.7448 | 1471.8629 | 460.3773 |
| short45_2r5_balanced | 21.1250 | -40.5250 | 11.7500 | 3.5746 | -45.7192 | 46.4642 | -1.3613 | 109.3454 | 243.0346 | -109.1446 | 804.9762 | 58.4371 | 308.3333 | -38.1637 | 580.5142 | 1405.7229 | 583.4442 |
| short45_2r5_maxnet | 22.8750 | -64.0583 | 13.7500 | -11.8004 | -48.8442 | 42.6475 | -4.7033 | 90.9704 | 209.6975 | -146.5446 | 845.4821 | 215.4729 | 359.1550 | 32.0883 | 652.7025 | 1579.0887 | 602.4092 |

## Worst Rolling 90-Day Windows

| start | end | trades | net_points | label |
| --- | --- | --- | --- | --- |
| 2022-12-26 | 2023-03-26 | 40 | -210.5892 | highest_fullsample_3r_neighbor |
| 2022-12-26 | 2023-03-26 | 46 | -166.6333 | short45_2r5_maxnet |
| 2023-06-15 | 2023-09-13 | 12 | -154.2483 | best_wf_3r |
| 2023-06-24 | 2023-09-22 | 26 | -141.9321 | short45_2r5_balanced |
| 2022-11-10 | 2023-02-08 | 23 | -141.8550 | best_wf_2r |
| 2022-03-22 | 2022-06-20 | 8 | -134.0742 | best_wf_3r |
| 2023-06-24 | 2023-09-22 | 33 | -130.0165 | short45_2r25_netdd |
| 2022-12-26 | 2023-03-26 | 40 | -122.8392 | short45_2r5_balanced |
| 2021-01-05 | 2021-04-05 | 38 | -110.8771 | short45_2r25_netdd |
| 2022-12-26 | 2023-03-26 | 46 | -109.2571 | short45_2r25_netdd |
| 2023-06-24 | 2023-09-22 | 32 | -104.7287 | short45_2r5_maxnet |
| 2023-09-13 | 2023-12-12 | 14 | -99.8325 | best_wf_3r |
| 2021-01-05 | 2021-04-05 | 38 | -97.8533 | short45_2r5_maxnet |
| 2023-06-24 | 2023-09-22 | 24 | -97.8217 | highest_fullsample_3r_neighbor |
| 2019-01-16 | 2019-04-16 | 22 | -96.3892 | highest_fullsample_3r_neighbor |
| 2018-12-01 | 2019-03-01 | 19 | -94.8392 | best_wf_2r |
| 2025-12-01 | 2026-03-01 | 25 | -87.4150 | best_wf_3r |
| 2019-01-16 | 2019-04-16 | 25 | -84.8517 | short45_2r5_balanced |
| 2021-01-05 | 2021-04-05 | 35 | -79.1296 | short45_2r5_balanced |
| 2019-01-07 | 2019-04-07 | 12 | -77.1033 | best_wf_3r |

## Interpretation

- Passing this audit means the candidate is historically stable under the defined gates.
- It still needs paper trading and execution validation before live deployment.
- The edge remains concentrated in the `us_late` long-side NQ behavior, so regime drift is the main residual risk.
