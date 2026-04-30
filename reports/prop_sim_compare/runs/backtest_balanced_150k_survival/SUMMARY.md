# Prop firm profit farming report

**Firm / run label:** compare_backtest_Balanced_150k_survival

Generated (UTC): `2026-04-30T03:42:02.663578+00:00`

## Run configuration

```json
{
  "firm_name": "compare_backtest_Balanced_150k_survival",
  "firm_name_slug": "compare_backtest_Balanced_150k_survival",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\backtest\\balanced_150k_survival",
  "scope": "oos",
  "portfolio_tier": "150k-survival",
  "portfolio_key": "Balanced_150k_survival",
  "firm_preset_yaml": "phoenix_topstep_150k",
  "presets_file": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\prop_farming_calculator\\presets.yaml",
  "trade_mult": 1.0,
  "n_sims": 600,
  "seed": 42,
  "accounts": 1,
  "start_frequency": "monthly",
  "challenge_fee_usd": 149.0,
  "challenge_billing": "one_time",
  "activation_fee_usd": 0.0,
  "use_vps": true,
  "vps_monthly_usd": 199.0,
  "audition": {
    "profit_target_usd": 9000.0,
    "trailing_drawdown_usd": 4500.0,
    "eval_window_days": 60,
    "daily_loss_limit_usd": null,
    "consistency_max_best_day_fraction": null
  },
  "funded": {
    "starting_balance_usd": 150000.0,
    "trail_on_profit_usd": 4500.0,
    "min_profit_per_day_usd": 150.0,
    "n_qualifying_days": 5,
    "withdraw_fraction": 0.5,
    "max_gross_payout_per_cycle_usd": null,
    "funded_model": "classic",
    "express_trader_first_full_usd": 10000.0,
    "express_trader_split_after_first": 0.9,
    "profit_target_note_usd": null
  },
  "cohort": {
    "traders": 10,
    "horizon_label": "6 Months",
    "trading_days": 126,
    "seed": 12345
  },
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\backtest_balanced_150k_survival"
}
```

## Daily pool

- Trading days: **1606**
- Range: **2020-01-02** → **2026-03-25**
- Portfolio contracts key: **Balanced_150k_survival**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 100.0% |
| **Avg trading days to pass** (mean over paths that pass) | 9.9 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 19.4 |
| Avg funded-only trading days to first payout | 9.5 |
| % MC paths with any payout | 100.0% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **100.0%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **9.8**
- Median trading days to pass (conditional on pass): **9.0**
- Rolling windows scored: **1547**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 16.2% |
| Avg trading days to pass audition | 4.1 (mean over MC paths that pass) |
| Avg trading days to first payout | — (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | — (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | — |
| % simulations with any payout | 0.0% |
| Avg payouts per trader (events) | 0.00 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $0 |
| Avg total expenses incl. VPS (1 acct) | $196 |
| Avg net profit (1 acct) | -$196 |
| Avg ROI | -100.0% |
| % positive ROI | 0.0% |
| Throughput-scaled est. net | -$196 |
| Mean eval days used (all MC outcomes, any end state) | 4.8 |

**Where simulations end (% of paths):**

- Audition: window ended (no pass): 83.8%
- Funded: survived funded segment (no trail hit): 9.2%
- Passed eval, no funded days left in horizon: 6.7%
- Funded: breach before 1st payout: 0.3%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 98.7% |
| Avg trading days to pass audition | 9.1 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.9 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 6.8 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 7.3 |
| % simulations with any payout | 72.8% |
| Avg payouts per trader (events) | 0.98 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $5,032 |
| Avg total expenses incl. VPS (1 acct) | $348 |
| Avg net profit (1 acct) | $4,684 |
| Avg ROI | 1345.9% |
| % positive ROI | 72.8% |
| Throughput-scaled est. net | $4,684 |
| Mean eval days used (all MC outcomes, any end state) | 9.2 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 68.8%
- Funded: breach after ≥1 payout: 29.0%
- Audition: window ended (no pass): 1.2%
- Passed eval, no funded days left in horizon: 0.5%
- Funded: breach before 1st payout: 0.3%
- Audition: max trailing drawdown: 0.2%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 100.0% |
| Avg trading days to pass audition | 9.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 18.7 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.1 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 11.0 |
| % simulations with any payout | 100.0% |
| Avg payouts per trader (events) | 1.90 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,465 |
| Avg total expenses incl. VPS (1 acct) | $746 |
| Avg net profit (1 acct) | $11,719 |
| Avg ROI | 1570.9% |
| % positive ROI | 100.0% |
| Throughput-scaled est. net | $35,156 |
| Mean eval days used (all MC outcomes, any end state) | 9.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 100.0%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 100.0% |
| Avg trading days to pass audition | 9.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 19.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.5 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.5 |
| % simulations with any payout | 100.0% |
| Avg payouts per trader (events) | 1.91 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,396 |
| Avg total expenses incl. VPS (1 acct) | $1,343 |
| Avg net profit (1 acct) | $11,053 |
| Avg ROI | 823.0% |
| % positive ROI | 100.0% |
| Throughput-scaled est. net | $66,320 |
| Mean eval days used (all MC outcomes, any end state) | 9.9 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 100.0%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 100.0% |
| Avg trading days to pass audition | 9.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 18.6 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.0 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.2 |
| % simulations with any payout | 100.0% |
| Avg payouts per trader (events) | 1.91 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,406 |
| Avg total expenses incl. VPS (1 acct) | $2,537 |
| Avg net profit (1 acct) | $9,869 |
| Avg ROI | 389.0% |
| % positive ROI | 100.0% |
| Throughput-scaled est. net | $118,431 |
| Mean eval days used (all MC outcomes, any end state) | 9.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 100.0%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 100.0% |
| Avg trading days to pass audition | 9.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 19.3 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.7 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.5 |
| % simulations with any payout | 100.0% |
| Avg payouts per trader (events) | 1.90 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,615 |
| Avg total expenses incl. VPS (1 acct) | $3,731 |
| Avg net profit (1 acct) | $8,884 |
| Avg ROI | 238.1% |
| % positive ROI | 99.8% |
| Throughput-scaled est. net | $159,912 |
| Mean eval days used (all MC outcomes, any end state) | 9.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 100.0%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 100.0% |
| Avg trading days to pass audition | 9.7 (mean over MC paths that pass) |
| Avg trading days to first payout | 18.8 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.1 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.6 |
| % simulations with any payout | 100.0% |
| Avg payouts per trader (events) | 1.92 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,150 |
| Avg total expenses incl. VPS (1 acct) | $4,925 |
| Avg net profit (1 acct) | $7,225 |
| Avg ROI | 146.7% |
| % positive ROI | 98.0% |
| Throughput-scaled est. net | $173,392 |
| Mean eval days used (all MC outcomes, any end state) | 9.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 100.0%

## Files in this folder

| File | Description |
|------|-------------|
| `run_meta.json` | Full parameters for reproducibility |
| `horizons_summary.csv` | One row per horizon (main KPIs) |
| `overall_headline.json` | Pass %, avg days to pass & to payout at `--cohort-horizon` (+ rolling pass %) |
| `funnel_by_horizon.csv` | Failure / outcome funnel by horizon |
| `cohort_multi_attempt.csv` | Per-trader multi-attempt simulation |
| `pool_diagnostics.csv` | Historical + rolling eval (contiguous windows) |
| `monthly_pnl.csv` | Loaded series monthly PnL |
| `SUMMARY.md` | This report |
