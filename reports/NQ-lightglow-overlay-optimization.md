# Lightglow Trade Overlay Optimization

## Scope

- Trades source: `.tmp/nq-lightglow-5y-walkforward-trades.csv`.
- Candidates: `lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time, lightglow_premium_discount_reversal_3m_all_hold3m_reverse_time`.
- Extra costs tested: `0.0, 0.25, 0.5, 1.0`.
- Daily caps tested: `0, 40, 80, 120` where `0` means no cap.
- Daily stops tested: `0.0, 200.0, 300.0, 400.0` where `0` means no daily stop.

## Ranked Overlays

| candidate | overlay | trades | net_points | max_drawdown_points | net_to_drawdown | profit_factor | positive_day_rate | worst_day_points | avg_trades_per_day | controlled_score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_capnone_dstopnone | 38836 | 104031.7500 | 2323.5000 | 44.7737 | 1.9172 | 0.3669 | -424.2500 | 39.4675 | 166.9990 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_capnone_dstop400 | 38835 | 104029.6250 | 2323.5000 | 44.7728 | 1.9172 | 0.3669 | -426.3750 | 39.4665 | 166.9958 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_capnone_dstop200 | 38637 | 103904.8750 | 2323.5000 | 44.7191 | 1.9246 | 0.3659 | -426.3750 | 39.2652 | 166.8818 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_capnone_dstop300 | 38816 | 103920.7500 | 2323.5000 | 44.7260 | 1.9170 | 0.3669 | -426.3750 | 39.4472 | 166.8383 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap120_dstopnone | 38810 | 102728.2500 | 2323.5000 | 44.2127 | 1.9062 | 0.3669 | -424.2500 | 39.4411 | 165.0252 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap120_dstop400 | 38809 | 102726.1250 | 2323.5000 | 44.2118 | 1.9062 | 0.3669 | -426.3750 | 39.4400 | 165.0219 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap120_dstop200 | 38611 | 102601.3750 | 2323.5000 | 44.1581 | 1.9136 | 0.3659 | -426.3750 | 39.2388 | 164.9069 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap120_dstop300 | 38790 | 102617.2500 | 2323.5000 | 44.1649 | 1.9060 | 0.3669 | -426.3750 | 39.4207 | 164.8643 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap80_dstopnone | 38477 | 88790.1250 | 2321.6250 | 38.2448 | 1.7897 | 0.3669 | -424.2500 | 39.1026 | 143.9578 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap80_dstop400 | 38476 | 88788.0000 | 2321.6250 | 38.2439 | 1.7897 | 0.3669 | -426.3750 | 39.1016 | 143.9546 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap80_dstop200 | 38278 | 88663.2500 | 2321.6250 | 38.1902 | 1.7960 | 0.3659 | -426.3750 | 38.9004 | 143.8292 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0_cap80_dstop300 | 38457 | 88679.1250 | 2321.6250 | 38.1970 | 1.7894 | 0.3669 | -426.3750 | 39.0823 | 143.7959 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_capnone_dstop200 | 38590 | 94504.7500 | 3050.5000 | 30.9801 | 1.8039 | 0.3120 | -303.1250 | 39.2175 | 140.5427 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_capnone_dstopnone | 38836 | 94322.7500 | 3050.5000 | 30.9204 | 1.7921 | 0.3130 | -440.2500 | 39.4675 | 140.1933 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_capnone_dstop400 | 38835 | 94320.8750 | 3050.5000 | 30.9198 | 1.7921 | 0.3130 | -442.1250 | 39.4665 | 140.1907 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_capnone_dstop300 | 38806 | 94158.5000 | 3050.5000 | 30.8666 | 1.7916 | 0.3130 | -442.1250 | 39.4370 | 139.9697 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap120_dstop200 | 38564 | 93207.7500 | 3050.5000 | 30.5549 | 1.7934 | 0.3120 | -303.1250 | 39.1911 | 138.7151 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap120_dstopnone | 38810 | 93025.7500 | 3050.5000 | 30.4952 | 1.7817 | 0.3130 | -440.2500 | 39.4411 | 138.3669 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap120_dstop400 | 38809 | 93023.8750 | 3050.5000 | 30.4946 | 1.7817 | 0.3130 | -442.1250 | 39.4400 | 138.3643 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap120_dstop300 | 38780 | 92861.5000 | 3050.5000 | 30.4414 | 1.7811 | 0.3130 | -442.1250 | 39.4106 | 138.1433 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_capnone_dstop200 | 38515 | 85020.6250 | 3784.2500 | 22.4670 | 1.6913 | 0.2683 | -272.3750 | 39.1413 | 119.5153 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap80_dstop200 | 38231 | 79352.8750 | 3047.8750 | 26.0355 | 1.6810 | 0.3120 | -303.1250 | 38.8526 | 119.2227 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_capnone_dstopnone | 38836 | 84613.7500 | 3780.1250 | 22.3838 | 1.6771 | 0.2693 | -456.2500 | 39.4675 | 118.9014 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_capnone_dstop400 | 38835 | 84612.1250 | 3780.1250 | 22.3834 | 1.6771 | 0.2693 | -457.8750 | 39.4665 | 118.8992 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap80_dstopnone | 38477 | 79170.8750 | 3047.8750 | 25.9758 | 1.6707 | 0.3130 | -440.2500 | 39.1026 | 118.8880 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap80_dstop400 | 38476 | 79169.0000 | 3047.8750 | 25.9751 | 1.6707 | 0.3130 | -442.1250 | 39.1016 | 118.8853 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_capnone_dstop300 | 38797 | 84457.8750 | 3780.1250 | 22.3426 | 1.6767 | 0.2693 | -457.8750 | 39.4278 | 118.7004 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.25_cap80_dstop300 | 38447 | 79006.6250 | 3047.8750 | 25.9219 | 1.6700 | 0.3130 | -442.1250 | 39.0722 | 118.6630 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_cap120_dstop200 | 38489 | 83730.1250 | 3784.2500 | 22.1259 | 1.6813 | 0.2683 | -272.3750 | 39.1148 | 117.7830 |
| lightglow_premium_discount_reversal_1m_all_hold2m_reverse_time | cost0.5_cap120_dstopnone | 38810 | 83323.2500 | 3780.1250 | 22.0425 | 1.6672 | 0.2693 | -456.2500 | 39.4411 | 117.1703 |
