# NQM6 2R Feasibility Diagnostics

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Stop-loss points: 4.0, 8.0, 16.0
Horizons: 30, 60, 120
Sessions: all, europe, us_rth, us_late

## Interpretation

- Setup rows test every eligible minute entry for fixed 2R brackets, before adding strategy-specific filters.
- Feature-bin rows use train-period quantiles for a single feature and report future holdout results for the same bin.
- Pair-bin rows, when enabled, combine only the best train-period single bins before future evaluation.
- A passing feature bin is not a live strategy; it is only evidence that a simple learnable 2R edge may exist.

Setups evaluated: 72
Feature bins evaluated: 360
Future feature bins passing 60%/2R feasibility gate: 0

## Passed Feature Bins

_No rows._

## Best Base Setups

| direction | stop_loss_points | take_profit_points | horizon_minutes | session | events | win_rate | net_points | profit_factor | target_exit_share | stop_exit_share | timeout_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1 | 16.0000 | 32.0000 | 30 | us_late | 8086 | 0.1478 | -77117.0000 | 0.3269 | 0.1475 | 0.8522 | 0.0002 |
| -1 | 16.0000 | 32.0000 | 60 | us_late | 8086 | 0.1477 | -77148.7500 | 0.3267 | 0.1475 | 0.8523 | 0.0001 |
| -1 | 16.0000 | 32.0000 | 120 | us_late | 8086 | 0.1477 | -77148.7500 | 0.3267 | 0.1475 | 0.8523 | 0.0001 |
| 1 | 16.0000 | 32.0000 | 60 | us_late | 8086 | 0.1464 | -77601.7500 | 0.3236 | 0.1463 | 0.8535 | 0.0002 |
| 1 | 16.0000 | 32.0000 | 120 | us_late | 8086 | 0.1464 | -77601.7500 | 0.3236 | 0.1463 | 0.8535 | 0.0002 |
| 1 | 16.0000 | 32.0000 | 30 | us_late | 8086 | 0.1464 | -77657.5000 | 0.3231 | 0.1461 | 0.8535 | 0.0005 |
| -1 | 8.0000 | 16.0000 | 30 | us_late | 8086 | 0.1282 | -44868.7500 | 0.2620 | 0.1281 | 0.8718 | 0.0001 |
| -1 | 8.0000 | 16.0000 | 60 | us_late | 8086 | 0.1282 | -44868.7500 | 0.2620 | 0.1281 | 0.8718 | 0.0001 |
| -1 | 8.0000 | 16.0000 | 120 | us_late | 8086 | 0.1282 | -44868.7500 | 0.2620 | 0.1281 | 0.8718 | 0.0001 |
| -1 | 4.0000 | 8.0000 | 30 | us_late | 8086 | 0.1107 | -26657.7500 | 0.1985 | 0.1107 | 0.8893 | 0.0000 |
| -1 | 4.0000 | 8.0000 | 60 | us_late | 8086 | 0.1107 | -26657.7500 | 0.1985 | 0.1107 | 0.8893 | 0.0000 |
| -1 | 4.0000 | 8.0000 | 120 | us_late | 8086 | 0.1107 | -26657.7500 | 0.1985 | 0.1107 | 0.8893 | 0.0000 |
| 1 | 8.0000 | 16.0000 | 30 | us_late | 8086 | 0.1081 | -48758.7500 | 0.2161 | 0.1081 | 0.8918 | 0.0001 |
| 1 | 8.0000 | 16.0000 | 60 | us_late | 8086 | 0.1081 | -48758.7500 | 0.2161 | 0.1081 | 0.8918 | 0.0001 |
| 1 | 8.0000 | 16.0000 | 120 | us_late | 8086 | 0.1081 | -48758.7500 | 0.2161 | 0.1081 | 0.8918 | 0.0001 |
| 1 | 4.0000 | 8.0000 | 30 | us_late | 8086 | 0.0971 | -27977.7500 | 0.1715 | 0.0971 | 0.9029 | 0.0000 |
| 1 | 4.0000 | 8.0000 | 60 | us_late | 8086 | 0.0971 | -27977.7500 | 0.1715 | 0.0971 | 0.9029 | 0.0000 |
| 1 | 4.0000 | 8.0000 | 120 | us_late | 8086 | 0.0971 | -27977.7500 | 0.1715 | 0.0971 | 0.9029 | 0.0000 |
| -1 | 16.0000 | 32.0000 | 30 | all | 60198 | 0.0929 | -732519.0000 | 0.1931 | 0.0928 | 0.9071 | 0.0000 |
| -1 | 16.0000 | 32.0000 | 60 | all | 60198 | 0.0928 | -732550.7500 | 0.1931 | 0.0928 | 0.9072 | 0.0000 |

## Best Future Feature Bins

| direction | stop_loss_points | horizon_minutes | session | bin_type | feature | feature_2 | op | op_2 | threshold | threshold_2 | train_events | train_win_rate | test_events | test_win_rate | test_net_points | test_profit_factor | oracle_60wr_2r_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -1 | 8.0000 | 30 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1827 | 32 | 0.5938 | 180.0000 | 2.6054 | False |
| -1 | 8.0000 | 60 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1827 | 32 | 0.5938 | 180.0000 | 2.6054 | False |
| -1 | 8.0000 | 120 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1827 | 32 | 0.5938 | 180.0000 | 2.6054 | False |
| -1 | 16.0000 | 30 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1442 | 32 | 0.5312 | 284.0000 | 2.1388 | False |
| -1 | 16.0000 | 60 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1442 | 32 | 0.5312 | 284.0000 | 2.1388 | False |
| -1 | 16.0000 | 120 | us_late | pair | quote_count | realized_vol_30 | <= | <= | 129.0000 | 0.0003 | 104 | 0.1442 | 32 | 0.5312 | 284.0000 | 2.1388 | False |
| -1 | 16.0000 | 30 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.2902 | 56 | 0.5179 | 461.0000 | 2.0270 | False |
| -1 | 16.0000 | 60 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.2902 | 56 | 0.5179 | 461.0000 | 2.0270 | False |
| -1 | 16.0000 | 120 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.2902 | 56 | 0.5179 | 461.0000 | 2.0270 | False |
| -1 | 8.0000 | 30 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.3109 | 56 | 0.5179 | 213.0000 | 1.9147 | False |
| -1 | 8.0000 | 60 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.3109 | 56 | 0.5179 | 213.0000 | 1.9147 | False |
| -1 | 8.0000 | 120 | us_late | pair | range_1m | realized_vol_30 | <= | <= | 6.0000 | 0.0003 | 193 | 0.3109 | 56 | 0.5179 | 213.0000 | 1.9147 | False |
| -1 | 8.0000 | 30 | us_late | single | depth_mean |  | <= |  | 2.2019 | nan | 281 | 0.2100 | 34 | 0.4706 | 90.7500 | 1.5845 | False |
| -1 | 8.0000 | 60 | us_late | single | depth_mean |  | <= |  | 2.2019 | nan | 281 | 0.2100 | 34 | 0.4706 | 90.7500 | 1.5845 | False |
| -1 | 8.0000 | 120 | us_late | single | depth_mean |  | <= |  | 2.2019 | nan | 281 | 0.2100 | 34 | 0.4706 | 90.7500 | 1.5845 | False |
| -1 | 16.0000 | 30 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1495 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 16.0000 | 60 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1495 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 16.0000 | 120 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1495 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 16.0000 | 30 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1454 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 16.0000 | 60 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1454 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 16.0000 | 120 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1454 | 30 | 0.4667 | 173.2500 | 1.6513 | False |
| -1 | 8.0000 | 30 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1204 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 60 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1204 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 120 | us_late | single | spread_mean |  | >= |  | 3.7544 | nan | 1121 | 0.1204 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 30 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1022 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 60 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1022 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 120 | all | single | spread_mean |  | >= |  | 3.7772 | nan | 8216 | 0.1022 | 30 | 0.4667 | 77.2500 | 1.5598 | False |
| -1 | 8.0000 | 30 | all | single | depth_mean |  | <= |  | 2.2850 | nan | 2054 | 0.1086 | 35 | 0.4571 | 82.1250 | 1.5011 | False |
| -1 | 8.0000 | 60 | all | single | depth_mean |  | <= |  | 2.2850 | nan | 2054 | 0.1086 | 35 | 0.4571 | 82.1250 | 1.5011 | False |
| -1 | 8.0000 | 120 | all | single | depth_mean |  | <= |  | 2.2850 | nan | 2054 | 0.1086 | 35 | 0.4571 | 82.1250 | 1.5011 | False |
