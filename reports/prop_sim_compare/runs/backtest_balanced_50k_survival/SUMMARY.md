# Prop firm profit farming report

**Firm / run label:** compare_backtest_Balanced_50k_survival

Generated (UTC): `2026-04-30T03:41:58.280788+00:00`

## Run configuration

```json
{
  "firm_name": "compare_backtest_Balanced_50k_survival",
  "firm_name_slug": "compare_backtest_Balanced_50k_survival",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\backtest\\balanced_50k_survival",
  "scope": "oos",
  "portfolio_tier": "50k-survival",
  "portfolio_key": "Balanced_50k_survival",
  "firm_preset_yaml": "phoenix_topstep_50k",
  "presets_file": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\prop_farming_calculator\\presets.yaml",
  "trade_mult": 1.0,
  "n_sims": 600,
  "seed": 42,
  "accounts": 1,
  "start_frequency": "monthly",
  "challenge_fee_usd": 91.0,
  "challenge_billing": "one_time",
  "activation_fee_usd": 0.0,
  "use_vps": true,
  "vps_monthly_usd": 199.0,
  "audition": {
    "profit_target_usd": 3000.0,
    "trailing_drawdown_usd": 2000.0,
    "eval_window_days": 60,
    "daily_loss_limit_usd": null,
    "consistency_max_best_day_fraction": null
  },
  "funded": {
    "starting_balance_usd": 50000.0,
    "trail_on_profit_usd": 2000.0,
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\backtest_balanced_50k_survival"
}
```

## Warnings

- No CSV (skipped): CL

## Daily pool

- Trading days: **1606**
- Range: **2020-01-02** → **2026-03-25**
- Portfolio contracts key: **Balanced_50k_survival**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 99.2% |
| **Avg trading days to pass** (mean over paths that pass) | 6.1 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 16.3 |
| Avg funded-only trading days to first payout | 10.2 |
| % MC paths with any payout | 97.3% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **99.5%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **6.2**
- Median trading days to pass (conditional on pass): **5.0**
- Rolling windows scored: **1547**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 55.2% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | — (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | — (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | — |
| % simulations with any payout | 0.0% |
| Avg payouts per trader (events) | 0.00 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $0 |
| Avg total expenses incl. VPS (1 acct) | $138 |
| Avg net profit (1 acct) | -$138 |
| Avg ROI | -100.0% |
| % positive ROI | 0.0% |
| Throughput-scaled est. net | -$138 |
| Mean eval days used (all MC outcomes, any end state) | 4.3 |

**Where simulations end (% of paths):**

- Audition: window ended (no pass): 44.7%
- Funded: survived funded segment (no trail hit): 37.3%
- Passed eval, no funded days left in horizon: 17.8%
- Audition: max trailing drawdown: 0.2%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 98.7% |
| Avg trading days to pass audition | 5.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 12.8 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.7 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 8.0 |
| % simulations with any payout | 76.5% |
| Avg payouts per trader (events) | 0.97 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $3,268 |
| Avg total expenses incl. VPS (1 acct) | $290 |
| Avg net profit (1 acct) | $2,978 |
| Avg ROI | 1026.8% |
| % positive ROI | 76.5% |
| Throughput-scaled est. net | $2,978 |
| Mean eval days used (all MC outcomes, any end state) | 5.8 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 52.0%
- Funded: survived funded segment (no trail hit): 46.3%
- Audition: window ended (no pass): 1.2%
- Funded: breach before 1st payout: 0.3%
- Audition: max trailing drawdown: 0.2%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 99.8% |
| Avg trading days to pass audition | 6.0 (mean over MC paths that pass) |
| Avg trading days to first payout | 16.0 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.1 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.8 |
| % simulations with any payout | 98.7% |
| Avg payouts per trader (events) | 1.48 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,158 |
| Avg total expenses incl. VPS (1 acct) | $688 |
| Avg net profit (1 acct) | $5,470 |
| Avg ROI | 795.1% |
| % positive ROI | 98.7% |
| Throughput-scaled est. net | $16,410 |
| Mean eval days used (all MC outcomes, any end state) | 6.0 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 98.7%
- Funded: breach before 1st payout: 1.2%
- Audition: max trailing drawdown: 0.2%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 99.2% |
| Avg trading days to pass audition | 6.1 (mean over MC paths that pass) |
| Avg trading days to first payout | 16.3 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.2 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 13.1 |
| % simulations with any payout | 97.3% |
| Avg payouts per trader (events) | 1.51 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,398 |
| Avg total expenses incl. VPS (1 acct) | $1,285 |
| Avg net profit (1 acct) | $5,113 |
| Avg ROI | 397.9% |
| % positive ROI | 97.2% |
| Throughput-scaled est. net | $30,678 |
| Mean eval days used (all MC outcomes, any end state) | 6.1 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 97.3%
- Funded: breach before 1st payout: 1.8%
- Audition: max trailing drawdown: 0.8%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 99.7% |
| Avg trading days to pass audition | 6.1 (mean over MC paths that pass) |
| Avg trading days to first payout | 16.1 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.0 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.7 |
| % simulations with any payout | 98.5% |
| Avg payouts per trader (events) | 1.46 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,291 |
| Avg total expenses incl. VPS (1 acct) | $2,479 |
| Avg net profit (1 acct) | $3,812 |
| Avg ROI | 153.8% |
| % positive ROI | 94.8% |
| Throughput-scaled est. net | $45,749 |
| Mean eval days used (all MC outcomes, any end state) | 6.1 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 98.5%
- Funded: breach before 1st payout: 1.2%
- Audition: max trailing drawdown: 0.3%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 99.7% |
| Avg trading days to pass audition | 6.0 (mean over MC paths that pass) |
| Avg trading days to first payout | 16.2 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.3 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 13.5 |
| % simulations with any payout | 98.3% |
| Avg payouts per trader (events) | 1.46 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,113 |
| Avg total expenses incl. VPS (1 acct) | $3,673 |
| Avg net profit (1 acct) | $2,440 |
| Avg ROI | 66.4% |
| % positive ROI | 74.5% |
| Throughput-scaled est. net | $43,914 |
| Mean eval days used (all MC outcomes, any end state) | 6.0 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 98.3%
- Funded: breach before 1st payout: 1.3%
- Audition: max trailing drawdown: 0.3%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 99.8% |
| Avg trading days to pass audition | 6.1 (mean over MC paths that pass) |
| Avg trading days to first payout | 16.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.3 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.3 |
| % simulations with any payout | 97.7% |
| Avg payouts per trader (events) | 1.46 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,070 |
| Avg total expenses incl. VPS (1 acct) | $4,867 |
| Avg net profit (1 acct) | $1,203 |
| Avg ROI | 24.7% |
| % positive ROI | 56.0% |
| Throughput-scaled est. net | $28,875 |
| Mean eval days used (all MC outcomes, any end state) | 6.1 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 97.7%
- Funded: breach before 1st payout: 2.2%
- Audition: max trailing drawdown: 0.2%

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
