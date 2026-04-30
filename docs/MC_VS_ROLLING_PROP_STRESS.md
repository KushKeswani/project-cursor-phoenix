# Monte Carlo vs rolling historical stress (prop farming)

`goals.md` §3 and §5 ask you to **not** optimize to Monte Carlo lifecycle outcomes alone: compare them to **rolling historical audition windows** on the real daily PnL pool.

## Where the numbers live

Each `prop_farming_calculator` run writes:

| File | Role |
|------|------|
| `SUMMARY.md` | Human-readable headline; cites rolling pass % when available. |
| `pool_diagnostics.csv` | **`mc_eval_pass_pct`** aliases **`rolling_pass_pct`** — fraction of contiguous eval-length windows on the **actual** daily series that pass audition rules. |
| `horizons_summary.csv` | MC audition pass % by cohort horizon label. |

`scripts/run_prop_sim_backtest_vs_live_compare.py` pulls **`rolling_pass_pct`** from `pool_diagnostics.csv` into **`reports/prop_sim_compare/COMPARE_PROP_SIM.md`** next to MC **`audition_pass_pct`**.

## How to read deltas

- **Rolling historical pass** answers: “If I slid the eval window along realized portfolio dailies, how often would the rule-set pass?”
- **MC audition pass** answers: “If I simulated stochastic paths/cohorts under the same rule-set, how often do synthetic traders pass?”

Large gaps warrant deeper review (`prop_farming_calculator/CALCULATOR_BREAKDOWN.md` §5), path dependence, and pool length (short replay-derived pools are **not** comparable to multi-year backtest pools row-for-row).
