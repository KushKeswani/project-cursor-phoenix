# Combined Portfolio Risk Profiles

Low, Med, and High are defined at the combined portfolio level.

## Tier Rules

| Tier | Target Bust % | Contract Logic |
|---|---:|---|
| Low | Current baseline | CL 1, MGC 5, MNQ 5, YM 1 |
| Med | <= 10% | Highest whole-contract portfolio under the target |
| High | <= 20% | Highest whole-contract portfolio under the target |

- Monte Carlo sims: 5000
- Eval length: 60 trading days
- EOD trailing DD: $5,000
- DLL: $3,000

## Tier Summary

| Tier | Scale Label | CL | MGC | MNQ | YM | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Low | 1.00x | 1 | 5 | 5 | 1 | 16.64% | $13,237 | $23,363 | $27,011 | $30,178 | $33,178 | $25,389 | 94.4% |
| Med | 1.00x | 1 | 5 | 5 | 1 | 16.64% | $13,237 | $23,363 | $27,011 | $30,178 | $33,178 | $25,389 | 94.4% |
| High | 1.10x | 1 | 6 | 6 | 1 | 16.26% | $14,978 | $25,492 | $29,528 | $33,031 | $36,457 | $27,861 | 95.0% |

## Backtest Stats

| Tier | Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Sharpe |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Low | Full | $2,118,711.62 | $28,249.49 | $9,006.08 | 7596 | 64.57% | 4.17 | $278.92 | 6.73 |
| Low | OOS | $2,118,711.62 | $28,249.49 | $9,006.08 | 7596 | 64.57% | 4.17 | $278.92 | 6.73 |
| Med | Full | $2,118,711.62 | $28,249.49 | $9,006.08 | 7596 | 64.57% | 4.17 | $278.92 | 6.73 |
| Med | OOS | $2,118,711.62 | $28,249.49 | $9,006.08 | 7596 | 64.57% | 4.17 | $278.92 | 6.73 |
| High | Full | $2,315,857.95 | $30,878.11 | $10,728.30 | 7596 | 64.57% | 4.11 | $304.88 | 6.52 |
| High | OOS | $2,315,857.95 | $30,878.11 | $10,728.30 | 7596 | 64.57% | 4.11 | $304.88 | 6.52 |

## Scale Matrix

| Scale | CL | MGC | MNQ | YM | Bust % | P25 | P50 | P75 | Avg/mo | Reach $7K % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.00x | 1 | 5 | 5 | 1 | 16.64% | $23,363 | $27,011 | $30,178 | $25,389 | 94.4% |
| 1.10x | 1 | 6 | 6 | 1 | 16.26% | $25,492 | $29,528 | $33,031 | $27,861 | 95.0% |
| 1.35x | 1 | 7 | 7 | 1 | 21.92% | $26,388 | $31,644 | $35,738 | $29,244 | 93.4% |
| 1.50x | 2 | 8 | 8 | 2 | 36.32% | $30,143 | $46,768 | $53,301 | $40,699 | 92.0% |