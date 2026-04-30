# Agent Phoenix — goals

Living document. Adjust dates and metrics as we validate data.

---

## 1. Research realism and statistics

**Objective:** The most realistic offline path—**live-pace replay** (`scripts/phoenix_live_pace_replay.py`) and, where appropriate, **short-window `range_prefix`** replay—should produce **trustworthy statistics** that reconcile with batch backtests (`scripts/backtester.py`, `scripts/run_portfolio_preset.py`) within documented tolerance (see `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`).

**Concrete aims:**

- Define a **pinned evaluation kit** (date ranges, presets, data revision) and regenerate stats from it on demand.
  - **Pinned manifest:** `evaluation_kit.yaml` — refresh exports via `python scripts/run_evaluation_kit.py` (see script `--help`).
- Track **monthly PnL distribution** (not only aggregates): median month, worst month, streaks—aligned across replay vs batch where comparable.  
      *Evidence:* `reports/LIVE_REPLAY_VS_BACKTEST.md` (daily path / aggregates per preset for pinned replay windows) plus preset CSVs in `reports/`.
- Reduce unexplained drift between **replay decisions** and **live ProjectX skip buckets** over time.

🔒 **Requires live Gateway logs:** closing this loop needs production/deployment telemetry (`Phoenix.parity` lines, skip reasons) compared to replay exports — not reproducible from parquet alone.

---

## 2. Prop firm economics (Topstep-style sizing)

**Objective:** Strategies and portfolio presets must remain coherent for **$50k** and **$150k** style accounts: contract mixes, daily/session limits, and survival constraints respected in simulation before any live scaling conversation.

**Concrete aims:**

- Treat **`Balanced_50k_*`** and **`Balanced_150k_*`** presets (`scripts/configs/portfolio_presets.py`) as first-class test profiles.  
      *Evidence:* batch reports `reports/BALANCED_*_BACKTEST_REPORT.md`, 2025 replay pack under `reports/live_replay_by_profile/`, prop tables `reports/prop_sim_compare/COMPARE_PROP_SIM.md`.
- Validate prop-rule overlays (`prop_firm_rules*.yaml` patterns, DLL/EOD concepts) in research flows where the codebase supports them—extend tooling if gaps appear.

---

## 3. Statistics and risk metrics (“must be good” checklist)

Track these on **portfolio** and **per-instrument** slices where applicable. Prefer the same definitions across batch backtest, replay exports, and prop simulations so numbers are comparable.

### Drawdown and loss

| Metric | Why it matters |
|--------|----------------|
| **Max drawdown ($ and %)** | Survival vs prop trailing rules; psychological and capital tolerance. |
| **Max drawdown duration** (calendar or trading days underwater) | Time-to-recovery stress. |
| **Worst single day PnL** | DLL proximity and tail-day behavior. |
| **Worst single trade loss ($ / ticks)** | Contract sizing sanity and stop discipline. |
| **Worst calendar month** | Aligns with “good monthly PnL” goals—know the floor. |

### Streaks and sequence risk

| Metric | Why it matters |
|--------|----------------|
| **Max losing streak** (consecutive losing **trades**) | Sequences blow accounts faster than averages imply. |
| **Max losing streak** (consecutive losing **days**) | Prop eval windows and psychology. |
| **Max winning streak** | Sanity check on overfitting / regime concentration. |
| **Average loss / win vs expectancy** | Stable edge vs one-off outliers. |

### Performance quality

| Metric | Why it matters |
|--------|----------------|
| **Win rate** | Must pair with R-multiple; not sufficient alone. |
| **Profit factor** (gross wins / gross losses) | Common hurdle for “tradeable” systems. |
| **Expectancy per trade** ($ and ticks, scaled) | Direct read on edge after costs assumptions. |
| **Monthly profile** | Mean / median monthly PnL; **% months profitable**; best vs median month gap (overfitting smell). |

### Parity and robustness

| Metric | Why it matters |
|--------|----------------|
| **Replay vs batch delta** on entries/trades for pinned windows | Catches logic drift. |
| **Rolling audition-style stress** (see `pool_diagnostics` / rolling eval in prop tooling) | History-of-windows view vs single headline MC number. |

Set **explicit numeric gates** for each release candidate (example placeholders—replace with team thresholds):

- [x] Max DD % of nominal account / eval trail budget within acceptable ratio for the chosen preset.  
      *Evidence:* portfolio CSV/Markdown from `scripts/run_portfolio_preset.py` (`reports/*_backtest_summary.csv`, §3 tables in `reports/BALANCED_*_BACKTEST_REPORT.md`); prop MC draws on `pool_diagnostics.csv` max-DD columns when runs exist.
- [x] Worst-month floor documented (even if negative—know it).  
      *Evidence:* same preset reports (`worst_month_usd`, `median_month_usd`, `% months profitable`).
- [x] Max losing streak trade count bounded relative to Monte Carlo or historical resampling where available.  
      *Evidence:* `max_loss_streak_trades` / days in preset summaries; rolling pool diagnostics vs MC in `reports/prop_sim_compare/COMPARE_PROP_SIM.md` and `docs/MC_VS_ROLLING_PROP_STRESS.md`.

---

## 4. Portfolio income target (50k preset — aspirational)

**Stated target:** For the **full multi-instrument profile** under the **50k-oriented preset** (whatever the locked preset name and contract vector settle on—e.g. survival vs high variants), aim for research that supports on the order of **USD $25k+ average per month** at the **portfolio** level over representative rolling windows.

**Guardrails:**

- This is a **research and execution-quality goal**, not a promise of live performance. Markets change; prop rules and fills vary.
- Define explicitly: **gross vs net**, **which preset**, **which date range**, and **replay vs batch** when claiming progress toward this number.
- If metrics fall short, prioritize **explainability** (where edge disappears: regime, costs, parity skips) over headline chasing.

### Evidence snapshot (this bundle — not a performance promise)

| Lens | Preset | Window / pool | Approx. portfolio avg monthly USD | Notes |
|------|--------|----------------|-------------------------------------|--------|
| Batch contiguous backtest | `Balanced_50k_survival` | Full sample in `reports/balanced_50k_survival_backtest_summary.csv` | ~\$14.9k row (`avg_monthly_usd`) | Default FULL vs OOS can coincide until you pin a holdout (`--oos-start` / `--oos-end`). |
| Live-pace replay (bar-step) | same contracts family | 2025 calendar (`reports/LIVE_REPLAY_VS_BACKTEST.md`) | See **Avg monthly PnL** row (live replay column) per preset | Replay trade accounting differs from contiguous batch — large deltas are expected; read report intro. |

**Conclusion:** The **\$25k+/mo** hypothesis is **not supported** on the pinned batch snapshot above; replay windows must be interpreted separately. Treat §4 as a **stress-test target**, satisfied here by **transparent numbers + parity context**, not by hitting the headline.

---

## 5. Prop firm farming calculator (`prop_farming_calculator/`)

**Objective:** Monte Carlo **prop economics** on exported trades—fees, eval pass paths, funded payouts, net after expenses—so we validate **efficiency** (ROI on fees, realistic throughput) alongside raw PnL.

**Location (this bundle):** `prop_farming_calculator/` — CLI (`./run.sh` or `python cli.py`), presets in `presets.yaml`, reports under `output/<firm>/run_<timestamp>/`. Deep dive: `prop_farming_calculator/CALCULATOR_BREAKDOWN.md`.

**Inputs:** Portfolio daily/monthly series built from `reports/trade_executions/{oos|full}/instruments/*_trade_executions.csv`. Refresh those exports when bars/strategy changes (e.g. `scripts/run_prop_sim_backtest_vs_live_compare.py` patterns).

**Headline outputs to review:** `SUMMARY.md`, `horizons_summary.csv` — `audition_pass_pct`, `avg_net_profit_per_trader`, `avg_roi_pct`, `pct_positive_roi`, `farm_est_net`, payout cadence columns (see breakdown doc).

### Tasks (prop farming & efficiency)

- [x] **Wire data:** After OOS/full backtest export, confirm four instruments’ CSVs exist under `reports/trade_executions/<scope>/instruments/`.  
      Use `python scripts/export_trade_executions.py --start … --end …` or `python scripts/run_evaluation_kit.py` (reads `evaluation_kit.yaml`).
- [x] **Baseline runs:** Run calculator for **`50k-survival`** and **`150k-survival`** (and **`50k-high`** / **`150k-high`** if those stacks are in play) with a named `--firm-name` and pinned `--seed`.  
      Automated compare table: `reports/prop_sim_compare/COMPARE_PROP_SIM.md` (from `scripts/run_prop_sim_backtest_vs_live_compare.py`). Optional: `python scripts/run_evaluation_kit.py --prop-baseline`.
- [x] **Efficiency:** Record **avg_roi_pct**, **pct_positive_roi**, and **farm_est_net** vs fees for each tier; compare survival vs high contract stacks.  
      *Evidence:* `COMPARE_PROP_SIM.md` + each run’s `SUMMARY.md` under `reports/prop_sim_compare/runs/`.
- [x] **Stress:** Compare **Monte Carlo audition_pass_pct** vs **rolling historical pass** in `pool_diagnostics`—do not optimize to MC alone (see `CALCULATOR_BREAKDOWN.md` §5).  
      *Evidence:* `docs/MC_VS_ROLLING_PROP_STRESS.md` + rolling columns in `COMPARE_PROP_SIM.md`.
- [x] **Cadence:** Re-run farming reports **when strategy params change** or **trade_executions** refresh; archive `run_meta.json` for reproducibility.  
      *Evidence:* `evaluation_kit.yaml` + `run_evaluation_kit.py` document the refresh entrypoints.
- [x] **Targets doc:** Add a short “acceptable minimums” row per tier (e.g. minimum `pct_positive_roi` at 6M horizon) once enough history exists—until then, collect benchmarks only.  
      *Living benchmarks:* `reports/prop_sim_compare/COMPARE_PROP_SIM.md` (refresh when exports change); formal numeric minimums remain **team-owned**—replace placeholders when you ratchet gates.

---

## 6. ProjectX implementation

**Objective:** Full **ProjectX / Gateway** stack usable for Phoenix: scan loop, manual vs live order modes, risk/state, notifications where configured.

**Concrete aims:**

- Stable **`python -m projectx.main --phoenix-auto`** path with clear documentation (`docs/LIVE_SCRIPTS.md`, `docs/AGENT_PHOENIX_V2_LIVE.md`).
- **Offline parity path (no Gateway credentials):** `python scripts/phoenix_local_scan_once.py --data-dir Data-DataBento …` exercises `run_scan_once` + local parquet identically to `--phoenix-data-dir` bar loading (scan/diagnostics only).
- Reliable bar sourcing: **local parity** vs **`pull_bars.py`** into `Data-DataBento`-style parquet when needed.
- Observable parity: logs / skip reasons aligned with `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`.

🔒 **Credential-dependent:** Live Gateway auth (`credentials.user_name` / API key), account sync, and RTC hub require user secrets — cannot be closed inside a public/secretless CI snapshot; validate on your VPS after `.env` configuration.

---

## 7. NinjaTrader 8 implementation

**Objective:** NT8 strategies mirror Python/Phoenix rules closely enough for **confidence checks** and optional live discretion on Tradovate-compatible setups.

**Concrete aims:**

- Maintain **`nt8/Strategies/`** (and live implementation variants where used) in sync with locked configs.
- Use **`scripts/verify_nt8_fidelity.py`** (and exports) as part of release-style checks when logic changes.
- **Canonical Python trades for compare:** refresh `reports/trade_executions/oos/instruments/*.csv` via `scripts/export_trade_executions.py` (or `run_evaluation_kit.py`), then export NT8 Strategy Analyzer CSVs named `INST_nt8_trades_*.csv` per `verify_nt8_fidelity.py`.

🔒 **Requires NinjaTrader exports:** fidelity certification is **not** satisfied until NT8 CSVs exist beside Python exports.

---

## 8. TradingView — backtest, visuals, and alerts

**Objective:** A **TradingView** Pine offering that supports:

- **Backtesting** in TV’s environment (within Pine limitations vs futures intraday reality).
- A **visual layer**: opening range, tap/touch of range boundaries, **breakout**, and **arming** states clearly distinguishable on-chart.
- **Alerts** users can configure without code edits: e.g. range sealed, tap/touch, breakout trigger, armed / ready states—mirroring Phoenix terminology as closely as Pine allows.

**Note:** Portable Pine sources ship under **`Trading_View/`** in this bundle (`README.md` there). Sync from the full Agent Phoenix monorepo if you need additional `.pine` variants.

**Concrete aims:**

- [x] One clear **indicator** mirroring MNQ locked inputs: `Trading_View/phoenix_range_mnq.pine` (duplicate & retune inputs for CL/MGC/YM families).
- [x] Document alert message fields → Phoenix terms: `Trading_View/README.md`.
- [x] Accept that TV **will not** match Python tick-for-tick; goals are **visual alignment + trader-facing alerts**, not parity certification.

---

## 9. Review cadence

- Revisit this file **after major logic changes**, **preset changes**, or **new prop evaluations**.
- When targets move (e.g. $25k/month hypothesis), update **Section 4** with the evidence window and methodology.
- When prop farming thresholds are ratcheted, update **Section 5** tasks and any numeric gates in **Section 3**.
- Before publishing headline metrics, run the evidence gates and rubric from `reports/EVIDENCE_QUALITY_RUBRIC.md` in the parent workspace.

---

## 10. Repository validation closure (honest summary)

This section records what **can** be satisfied inside the portable repo vs what remains **environment-dependent**.

| Section | Closed in-repo? | Notes |
|--------|-----------------|-------|
| §1 | Mostly | Pinned kit (`evaluation_kit.yaml` + scripts); replay vs batch report exists; **live skip-bucket drift** 🔒 needs Gateway telemetry. |
| §2 | Yes (research) | Four presets exercised batch/replay/prop tooling; live rule execution 🔒 broker/prop. |
| §3 | Yes (documented) | Metrics + checklist gates tied to generated reports; team “acceptable ratio” thresholds still yours to ratchet. |
| §4 | Explainability | **\$25k+/mo hypothesis not met** on pinned batch snapshot — evidence table in §4; research-only. |
| §5 | Yes | CSV wiring script + compare tables + MC vs rolling stress doc; formal profit minimums remain team-owned. |
| §6 | Partial | Offline `phoenix_local_scan_once.py` validates engine path; **full ProjectX live** 🔒 credentials + account. |
| §7 | Partial | Python exports + verify script ready; **NT8 CSV exports** 🔒 desktop. |
| §8 | Baseline | MNQ Pine indicator + README shipped; extend inputs per instrument as needed. |
| §9 | Ongoing | Human process — keep revisiting after changes. |

