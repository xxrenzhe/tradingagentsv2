# NQ 1m ICT Chart Feature Backtest

## Research Read

The screenshots point to three repeatable trade shapes: stair-step continuation after displacement, liquidity sweep/reclaim into a reversal leg, and confirmed entries after premium/discount POIs. `docs/Strategy/ICT2022-2.md` frames those as structure, POI, liquidity sweep, and CHoCH/MSS confirmation. `docs/Strategy/lightglow.md` supplies the measurable SMC parts: internal/swing structure, FVGs, equal highs/lows, order blocks, and premium/discount zones.

## Data

- Source: `data/raw/databento/GLBX-20260428-YXQY7CP9FT.zip`.
- Loaded continuous NQ 1m span: `2021-04-28 00:00:00+00:00` to `2026-04-27 23:59:00+00:00`.
- Rows: `1,769,740`; symbols selected: `21`.
- Costs: `0.625` NQ points round trip.

## Feature Families Tested

- `displacement_bos_lb20`: Strong body/range expansion that closes through a prior range high/low.
- `displacement_bos_lb50`: Strong body/range expansion that closes through a prior range high/low.
- `fvg_displacement_continue`: FVG/imbalance continuation after a strong displacement candle.
- `pd_choch_lb100_ib10`: Confirmation entry: after discount/premium POI, wait for an internal CHoCH break.
- `pd_choch_lb100_ib20`: Confirmation entry: after discount/premium POI, wait for an internal CHoCH break.
- `pd_choch_lb50_ib10`: Confirmation entry: after discount/premium POI, wait for an internal CHoCH break.
- `pd_choch_lb50_ib20`: Confirmation entry: after discount/premium POI, wait for an internal CHoCH break.
- `pd_continue_lb100`: Premium/discount continuation: follow persistent expansion at the extreme.
- `pd_continue_lb50`: Premium/discount continuation: follow persistent expansion at the extreme.
- `pd_displacement_continue_lb100_bos20`: Screenshot-style stair-step continuation: P/D extreme plus displacement BOS.
- `pd_displacement_continue_lb100_bos50`: Screenshot-style stair-step continuation: P/D extreme plus displacement BOS.
- `pd_fade_lb100`: Textbook premium/discount fade: buy discount and sell premium.
- `pd_fade_lb50`: Textbook premium/discount fade: buy discount and sell premium.
- `sweep_mss_lb100_c3`: LQ-EM style entry: sweep first, then require a 3-bar MSS through the sweep candle.
- `sweep_mss_lb20_c3`: LQ-EM style entry: sweep first, then require a 3-bar MSS through the sweep candle.
- `sweep_mss_lb50_c3`: LQ-EM style entry: sweep first, then require a 3-bar MSS through the sweep candle.
- `sweep_pd_lb100_pd100`: Sweep only when it happens inside the matching discount or premium POI.
- `sweep_pd_lb20_pd100`: Sweep only when it happens inside the matching discount or premium POI.
- `sweep_pd_lb50_pd100`: Sweep only when it happens inside the matching discount or premium POI.
- `sweep_pd_lb50_pd50`: Sweep only when it happens inside the matching discount or premium POI.
- `sweep_reclaim_lb100`: Liquidity sweep and reclaim: fade a stop-run above/below the prior range.
- `sweep_reclaim_lb20`: Liquidity sweep and reclaim: fade a stop-run above/below the prior range.
- `sweep_reclaim_lb50`: Liquidity sweep and reclaim: fade a stop-run above/below the prior range.

## Walk-Forward Design

- Train/test: `365` train days, `5` purge days, `90` test days, `90` step days.
- Sessions: `all, ldn_ny, europe, us_rth, us_late`.
- Holds: `2, 3, 5` minutes.
- Exit profiles: `time`.
- Train gate: trades >= `40`, PF >= `1.03`, net > 0.
- Test gate: trades >= `5`, PF >= `1.0`, net > 0.

## Verdict

Best positive aggregate candidate: `chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time` with `427.88` future test net points, `100.00%` positive selected folds, `1.065` average test PF, and `577` test trades.

## Aggregate Ranking

| candidate | family | session | holding_minutes | exit_profile | selected_folds | positive_test_fold_rate | test_trades | test_net_points | test_max_drawdown_points | net_to_drawdown | avg_test_profit_factor | avg_test_win_rate | min_test_net_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 1 | 1.0000 | 577 | 427.8750 | 744.0000 | 0.5751 | 1.0654 | 0.4835 | 427.8750 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_time | displacement_bos | us_late | 5 | time | 9 | 0.3333 | 813 | 410.6250 | 381.8750 | 1.0753 | 1.1829 | 0.4815 | -293.8750 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 5 | 0.6000 | 377 | 312.1250 | 218.7500 | 1.4269 | 1.0657 | 0.4878 | -211.0000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 5 | 0.6000 | 392 | 293.0000 | 237.2500 | 1.2350 | 1.0539 | 0.4755 | -231.6250 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | sweep_at_pd_poi | us_late | 3 | time | 3 | 1.0000 | 399 | 103.6250 | 124.8750 | 0.8298 | 1.0778 | 0.4836 | 2.5000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 8 | 0.2500 | 521 | 91.3750 | 303.6250 | 0.3009 | 1.1685 | 0.4827 | -266.7500 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 8 | 0.2500 | 505 | 57.6250 | 287.6250 | 0.2003 | 1.1671 | 0.4819 | -238.0000 |
| chart_ict_pd_choch_lb50_ib20_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 4 | 0.7500 | 49 | 55.8750 | 36.6250 | 1.5256 | 1.7355 | 0.5267 | -45.5000 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 4 | 0.5000 | 467 | 38.3750 | 302.1250 | 0.1270 | 1.0918 | 0.4863 | -41.7500 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 4 | 0.7500 | 46 | 37.5000 | 58.7500 | 0.6383 | 1.9334 | 0.4511 | -48.3750 |
| chart_ict_pd_choch_lb100_ib20_europe_hold2m_time | pd_choch_confirmation | europe | 2 | time | 6 | 0.3333 | 199 | 27.8750 | 95.8750 | 0.2907 | 1.1890 | 0.4206 | -93.7500 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold5m_time | pd_choch_confirmation | us_late | 5 | time | 4 | 0.7500 | 46 | 27.0000 | 75.7500 | 0.3564 | 2.1906 | 0.5337 | -46.3750 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 4 | 0.2500 | 265 | -3.8750 | 302.1250 | -0.0128 | 0.8950 | 0.4030 | -247.5000 |
| chart_ict_pd_choch_lb50_ib20_us_late_hold5m_time | pd_choch_confirmation | us_late | 5 | time | 3 | 0.6667 | 35 | -18.8750 | 44.8750 | -0.4206 | 1.3694 | 0.5150 | -66.7500 |
| chart_ict_pd_choch_lb100_ib10_us_late_hold2m_time | pd_choch_confirmation | us_late | 2 | time | 3 | 0.6667 | 93 | -20.6250 | 65.0000 | -0.3173 | 1.1099 | 0.4013 | -60.1250 |
| chart_ict_pd_choch_lb100_ib20_europe_hold3m_time | pd_choch_confirmation | europe | 3 | time | 5 | 0.4000 | 159 | -21.1250 | 127.3750 | -0.1658 | 1.5643 | 0.4655 | -114.5000 |
| chart_ict_sweep_reclaim_lb50_us_late_hold5m_time | liquidity_sweep_reclaim | us_late | 5 | time | 3 | 0.3333 | 537 | -21.8750 | 209.5000 | -0.1044 | 1.0054 | 0.4819 | -110.8750 |
| chart_ict_pd_choch_lb100_ib10_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 3 | 0.6667 | 91 | -26.8750 | 102.6250 | -0.2619 | 1.2172 | 0.4193 | -87.7500 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold2m_time | pd_choch_confirmation | us_late | 2 | time | 3 | 0.6667 | 39 | -44.8750 | 98.7500 | -0.4544 | 1.9335 | 0.4571 | -92.6250 |
| chart_ict_pd_choch_lb50_ib10_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 3 | 0.6667 | 102 | -47.5000 | 90.0000 | -0.5278 | 1.0813 | 0.4208 | -100.2500 |
| chart_ict_pd_choch_lb50_ib20_us_late_hold2m_time | pd_choch_confirmation | us_late | 2 | time | 2 | 0.5000 | 22 | -50.7500 | 61.6250 | -0.8235 | 1.0300 | 0.5500 | -78.0000 |
| chart_ict_fvg_displacement_continue_us_late_hold5m_time | fvg_displacement | us_late | 5 | time | 1 | 0.0000 | 327 | -51.3750 | 449.5000 | -0.1143 | 0.9687 | 0.4618 | -51.3750 |
| chart_ict_sweep_mss_lb50_c3_us_late_hold3m_time | sweep_then_mss | us_late | 3 | time | 1 | 0.0000 | 127 | -59.6250 | 170.1250 | -0.3505 | 0.8808 | 0.4331 | -59.6250 |
| chart_ict_pd_choch_lb100_ib20_all_hold2m_time | pd_choch_confirmation | all | 2 | time | 1 | 0.0000 | 132 | -62.7500 | 135.2500 | -0.4640 | 0.8259 | 0.4470 | -62.7500 |
| chart_ict_pd_choch_lb50_ib20_europe_hold3m_time | pd_choch_confirmation | europe | 3 | time | 2 | 0.0000 | 75 | -68.3750 | 122.2500 | -0.5593 | 0.8486 | 0.4473 | -58.8750 |

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
| True | chart_ict_pd_continue_lb50_us_late_hold5m_time | 12 | 14 | 1083 | 210.1250 | 1.0350 | 253 | 407.8750 | 1.2944 | 0.4783 |
| True | chart_ict_displacement_bos_lb50_us_late_hold5m_time | 0 | 3 | 351 | 293.8750 | 1.1418 | 73 | 211.6250 | 2.0053 | 0.5616 |
| True | chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | 0 | 6 | 253 | 149.3750 | 1.0871 | 42 | 167.5000 | 2.2454 | 0.6190 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | 0 | 7 | 245 | 142.1250 | 1.0844 | 42 | 167.5000 | 2.2454 | 0.6190 |
| True | chart_ict_displacement_bos_lb50_us_late_hold3m_time | 0 | 8 | 379 | 82.1250 | 1.0474 | 83 | 155.3750 | 1.6563 | 0.4699 |
| True | chart_ict_pd_choch_lb100_ib20_europe_hold3m_time | 3 | 12 | 106 | 198.2500 | 1.4128 | 36 | 155.0000 | 4.9744 | 0.6667 |
| True | chart_ict_displacement_bos_lb50_us_late_hold3m_time | 14 | 4 | 396 | 496.7500 | 1.2138 | 101 | 150.3750 | 1.2482 | 0.5248 |
| True | chart_ict_pd_continue_lb50_us_late_hold3m_time | 15 | 1 | 1312 | 1127.2500 | 1.1912 | 358 | 147.5000 | 1.0779 | 0.5084 |
| True | chart_ict_displacement_bos_lb50_us_late_hold5m_time | 14 | 1 | 367 | 837.8750 | 1.3424 | 88 | 147.2500 | 1.2019 | 0.5114 |
| True | chart_ict_pd_continue_lb100_us_late_hold3m_time | 2 | 13 | 937 | 314.8750 | 1.0799 | 230 | 134.0000 | 1.1542 | 0.5217 |
| True | chart_ict_pd_choch_lb100_ib20_europe_hold2m_time | 3 | 1 | 109 | 353.6250 | 2.0647 | 36 | 115.2500 | 2.9785 | 0.4444 |
| True | chart_ict_displacement_bos_lb50_us_late_hold2m_time | 14 | 2 | 420 | 506.2500 | 1.2421 | 107 | 102.8750 | 1.1877 | 0.5701 |
| True | chart_ict_sweep_reclaim_lb50_us_late_hold5m_time | 6 | 7 | 713 | 330.1250 | 1.1238 | 187 | 102.1250 | 1.1492 | 0.4920 |
| True | chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | 14 | 8 | 291 | 373.8750 | 1.2321 | 73 | 92.8750 | 1.2305 | 0.5890 |
| True | chart_ict_pd_continue_lb50_us_late_hold2m_time | 15 | 2 | 1437 | 820.6250 | 1.1521 | 388 | 92.2500 | 1.0511 | 0.4639 |
| True | chart_ict_pd_choch_lb100_ib20_europe_hold2m_time | 1 | 6 | 100 | 213.7500 | 1.8309 | 35 | 89.1250 | 1.6517 | 0.5429 |
| True | chart_ict_displacement_bos_lb20_us_late_hold3m_time | 14 | 13 | 551 | 350.8750 | 1.1139 | 145 | 88.6250 | 1.1023 | 0.4828 |
| True | chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | 10 | 2 | 463 | 65.8750 | 1.0520 | 160 | 85.0000 | 1.1295 | 0.5188 |

## Full-Sample Sanity Check

| candidate | family | session | holding_minutes | exit_profile | trades | net_points | profit_factor | win_rate | max_drawdown_points |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| chart_ict_sweep_pd_lb20_pd100_us_rth_hold5m_time | sweep_at_pd_poi | us_rth | 5 | time | 10535 | -2471.1250 | 0.9672 | 0.4880 | 3615.0000 |
| chart_ict_displacement_bos_lb50_us_late_hold5m_time | displacement_bos | us_late | 5 | time | 1726 | 680.5000 | 1.0647 | 0.4670 | 708.6250 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 1354 | 66.5000 | 1.0102 | 0.4594 | 485.8750 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold2m_time | pd_displacement_continuation | us_late | 2 | time | 1400 | 93.7500 | 1.0142 | 0.4557 | 514.3750 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold3m_time | sweep_at_pd_poi | us_late | 3 | time | 2588 | -1481.7500 | 0.8609 | 0.4710 | 2105.0000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 1214 | 178.2500 | 1.0212 | 0.4687 | 672.5000 |
| chart_ict_pd_displacement_continue_lb100_bos50_us_late_hold5m_time | pd_displacement_continuation | us_late | 5 | time | 1173 | 226.3750 | 1.0277 | 0.4697 | 682.5000 |
| chart_ict_pd_choch_lb50_ib20_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 207 | -374.8750 | 0.6700 | 0.4541 | 576.5000 |
| chart_ict_sweep_pd_lb50_pd50_us_late_hold5m_time | sweep_at_pd_poi | us_late | 5 | time | 2363 | -930.3750 | 0.9238 | 0.4799 | 1578.3750 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 187 | -274.8750 | 0.7223 | 0.4278 | 418.3750 |
| chart_ict_pd_choch_lb100_ib20_europe_hold2m_time | pd_choch_confirmation | europe | 2 | time | 664 | -136.0000 | 0.9343 | 0.4262 | 531.0000 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold5m_time | pd_choch_confirmation | us_late | 5 | time | 181 | -450.8750 | 0.6265 | 0.4365 | 526.0000 |
| chart_ict_pd_displacement_continue_lb100_bos20_us_late_hold3m_time | pd_displacement_continuation | us_late | 3 | time | 1319 | 67.3750 | 1.0093 | 0.4617 | 629.2500 |
| chart_ict_pd_choch_lb50_ib20_us_late_hold5m_time | pd_choch_confirmation | us_late | 5 | time | 202 | -519.2500 | 0.6091 | 0.4257 | 649.0000 |
| chart_ict_pd_choch_lb100_ib10_us_late_hold2m_time | pd_choch_confirmation | us_late | 2 | time | 635 | -390.8750 | 0.8061 | 0.4457 | 418.2500 |
| chart_ict_pd_choch_lb100_ib20_europe_hold3m_time | pd_choch_confirmation | europe | 3 | time | 640 | -148.2500 | 0.9364 | 0.4484 | 525.0000 |
| chart_ict_sweep_reclaim_lb50_us_late_hold5m_time | liquidity_sweep_reclaim | us_late | 5 | time | 3818 | -1989.7500 | 0.9046 | 0.4880 | 2868.2500 |
| chart_ict_pd_choch_lb100_ib10_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 614 | -591.0000 | 0.7547 | 0.4495 | 637.3750 |
| chart_ict_pd_choch_lb100_ib20_us_late_hold2m_time | pd_choch_confirmation | us_late | 2 | time | 191 | -363.6250 | 0.5804 | 0.4084 | 437.6250 |
| chart_ict_pd_choch_lb50_ib10_us_late_hold3m_time | pd_choch_confirmation | us_late | 3 | time | 722 | -623.7500 | 0.7785 | 0.4474 | 768.3750 |

## Interpretation

- Treat the result as a feature validation pass, not a live-trading approval. The strongest candidates still need roll-aware execution checks and paper-trading validation.
- Any result led by very short holding periods is sensitive to slippage assumptions. Re-run with wider costs before promotion.
- Sweep/MSS and CHoCH candidates with sparse selections are useful as filters even when they are weaker standalone entry systems.
