# Balanced $150k high — CL 1 / MGC 11 / MNQ 3 / YM 1 Portfolio Backtest

## Profile

- Data dir: `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- Contracts: CL 1, MGC 11, MNQ 3, YM 1
- Full window: 2020-01-01 to 2026-12-31
- OOS window: 2020-01-01 to 2026-04-29
- Execution model: zero-slippage stop-trigger baseline
- EOD trailing DD (MC): $5,000
- DLL (MC): $3,000
- Monte Carlo eval length: 60 trading days
- Note: 150k high — CL 1 / MGC 11 / MNQ 3 / YM 1. EOD $5k / DLL $3k MC band in past sweeps.

## Combined Portfolio

| Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Trade Sharpe | Daily Sharpe | Best Month | Worst Month | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $2,349,925.57 | $31,332.34 | $8,370.00 | 7596 | 64.57% | 4.57 | $309.36 | 5.78 | 11.74 | $103,610.13 | $-822.00 | 98.7% |
| OOS | $2,349,925.57 | $31,332.34 | $8,370.00 | 7596 | 64.57% | 4.57 | $309.36 | 5.78 | 11.74 | $103,610.13 | $-822.00 | 98.7% |

## goals.md §3 — Drawdown, streaks, tails

| Period | Max DD $ | Max DD % | Max DD dur (d) | Worst day | Worst trade | Max loss streak (trades) | Max loss streak (days) | Median month |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $8,370.00 | 0.39% | 19 | $-8,370.00 | $-8,910.00 | 8 | 7 | $28,932.29 |
| OOS | $8,370.00 | 0.39% | 19 | $-8,370.00 | $-8,910.00 | 8 | 7 | $28,932.29 |

## Monte Carlo Risk

| Period | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 19.34% | $12,394 | $25,062 | $29,601 | $33,520 | $37,246 | $27,691 | 93.5% |
| OOS | 19.34% | $12,394 | $25,062 | $29,601 | $33,520 | $37,246 | $27,691 | 93.5% |

## Instrument Breakdown

| Period | Instrument | Contracts | Trades | WR | PF | Total PnL | Expectancy | Trade Sharpe | Daily Sharpe | Max DD | Worst trade | Mx L streak | Best Month | Worst Month | Pos mo % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | CL | 1 | 1760 | 74.83% | 2.90 | $366,810.00 | $208.41 | 6.09 | 7.56 | $5,700.00 | $-4,350.00 | 6 | $25,090.00 | $-2,150.00 | 98.2% |
| FULL | MGC | 11 | 1252 | 65.50% | 5.41 | $860,071.57 | $686.96 | 6.50 | 6.50 | $8,910.00 | $-8,910.00 | 6 | $78,486.13 | $2,077.42 | 100.0% |
| FULL | MNQ | 3 | 2252 | 50.98% | 3.06 | $356,874.00 | $158.47 | 5.52 | 6.84 | $5,212.50 | $-4,972.50 | 8 | $18,984.00 | $-1,029.00 | 97.3% |
| FULL | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |
| OOS | CL | 1 | 1760 | 74.83% | 2.90 | $366,810.00 | $208.41 | 6.09 | 7.56 | $5,700.00 | $-4,350.00 | 6 | $25,090.00 | $-2,150.00 | 98.2% |
| OOS | MGC | 11 | 1252 | 65.50% | 5.41 | $860,071.57 | $686.96 | 6.50 | 6.50 | $8,910.00 | $-8,910.00 | 6 | $78,486.13 | $2,077.42 | 100.0% |
| OOS | MNQ | 3 | 2252 | 50.98% | 3.06 | $356,874.00 | $158.47 | 5.52 | 6.84 | $5,212.50 | $-4,972.50 | 8 | $18,984.00 | $-1,029.00 | 97.3% |
| OOS | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |

## Visuals

- Equity curve: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_150k_high_combined_equity_curve.png`
- Monthly PnL: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_150k_high_combined_monthly_pnl.png`