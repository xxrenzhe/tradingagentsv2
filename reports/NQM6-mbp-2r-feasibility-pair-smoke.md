# NQM6 2R Feasibility Diagnostics

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Stop-loss points: 8.0
Horizons: 30
Sessions: us_late

## Interpretation

- Setup rows test every eligible minute entry for fixed 2R brackets, before adding strategy-specific filters.
- Feature-bin rows use train-period quantiles for a single feature and report future holdout results for the same bin.
- Pair-bin rows, when enabled, combine only the best train-period single bins before future evaluation.
- A passing feature bin is not a live strategy; it is only evidence that a simple learnable 2R edge may exist.

Setups evaluated: 2
Feature bins evaluated: 20
Future feature bins passing 60%/2R feasibility gate: 0

## Passed Feature Bins

_No rows._

## Best Base Setups

| direction | stop_loss_points | take_profit_points | horizon_minutes | session | events | win_rate | net_points | profit_factor | target_exit_share | stop_exit_share | timeout_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1 | 8.0000 | 16.0000 | 30 | us_late | 8086 | 0.1282 | -44868.7500 | 0.2620 | 0.1281 | 0.8718 | 0.0001 |
| 1 | 8.0000 | 16.0000 | 30 | us_late | 8086 | 0.1081 | -48758.7500 | 0.2161 | 0.1081 | 0.8918 | 0.0001 |

## Best Future Feature Bins

| direction | stop_loss_points | horizon_minutes | session | bin_type | feature | feature_2 | op | op_2 | threshold | threshold_2 | train_events | train_win_rate | test_events | test_win_rate | test_net_points | test_profit_factor | oracle_60wr_2r_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1 | 8.0000 | 30 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0002 | 77 | 0.1688 | 25 | 0.5200 | 96.3750 | 1.9312 | False |
| -1 | 8.0000 | 30 | us_late | pair | quote_count | realized_vol_15 | <= | <= | 129.0000 | 0.0002 | 58 | 0.1724 | 29 | 0.5172 | 109.8750 | 1.9099 | False |
| -1 | 8.0000 | 30 | us_late | single | depth_mean |  | <= |  | 2.2019 | nan | 281 | 0.2100 | 34 | 0.4706 | 90.7500 | 1.5845 | False |
| -1 | 8.0000 | 30 | us_late | single | spread_mean |  | >= |  | 8.2361 | nan | 281 | 0.0996 | 17 | 0.4706 | 45.3750 | 1.5845 | False |
| -1 | 8.0000 | 30 | us_late | single | range_1m |  | <= |  | 6.0000 | nan | 287 | 0.3415 | 103 | 0.4369 | 191.6250 | 1.3831 | False |
| -1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_15 | <= | <= | 6.0000 | 0.0002 | 162 | 0.3272 | 51 | 0.4314 | 88.1250 | 1.3523 | False |
| -1 | 8.0000 | 30 | us_late | single | quote_count |  | <= |  | 129.0000 | nan | 282 | 0.2695 | 93 | 0.4301 | 157.8750 | 1.3454 | False |
| -1 | 8.0000 | 30 | us_late | pair | range_1m | quote_count | <= | <= | 6.0000 | 129.0000 | 157 | 0.2803 | 70 | 0.4286 | 116.2500 | 1.3370 | False |
| -1 | 8.0000 | 30 | us_late | single | spread_mean |  | >= |  | 2.8765 | nan | 1541 | 0.1311 | 35 | 0.4000 | 34.1250 | 1.1884 | False |
| -1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0002 | 171 | 0.3333 | 42 | 0.3810 | 21.7500 | 1.0970 | False |
| 1 | 8.0000 | 30 | us_late | single | spread_mean |  | >= |  | 8.2361 | nan | 281 | 0.1139 | 17 | 0.2941 | -26.6250 | 0.7428 | False |
| 1 | 8.0000 | 30 | us_late | single | range_1m |  | <= |  | 6.0000 | nan | 287 | 0.2718 | 103 | 0.2621 | -240.3750 | 0.6333 | False |
| 1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0002 | 171 | 0.2807 | 42 | 0.2619 | -98.2500 | 0.6325 | False |
| 1 | 8.0000 | 30 | us_late | single | quote_count |  | <= |  | 129.0000 | nan | 282 | 0.1702 | 93 | 0.2581 | -226.1250 | 0.6200 | False |
| 1 | 8.0000 | 30 | us_late | single | depth_mean |  | <= |  | 2.2019 | nan | 281 | 0.1246 | 34 | 0.2353 | -101.2500 | 0.5485 | False |
| 1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_15 | <= | <= | 6.0000 | 0.0002 | 162 | 0.3025 | 51 | 0.2157 | -175.8750 | 0.4902 | False |
| 1 | 8.0000 | 30 | us_late | single | spread_mean |  | >= |  | 2.8765 | nan | 1541 | 0.0857 | 35 | 0.2000 | -133.8750 | 0.4457 | False |
| 1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_15 | <= | <= | 6.0000 | 0.0003 | 202 | 0.2772 | 62 | 0.1935 | -246.7500 | 0.4278 | False |
| 1 | 8.0000 | 30 | us_late | single | depth_mean |  | <= |  | 2.9098 | nan | 1541 | 0.1350 | 96 | 0.1458 | -492.0000 | 0.3043 | False |
| 1 | 8.0000 | 30 | us_late | single | body_to_range |  | <= |  | -0.4421 | nan | 274 | 0.1241 | 53 | 0.1321 | -289.1250 | 0.2713 | False |
