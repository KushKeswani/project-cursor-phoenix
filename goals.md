# Agent Phoenix — goals

Living document. Adjust dates and metrics as we validate data.

---

## 1. Research realism and statistics

**Objective:** The most realistic offline path—**live-pace replay** (`scripts/phoenix_live_pace_replay.py`) and, where appropriate, **short-window `range_prefix`** replay—should produce **trustworthy statistics** that reconcile with batch backtests (`scripts/backtester.py`, `scripts/run_portfolio_preset.py`) within documented tolerance (see `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`).

**Concrete aims:**

- Define a **pinned evaluation kit** (date ranges, presets, data revision) and regenerate stats from it on demand.
- Track **monthly PnL distribution** (not only aggregates): median month, worst month, streaks—aligned across replay vs batch where comparable.
- Reduce unexplained drift between **replay decisions** and **live ProjectX skip buckets** over time.

---

## 2. Prop firm economics (Topstep-style sizing)

**Objective:** Strategies and portfolio presets must remain coherent for **$50k** and **$150k** style accounts: contract mixes, daily/session limits, and survival constraints respected in simulation before any live scaling conversation.

**Concrete aims:**

- Treat **`Balanced_50k_*`** and **`Balanced_150k_*`** presets (`scripts/configs/portfolio_presets.py`) as first-class test profiles.
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

- [ ] Max DD % of nominal account / eval trail budget within acceptable ratio for the chosen preset.
- [ ] Worst-month floor documented (even if negative—know it).
- [ ] Max losing streak trade count bounded relative to Monte Carlo or historical resampling where available.

---

## 4. Portfolio income target (50k preset — aspirational)

**Stated target:** For the **full multi-instrument profile** under the **50k-oriented preset** (whatever the locked preset name and contract vector settle on—e.g. survival vs high variants), aim for research that supports on the order of **USD $25k+ average per month** at the **portfolio** level over representative rolling windows.

**Guardrails:**

- This is a **research and execution-quality goal**, not a promise of live performance. Markets change; prop rules and fills vary.
- Define explicitly: **gross vs net**, **which preset**, **which date range**, and **replay vs batch** when claiming progress toward this number.
- If metrics fall short, prioritize **explainability** (where edge disappears: regime, costs, parity skips) over headline chasing.

---

## 5. Prop firm farming calculator (`prop_farming_calculator/`)

**Objective:** Monte Carlo **prop economics** on exported trades—fees, eval pass paths, funded payouts, net after expenses—so we validate **efficiency** (ROI on fees, realistic throughput) alongside raw PnL.

**Location (this bundle):** `prop_farming_calculator/` — CLI (`./run.sh` or `python cli.py`), presets in `presets.yaml`, reports under `output/<firm>/run_<timestamp>/`. Deep dive: `prop_farming_calculator/CALCULATOR_BREAKDOWN.md`.

**Inputs:** Portfolio daily/monthly series built from `reports/trade_executions/{oos|full}/instruments/*_trade_executions.csv`. Refresh those exports when bars/strategy changes (e.g. `scripts/run_prop_sim_backtest_vs_live_compare.py` patterns).

**Headline outputs to review:** `SUMMARY.md`, `horizons_summary.csv` — `audition_pass_pct`, `avg_net_profit_per_trader`, `avg_roi_pct`, `pct_positive_roi`, `farm_est_net`, payout cadence columns (see breakdown doc).

### Tasks (prop farming & efficiency)

- [ ] **Wire data:** After OOS/full backtest export, confirm four instruments’ CSVs exist under `reports/trade_executions/<scope>/instruments/`.
- [ ] **Baseline runs:** Run calculator for **`50k-survival`** and **`150k-survival`** (and **`50k-high`** / **`150k-high`** if those stacks are in play) with a named `--firm-name` and pinned `--seed`.
- [ ] **Efficiency:** Record **avg_roi_pct**, **pct_positive_roi**, and **farm_est_net** vs fees for each tier; compare survival vs high contract stacks.
- [ ] **Stress:** Compare **Monte Carlo audition_pass_pct** vs **rolling historical pass** in `pool_diagnostics`—do not optimize to MC alone (see `CALCULATOR_BREAKDOWN.md` §5).
- [ ] **Cadence:** Re-run farming reports **when strategy params change** or **trade_executions** refresh; archive `run_meta.json` for reproducibility.
- [ ] **Targets doc:** Add a short “acceptable minimums” row per tier (e.g. minimum `pct_positive_roi` at 6M horizon) once enough history exists—until then, collect benchmarks only.

---

## 6. ProjectX implementation

**Objective:** Full **ProjectX / Gateway** stack usable for Phoenix: scan loop, manual vs live order modes, risk/state, notifications where configured.

**Concrete aims:**

- Stable **`python -m projectx.main --phoenix-auto`** path with clear documentation (`docs/LIVE_SCRIPTS.md`, `docs/AGENT_PHOENIX_V2_LIVE.md`).
- Reliable bar sourcing: **local parity** vs **`pull_bars.py`** into `Data-DataBento`-style parquet when needed.
- Observable parity: logs / skip reasons aligned with `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`.

---

## 7. NinjaTrader 8 implementation

**Objective:** NT8 strategies mirror Python/Phoenix rules closely enough for **confidence checks** and optional live discretion on Tradovate-compatible setups.

**Concrete aims:**

- Maintain **`nt8/Strategies/`** (and live implementation variants where used) in sync with locked configs.
- Use **`scripts/verify_nt8_fidelity.py`** (and exports) as part of release-style checks when logic changes.

---

## 8. TradingView — backtest, visuals, and alerts

**Objective:** A **TradingView** Pine offering that supports:

- **Backtesting** in TV’s environment (within Pine limitations vs futures intraday reality).
- A **visual layer**: opening range, tap/touch of range boundaries, **breakout**, and **arming** states clearly distinguishable on-chart.
- **Alerts** users can configure without code edits: e.g. range sealed, tap/touch, breakout trigger, armed / ready states—mirroring Phoenix terminology as closely as Pine allows.

**Note:** In the full Agent Phoenix repo, Pine sources live under **`Trading_View/*.pine`**. This Project Cursor bundle may not include that folder; sync from the parent repo or copy Pine files here if you want a single portable tree.

**Concrete aims:**

- One clear **indicator** (and/or strategy) per instrument family as needed, sharing inputs with Python parameter names where practical.
- Document alert JSON / message fields so they map to Phoenix terminology (`range sealed`, `tap`, `breakout`, `arm`).
- Accept that TV **will not** match Python tick-for-tick; goals are **visual alignment + trader-facing alerts**, not parity certification.

---

## 9. Review cadence

- Revisit this file **after major logic changes**, **preset changes**, or **new prop evaluations**.
- When targets move (e.g. $25k/month hypothesis), update **Section 4** with the evidence window and methodology.
- When prop farming thresholds are ratcheted, update **Section 5** tasks and any numeric gates in **Section 3**.
