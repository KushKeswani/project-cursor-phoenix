# Balanced $50k survival — CL 0 / MGC 3 / MNQ 1 / YM 1 Portfolio Backtest

## Profile

- Data dir: `C:\Users\Administrator\AI\project-cursor-phoenix\Data-DataBento`
- Contracts: CL 0, MGC 3, MNQ 1, YM 1
- Full window: 2020-01-01 to 2026-12-31
- OOS window: 2020-01-01 to 2026-04-29
- Execution model: zero-slippage stop-trigger baseline
- EOD trailing DD (MC): $5,000
- DLL (MC): $3,000
- Monte Carlo eval length: 60 trading days
- Note: 50k survival — no CL. CL 0 / MGC 3 / MNQ 1 / YM 1. Re-run MC with --eod-dd / --dll.

## Combined Portfolio

| Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Trade Sharpe | Daily Sharpe | Best Month | Worst Month | Positive Months |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $1,119,692.97 | $14,929.24 | $3,378.00 | 7596 | 47.24% | 6.37 | $147.41 | 5.96 | 12.98 | $41,744.50 | $-274.00 | 98.7% |
| OOS | $1,119,692.97 | $14,929.24 | $3,378.00 | 7596 | 47.24% | 6.37 | $147.41 | 5.96 | 12.98 | $41,744.50 | $-274.00 | 98.7% |

## goals.md §3 — Drawdown, streaks, tails

| Period | Max DD $ | Max DD % | Max DD dur (d) | Worst day | Worst trade | Max loss streak (trades) | Max loss streak (days) | Median month |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | $3,378.00 | 0.53% | 19 | $-3,074.00 | $-2,635.00 | 8 | 7 | $13,874.02 |
| OOS | $3,378.00 | 0.53% | 19 | $-3,074.00 | $-2,635.00 | 8 | 7 | $13,874.02 |

## Monte Carlo Risk

| Period | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 3.48% | $11,504 | $12,898 | $14,484 | $16,094 | $17,702 | $14,394 | 97.9% |
| OOS | 3.48% | $11,504 | $12,898 | $14,484 | $16,094 | $17,702 | $14,394 | 97.9% |

## Instrument Breakdown

| Period | Instrument | Contracts | Trades | WR | PF | Total PnL | Expectancy | Trade Sharpe | Daily Sharpe | Max DD | Worst trade | Mx L streak | Best Month | Worst Month | Pos mo % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | CL | 0 | 1760 | 0.00% | 0.00 | $0.00 | $0.00 | 0.00 | 0.00 | $0.00 | $0.00 | 0 | $0.00 | $0.00 | 0.0% |
| FULL | MGC | 3 | 1252 | 65.50% | 5.41 | $234,564.97 | $187.35 | 6.50 | 6.50 | $2,430.00 | $-2,430.00 | 6 | $21,405.31 | $566.57 | 100.0% |
| FULL | MNQ | 1 | 2252 | 50.98% | 3.06 | $118,958.00 | $52.82 | 5.52 | 6.84 | $1,737.50 | $-1,657.50 | 8 | $6,328.00 | $-343.00 | 97.3% |
| FULL | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |
| OOS | CL | 0 | 1760 | 0.00% | 0.00 | $0.00 | $0.00 | 0.00 | 0.00 | $0.00 | $0.00 | 0 | $0.00 | $0.00 | 0.0% |
| OOS | MGC | 3 | 1252 | 65.50% | 5.41 | $234,564.97 | $187.35 | 6.50 | 6.50 | $2,430.00 | $-2,430.00 | 6 | $21,405.31 | $566.57 | 100.0% |
| OOS | MNQ | 1 | 2252 | 50.98% | 3.06 | $118,958.00 | $52.82 | 5.52 | 6.84 | $1,737.50 | $-1,657.50 | 8 | $6,328.00 | $-343.00 | 97.3% |
| OOS | YM | 1 | 2332 | 69.47% | 8.85 | $766,170.00 | $328.55 | 9.37 | 12.02 | $3,310.00 | $-2,635.00 | 6 | $32,875.00 | $450.00 | 100.0% |

## Visuals

- Equity curve: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_50k_survival_combined_equity_curve.png`
- Monthly PnL: `C:\Users\Administrator\AI\project-cursor-phoenix\reports\visuals\portfolio_risk_profiles\balanced_50k_survival_combined_monthly_pnl.png`