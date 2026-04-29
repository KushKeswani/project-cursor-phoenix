# Prop firm farming calculator — how it works

This document explains how the calculator turns trade CSVs into prop-firm economics, what each statistic means, and how to mirror the CLI report on a website.

---

## 1. Pipeline overview

1. **Load** per-instrument execution CSVs from `reports/trade_executions/{oos|full}/instruments/`.
2. **Merge and scale** trades using `PORTFOLIO_PRESETS` (contracts per symbol), then apply an optional **trade size multiplier**.
3. **Aggregate** to a **daily** (and **monthly**) portfolio PnL series — see `data_loader.py` → `build_daily_monthly`.
4. **Simulate** many Monte Carlo paths: each path uses a **contiguous** slice of that daily series on a **circular tape** (wrap at end). This matches rolling historical windows and avoids i.i.d. resampling that would distort pass rates.
5. **Score** each path: **audition** (`prop_firm_sim.evaluate_path`) then, if pass, **funded** leg (`simulation.run_funded_segment` → `firm_funded_path`).
6. **Aggregate** by **horizon** (trading-day count): 1 Week, 1 Month, 1 Quarter, 6 / 12 / 18 / 24 Months — see `simulation.HORIZONS` and `TD_PER_MONTH = 21`.
7. **Write** Markdown + CSV + JSON under `output/<firm>/run_<timestamp>/` — see `reporting.write_reports`.

Entry points: `cli.py` (interactive or flags), `run.sh`.

---

## 2. Audition (evaluation) rules

`PropEvalProfile` holds: profit target, trailing drawdown, optional daily loss limit, optional consistency cap (max fraction of cumulative PnL from the best single day), `min_trading_days`, `eval_window_days`.

`evaluate_path` walks the window in calendar order:

- **`fail_dll`**: day PnL hits the daily loss limit.
- **`fail_trailing`**: equity drawdown from the running peak exceeds trailing drawdown.
- **`pass`**: after `min_trading_days`, cumulative PnL ≥ profit target (and consistency rule if set).
- **`expire`**: window ends without pass or hard fail.

Implementation: `scripts/prop_firm_sim.py` → `evaluate_path`.

---

## 3. Single-lifecycle Monte Carlo (main economics)

For each simulation index `i`:

1. RNG: `seed + horizon_days * 1_000_003 + i * 97_981`.
2. Pick a **uniform random start** on the pool so the eval window has length `min(eval_window_days, horizon)` and is **contiguous** on the tape (`_random_eval_start`, `_tape_contiguous`).
3. Run `evaluate_path` on the eval sample. Record outcome, days used, and funnel bucket.
4. If **pass** and trading days remain: run **funded** segment on the **next** contiguous days (same tape, circular). Payouts are either classic withdrawals or Express-style (cap + trader split) depending on `FarmSimParams.funded_payout_cap_usd`.

**Per-path cash economics**

- **Challenge fee**: `one_time` = one fee for the horizon attempt model; `monthly` = fee × ceiling of horizon months (see `_challenge_component`).
- **Activation fee**: applied when eval passes.
- **VPS**: `vps_monthly_usd × horizon_months` if `use_vps`.
- **`firm_fees_usd`**: challenge component + activation (when passed).
- **`expenses_incl_vps_usd`**: firm fees + VPS.
- **`payouts_usd`**: trader cash from funded engine (withdrawals or `total_trader_received_usd` in Express mode).
- **`net_usd`**: `payouts_usd - expenses_incl_vps_usd`.
- **`roi_pct`**: `100 × net / expenses` (or 0 if expenses negligible).

Implementation: `simulation.simulate_one_lifecycle`, aggregated in `simulation.run_horizon_batch`.

---

## 4. Horizon batch outputs (per horizon)

`run_horizon_batch` runs `farm.n_sims` paths and returns means / rates including:

| Key | Meaning |
|-----|--------|
| `horizon_trading_days` | Horizon length in trading days |
| `eval_starts_scaled` | Throughput: rough count of eval starts in the horizon from `n_accounts` × `start_frequency` — see `eval_starts_in_horizon` |
| `audition_pass_pct` | % of MC paths that pass the eval |
| `avg_payout_events_per_trader` | Mean number of funded payout events |
| `avg_prop_firm_fees_per_trader` | Mean challenge + activation (per path) |
| `avg_total_payouts_per_trader` | Mean trader payouts |
| `avg_total_expenses_per_trader` | Mean expenses incl. VPS |
| `avg_net_profit_per_trader` | Mean net |
| `avg_roi_pct` | Mean ROI % across paths |
| `pct_positive_roi` | % of paths with net > 0 |
| `farm_est_total_fees` | `avg_prop_firm_fees_per_trader × eval_starts_scaled` |
| `farm_est_net` | `avg_net_profit_per_trader × eval_starts_scaled` |
| `avg_monthly_payout_usd` | `avg_total_payouts / horizon_months` |
| `mean_days_to_first_payout_trading` | Mean over paths with ≥1 payout: eval days + funded days to first payout |
| `mean_funded_trading_days_to_first_payout` | Funded-only leg to first payout (same paths) |
| `mean_days_between_payouts_conditional` | If ≥2 payouts: average spacing |
| `pct_simulations_with_any_payout` | % of paths with at least one payout |
| `mean_eval_days_used_single_lifecycle` | Mean eval days used (all outcomes) |
| `mean_days_to_pass_eval_conditional_mc` | Mean eval days over **passing** paths only |
| `funnel_pct__*` | % of paths in each funnel bucket — see `FUNNEL_LABELS` in `simulation.py` |

---

## 5. Two different “pass rate” numbers

Do **not** conflate these on a UI:

1. **`audition_pass_pct`** — Pass rate over **Monte Carlo single-lifecycle** paths (random start on the tape).
2. **Rolling historical pass** — `pool_diagnostics` / `mc_eval_pass_pct`: every contiguous `eval_window_days` window on the **actual** daily series, no bootstrap. From `rolling_eval_stats` in `prop_firm_sim.py`.

The generated `SUMMARY.md` compares MC headline vs rolling where meta allows.

---

## 6. Pool diagnostics (`pool_diagnostics.csv`)

`pool_diagnostics` combines:

- **`obs_*`**: Observed series stats (e.g. best day vs total PnL pressure) from `observed_path_consistency_pressure`.
- **`roll_*`**: Rolling window eval stats from `rolling_eval_stats`.
- **`mc_eval_*`**: Aliases of rolling stats for stable column names (e.g. `mc_eval_pass_pct`, mean/median days to pass/fail, quantiles on days and max DD during window).

These describe **audition timing and stress on history**, not funded payout timing.

---

## 7. Cohort mode (`cohort_multi_attempt.csv`)

`build_cohort_rows` → `simulate_sequential_trader`: one **trader slot** repeats audition → funded until the horizon’s trading-day budget is exhausted. Fees stack: **challenge per attempt**, **activation per funded account**, **VPS once** for the horizon.

Use this for a “persistent trader / repeat attempts” view; the main horizon table is **single lifecycle per sim** (one eval draw + optional funded segment per path).

---

## 8. Report artifacts (files in each run folder)

| File | Purpose |
|------|--------|
| `run_meta.json` | Full inputs for reproducibility |
| `horizons_summary.csv` | One row per horizon — main KPIs |
| `overall_headline.json` | Primary-horizon headline + rolling pass for APIs |
| `funnel_by_horizon.csv` | Funnel buckets by horizon |
| `cohort_multi_attempt.csv` | Multi-attempt cohort (if enabled) |
| `pool_diagnostics.csv` | Historical + rolling eval |
| `monthly_pnl.csv` | Monthly series from loaded data |
| `SUMMARY.md` | Human-readable report |
| `warnings.txt` | Data warnings if any |

---

## 9. Website layout (mirror the report)

Suggested sections mapping 1:1 to artifacts:

1. **Run configuration** — from `run_meta.json` (firm, preset, eval rules, fees, VPS, portfolio, scope, seeds, `n_sims`).
2. **Data pool** — trading day count, date range, portfolio key, trade multiplier; show warnings.
3. **Headline** — `overall_headline.json`: MC pass %, days to pass, days to first payout, % with payout; **footnote** rolling historical pass %.
4. **Historical timing** — pool diagnostics: mean/median days to pass/fail on rolling windows.
5. **Horizon cards or table** — same columns as `horizons_summary.csv` / per-horizon blocks in `SUMMARY.md`.
6. **Funnel** — chart from `funnel_by_horizon.csv`.
7. **Optional** — cohort table, monthly PnL sparkline.

**Backend**: run the same Python pipeline and return JSON shaped like the files above. **Frontend**: horizon selector + cards; always label MC vs rolling pass %.

---

## 10. Key source files

| File | Role |
|------|------|
| `cli.py` | Args, presets merge, orchestration |
| `data_loader.py` | CSV load, daily/monthly series |
| `simulation.py` | Lifecycle sim, horizons, cohort, `eval_starts_in_horizon` |
| `reporting.py` | `SUMMARY.md`, CSVs, JSON |
| `presets.yaml` | Firm/rule templates |
| `../scripts/prop_firm_sim.py` | `evaluate_path`, `rolling_eval_stats` |
| `firm_funded_path.py` | Funded payout simulation |

---

## 11. CLI quick reference

```bash
cd prop_farming_calculator
./run.sh --firm-name "MyFirm" --portfolio 50k-survival
./run.sh --help
```

See `README.md` for full flag list and interactive mode (`-i`).
