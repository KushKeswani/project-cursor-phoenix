# Prop firm profit farming report

**Firm / run label:** compare_live_replay_Balanced_150k_survival

Generated (UTC): `2026-04-30T03:42:11.851400+00:00`

## Run configuration

```json
{
  "firm_name": "compare_live_replay_Balanced_150k_survival",
  "firm_name_slug": "compare_live_replay_Balanced_150k_survival",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\live_replay\\balanced_150k_survival",
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\live_replay_balanced_150k_survival"
}
```

## Daily pool

- Trading days: **258**
- Range: **2025-01-02** → **2025-12-31**
- Portfolio contracts key: **Balanced_150k_survival**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 96.3% |
| **Avg trading days to pass** (mean over paths that pass) | 4.5 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 14.5 |
| Avg funded-only trading days to first payout | 9.8 |
| % MC paths with any payout | 83.3% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **95.5%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **4.6**
- Median trading days to pass (conditional on pass): **4.0**
- Rolling windows scored: **199**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 66.0% |
| Avg trading days to pass audition | 3.3 (mean over MC paths that pass) |
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
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 47.8%
- Audition: window ended (no pass): 27.7%
- Passed eval, no funded days left in horizon: 15.5%
- Audition: max trailing drawdown: 6.3%
- Funded: breach before 1st payout: 2.7%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 94.0% |
| Avg trading days to pass audition | 4.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 12.2 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 7.9 |
| % simulations with any payout | 72.5% |
| Avg payouts per trader (events) | 0.78 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $10,420 |
| Avg total expenses incl. VPS (1 acct) | $348 |
| Avg net profit (1 acct) | $10,072 |
| Avg ROI | 2894.2% |
| % positive ROI | 72.5% |
| Throughput-scaled est. net | $10,072 |
| Mean eval days used (all MC outcomes, any end state) | 4.5 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 64.7%
- Funded: survived funded segment (no trail hit): 19.5%
- Funded: breach before 1st payout: 9.8%
- Audition: max trailing drawdown: 6.0%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 95.5% |
| Avg trading days to pass audition | 4.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.6 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.8 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 9.0 |
| % simulations with any payout | 84.3% |
| Avg payouts per trader (events) | 1.07 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $16,896 |
| Avg total expenses incl. VPS (1 acct) | $746 |
| Avg net profit (1 acct) | $16,150 |
| Avg ROI | 2164.9% |
| % positive ROI | 84.3% |
| Throughput-scaled est. net | $48,451 |
| Mean eval days used (all MC outcomes, any end state) | 4.4 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 84.3%
- Funded: breach before 1st payout: 11.2%
- Audition: max trailing drawdown: 4.5%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 96.3% |
| Avg trading days to pass audition | 4.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.8 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 8.6 |
| % simulations with any payout | 83.3% |
| Avg payouts per trader (events) | 1.07 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $16,955 |
| Avg total expenses incl. VPS (1 acct) | $1,343 |
| Avg net profit (1 acct) | $15,612 |
| Avg ROI | 1162.5% |
| % positive ROI | 83.3% |
| Throughput-scaled est. net | $93,674 |
| Mean eval days used (all MC outcomes, any end state) | 4.4 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 83.3%
- Funded: breach before 1st payout: 13.0%
- Audition: max trailing drawdown: 3.7%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 94.2% |
| Avg trading days to pass audition | 4.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 9.7 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 8.8 |
| % simulations with any payout | 86.5% |
| Avg payouts per trader (events) | 1.09 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $17,410 |
| Avg total expenses incl. VPS (1 acct) | $2,537 |
| Avg net profit (1 acct) | $14,873 |
| Avg ROI | 586.2% |
| % positive ROI | 86.5% |
| Throughput-scaled est. net | $178,475 |
| Mean eval days used (all MC outcomes, any end state) | 4.5 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 86.5%
- Funded: breach before 1st payout: 7.7%
- Audition: max trailing drawdown: 5.8%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 94.8% |
| Avg trading days to pass audition | 4.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 14.7 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.0 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 8.7 |
| % simulations with any payout | 85.3% |
| Avg payouts per trader (events) | 1.09 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $17,347 |
| Avg total expenses incl. VPS (1 acct) | $3,731 |
| Avg net profit (1 acct) | $13,616 |
| Avg ROI | 364.9% |
| % positive ROI | 85.3% |
| Throughput-scaled est. net | $245,080 |
| Mean eval days used (all MC outcomes, any end state) | 4.3 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 85.3%
- Funded: breach before 1st payout: 9.5%
- Audition: max trailing drawdown: 5.2%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 96.0% |
| Avg trading days to pass audition | 4.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 15.1 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 10.3 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 8.7 |
| % simulations with any payout | 85.8% |
| Avg payouts per trader (events) | 1.12 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $18,622 |
| Avg total expenses incl. VPS (1 acct) | $4,925 |
| Avg net profit (1 acct) | $13,697 |
| Avg ROI | 278.1% |
| % positive ROI | 85.7% |
| Throughput-scaled est. net | $328,737 |
| Mean eval days used (all MC outcomes, any end state) | 4.5 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 85.8%
- Funded: breach before 1st payout: 10.2%
- Audition: max trailing drawdown: 4.0%

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
