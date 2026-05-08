# NQ 1m ICT Chart Feature Backtest

## Research Read

The screenshots point to three repeatable trade shapes: stair-step continuation after displacement, liquidity sweep/reclaim into a reversal leg, and confirmed entries after premium/discount POIs. `docs/Strategy/ICT2022-2.md` frames those as structure, POI, liquidity sweep, and CHoCH/MSS confirmation. `docs/Strategy/lightglow.md` supplies the measurable SMC parts: internal/swing structure, FVGs, equal highs/lows, order blocks, and premium/discount zones.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Loaded continuous NQ 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `1,769,740`; symbols selected: `21`.
- Costs: `0.625` NQ points round trip.

## Feature Families Tested

- `displacement_bos_lb50`: Strong body/range expansion that closes through a prior range high/low.
- `pd_displacement_continue_lb100_bos20`: Screenshot-style stair-step continuation: P/D extreme plus displacement BOS.
- `pd_displacement_continue_lb100_bos50`: Screenshot-style stair-step continuation: P/D extreme plus displacement BOS.
- `sweep_pd_lb20_pd100`: Sweep only when it happens inside the matching discount or premium POI.
- `sweep_pd_lb50_pd50`: Sweep only when it happens inside the matching discount or premium POI.

## Walk-Forward Design

- Train/test: `365` train days, `5` purge days, `90` test days, `90` step days.
- Sessions: `us_rth, us_late`.
- Holds: `2, 3, 5` minutes.
- Exit profiles: `time, sl8_tp12, sl8_tp16, sl12_tp24`.
- Train gate: trades >= `40`, PF >= `1.03`, net > 0.
- Test gate: trades >= `5`, PF >= `1.0`, net > 0.

## Verdict

Best positive aggregate candidate: `chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time` with `427.88` future test net points, `100.00%` positive selected folds, `1.065` average test PF, and `577` test trades.

## Aggregate Ranking

| candidate | family | session | holding_minutes | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 1 | 1.0000 | 577 | 427.8750 | 744.0000 | 0.5751 | 1.0654 | 0.4835 | 427.8750 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_time | displacement_bos | us_late | 5 | time | 9 | 0.3333 | 813 | 410.6250 | 381.8750 | 1.0753 | 1.1829 | 0.4815 | -293.8750 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | sweep_at_pd_poi | us_late | 3 | time | 3 | 1.0000 | 399 | 103.6250 | 124.8750 | 0.8298 | 1.0778 | 0.4836 | 2.5000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 6 | 0.5000 | 462 | 101.0000 | 237.2500 | 0.4257 | 0.9687 | 0.4748 | -231.6250 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 9 | 0.2222 | 580 | 38.7500 | 303.6250 | 0.1276 | 1.1320 | 0.4799 | -266.7500 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 4 | 0.5000 | 467 | 38.3750 | 302.1250 | 0.1270 | 1.0918 | 0.4863 | -41.7500 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 7 | 0.4286 | 552 | 35.7500 | 218.7500 | 0.1634 | 0.9514 | 0.4851 | -211.0000 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 9 | 0.2222 | 562 | 31.7500 | 287.6250 | 0.1104 | 1.1390 | 0.4810 | -238.0000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_sl12_tp24 | pd_displacement_continuation | us_late | 5 | sl12_tp24 | 2 | 0.0000 | 144 | -125.7500 | 123.7500 | -1.0162 | 0.8024 | 0.4289 | -70.6250 |
| chart_ict_displacement_bos_lb50_us_late_hold2m_sl12_tp24 | displacement_bos | us_late | 2 | sl12_tp24 | 1 | 0.0000 | 129 | -133.1250 | 279.3750 | -0.4765 | 0.8012 | 0.4186 | -133.1250 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_sl12_tp24 | pd_displacement_continuation | us_late | 5 | sl12_tp24 | 2 | 0.0000 | 141 | -142.1250 | 130.6250 | -1.0880 | 0.7801 | 0.4294 | -82.5000 |
| chart_ict_sweep_pd_lb20_pd100_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 1 | 0.0000 | 86 | -150.0000 | 167.7500 | -0.8942 | 0.6715 | 0.4535 | -150.0000 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_sl12_tp24 | sweep_at_pd_poi | us_late | 5 | sl12_tp24 | 1 | 0.0000 | 138 | -174.2500 | 190.1250 | -0.9165 | 0.7316 | 0.4348 | -174.2500 |
| chart_ict_sweep_pd_lb20_pd100_us_late_hold5m_sl12_tp24 | sweep_at_pd_poi | us_late | 5 | sl12_tp24 | 1 | 0.0000 | 90 | -185.5000 | 202.0000 | -0.9183 | 0.5864 | 0.4000 | -185.5000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 8 | 0.3750 | 585 | -208.6250 | 302.1250 | -0.6905 | 0.8906 | 0.4473 | -247.5000 |
| chart_ict_sweep_pd_lb50_pd50_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 1 | 0.0000 | 664 | -308.2500 | 470.5000 | -0.6552 | 0.9171 | 0.4593 | -308.2500 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_sl12_tp24 | displacement_bos | us_late | 5 | sl12_tp24 | 4 | 0.0000 | 400 | -367.5000 | 260.5000 | -1.4107 | 0.8271 | 0.4007 | -129.3750 |
| chart_ict_displacement_bos_lb50_us_late_hold3m_sl12_tp24 | displacement_bos | us_late | 3 | sl12_tp24 | 3 | 0.0000 | 332 | -502.0000 | 280.6250 | -1.7889 | 0.6872 | 0.3900 | -251.6250 |
| chart_ict_displacement_bos_lb50_us_late_hold2m_time | displacement_bos | us_late | 2 | time | 7 | 0.2857 | 743 | -505.6250 | 254.6250 | -1.9858 | 0.8332 | 0.4680 | -230.2500 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 7 | 0.1429 | 486 | -614.5000 | 283.1250 | -2.1704 | 0.7852 | 0.4439 | -221.8750 |
| chart_ict_displacement_bos_lb50_us_late_hold3m_time | displacement_bos | us_late | 3 | time | 8 | 0.2500 | 777 | -615.6250 | 260.0000 | -2.3678 | 0.9016 | 0.4393 | -238.7500 |

## Top Future Fold Rows

| test_pass | candidate | fold | fold_rank | train_trades | train_net_points | train_profit_factor | test_trades | test_net_points | test_profit_factor | test_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| True | chart_ict_displacement_bos_lb50_us_late_hold5m_time | 11 | 5 | 324 | 65.2500 | 1.0352 | 102 | 1065.5000 | 2.9911 | 0.5784 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | 11 | 2 | 216 | 118.2500 | 1.0861 | 72 | 822.7500 | 2.8996 | 0.5417 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | 11 | 4 | 226 | 108.0000 | 1.0761 | 73 | 817.3750 | 2.8383 | 0.5479 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | 11 | 3 | 257 | 164.3750 | 1.1475 | 85 | 497.8750 | 1.8453 | 0.4824 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | 11 | 7 | 246 | 89.2500 | 1.0799 | 83 | 497.6250 | 1.8604 | 0.4819 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | 11 | 6 | 245 | 85.6250 | 1.0671 | 81 | 464.6250 | 1.7379 | 0.5185 |
| True | chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time | 11 | 1 | 2094 | 432.5000 | 1.0315 | 577 | 427.8750 | 1.0654 | 0.4835 |
| True | chart_ict_displacement_bos_lb50_us_late_hold5m_time | 0 | 1 | 351 | 293.8750 | 1.1418 | 73 | 211.6250 | 2.0053 | 0.5616 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | 0 | 2 | 253 | 149.3750 | 1.0871 | 42 | 167.5000 | 2.2454 | 0.6190 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | 0 | 3 | 245 | 142.1250 | 1.0844 | 42 | 167.5000 | 2.2454 | 0.6190 |
| True | chart_ict_displacement_bos_lb50_us_late_hold3m_time | 0 | 4 | 379 | 82.1250 | 1.0474 | 83 | 155.3750 | 1.6563 | 0.4699 |
| True | chart_ict_displacement_bos_lb50_us_late_hold3m_time | 14 | 3 | 396 | 496.7500 | 1.2138 | 101 | 150.3750 | 1.2482 | 0.5248 |
| True | chart_ict_displacement_bos_lb50_us_late_hold5m_time | 14 | 1 | 367 | 837.8750 | 1.3424 | 88 | 147.2500 | 1.2019 | 0.5114 |
| True | chart_ict_displacement_bos_lb50_us_late_hold2m_time | 14 | 2 | 420 | 506.2500 | 1.2421 | 107 | 102.8750 | 1.1877 | 0.5701 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold3m_time | 14 | 9 | 275 | 285.6250 | 1.1554 | 69 | 94.6250 | 1.2204 | 0.5072 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | 14 | 6 | 291 | 373.8750 | 1.2321 | 73 | 92.8750 | 1.2305 | 0.5890 |
| True | chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | 10 | 2 | 463 | 65.8750 | 1.0520 | 160 | 85.0000 | 1.1295 | 0.5188 |
| True | chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_time | 8 | 1 | 422 | 226.2500 | 1.1650 | 86 | 82.7500 | 1.4416 | 0.4767 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | 14 | 4 | 297 | 429.8750 | 1.2678 | 79 | 71.6250 | 1.1688 | 0.5443 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | 15 | 6 | 310 | 254.2500 | 1.1387 | 93 | 67.1250 | 1.1122 | 0.5376 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | 14 | 8 | 280 | 312.7500 | 1.1720 | 75 | 62.8750 | 1.1364 | 0.4667 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | 15 | 5 | 298 | 293.2500 | 1.1646 | 90 | 47.2500 | 1.0798 | 0.5444 |
| True | chart_ict_displacement_bos_lb50_us_late_hold2m_time | 15 | 2 | 431 | 533.6250 | 1.2391 | 129 | 20.8750 | 1.0255 | 0.4961 |
| True | chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | 8 | 2 | 450 | 49.7500 | 1.0398 | 95 | 16.1250 | 1.0991 | 0.4737 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | 15 | 12 | 293 | 129.6250 | 1.0633 | 83 | 4.8750 | 1.0082 | 0.5181 |

## Full-Sample Sanity Check

| candidate | family | session | holding_minutes | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 10535 | -2471.1250 | 0.9672 | 0.4880 | 3615.0000 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_time | displacement_bos | us_late | 5 | time | 1726 | 680.5000 | 1.0647 | 0.4670 | 708.6250 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | sweep_at_pd_poi | us_late | 3 | time | 2588 | -1481.7500 | 0.8609 | 0.4710 | 2105.0000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 1400 | 93.7500 | 1.0142 | 0.4557 | 514.3750 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 1214 | 178.2500 | 1.0212 | 0.4687 | 672.5000 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 2363 | -930.3750 | 0.9238 | 0.4799 | 1578.3750 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 1354 | 66.5000 | 1.0102 | 0.4594 | 485.8750 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 1173 | 226.3750 | 1.0277 | 0.4697 | 682.5000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_sl12_tp24 | pd_displacement_continuation | us_late | 5 | sl12_tp24 | 1290 | -777.2500 | 0.8898 | 0.3984 | 983.5000 |
| chart_ict_displacement_bos_lb50_us_late_hold2m_sl12_tp24 | displacement_bos | us_late | 2 | sl12_tp24 | 1993 | -909.6250 | 0.8805 | 0.4235 | 994.2500 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_sl12_tp24 | pd_displacement_continuation | us_late | 5 | sl12_tp24 | 1247 | -775.3750 | 0.8868 | 0.3970 | 946.1250 |
| chart_ict_sweep_pd_lb20_pd100_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 1689 | -1053.8750 | 0.8907 | 0.4879 | 1514.8750 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_sl12_tp24 | sweep_at_pd_poi | us_late | 5 | sl12_tp24 | 2468 | -1734.0000 | 0.8392 | 0.4360 | 1848.7500 |
| chart_ict_sweep_pd_lb20_pd100_us_late_hold5m_sl12_tp24 | sweep_at_pd_poi | us_late | 5 | sl12_tp24 | 1798 | -1517.2500 | 0.8206 | 0.4333 | 1553.8750 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 1319 | 67.3750 | 1.0093 | 0.4617 | 629.2500 |
| chart_ict_sweep_pd_lb50_pd50_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 13090 | -4905.0000 | 0.9474 | 0.4866 | 5850.0000 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_sl12_tp24 | displacement_bos | us_late | 5 | sl12_tp24 | 1828 | -471.2500 | 0.9483 | 0.4092 | 875.8750 |
| chart_ict_displacement_bos_lb50_us_late_hold3m_sl12_tp24 | displacement_bos | us_late | 3 | sl12_tp24 | 1911 | -959.6250 | 0.8849 | 0.4129 | 1075.5000 |
| chart_ict_displacement_bos_lb50_us_late_hold2m_time | displacement_bos | us_late | 2 | time | 1992 | 241.7500 | 1.0287 | 0.4568 | 661.7500 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 1274 | 104.5000 | 1.0147 | 0.4655 | 603.6250 |

## Interpretation

- Treat the result as a feature validation pass, not a live-trading approval. The strongest candidates still need roll-aware execution checks and paper-trading validation.
- Any result led by very short holding periods is sensitive to slippage assumptions. Re-run with wider costs before promotion.
- Sweep/MSS and CHoCH candidates with sparse selections are useful as filters even when they are weaker standalone entry systems.
