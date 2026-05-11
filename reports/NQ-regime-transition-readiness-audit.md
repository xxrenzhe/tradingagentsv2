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

Best audited candidate `regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240` passes the historical stability gate. It is a historical stable trend candidate, not a production approval.

## Candidate Summary

| label | candidate | historical_stable_pass | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | max_drawdown_points | net_to_drawdown | positive_year_rate | positive_90d_rate | first_half_points | second_half_points | net_at_cost_2.125 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| highest_fullsample_3r_neighbor | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 | True | 942 | 3500.0942 | 1.4143 | 0.3386 | 2.7620 | 3.7156 | 406.0883 | 8.6190 | 0.8235 | 0.6349 | 958.7650 | 2541.3292 | 2087.0942 |
| best_wf_3r | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 | True | 558 | 2106.2667 | 1.4314 | 0.3495 | 2.6646 | 3.7747 | 288.6150 | 7.2978 | 0.7059 | 0.5873 | 974.3550 | 1131.9117 | 1269.2667 |
| best_wf_2r | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 | True | 462 | 1685.1617 | 1.4208 | 0.4199 | 1.9628 | 3.6475 | 266.3983 | 6.3257 | 0.7059 | 0.6032 | 388.0175 | 1297.1442 | 992.1617 |

## Gate Detail

| label | gate_net_positive | gate_profit_factor | gate_net_to_drawdown | gate_positive_year_rate | gate_positive_90d_rate | gate_first_half_positive | gate_second_half_positive | gate_cost_stress_positive |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| highest_fullsample_3r_neighbor | True | True | True | True | True | True | True | True |
| best_wf_3r | True | True | True | True | True | True | True | True |
| best_wf_2r | True | True | True | True | True | True | True | True |

## Yearly Net Points

| label | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| best_wf_2r | 9.1250 | -34.3950 | 10.7500 | -5.9358 | 17.4617 | 10.5808 | -19.8583 | 78.9983 | 73.6758 | -36.7325 | 227.3592 | 17.7633 | -24.2333 | 169.2017 | 467.8625 | 580.6375 | 142.9008 |
| best_wf_3r | 3.6250 | -44.2700 | 10.7500 | -5.9358 | 0.5867 | 38.3600 | 12.1008 | 85.9475 | 192.8925 | -15.5775 | 700.6933 | -52.0192 | 76.7450 | -18.5958 | 472.4400 | 477.1908 | 171.3333 |
| highest_fullsample_3r_neighbor | 18.2500 | -45.6450 | 10.7500 | 2.0767 | -29.6467 | 48.5767 | 6.9700 | 75.1975 | 262.1425 | -137.7925 | 427.9550 | 314.0658 | 110.4733 | 77.5050 | 451.9475 | 1369.4517 | 537.8167 |

## Worst Rolling 90-Day Windows

| start | end | trades | net_points | label |
| --- | --- | --- | --- | --- |
| 2022-12-26 | 2023-03-26 | 40 | -210.5892 | highest_fullsample_3r_neighbor |
| 2023-06-15 | 2023-09-13 | 12 | -154.2483 | best_wf_3r |
| 2022-11-10 | 2023-02-08 | 23 | -141.8550 | best_wf_2r |
| 2022-03-22 | 2022-06-20 | 8 | -134.0742 | best_wf_3r |
| 2023-09-13 | 2023-12-12 | 14 | -99.8325 | best_wf_3r |
| 2023-06-24 | 2023-09-22 | 24 | -97.8217 | highest_fullsample_3r_neighbor |
| 2019-01-16 | 2019-04-16 | 22 | -96.3892 | highest_fullsample_3r_neighbor |
| 2018-12-01 | 2019-03-01 | 19 | -94.8392 | best_wf_2r |
| 2025-12-01 | 2026-03-01 | 25 | -87.4150 | best_wf_3r |
| 2019-01-07 | 2019-04-07 | 12 | -77.1033 | best_wf_3r |
| 2021-12-31 | 2022-03-31 | 32 | -71.3158 | highest_fullsample_3r_neighbor |
| 2023-08-07 | 2023-11-05 | 4 | -69.9708 | best_wf_2r |
| 2021-01-05 | 2021-04-05 | 34 | -61.0225 | highest_fullsample_3r_neighbor |
| 2021-09-23 | 2021-12-22 | 23 | -59.6967 | best_wf_3r |
| 2020-10-07 | 2021-01-05 | 28 | -57.7217 | highest_fullsample_3r_neighbor |
| 2021-08-17 | 2021-11-15 | 6 | -55.6783 | best_wf_2r |
| 2022-12-17 | 2023-03-17 | 21 | -48.9525 | best_wf_3r |
| 2019-07-15 | 2019-10-13 | 13 | -45.7033 | highest_fullsample_3r_neighbor |
| 2014-11-08 | 2015-02-06 | 17 | -39.7375 | highest_fullsample_3r_neighbor |
| 2024-06-09 | 2024-09-07 | 12 | -39.0042 | best_wf_3r |

## Interpretation

- Passing this audit means the candidate is historically stable under the defined gates.
- It still needs paper trading and execution validation before live deployment.
- The edge remains concentrated in the `us_late` long-side NQ behavior, so regime drift is the main residual risk.
