# NQ Long-Term Profitable Strategy Backtest Audit

## Verdict

The best current long-term research candidate is `defensive45_2r5_loweff`:

`regime_breakout_lb45_w10_eff0.1_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.5_h180`

It is a **range-compression to upside-displacement breakout** strategy, not a generic indicator rule:

- Look back 45 minutes and require a compressed, inefficient range: width <= 10 ATR and efficiency <= 0.10.
- Trade only `us_late`, long only.
- Require upside displacement: candle range >= 1.6 ATR30, body share >= 0.55, volume z >= 0.
- Enter next bar open.
- Stop below the displacement bar low with structural buffer.
- Target 2.5R, timeout 180 minutes.

This strategy passes the long-term research gate, but it is **not production-ready** because paper validation, execution validation, and live risk-limit validation are still missing.

## Top Candidate Metrics

| Metric | Value |
| --- | ---: |
| Sample | 2011-2026 |
| Sample years with trades | 16 |
| Trades | 586 |
| Net points | 3500.49 |
| Net dollars at NQ $20/pt | 70009.70 |
| Profit factor | 1.737 |
| Win rate | 39.76% |
| Payoff ratio | 2.63 |
| Expectancy points/trade | 5.97 |
| Max drawdown points | 230.09 |
| Net / max drawdown | 15.21 |
| Positive year rate | 81.25% |
| Positive 90d rolling rate | 65.00% |
| Positive 180d rolling rate | 70.00% |
| Worst year points | -98.45 |
| Worst 90d window points | -122.20 |
| Worst 180d window points | -190.61 |
| Net at 2.125pt round-trip cost | 2621.49 |
| Net at 3.125pt round-trip cost | 2035.49 |
| 2026 partial-year net | 773.29 |

## Candidate Pool Coverage

| strategy_source | candidates | long_term_pass | production_ready | best_net_points |
| --- | --- | --- | --- | --- |
| ict_order_flow_shift | 7 | 0 | 0 | 1065.7804 |
| regime_transition | 9 | 8 | 0 | 4390.3883 |
| screenshot_smc_momentum | 8 | 0 | 0 | 663.8117 |

Interpretation:

- `regime_transition`: the only pool with candidates passing the long-term gate. These use the full 2010-2026 Databento 1m history.
- `ict_order_flow_shift`: still interesting, especially high-relative-volume bullish OFS, but only has 2020-2026 evidence and fails long-term gates.
- `screenshot_smc_momentum`: EQL sweep reclaim is a research lead, but not a long-term strategy yet; naked BOS/displacement visual continuation fails.

## Long-Term Gate Passed Candidates

| strategy_label | trades | net_points | profit_factor | win_rate | payoff_ratio | expectancy_points | max_drawdown_points | net_to_drawdown | positive_year_rate | positive_90d_rate | positive_180d_rate | cost_3_125_net_points | candidate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| defensive45_2r5_loweff | 586 | 3500.4850 | 1.7375 | 0.3976 | 2.6323 | 5.9735 | 230.0867 | 15.2138 | 0.8125 | 0.6500 | 0.7000 | 2035.4850 | regime_breakout_lb45_w10_eff0.1_disp1.6_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 |
| defensive45_2r5_lossfilter | 649 | 3752.7625 | 1.6886 | 0.4052 | 2.4783 | 5.7824 | 254.1508 | 14.7659 | 0.7059 | 0.6984 | 0.6774 | 2130.2625 | regime_breakout_lb45_w10_eff0.25_disp1.8_body0.55_vol0.5_us_late_long_break_bar_rr2.5_h180 |
| short45_2r25_netdd | 1156 | 4362.1504 | 1.4531 | 0.3893 | 2.2798 | 3.7735 | 303.2383 | 14.3852 | 0.7059 | 0.6032 | 0.6452 | 1472.1504 | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.25_h240 |
| short45_2r5_balanced | 986 | 3941.8079 | 1.4803 | 0.3834 | 2.3810 | 3.9978 | 311.3529 | 12.6603 | 0.7059 | 0.6667 | 0.7097 | 1476.8079 | regime_breakout_lb45_w12_eff0.15_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h180 |
| short45_2r5_maxnet | 1138 | 4390.3883 | 1.4489 | 0.3673 | 2.4957 | 3.8580 | 441.7425 | 9.9388 | 0.7059 | 0.6032 | 0.6774 | 1545.3883 | regime_breakout_lb45_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2.5_h240 |
| highest_fullsample_3r_neighbor | 942 | 3500.0942 | 1.4143 | 0.3386 | 2.7620 | 3.7156 | 406.0883 | 8.6190 | 0.8235 | 0.6349 | 0.7097 | 1145.0942 | regime_breakout_lb60_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr3_h240 |
| best_wf_3r | 558 | 2106.2667 | 1.4314 | 0.3495 | 2.6646 | 3.7747 | 288.6150 | 7.2978 | 0.7059 | 0.5873 | 0.6774 | 711.2667 | regime_breakout_lb120_w12_eff0.25_disp1_body0.55_vol-0.5_us_late_long_break_bar_rr3_h240 |
| best_wf_2r | 462 | 1685.1617 | 1.4208 | 0.4199 | 1.9628 | 3.6475 | 266.3983 | 6.3257 | 0.7059 | 0.6032 | 0.6452 | 530.1617 | regime_breakout_lb120_w12_eff0.25_disp1.2_body0.55_vol0_us_late_long_break_bar_rr2_h240 |

## Top Candidate Yearly Net

| year | trades | net_points |
| --- | --- | --- |
| 2011 | 10 | -32.2750 |
| 2012 | 3 | 9.3750 |
| 2013 | 7 | 3.6225 |
| 2014 | 13 | -9.8350 |
| 2015 | 23 | 29.2671 |
| 2016 | 28 | 10.3937 |
| 2017 | 20 | 59.2100 |
| 2018 | 38 | 96.5746 |
| 2019 | 42 | -98.4508 |
| 2020 | 63 | 772.0379 |
| 2021 | 58 | 99.6267 |
| 2022 | 52 | 331.6600 |
| 2023 | 64 | 118.1817 |
| 2024 | 69 | 526.7446 |
| 2025 | 73 | 811.0596 |
| 2026 | 23 | 773.2925 |

## Top Candidate Worst Rolling Windows

| rolling_days | start | end | trades | net_points |
| --- | --- | --- | --- | --- |
| 180 | 2022-08-20 | 2023-02-16 | 37 | -190.6112 |
| 90 | 2021-08-25 | 2021-11-23 | 16 | -122.1983 |
| 90 | 2022-11-18 | 2023-02-16 | 21 | -117.8129 |
| 90 | 2018-12-09 | 2019-03-09 | 25 | -116.3300 |
| 180 | 2018-09-10 | 2019-03-09 | 34 | -84.8554 |
| 90 | 2022-08-20 | 2022-11-18 | 16 | -72.7983 |
| 90 | 2019-09-05 | 2019-12-04 | 8 | -48.1508 |
| 180 | 2014-10-01 | 2015-03-30 | 20 | -48.0442 |
| 90 | 2023-08-15 | 2023-11-13 | 15 | -47.8950 |
| 90 | 2016-09-20 | 2016-12-19 | 8 | -40.6208 |

## Best Candidates By Source

| strategy_source | strategy_label | readiness_tier | trades | net_points | profit_factor | net_to_drawdown | positive_year_rate | positive_180d_rate | cost_3_125_net_points | research_blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ict_order_flow_shift | high_relative_volume_rr1.5_c2 | continue_research | 355 | 1065.7804 | 1.2406 | 3.2195 | 0.8571 | 0.7500 | 178.2804 | sample_years, profit_factor, net_to_drawdown, positive_90d_rate, current_year_nonnegative |
| ict_order_flow_shift | high_relative_volume_rr1.5_c3 | continue_research | 376 | 1044.6421 | 1.2253 | 2.9256 | 0.8571 | 0.7083 | 104.6421 | sample_years, profit_factor, net_to_drawdown, positive_90d_rate, current_year_nonnegative |
| ict_order_flow_shift | open_trend_volume_rr1.75_c3 | continue_research | 289 | 795.4656 | 1.1969 | 2.1738 | 0.8571 | 0.8333 | 72.9656 | sample_years, trades, profit_factor, net_to_drawdown, positive_90d_rate, current_year_nonnegative |
| regime_transition | defensive45_2r5_loweff | promote_to_paper_validation | 586 | 3500.4850 | 1.7375 | 15.2138 | 0.8125 | 0.7000 | 2035.4850 |  |
| regime_transition | defensive45_2r5_lossfilter | promote_to_paper_validation | 649 | 3752.7625 | 1.6886 | 14.7659 | 0.7059 | 0.6774 | 2130.2625 |  |
| regime_transition | short45_2r25_netdd | promote_to_paper_validation | 1156 | 4362.1504 | 1.4531 | 14.3852 | 0.7059 | 0.6452 | 1472.1504 |  |
| screenshot_smc_momentum | rth_long_eql_sweep_reclaim_rr1.25 | continue_research | 373 | 663.8117 | 1.1451 | 1.6093 | 0.7143 | 0.5833 | -268.6883 | sample_years, profit_factor, net_to_drawdown, positive_90d_rate, positive_180d_rate, cost_3_125_positive |
| screenshot_smc_momentum | rth_short_eqh_sweep_reject_rr1 | reject_current_form | 301 | 381.6675 | 1.2097 | 1.4940 | 0.5714 | 0.5417 | -370.8325 | sample_years, profit_factor, net_to_drawdown, positive_year_rate, positive_90d_rate, positive_180d_rate, cost_2_125_positive, cost_3_125_positive |
| screenshot_smc_momentum | rth_long_displacement_reclaim_rr1.5 | reject_current_form | 3280 | 62.6642 | 1.0014 | 0.0337 | 0.5714 | 0.4583 | -8137.3358 | sample_years, profit_factor, net_to_drawdown, positive_year_rate, positive_90d_rate, positive_180d_rate, cost_2_125_positive, cost_3_125_positive |

## Completion Audit

| Requirement | Evidence | Status |
| --- | --- | --- |
| Backtest 1m NQ after 2020 | OFS and screenshot SMC pressure tests cover 2020-2026; source rows are included in `.tmp/nq-ofs-candidate-pressure-*` and `.tmp/nq-screenshot-smc-candidate-pressure-*`. | covered |
| Search for long-term profitability | Regime-transition audit covers 2010-06-06 to 2026-04-27, 5,383,225 bars, 502,361 events. | covered |
| Validate stability, not just net profit | Gate includes PF, net/DD, positive years, 90d/180d rolling windows, current-year nonnegative, and 2.125/3.125 point cost stress. | covered |
| Include screenshot-derived features | `screenshot_smc_momentum` pool is included in the unified audit; no screenshot candidate passes long-term gates. | covered |
| Distinguish research vs production | `production_ready` is false until paper validation, execution validation, and live risk limits are proven. | covered |

## Files

- HTML audit: `reports/NQ-long-term-strategy-candidate-audit.html`
- CSV audit: `.tmp/nq-long-term-strategy-candidate-audit.csv`
- Yearly detail: `.tmp/nq-long-term-strategy-candidate-yearly.csv`
- Rolling detail: `.tmp/nq-long-term-strategy-candidate-rolling.csv`
