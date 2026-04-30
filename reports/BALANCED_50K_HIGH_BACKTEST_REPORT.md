# Balanced $50k high — CL 0 / MGC 5 / MNQ 4 / YM 1 Portfolio Backtest

## Profile

- Data dir: `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- Contracts: CL 0, MGC 5, MNQ 4, YM 1
- Full window: 2020-01-01 to 2026-12-31
- OOS window: 2020-01-01 to 2026-04-29
- Execution model: zero-slippage stop-trigger baseline
- EOD trailing DD (MC): $5,000
- DLL (MC): $3,000
- Monte Carlo eval length: 60 trading days
- Note: 50k high — no CL. CL 0 / MGC 5 / MNQ 4 / YM 1. Re-run MC with your EOD/DLL.

## Combined Portfolio

| Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Trade Sharpe | Daily Sharpe | Best Month | Worst Month | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $1,632,943.62 | $21,772.58 | $6,638.58 | 7596 | 47.24% | 4.91 | $214.97 | 6.07 | 12.28 | $63,217.52 | $-1,096.00 | 98.7% |
| OOS | $1,632,943.62 | $21,772.58 | $6,638.58 | 7596 | 47.24% | 4.91 | $214.97 | 6.07 | 12.28 | $63,217.52 | $-1,096.00 | 98.7% |

## goals.md §3 — Drawdown, streaks, tails

| Period | Max DD $ | Max DD % | Max DD dur (d) | Worst day | Worst trade | Max loss streak (trades) | Max loss streak (days) | Median month |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $6,638.58 | 0.59% | 19 | $-6,638.58 | $-6,630.00 | 8 | 7 | $19,303.79 |
| OOS | $6,638.58 | 0.59% | 19 | $-6,638.58 | $-6,630.00 | 8 | 7 | $19,303.79 |

## Monte Carlo Risk

| Period | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 13.06% | $13,143 | $18,073 | $20,918 | $23,430 | $25,900 | $19,984 | 94.4% |
| OOS | 13.06% | $13,143 | $18,073 | $20,918 | $23,430 | $25,900 | $19,984 | 94.4% |

## Instrument Breakdown

| Period | Instrument | Contracts | Trades | WR | PF | Total PnL | Expectancy | Trade Sharpe | Daily Sharpe | Max DD | Worst trade | Mx L streak | Best Month | Worst Month | Pos mo % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | CL | 0 | 1760 | 0.00% | 0.00 | $0.00 | $0.00 | 0.00 | 0.00 | $0.00 | $0.00 | 0 | $0.00 | $0.00 | 0.0% |
| FULL | MGC | 5 | 1252 | 65.50% | 5.41 | $390,941.62 | $312.25 | 6.50 | 6.50 | $4,050.00 | $-4,050.00 | 6 | $35,675.52 | $944.28 | 100.0% |
| FULL | MNQ | 4 | 2252 | 50.98% | 3.06 | $475,832.00 | $211.29 | 5.52 | 6.84 | $6,950.00 | $-6,630.00 | 8 | $25,312.00 | $-1,372.00 | 97.3% |
| FULL | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |
| OOS | CL | 0 | 1760 | 0.00% | 0.00 | $0.00 | $0.00 | 0.00 | 0.00 | $0.00 | $0.00 | 0 | $0.00 | $0.00 | 0.0% |
| OOS | MGC | 5 | 1252 | 65.50% | 5.41 | $390,941.62 | $312.25 | 6.50 | 6.50 | $4,050.00 | $-4,050.00 | 6 | $35,675.52 | $944.28 | 100.0% |
| OOS | MNQ | 4 | 2252 | 50.98% | 3.06 | $475,832.00 | $211.29 | 5.52 | 6.84 | $6,950.00 | $-6,630.00 | 8 | $25,312.00 | $-1,372.00 | 97.3% |
| OOS | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |

## Visuals

- Equity curve: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_50k_high_combined_equity_curve.png`
- Monthly PnL: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_50k_high_combined_monthly_pnl.png`