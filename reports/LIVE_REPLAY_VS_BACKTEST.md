# Live replay vs traditional backtest

For each Phoenix portfolio preset, **traditional backtest** is a contiguous `run_backtest` on full session bars for the **same `start_date`–`end_date` and contract counts** recorded in that preset’s live replay stats JSON. **Live replay** uses closed trades collected during bar-step replay (deduped engine closes; see `live_backtest_trades.description` in the JSON).

**Daily / monthly path metrics** below aggregate realized PnL by **US/Eastern calendar day** of `exit_ts` (traditional: engine timestamps interpreted as UTC then converted to ET; live: `exit_ts_et`).

**Trade count:** Live replay often reports **more closed trades** than the traditional run because it records round-trips discovered across many `as_of` bar steps (see `unique_signal_fingerprints` vs `n_trades` in the JSON). Per-day realized PnL can still line up on the same number of Eastern trading days when you bucket exits by date.

## Balanced_150k_high

- **Window:** 2025-01-01 → 2025-12-31
- **Data:** `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- **Contracts:** CL 1, MGC 11, MNQ 3, YM 1
- **Live stats JSON:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_150k_high.json`
- **Live trades CSV:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_150k_high_live_replay_trades.csv`

### Portfolio trade statistics

| Metric | Traditional backtest | Live replay | Δ (live − traditional) |
|---|---:|---:|---|
| Closed trades | 1347 | 2373 | 1026 |
| Win rate | 63.55% | 62.45% | -1.10 pp |
| Profit factor | 4.7373 | 2.8931 | -1.84 |
| Expectancy / trade | $371.39 | $357.57 | -13.82 |
| Trade Sharpe (rf=0) | 6.0249 | 4.5484 | -1.48 |
| Total PnL | $500,259.14 | $848,503.00 | +348,243.86 |
| Gross profit | $634,114.85 | $1,296,723.00 | +662,608.15 |
| Gross loss | $133,855.71 | $448,220.00 | +314,364.29 |

### Daily path (Eastern exit date)

| Metric | Traditional | Live replay | Δ |
|---|---:|---:|---|
| Trading days with PnL | 257 | 258 | 1 |
| Max drawdown (daily cum PnL) | $3,686.00 | $12,725.50 | +9,039.50 |
| Avg monthly PnL | $41,688.26 | $70,708.58 | +29,020.32 |
| Daily Sharpe (rf=0) | 13.4191 | 10.9619 | -2.46 |

### Replay run metadata (live JSON only)

| Field | Value |
|---|---|
| Timeline points | 45717 |
| Steps executed | 45717 |
| Steps with any hit | 2970 |
| Total hit events | 3311 |
| Unique signal fingerprints | 1352 |
| Wall seconds (replay) | 1548.169 |
| Step mode | bar |
| Sim step seconds | 30 |
| Entry fill mode | touch |

## Balanced_150k_survival

- **Window:** 2025-01-01 → 2025-12-31
- **Data:** `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- **Contracts:** CL 1, MGC 7, MNQ 2, YM 1
- **Live stats JSON:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_150k_survival.json`
- **Live trades CSV:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_150k_survival_live_replay_trades.csv`

### Portfolio trade statistics

| Metric | Traditional backtest | Live replay | Δ (live − traditional) |
|---|---:|---:|---|
| Closed trades | 1347 | 2373 | 1026 |
| Win rate | 63.55% | 62.45% | -1.10 pp |
| Profit factor | 4.7297 | 2.8416 | -1.89 |
| Expectancy / trade | $291.39 | $292.76 | +1.37 |
| Trade Sharpe (rf=0) | 6.5888 | 4.5756 | -2.01 |
| Total PnL | $392,496.95 | $694,708.00 | +302,211.05 |
| Gross profit | $497,731.54 | $1,071,942.00 | +574,210.46 |
| Gross loss | $105,234.59 | $377,234.00 | +271,999.41 |

### Daily path (Eastern exit date)

| Metric | Traditional | Live replay | Δ |
|---|---:|---:|---|
| Trading days with PnL | 257 | 258 | 1 |
| Max drawdown (daily cum PnL) | $2,402.00 | $10,433.00 | +8,031.00 |
| Avg monthly PnL | $32,708.08 | $57,892.33 | +25,184.25 |
| Daily Sharpe (rf=0) | 14.5154 | 10.8504 | -3.66 |

### Replay run metadata (live JSON only)

| Field | Value |
|---|---|
| Timeline points | 45717 |
| Steps executed | 45717 |
| Steps with any hit | 2970 |
| Total hit events | 3311 |
| Unique signal fingerprints | 1352 |
| Wall seconds (replay) | 1551.363 |
| Step mode | bar |
| Sim step seconds | 30 |
| Entry fill mode | touch |

## Balanced_50k_high

- **Window:** 2025-01-01 → 2025-12-31
- **Data:** `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- **Contracts:** CL 0, MGC 5, MNQ 4, YM 1
- **Live stats JSON:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_50k_high.json`
- **Live trades CSV:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_50k_high_live_replay_trades.csv`

### Portfolio trade statistics

| Metric | Traditional backtest | Live replay | Δ (live − traditional) |
|---|---:|---:|---|
| Closed trades | 983 | 1729 | 746 |
| Win rate | 59.82% | 60.84% | +1.03 pp |
| Profit factor | 5.9362 | 2.8296 | -3.11 |
| Expectancy / trade | $370.29 | $374.50 | +4.21 |
| Trade Sharpe (rf=0) | 7.3962 | 4.6498 | -2.75 |
| Total PnL | $363,997.11 | $647,518.00 | +283,520.89 |
| Gross profit | $437,737.39 | $1,001,434.00 | +563,696.61 |
| Gross loss | $73,740.28 | $353,916.00 | +280,175.72 |

### Daily path (Eastern exit date)

| Metric | Traditional | Live replay | Δ |
|---|---:|---:|---|
| Trading days with PnL | 257 | 258 | 1 |
| Max drawdown (daily cum PnL) | $1,360.00 | $19,887.00 | +18,527.00 |
| Avg monthly PnL | $30,333.09 | $53,959.83 | +23,626.74 |
| Daily Sharpe (rf=0) | 13.8616 | 9.1562 | -4.71 |

### Replay run metadata (live JSON only)

| Field | Value |
|---|---|
| Timeline points | 41113 |
| Steps executed | 41113 |
| Steps with any hit | 1356 |
| Total hit events | 1576 |
| Unique signal fingerprints | 987 |
| Wall seconds (replay) | 1056.23 |
| Step mode | bar |
| Sim step seconds | 30 |
| Entry fill mode | touch |

## Balanced_50k_survival

- **Window:** 2025-01-01 → 2025-12-31
- **Data:** `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- **Contracts:** CL 0, MGC 3, MNQ 1, YM 1
- **Live stats JSON:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_50k_survival.json`
- **Live trades CSV:** `C:\Users\Administrator\AI\project-cursor-phoenix\reports\live_replay_by_profile\Balanced_50k_survival_live_replay_trades.csv`

### Portfolio trade statistics

| Metric | Traditional backtest | Live replay | Δ (live − traditional) |
|---|---:|---:|---|
| Closed trades | 983 | 1729 | 746 |
| Win rate | 59.82% | 60.84% | +1.03 pp |
| Profit factor | 7.1480 | 3.1197 | -4.03 |
| Expectancy / trade | $243.63 | $257.38 | +13.75 |
| Trade Sharpe (rf=0) | 7.8955 | 4.5293 | -3.37 |
| Total PnL | $239,484.77 | $445,003.00 | +205,518.23 |
| Gross profit | $278,438.23 | $654,941.00 | +376,502.77 |
| Gross loss | $38,953.47 | $209,938.00 | +170,984.53 |

### Daily path (Eastern exit date)

| Metric | Traditional | Live replay | Δ |
|---|---:|---:|---|
| Trading days with PnL | 257 | 258 | 1 |
| Max drawdown (daily cum PnL) | $918.00 | $12,491.00 | +11,573.00 |
| Avg monthly PnL | $19,957.06 | $37,083.58 | +17,126.52 |
| Daily Sharpe (rf=0) | 16.0062 | 9.1664 | -6.84 |

### Replay run metadata (live JSON only)

| Field | Value |
|---|---|
| Timeline points | 41113 |
| Steps executed | 41113 |
| Steps with any hit | 1356 |
| Total hit events | 1576 |
| Unique signal fingerprints | 987 |
| Wall seconds (replay) | 995.48 |
| Step mode | bar |
| Sim step seconds | 30 |
| Entry fill mode | touch |

---

*Generated by `scripts/generate_live_replay_vs_backtest_report.py`.*
