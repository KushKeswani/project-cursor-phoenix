# Prop firm profit farming report

**Firm / run label:** compare_live_replay_Balanced_150k_high

Generated (UTC): `2026-04-30T03:42:14.127018+00:00`

## Run configuration

```json
{
  "firm_name": "compare_live_replay_Balanced_150k_high",
  "firm_name_slug": "compare_live_replay_Balanced_150k_high",
  "execution_reports_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\live_replay\\balanced_150k_high",
  "scope": "oos",
  "portfolio_tier": "150k-high",
  "portfolio_key": "Balanced_150k_high",
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
  "output_dir": "C:\\Users\\Administrator\\AI\\project-cursor-phoenix\\reports\\prop_sim_compare\\runs\\live_replay_balanced_150k_high"
}
```

## Daily pool

- Trading days: **258**
- Range: **2025-01-02** → **2025-12-31**
- Portfolio contracts key: **Balanced_150k_high**
- Trade size multiplier: **1.0×**

## Overall headline (single-lifecycle Monte Carlo)

Primary horizon matches **`--cohort-horizon`** (`6 Months`): **6 Months** (~126 trading days).

| Metric | Value |
|--------|-------|
| **Audition pass rate** | 93.0% |
| **Avg trading days to pass** (mean over paths that pass) | 3.8 |
| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | 11.4 |
| Avg funded-only trading days to first payout | 7.4 |
| % MC paths with any payout | 68.8% |

For comparison, **rolling historical audition pass rate** (every `60`-day window on the real daily series, when eval days are in meta): **92.5%**.

Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.

## Timing — historical pool (rolling eval, every start day)

These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).

- Mean trading days to **pass** (conditional on pass): **3.8**
- Median trading days to pass (conditional on pass): **3.0**
- Rolling windows scored: **199**

## Horizons (single-lifecycle Monte Carlo)

### 1 Week (~5 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 71.3% |
| Avg trading days to pass audition | 3.1 (mean over MC paths that pass) |
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
| Mean eval days used (all MC outcomes, any end state) | 3.4 |

**Where simulations end (% of paths):**

- Funded: survived funded segment (no trail hit): 50.8%
- Audition: window ended (no pass): 18.2%
- Passed eval, no funded days left in horizon: 14.5%
- Audition: max trailing drawdown: 10.5%
- Funded: breach before 1st payout: 6.0%

### 1 Month (~21 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 91.8% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 7.1 |
| % simulations with any payout | 69.3% |
| Avg payouts per trader (events) | 0.79 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $12,611 |
| Avg total expenses incl. VPS (1 acct) | $348 |
| Avg net profit (1 acct) | $12,263 |
| Avg ROI | 3523.9% |
| % positive ROI | 69.3% |
| Throughput-scaled est. net | $12,263 |
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 61.3%
- Funded: breach before 1st payout: 20.0%
- Funded: survived funded segment (no trail hit): 10.5%
- Audition: max trailing drawdown: 8.2%

### 1 Quarter (~63 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 93.5% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.5 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.5 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 9.6 |
| % simulations with any payout | 70.3% |
| Avg payouts per trader (events) | 0.91 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $15,181 |
| Avg total expenses incl. VPS (1 acct) | $746 |
| Avg net profit (1 acct) | $14,435 |
| Avg ROI | 1935.0% |
| % positive ROI | 70.3% |
| Throughput-scaled est. net | $43,304 |
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 70.3%
- Funded: breach before 1st payout: 23.2%
- Audition: max trailing drawdown: 6.5%

### 6 Months (~126 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 93.0% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.4 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 9.5 |
| % simulations with any payout | 68.8% |
| Avg payouts per trader (events) | 0.89 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $15,019 |
| Avg total expenses incl. VPS (1 acct) | $1,343 |
| Avg net profit (1 acct) | $13,676 |
| Avg ROI | 1018.3% |
| % positive ROI | 68.8% |
| Throughput-scaled est. net | $82,055 |
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 68.8%
- Funded: breach before 1st payout: 24.2%
- Audition: max trailing drawdown: 7.0%

### 12 Months (~252 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 90.5% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.4 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 9.9 |
| % simulations with any payout | 70.7% |
| Avg payouts per trader (events) | 0.91 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $16,132 |
| Avg total expenses incl. VPS (1 acct) | $2,537 |
| Avg net profit (1 acct) | $13,595 |
| Avg ROI | 535.9% |
| % positive ROI | 70.7% |
| Throughput-scaled est. net | $163,142 |
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 70.7%
- Funded: breach before 1st payout: 19.8%
- Audition: max trailing drawdown: 9.5%

### 18 Months (~378 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 92.5% |
| Avg trading days to pass audition | 3.8 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.6 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.6 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 9.0 |
| % simulations with any payout | 69.2% |
| Avg payouts per trader (events) | 0.91 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $15,044 |
| Avg total expenses incl. VPS (1 acct) | $3,731 |
| Avg net profit (1 acct) | $11,313 |
| Avg ROI | 303.2% |
| % positive ROI | 69.2% |
| Throughput-scaled est. net | $203,629 |
| Mean eval days used (all MC outcomes, any end state) | 3.7 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 69.2%
- Funded: breach before 1st payout: 23.3%
- Audition: max trailing drawdown: 7.5%

### 24 Months (~504 trading days)

| Metric | Value |
|--------|-------|
| Audition pass rate | 92.7% |
| Avg trading days to pass audition | 3.9 (mean over MC paths that pass) |
| Avg trading days to first payout | 11.4 (mean over MC paths with ≥1 payout; eval + funded) |
| Avg funded trading days to first payout | 7.4 (after pass; same paths as row above) |
| Avg days between payouts (if ≥2) | 10.1 |
| % simulations with any payout | 68.3% |
| Avg payouts per trader (events) | 0.88 |
| Avg prop firm fees (1 acct) | $149 |
| Avg total payouts (1 acct) | $15,135 |
| Avg total expenses incl. VPS (1 acct) | $4,925 |
| Avg net profit (1 acct) | $10,210 |
| Avg ROI | 207.3% |
| % positive ROI | 68.3% |
| Throughput-scaled est. net | $245,042 |
| Mean eval days used (all MC outcomes, any end state) | 3.8 |

**Where simulations end (% of paths):**

- Funded: breach after ≥1 payout: 68.3%
- Funded: breach before 1st payout: 24.3%
- Audition: max trailing drawdown: 7.3%

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
