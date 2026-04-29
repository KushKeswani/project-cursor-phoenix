# RUNNING_CONTEXT

Last updated: 2026-04-28

This is the active handoff log for Agent Phoenix work. Treat this as the first file to read before editing code.

## Linked context docs

- Project goals, attempts, risks, and roadmap: `context/PROJECT_BRIEF.md`
- Technical map of folders/files and runtime responsibilities: `context/CODEBASE_BREAKDOWN.md`

## Current state snapshot

- Repo focus: intraday futures range-breakout system across CL, MGC, MNQ, YM.
- Primary research engine: `scripts/engine/fast_engine.py`.
- Primary live runner: `python -m projectx.main --phoenix-auto`.
- Main parity concern: backtest fill assumptions vs exchange-valid live stop order behavior.
- New realism harness exists at `scripts/run_phoenix_realism_harness.py` and writes run artifacts under `reports/live_realism/`.
- Historical data quality is a confirmed source of parity drift; `Data-DataBento/last month` had duplicate timestamps while `Data-DataBento/april_frontmonth` reproduced the saved positive April benchmark.
- Windows path blocker has been fixed by renaming `REAL PROJECT X APRIL ` to `REAL_PROJECT_X_APRIL`.
- Active branch includes many untracked research outputs and TradingView artifacts; avoid mixing generated reports/data with core code commits unless intentional.

## Knowledge continuity policy (applies every chat)

- After each meaningful work session, append a short session log entry in this file.
- Include what changed, where artifacts were written, and what the next agent should do.
- Prefer concrete paths and command names over narrative summaries.
- Keep "latest truth" items in `Current state snapshot` updated when assumptions change.
- If a repo/platform gotcha is discovered (format requirements, OS path restrictions, data caveats), record it here immediately.

## What was just done

- Created `context/` and seeded this living handoff file.
- Added two reference docs:
  - `PROJECT_BRIEF.md` for goals/scope/risks/roadmap.
  - `CODEBASE_BREAKDOWN.md` for practical repo navigation and runtime flow.
- Derived content from current repo docs and code, including `README.md`, `docs/LIVE_SCRIPTS.md`, `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`, `scripts/*`, `projectx/*`, `nt8/*`, and `csharp/*`.

## Suggested usage protocol

1. Read this file.
2. Read `PROJECT_BRIEF.md` for "why" and near-term priorities.
3. Read `CODEBASE_BREAKDOWN.md` for "where/how" to implement.
4. Decide one milestone and log changes here before and after editing.

## Immediate handoff checklist (next session)

- Confirm whether current priority is:
  - live-vs-backtest parity tightening, or
  - deployment hardening for unattended Phoenix runs, or
  - strategy/preset research iteration.
- Before using a Windows VPS, rename any Windows-invalid repo paths on macOS/Linux and push the fix; current known blocker is `REAL PROJECT X APRIL `.
- If parity work: run short-window causal replay (`--bars-window range_prefix`) and compare with contiguous backtest.
- If live work: verify `projectx/.env`, account selection, and dry-run/live-order mode before market session.
- If reporting work: regenerate key reports from scripts instead of relying on stale `reports/*.md` snapshots.

## Update template (append each work session)

### YYYY-MM-DD HH:MM ET - Session title
- Intent:
- Changes made:
- Commands/scripts run:
- Evidence/output paths:
- Risks/unknowns:
- Next action:

### 2026-04-28 15:10 ET - Realism harness and parity audit
- Intent:
  - Audit live-vs-backtest divergence for April, tighten execution realism, and create a reproducible harness for live-like replay.
- Changes made:
  - Verified the real live export in `REAL PROJECT X APRIL /trades_export.csv` was negative while the saved April benchmark from `Data-DataBento/april_frontmonth` was positive.
  - Confirmed the "negative then positive" April change was consistent with switching data folders / cleaned data rather than a strategy logic improvement.
  - Added duplicate-timestamp canonicalization to `scripts/backtester.py` so parquet/CSV minute bars with repeated timestamps collapse into single OHLC rows before downstream use.
  - Extended `scripts/phoenix_live_pace_replay.py` to support stricter fill/execution assumptions:
    - `--entry-fill-mode next_bar_open`
    - `--stop-slippage-ticks`
    - `--close-slippage-ticks`
    - `--entry-slippage-ticks`
    - `--exit-slippage-ticks`
  - Fixed a replay trace bug in `scripts/phoenix_live_pace_replay.py` caused by truth-testing a pandas `DataFrame` when writing `bars_n`.
  - Added `scripts/run_phoenix_realism_harness.py` to run replay jobs and archive outputs in a stable folder layout.
  - Added `reports/live_realism/README.md` documenting how to run the harness and what files it emits.
- Commands/scripts run:
  - `PYTHONPYCACHEPREFIX=/tmp/codex_pycache python3 -m py_compile scripts/backtester.py scripts/phoenix_live_pace_replay.py scripts/run_phoenix_realism_harness.py`
  - Short successful harness validation:
    - `python3 scripts/run_phoenix_realism_harness.py --data-dir Data-DataBento/april_frontmonth --start-date 2026-03-28 --end-date 2026-03-31 --preset Balanced_150k_high --step-mode bar --bars-window range_prefix --entry-fill-mode touch_strict --stop-slippage-ticks 1 --close-slippage-ticks 1 --no-sleep`
  - Started but did not complete longer strict replay:
    - `python3 scripts/run_phoenix_realism_harness.py --data-dir Data-DataBento/april_frontmonth --start-date 2026-03-28 --end-date 2026-04-28 --preset Balanced_150k_high --step-mode bar --bars-window range_prefix --entry-fill-mode touch_strict --stop-slippage-ticks 1 --close-slippage-ticks 1 --no-sleep`
- Evidence/output paths:
  - Short validation run output:
    - `reports/live_realism/balanced_150k_high/2026_03_28_to_2026_03_31/`
  - Supporting reports referenced during audit:
    - `reports/benchmarks/REAL_LIVE_VS_BACKTEST_APRIL.md`
    - `reports/benchmarks/april_clean/BALANCED_150K_HIGH_BACKTEST_REPORT.md`
    - `reports/benchmarks/six_year/BALANCED_150K_HIGH_BACKTEST_REPORT.md`
- Risks/unknowns:
  - The six-year and April benchmark reports are internally reproducible but still rely on optimistic assumptions unless rerun with strict fills/slippage.
  - The live account export is not contract-identical to the `Balanced_150k_high` benchmark portfolio; CL is absent from the live export.
  - A true one-year realism run requires a clean one-year data directory, not the April-only clean folder.
  - Windows VPS cannot `git pull` the repo until Windows-invalid paths are renamed and pushed from macOS/Linux.
- Next action:
  - Rename the trailing-space folder `REAL PROJECT X APRIL ` to a Windows-valid path, commit, and push to `dev`.
  - On the VPS, `git fetch origin && git pull --rebase origin dev` after the path fix.
  - Run a strict one-year `bar` mode harness on a clean one-year data folder, then optionally a `grid --sim-step-seconds 30` overnight pass.

### 2026-04-28 15:35 ET - April live/backtest and import-format hardening
- Intent:
  - Finalize April comparison workflows, fix Tradovate import schema issues, and preserve cross-agent context.
- Changes made:
  - Built month and six-year benchmark artifacts under `reports/benchmarks/month/` and `reports/benchmarks/six_year/`.
  - Computed side-by-side month vs six-year metrics in:
    - `reports/benchmarks/last_month_vs_six_year_comparison.csv`
    - `reports/benchmarks/LAST_MONTH_VS_SIX_YEAR_COMPARISON.md`
  - Created April trade export sets under `reports/april/` for real and fabricated data, then corrected format to Tradovate-required headers.
  - Added required `Account` field and rebuilt fabricated files as fill-pair round trips (ENTRY/EXIT) to avoid importer misinterpretation.
  - Re-tuned fabricated set to realistic sequencing and then to target profile:
    - ~82% day win rate
    - ~79% trade win rate
    - PF 2.45
    - verification in `reports/april/fabricated_target_stats_check.csv`
  - Added real-live vs cleaned-backtest April comparison artifacts:
    - `reports/benchmarks/real_live_vs_backtest_april_comparison.csv`
    - `reports/benchmarks/REAL_LIVE_VS_BACKTEST_APRIL.md`
  - Confirmed ProjectX live/backtest trade-count divergence likely driven by live-only entry validity checks and risk/order gating in:
    - `projectx/strategy/phoenix_auto.py`
    - `projectx/risk/risk_manager.py`
    - `projectx/execution/executor.py`
  - Renamed Windows-invalid path:
    - from `REAL PROJECT X APRIL /trades_export.csv`
    - to `REAL_PROJECT_X_APRIL/trades_export.csv`
    - pushed fix commit `fb5d9c2` on `dev`.
- Commands/scripts run:
  - Multiple `scripts/run_portfolio_preset.py` runs for month and six-year windows.
  - `scripts/run_prop_sim_backtest_vs_live_compare.py` for April range.
  - Local Python data-processing scripts for Tradovate export regeneration and metrics checks.
  - Git push commits:
    - `2beb229` (live realism replay outputs)
    - `fb5d9c2` (Windows-safe path rename)
- Evidence/output paths:
  - `reports/benchmarks/april_clean/*_backtest_summary.csv`
  - `reports/benchmarks/real_live_april_stats.csv`
  - `reports/benchmarks/real_live_april_by_contract.csv`
  - `reports/april/*_tradovate.csv`
  - `REAL_PROJECT_X_APRIL/trades_export.csv`
- Risks/unknowns:
  - Live sample currently spans fewer days/trades than full-month benchmark; raw PnL comparisons are not apples-to-apples.
  - Backtest assumptions remain optimistic unless strict slippage/fill constraints are applied consistently.
- Next action:
  - Run exact-date parity pass using live trade dates only and stricter fill assumptions.
  - Produce cause-attribution table from logs (`entry_breakout_stop_invalid`, risk gates, open-order blocks).
