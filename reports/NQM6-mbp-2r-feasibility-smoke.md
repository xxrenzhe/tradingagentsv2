# NQM6 2R Feasibility Diagnostics

Feature rows: 60,200
Date range: 2026-03-02 23:59:00+00:00 to 2026-05-01 21:00:00+00:00
Stop-loss points: 4.0, 8.0
Horizons: 30
Sessions: europe

## Interpretation

- Setup rows test every eligible minute entry for fixed 2R brackets, before adding strategy-specific filters.
- Feature-bin rows use train-period quantiles for a single feature and report future holdout results for the same bin.
- A passing feature bin is not a live strategy; it is only evidence that a simple learnable 2R edge may exist.

Setups evaluated: 4
Feature bins evaluated: 12
Future feature bins passing 60%/2R feasibility gate: 0

## Passed Feature Bins

_No rows._

## Best Base Setups

| direction | stop_loss_points | take_profit_points | horizon_minutes | session | events | win_rate | net_points | profit_factor | target_exit_share | stop_exit_share | timeout_share |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 8.0000 | 16.0000 | 30 | europe | 17129 | 0.0586 | -123641.6250 | 0.1110 | 0.0586 | 0.9414 | 0.0000 |
| -1 | 8.0000 | 16.0000 | 30 | europe | 17129 | 0.0558 | -124793.6250 | 0.1054 | 0.0558 | 0.9442 | 0.0000 |
| 1 | 4.0000 | 8.0000 | 30 | europe | 17129 | 0.0454 | -69897.6250 | 0.0758 | 0.0454 | 0.9546 | 0.0000 |
| -1 | 4.0000 | 8.0000 | 30 | europe | 17129 | 0.0391 | -71193.6250 | 0.0648 | 0.0391 | 0.9609 | 0.0000 |

## Best Future Feature Bins

| direction | stop_loss_points | horizon_minutes | session | feature | op | threshold | train_events | train_win_rate | test_events | test_win_rate | test_net_points | test_profit_factor | oracle_60wr_2r_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 8.0000 | 30 | europe | range_1m | <= | 62.0000 | 587 | 0.2589 | 21 | 0.3333 | -13.1250 | 0.8913 | False |
| 1 | 4.0000 | 30 | europe | range_1m | <= | 62.0000 | 587 | 0.1567 | 21 | 0.2857 | -25.1250 | 0.6378 | False |
| -1 | 4.0000 | 30 | europe | range_1m | <= | 62.0000 | 587 | 0.1499 | 21 | 0.1905 | -49.1250 | 0.3752 | False |
| 1 | 4.0000 | 30 | europe | range_1m | <= | 113.0000 | 3217 | 0.0988 | 132 | 0.1818 | -322.5000 | 0.3544 | False |
| 1 | 8.0000 | 30 | europe | range_1m | <= | 113.0000 | 3217 | 0.1436 | 132 | 0.1818 | -562.5000 | 0.3961 | False |
| 1 | 4.0000 | 30 | europe | quote_count | <= | 1478.0000 | 3214 | 0.0737 | 889 | 0.0709 | -3355.6250 | 0.1216 | False |
| 1 | 8.0000 | 30 | europe | quote_count | <= | 1478.0000 | 3214 | 0.1189 | 889 | 0.0709 | -6155.6250 | 0.1360 | False |
| -1 | 8.0000 | 30 | europe | range_1m | <= | 62.0000 | 587 | 0.2675 | 21 | 0.0476 | -157.1250 | 0.0891 | False |
| -1 | 4.0000 | 30 | europe | range_1m | <= | 113.0000 | 3217 | 0.0886 | 132 | 0.0455 | -538.5000 | 0.0759 | False |
| -1 | 8.0000 | 30 | europe | range_1m | <= | 113.0000 | 3217 | 0.1430 | 132 | 0.0303 | -1042.5000 | 0.0557 | False |
| -1 | 4.0000 | 30 | europe | body_to_range | >= | 0.1788 | 584 | 0.0702 | 108 | 0.0185 | -475.5000 | 0.0301 | False |
| -1 | 8.0000 | 30 | europe | realized_vol_15 | <= | 0.0001 | 584 | 0.1901 | 1177 | 0.0153 | -9719.6250 | 0.0277 | False |
