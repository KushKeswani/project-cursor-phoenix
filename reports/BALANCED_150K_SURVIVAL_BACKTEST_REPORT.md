# Balanced $150k survival — CL 1 / MGC 7 / MNQ 2 / YM 1 Portfolio Backtest

## Profile

- Data dir: `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- Contracts: CL 1, MGC 7, MNQ 2, YM 1
- Full window: 2020-01-01 to 2026-12-31
- OOS window: 2020-01-01 to 2026-04-29
- Execution model: zero-slippage stop-trigger baseline
- EOD trailing DD (MC): $5,000
- DLL (MC): $3,000
- Monte Carlo eval length: 60 trading days
- Note: 150k survival — CL 1 / MGC 7 / MNQ 2 / YM 1 (~0.64× full Balanced). Typical MC band: EOD $5k / DLL $3k.

## Combined Portfolio

| Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Trade Sharpe | Daily Sharpe | Best Month | Worst Month | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $1,918,214.27 | $25,576.19 | $5,250.00 | 7596 | 64.57% | 4.62 | $252.53 | 6.40 | 12.87 | $72,011.72 | $-548.00 | 98.7% |
| OOS | $1,918,214.27 | $25,576.19 | $5,250.00 | 7596 | 64.57% | 4.62 | $252.53 | 6.40 | 12.87 | $72,011.72 | $-548.00 | 98.7% |

## goals.md §3 — Drawdown, streaks, tails

| Period | Max DD $ | Max DD % | Max DD dur (d) | Worst day | Worst trade | Max loss streak (trades) | Max loss streak (days) | Median month |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $5,250.00 | 0.29% | 19 | $-5,250.00 | $-5,670.00 | 8 | 7 | $24,769.58 |
| OOS | $5,250.00 | 0.29% | 19 | $-5,250.00 | $-5,670.00 | 8 | 7 | $24,769.58 |

## Monte Carlo Risk

| Period | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 13.66% | $15,761 | $21,439 | $24,454 | $27,370 | $30,099 | $23,357 | 94.9% |
| OOS | 13.66% | $15,761 | $21,439 | $24,454 | $27,370 | $30,099 | $23,357 | 94.9% |

## Instrument Breakdown

| Period | Instrument | Contracts | Trades | WR | PF | Total PnL | Expectancy | Trade Sharpe | Daily Sharpe | Max DD | Worst trade | Mx L streak | Best Month | Worst Month | Pos mo % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | CL | 1 | 1760 | 74.83% | 2.90 | $366,810.00 | $208.41 | 6.09 | 7.56 | $5,700.00 | $-4,350.00 | 6 | $25,090.00 | $-2,150.00 | 98.2% |
| FULL | MGC | 7 | 1252 | 65.50% | 5.41 | $547,318.27 | $437.16 | 6.50 | 6.50 | $5,670.00 | $-5,670.00 | 6 | $49,945.72 | $1,322.00 | 100.0% |
| FULL | MNQ | 2 | 2252 | 50.98% | 3.06 | $237,916.00 | $105.65 | 5.52 | 6.84 | $3,475.00 | $-3,315.00 | 8 | $12,656.00 | $-686.00 | 97.3% |
| FULL | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |
| OOS | CL | 1 | 1760 | 74.83% | 2.90 | $366,810.00 | $208.41 | 6.09 | 7.56 | $5,700.00 | $-4,350.00 | 6 | $25,090.00 | $-2,150.00 | 98.2% |
| OOS | MGC | 7 | 1252 | 65.50% | 5.41 | $547,318.27 | $437.16 | 6.50 | 6.50 | $5,670.00 | $-5,670.00 | 6 | $49,945.72 | $1,322.00 | 100.0% |
| OOS | MNQ | 2 | 2252 | 50.98% | 3.06 | $237,916.00 | $105.65 | 5.52 | 6.84 | $3,475.00 | $-3,315.00 | 8 | $12,656.00 | $-686.00 | 97.3% |
| OOS | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |

## Visuals

- Equity curve: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_150k_survival_combined_equity_curve.png`
- Monthly PnL: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_150k_survival_combined_monthly_pnl.png`