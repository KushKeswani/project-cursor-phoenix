# Prop firm profit farming report

**Firm / run label:** compare_live_replay_Balanced_50k_survival

Generated (UTC): `2026-04-30T03:42:07.413990+00:00`

## Run configuration

```json
{
  "firm_name": "compare_live_replay_Balanced_50k_survival",
  "firm_name_slug": "compare_live_replay_Balanced_50k_survival",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\live_replay\\balanced_50k_survival",
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\live_replay_balanced_50k_survival"
}
```

## Warnings

- No CSV (skipped): CL

## Daily pool

- Trading days: **258**
- Range: **2025-01-02** → **2025-12-31**
- Portfolio contracts key: **Balanced_50k_survival**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 82.8% |
| **Avg trading days to pass** (mean over paths that pass) | 2.6 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 10.4 |
| Avg funded-only trading days to first payout | 7.6 |
| % MC paths with any payout | 53.0% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **80.9%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **2.6**
- Median trading days to pass (conditional on pass): **2.0**
- Rolling windows scored: **199**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 74.8% |
| Avg trading days to pass audition | 2.2 (mean over MC paths that pass) |
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
| Mean eval days used (all MC outcomes, any end state) | 2.4 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 56.3%
- Audition: max trailing drawdown: 19.2%
- Funded: breach before 1st payout: 14.5%
- Audition: window ended (no pass): 6.0%
- Passed eval, no funded days left in horizon: 4.0%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 83.3% |
| Avg trading days to pass audition | 2.4 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.7 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.1 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 7.8 |
| % simulations with any payout | 45.3% |
| Avg payouts per trader (events) | 0.46 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $3,946 |
| Avg total expenses incl. VPS (1 acct) | $290 |
| Avg net profit (1 acct) | $3,656 |
| Avg ROI | 1260.8% |
| % positive ROI | 45.3% |
| Throughput-scaled est. net | $3,656 |
| Mean eval days used (all MC outcomes, any end state) | 2.4 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 43.2%
- Funded: breach before 1st payout: 35.5%
- Audition: max trailing drawdown: 16.7%
- Funded: survived funded segment (no trail hit): 4.7%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 83.2% |
| Avg trading days to pass audition | 2.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 10.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.7 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 15.2 |
| % simulations with any payout | 52.8% |
| Avg payouts per trader (events) | 0.57 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $5,149 |
| Avg total expenses incl. VPS (1 acct) | $688 |
| Avg net profit (1 acct) | $4,461 |
| Avg ROI | 648.4% |
| % positive ROI | 52.8% |
| Throughput-scaled est. net | $13,383 |
| Mean eval days used (all MC outcomes, any end state) | 2.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 52.8%
- Funded: breach before 1st payout: 30.3%
- Audition: max trailing drawdown: 16.8%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 82.8% |
| Avg trading days to pass audition | 2.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 10.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 18.8 |
| % simulations with any payout | 53.0% |
| Avg payouts per trader (events) | 0.56 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $5,115 |
| Avg total expenses incl. VPS (1 acct) | $1,285 |
| Avg net profit (1 acct) | $3,830 |
| Avg ROI | 298.1% |
| % positive ROI | 53.0% |
| Throughput-scaled est. net | $22,981 |
| Mean eval days used (all MC outcomes, any end state) | 2.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 53.0%
- Funded: breach before 1st payout: 29.8%
- Audition: max trailing drawdown: 17.2%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 80.7% |
| Avg trading days to pass audition | 2.7 (mean over MC paths that pass) |
| Avg trading days to first payout | 9.9 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.1 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 15.8 |
| % simulations with any payout | 53.8% |
| Avg payouts per trader (events) | 0.57 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $5,232 |
| Avg total expenses incl. VPS (1 acct) | $2,479 |
| Avg net profit (1 acct) | $2,753 |
| Avg ROI | 111.0% |
| % positive ROI | 53.8% |
| Throughput-scaled est. net | $33,033 |
| Mean eval days used (all MC outcomes, any end state) | 2.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 53.8%
- Funded: breach before 1st payout: 26.8%
- Audition: max trailing drawdown: 19.3%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 80.5% |
| Avg trading days to pass audition | 2.5 (mean over MC paths that pass) |
| Avg trading days to first payout | 10.3 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 19.2 |
| % simulations with any payout | 50.3% |
| Avg payouts per trader (events) | 0.53 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $4,626 |
| Avg total expenses incl. VPS (1 acct) | $3,673 |
| Avg net profit (1 acct) | $953 |
| Avg ROI | 26.0% |
| % positive ROI | 45.0% |
| Throughput-scaled est. net | $17,158 |
| Mean eval days used (all MC outcomes, any end state) | 2.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 50.3%
- Funded: breach before 1st payout: 30.2%
- Audition: max trailing drawdown: 19.5%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 81.8% |
| Avg trading days to pass audition | 2.6 (mean over MC paths that pass) |
| Avg trading days to first payout | 10.8 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 8.0 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 16.5 |
| % simulations with any payout | 51.3% |
| Avg payouts per trader (events) | 0.55 |
| Avg prop firm fees (1 acct) | $91 |
| Avg total payouts (1 acct) | $5,135 |
| Avg total expenses incl. VPS (1 acct) | $4,867 |
| Avg net profit (1 acct) | $268 |
| Avg ROI | 5.5% |
| % positive ROI | 43.3% |
| Throughput-scaled est. net | $6,443 |
| Mean eval days used (all MC outcomes, any end state) | 2.6 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 51.3%
- Funded: breach before 1st payout: 30.5%
- Audition: max trailing drawdown: 18.2%

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
