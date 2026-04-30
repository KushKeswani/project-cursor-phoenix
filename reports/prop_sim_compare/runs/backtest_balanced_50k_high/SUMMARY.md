# Prop firm profit farming report

**Firm / run label:** compare_backtest_Balanced_50k_high

Generated (UTC): `2026-04-30T03:42:00.411390+00:00`

## Run configuration

```json
{
  "firm_name": "compare_backtest_Balanced_50k_high",
  "firm_name_slug": "compare_backtest_Balanced_50k_high",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\backtest\\balanced_50k_high",
  "scope": "oos",
  "portfolio_tier": "50k-high",
  "portfolio_key": "Balanced_50k_high",
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\backtest_balanced_50k_high"
}
```

## Warnings

- No CSV (skipped): CL

## Daily pool

- Trading days: **1606**
- Range: **2020-01-02** → **2026-03-25**
- Portfolio contracts key: **Balanced_50k_high**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 98.5% |
| **Avg trading days to pass** (mean over paths that pass) | 4.5 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 14.3 |
| Avg funded-only trading days to first payout | 9.8 |
| % MC paths with any payout | 92.8% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **97.5%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **4.5**
- Median trading days to pass (conditional on pass): **4.0**
- Rolling windows scored: **1547**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 76.3% |
| Avg trading days to pass audition | 3.3 (mean over MC paths that pass) |
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
| Mean eval days used (all MC outcomes, any end state) | 3.6 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 62.2%
- Audition: window ended (no pass): 21.2%
- Passed eval, no funded days left in horizon: 13.0%
- Audition: max trailing drawdown: 2.5%
- Funded: breach before 1st payout: 1.2%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 96.8% |
| Avg trading days to pass audition | 4.1 (mean over MC paths that pass) |
| Avg trading days to first payout | 12.1 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 8.3 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 7.8 |
| % simulations with any payout | 79.3% |
| Avg payouts per trader (events) | 0.94 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $4,484 |
| Avg total expenses incl. VPS (1 acct) | $290 |
| Avg net profit (1 acct) | $4,194 |
| Avg ROI | 1446.3% |
| % positive ROI | 79.3% |
| Throughput-scaled est. net | $4,194 |
| Mean eval days used (all MC outcomes, any end state) | 4.2 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 68.7%
- Funded: survived funded segment (no trail hit): 23.8%
- Funded: breach before 1st payout: 4.3%
- Audition: max trailing drawdown: 2.3%
- Audition: window ended (no pass): 0.8%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 97.0% |
| Avg trading days to pass audition | 4.3 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.2 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.1 |
| % simulations with any payout | 93.3% |
| Avg payouts per trader (events) | 1.20 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,020 |
| Avg total expenses incl. VPS (1 acct) | $688 |
| Avg net profit (1 acct) | $6,332 |
| Avg ROI | 920.4% |
| % positive ROI | 93.3% |
| Throughput-scaled est. net | $18,997 |
| Mean eval days used (all MC outcomes, any end state) | 4.3 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 93.3%
- Funded: breach before 1st payout: 3.7%
- Audition: max trailing drawdown: 3.0%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 98.5% |
| Avg trading days to pass audition | 4.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.3 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.8 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 13.0 |
| % simulations with any payout | 92.8% |
| Avg payouts per trader (events) | 1.20 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,576 |
| Avg total expenses incl. VPS (1 acct) | $1,285 |
| Avg net profit (1 acct) | $5,291 |
| Avg ROI | 411.8% |
| % positive ROI | 92.5% |
| Throughput-scaled est. net | $31,747 |
| Mean eval days used (all MC outcomes, any end state) | 4.4 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 92.8%
- Funded: breach before 1st payout: 5.7%
- Audition: max trailing drawdown: 1.5%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 97.7% |
| Avg trading days to pass audition | 4.4 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.0 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.9 |
| % simulations with any payout | 93.3% |
| Avg payouts per trader (events) | 1.20 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,086 |
| Avg total expenses incl. VPS (1 acct) | $2,479 |
| Avg net profit (1 acct) | $4,607 |
| Avg ROI | 185.9% |
| % positive ROI | 89.8% |
| Throughput-scaled est. net | $55,287 |
| Mean eval days used (all MC outcomes, any end state) | 4.4 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 93.3%
- Funded: breach before 1st payout: 4.3%
- Audition: max trailing drawdown: 2.3%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 96.5% |
| Avg trading days to pass audition | 4.4 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.9 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.5 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.9 |
| % simulations with any payout | 91.0% |
| Avg payouts per trader (events) | 1.12 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,367 |
| Avg total expenses incl. VPS (1 acct) | $3,673 |
| Avg net profit (1 acct) | $2,694 |
| Avg ROI | 73.4% |
| % positive ROI | 72.5% |
| Throughput-scaled est. net | $48,495 |
| Mean eval days used (all MC outcomes, any end state) | 4.3 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 91.0%
- Funded: breach before 1st payout: 5.5%
- Audition: max trailing drawdown: 3.5%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 97.5% |
| Avg trading days to pass audition | 4.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.7 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.2 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.9 |
| % simulations with any payout | 93.2% |
| Avg payouts per trader (events) | 1.16 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,576 |
| Avg total expenses incl. VPS (1 acct) | $4,867 |
| Avg net profit (1 acct) | $1,709 |
| Avg ROI | 35.1% |
| % positive ROI | 61.2% |
| Throughput-scaled est. net | $41,013 |
| Mean eval days used (all MC outcomes, any end state) | 4.5 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 93.2%
- Funded: breach before 1st payout: 4.3%
- Audition: max trailing drawdown: 2.5%

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
