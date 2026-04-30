# Prop firm profit farming report

**Firm / run label:** compare_live_replay_Balanced_50k_high

Generated (UTC): `2026-04-30T03:42:09.540646+00:00`

## Run configuration

```json
{
  "firm_name": "compare_live_replay_Balanced_50k_high",
  "firm_name_slug": "compare_live_replay_Balanced_50k_high",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\live_replay\\balanced_50k_high",
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\live_replay_balanced_50k_high"
}
```

## Warnings

- No CSV (skipped): CL

## Daily pool

- Trading days: **258**
- Range: **2025-01-02** → **2025-12-31**
- Portfolio contracts key: **Balanced_50k_high**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 82.3% |
| **Avg trading days to pass** (mean over paths that pass) | 1.8 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 9.2 |
| Avg funded-only trading days to first payout | 7.3 |
| % MC paths with any payout | 44.8% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **80.4%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **1.9**
- Median trading days to pass (conditional on pass): **2.0**
- Rolling windows scored: **199**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 80.2% |
| Avg trading days to pass audition | 1.9 (mean over MC paths that pass) |
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
| Mean eval days used (all MC outcomes, any end state) | 1.9 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 59.2%
- Audition: max trailing drawdown: 19.8%
- Funded: breach before 1st payout: 18.2%
- Passed eval, no funded days left in horizon: 2.8%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 85.2% |
| Avg trading days to pass audition | 1.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.3 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.4 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 6.5 |
| % simulations with any payout | 42.7% |
| Avg payouts per trader (events) | 0.45 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $6,538 |
| Avg total expenses incl. VPS (1 acct) | $290 |
| Avg net profit (1 acct) | $6,248 |
| Avg ROI | 2154.5% |
| % positive ROI | 42.7% |
| Throughput-scaled est. net | $6,248 |
| Mean eval days used (all MC outcomes, any end state) | 1.9 |

**Where simulations end (% of paths):**

- Funded: breach before 1st payout: 41.7%
- Funded: breach after ≥1 payout: 40.2%
- Audition: max trailing drawdown: 14.8%
- Funded: survived funded segment (no trail hit): 3.3%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 83.5% |
| Avg trading days to pass audition | 1.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.1 |
| % simulations with any payout | 46.8% |
| Avg payouts per trader (events) | 0.51 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,398 |
| Avg total expenses incl. VPS (1 acct) | $688 |
| Avg net profit (1 acct) | $6,710 |
| Avg ROI | 975.2% |
| % positive ROI | 46.8% |
| Throughput-scaled est. net | $20,129 |
| Mean eval days used (all MC outcomes, any end state) | 1.9 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 46.8%
- Funded: breach before 1st payout: 36.7%
- Audition: max trailing drawdown: 16.5%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 82.3% |
| Avg trading days to pass audition | 1.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.2 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.3 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 13.0 |
| % simulations with any payout | 44.8% |
| Avg payouts per trader (events) | 0.50 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,296 |
| Avg total expenses incl. VPS (1 acct) | $1,285 |
| Avg net profit (1 acct) | $6,011 |
| Avg ROI | 467.8% |
| % positive ROI | 44.8% |
| Throughput-scaled est. net | $36,067 |
| Mean eval days used (all MC outcomes, any end state) | 1.9 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 44.8%
- Funded: breach before 1st payout: 37.5%
- Audition: max trailing drawdown: 17.7%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 77.3% |
| Avg trading days to pass audition | 2.0 (mean over MC paths that pass) |
| Avg trading days to first payout | 8.8 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 6.8 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 11.1 |
| % simulations with any payout | 44.8% |
| Avg payouts per trader (events) | 0.49 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,132 |
| Avg total expenses incl. VPS (1 acct) | $2,479 |
| Avg net profit (1 acct) | $4,653 |
| Avg ROI | 187.7% |
| % positive ROI | 44.8% |
| Throughput-scaled est. net | $55,839 |
| Mean eval days used (all MC outcomes, any end state) | 2.0 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 44.8%
- Funded: breach before 1st payout: 32.5%
- Audition: max trailing drawdown: 22.7%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 80.2% |
| Avg trading days to pass audition | 1.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.6 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.7 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 13.2 |
| % simulations with any payout | 45.2% |
| Avg payouts per trader (events) | 0.49 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,149 |
| Avg total expenses incl. VPS (1 acct) | $3,673 |
| Avg net profit (1 acct) | $3,476 |
| Avg ROI | 94.6% |
| % positive ROI | 45.2% |
| Throughput-scaled est. net | $62,573 |
| Mean eval days used (all MC outcomes, any end state) | 1.9 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 45.2%
- Funded: breach before 1st payout: 35.0%
- Audition: max trailing drawdown: 19.8%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 80.8% |
| Avg trading days to pass audition | 1.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 10.0 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 8.0 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 12.0 |
| % simulations with any payout | 46.2% |
| Avg payouts per trader (events) | 0.51 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $7,890 |
| Avg total expenses incl. VPS (1 acct) | $4,867 |
| Avg net profit (1 acct) | $3,023 |
| Avg ROI | 62.1% |
| % positive ROI | 44.2% |
| Throughput-scaled est. net | $72,545 |
| Mean eval days used (all MC outcomes, any end state) | 2.0 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 46.2%
- Funded: breach before 1st payout: 34.7%
- Audition: max trailing drawdown: 19.2%

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
