# Prop firm sim: backtest OOS vs live replay

Generated (UTC): `2026-04-30T03:42:14.532457+00:00`

Cohort horizon label for summary table: **6 Months** (match `horizons_summary.csv` row). Backtest OOS exports default to **`2020-01-01` → `2026-04-29`** (override with `--oos-start` / `--oos-end`). Re-run this script **without** `--skip-export-backtest` to refresh `trade_executions` and grow **pool days** when new bar data exists.

| Source | Preset | Pool days | Rolling eval pass % | Horizon | Audition pass % | Avg net $/trader | % positive ROI | Avg ROI % |
|---|---|---:|---:|---|---:|---:|---:|---:|
| backtest | Balanced_150k_high | 1606 | 99.42% | 6 Months | 99.67% | 11,687.89 | 98.83% | 870.28 |
| live_replay | Balanced_150k_high | 258 | 92.46% | 6 Months | 93.00% | 13,675.91 | 68.83% | 1018.31 |
| backtest | Balanced_150k_survival | 1606 | 100.00% | 6 Months | 100.00% | 11,053.25 | 100.00% | 823.03 |
| live_replay | Balanced_150k_survival | 258 | 95.48% | 6 Months | 96.33% | 15,612.39 | 83.33% | 1162.50 |
| backtest | Balanced_50k_high | 1606 | 97.48% | 6 Months | 98.50% | 5,291.11 | 92.50% | 411.76 |
| live_replay | Balanced_50k_high | 258 | 80.40% | 6 Months | 82.33% | 6,011.09 | 44.83% | 467.79 |
| backtest | Balanced_50k_survival | 1606 | 99.48% | 6 Months | 99.17% | 5,113.04 | 97.17% | 397.90 |
| live_replay | Balanced_50k_survival | 258 | 80.90% | 6 Months | 82.83% | 3,830.09 | 53.00% | 298.06 |

**Note:** Backtest rows use the OOS window from `--oos-start` / `--oos-end` (see each run’s `SUMMARY.md`). Live replay rows use whatever calendar span is in `reports/live_replay_by_profile/*_live_replay_trades.csv` — pool days often differ, so compare pass rates and ROI as distributions on each pool, not as identical samples.

## Funded outcomes by horizon

Monte Carlo **single-lifecycle** end states from `funnel_by_horizon.csv` (same runs as above). **Any funded fail** sums the three funded breach buckets. **Insufficient history** means the daily pool was shorter than the eval window (no funded leg). Horizons: **week → month → quarter → 6m → year (12m) → 18m → 24m**.

#### backtest — Balanced_50k_survival

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 0.00% | 0.00% | 0.00% | 0.00% | 37.33% | 0.00% |
| 1 Month | 0.33% | 52.00% | 0.00% | 52.33% | 46.33% | 0.00% |
| 1 Quarter | 1.17% | 98.67% | 0.00% | 99.83% | 0.00% | 0.00% |
| 6 Months | 1.83% | 97.33% | 0.00% | 99.17% | 0.00% | 0.00% |
| 12 Months | 1.17% | 98.50% | 0.00% | 99.67% | 0.00% | 0.00% |
| 18 Months | 1.33% | 98.33% | 0.00% | 99.67% | 0.00% | 0.00% |
| 24 Months | 2.17% | 97.67% | 0.00% | 99.83% | 0.00% | 0.00% |

#### backtest — Balanced_50k_high

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 1.17% | 0.00% | 0.00% | 1.17% | 62.17% | 0.00% |
| 1 Month | 4.33% | 68.67% | 0.00% | 73.00% | 23.83% | 0.00% |
| 1 Quarter | 3.67% | 93.33% | 0.00% | 97.00% | 0.00% | 0.00% |
| 6 Months | 5.67% | 92.83% | 0.00% | 98.50% | 0.00% | 0.00% |
| 12 Months | 4.33% | 93.33% | 0.00% | 97.67% | 0.00% | 0.00% |
| 18 Months | 5.50% | 91.00% | 0.00% | 96.50% | 0.00% | 0.00% |
| 24 Months | 4.33% | 93.17% | 0.00% | 97.50% | 0.00% | 0.00% |

#### backtest — Balanced_150k_survival

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 0.33% | 0.00% | 0.00% | 0.33% | 9.17% | 0.00% |
| 1 Month | 0.33% | 29.00% | 0.00% | 29.33% | 68.83% | 0.00% |
| 1 Quarter | 0.00% | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% |
| 6 Months | 0.00% | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% |
| 12 Months | 0.00% | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% |
| 18 Months | 0.00% | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% |
| 24 Months | 0.00% | 100.00% | 0.00% | 100.00% | 0.00% | 0.00% |

#### backtest — Balanced_150k_high

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 0.67% | 0.00% | 0.00% | 0.67% | 18.17% | 0.00% |
| 1 Month | 0.83% | 43.50% | 0.00% | 44.33% | 53.83% | 0.00% |
| 1 Quarter | 0.17% | 99.00% | 0.00% | 99.17% | 0.00% | 0.00% |
| 6 Months | 0.83% | 98.83% | 0.00% | 99.67% | 0.00% | 0.00% |
| 12 Months | 1.17% | 98.33% | 0.00% | 99.50% | 0.00% | 0.00% |
| 18 Months | 1.17% | 98.17% | 0.00% | 99.33% | 0.00% | 0.00% |
| 24 Months | 0.50% | 99.17% | 0.00% | 99.67% | 0.00% | 0.00% |

#### live_replay — Balanced_50k_survival

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 14.50% | 0.00% | 0.00% | 14.50% | 56.33% | 0.00% |
| 1 Month | 35.50% | 43.17% | 0.00% | 78.67% | 4.67% | 0.00% |
| 1 Quarter | 30.33% | 52.83% | 0.00% | 83.17% | 0.00% | 0.00% |
| 6 Months | 29.83% | 53.00% | 0.00% | 82.83% | 0.00% | 0.00% |
| 12 Months | 26.83% | 53.83% | 0.00% | 80.67% | 0.00% | 0.00% |
| 18 Months | 30.17% | 50.33% | 0.00% | 80.50% | 0.00% | 0.00% |
| 24 Months | 30.50% | 51.33% | 0.00% | 81.83% | 0.00% | 0.00% |

#### live_replay — Balanced_50k_high

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 18.17% | 0.00% | 0.00% | 18.17% | 59.17% | 0.00% |
| 1 Month | 41.67% | 40.17% | 0.00% | 81.83% | 3.33% | 0.00% |
| 1 Quarter | 36.67% | 46.83% | 0.00% | 83.50% | 0.00% | 0.00% |
| 6 Months | 37.50% | 44.83% | 0.00% | 82.33% | 0.00% | 0.00% |
| 12 Months | 32.50% | 44.83% | 0.00% | 77.33% | 0.00% | 0.00% |
| 18 Months | 35.00% | 45.17% | 0.00% | 80.17% | 0.00% | 0.00% |
| 24 Months | 34.67% | 46.17% | 0.00% | 80.83% | 0.00% | 0.00% |

#### live_replay — Balanced_150k_survival

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 2.67% | 0.00% | 0.00% | 2.67% | 47.83% | 0.00% |
| 1 Month | 9.83% | 64.67% | 0.00% | 74.50% | 19.50% | 0.00% |
| 1 Quarter | 11.17% | 84.33% | 0.00% | 95.50% | 0.00% | 0.00% |
| 6 Months | 13.00% | 83.33% | 0.00% | 96.33% | 0.00% | 0.00% |
| 12 Months | 7.67% | 86.50% | 0.00% | 94.17% | 0.00% | 0.00% |
| 18 Months | 9.50% | 85.33% | 0.00% | 94.83% | 0.00% | 0.00% |
| 24 Months | 10.17% | 85.83% | 0.00% | 96.00% | 0.00% | 0.00% |

#### live_replay — Balanced_150k_high

| Horizon | % funded fail: before 1st payout | % after ≥1 payout | % zero-payout edge | **% any funded fail** | % survived funded | % insufficient history (eval) |
|---|---:|---:|---:|---:|---:|---:|
| 1 Week | 6.00% | 0.00% | 0.00% | 6.00% | 50.83% | 0.00% |
| 1 Month | 20.00% | 61.33% | 0.00% | 81.33% | 10.50% | 0.00% |
| 1 Quarter | 23.17% | 70.33% | 0.00% | 93.50% | 0.00% | 0.00% |
| 6 Months | 24.17% | 68.83% | 0.00% | 93.00% | 0.00% | 0.00% |
| 12 Months | 19.83% | 70.67% | 0.00% | 90.50% | 0.00% | 0.00% |
| 18 Months | 23.33% | 69.17% | 0.00% | 92.50% | 0.00% | 0.00% |
| 24 Months | 24.33% | 68.33% | 0.00% | 92.67% | 0.00% | 0.00% |

## Run directories

Exports: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\prop_sim_compare\backtest`, `C:\Users\Administrator\AI\project-cursor-phoenix\reports\prop_sim_compare\live_replay`.
Sim outputs: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\prop_sim_compare\runs/<source>_<preset_slug>/`.
Regenerate everything: `python3 scripts/run_prop_sim_backtest_vs_live_compare.py` (add `--skip-export-live` if live CSVs unchanged).