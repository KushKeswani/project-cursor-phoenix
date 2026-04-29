# PROJECT_BRIEF

## End goal

Operate a reliable, auditable, and repeatable futures range-breakout stack that keeps three environments aligned:

- research backtests (`scripts/`)
- live-pace replay (`scripts/phoenix_live_pace_replay.py`)
- live execution (`projectx/main.py --phoenix-auto`)

Target instruments are CL, MGC, MNQ, and YM with fixed per-instrument strategy rules and configurable portfolio sizing presets.

## Current scope (as inferred from code + docs)

- Build and validate strategy logic with Databento-style historical bars under `Data-DataBento`.
- Generate portfolio-level stats and reports for preset contract mixes (`Balanced_50k_*`, `Balanced_150k_*`).
- Run Phoenix in "manual placement", dry-run, or live-order mode via ProjectX Gateway.
- Maintain semantic parity with NT8 and C# ports for execution logic confidence.
- Support VPS-style unattended operation and telemetry (logs + optional Telegram/webhook events).

## What has already been tried

The repository shows multiple maturity layers and parity attempts:

- **Parity documentation and instrumentation exists**
  - `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md` traces where live and backtest diverge (stop validity, tickValue rounding, partial bars).
  - `projectx/main.py` emits explicit parity skip buckets (`dedupe`, `risk`, `entry_breakout_stop_invalid`, etc.).
- **Cross-platform implementations were built**
  - Python engine (`fast_engine`) is the reference.
  - NT8 strategies in `nt8/Strategies/` mirror engine rules.
  - C# backtest ports in `csharp/*Backtest`.
- **Validation scripts were added**
  - `scripts/verify_nt8_fidelity.py`
  - `scripts/compare_cs_engine_vs_python.py`
  - `scripts/generate_live_replay_vs_backtest_report.py`
  - `scripts/run_prop_sim_backtest_vs_live_compare.py`
- **Operational hardening attempts exist**
  - `docs/LIVE_SCRIPTS.md` and `scripts/smoke_vps_check.py`
  - Telegram and webhook notification paths in `projectx/notify/*` and wrapper `scripts/telegram_script_done.py`
- **TradingView parity work is in progress**
  - `Trading_View/*.pine` and trade comparison scripts indicate ongoing reconciliation effort.

## Architecture and runtime flow

1. **Data ingestion + bar shaping**
   - `scripts/backtester.py::load_bars` loads parquet or DataBento CSV, converts timestamps to ET, and resamples via `resample_to_bars`.
2. **Strategy execution**
   - `scripts/engine/fast_engine.py::run_backtest` performs opening-range build, trade-window entry, and exit handling (SL/PT/BE/trail/flatten).
3. **Research outputs**
   - `scripts/run_portfolio_preset.py` and `scripts/backtester.py` generate instrument and portfolio reports under `reports/`.
4. **Live-pace replay**
   - `scripts/phoenix_live_pace_replay.py` calls the same Phoenix scan path to simulate polling behavior over historical data.
5. **Live scanning and order placement**
   - `projectx/main.py --phoenix-auto` calls `projectx/strategy/phoenix_auto.py::run_scan_once`.
   - New entries are deduped and routed to `Executor.execute_dollar_risk_bracket`.
6. **Risk + state gates**
   - `RiskManager` enforces session, drawdown, trades/day, and kill-switch rules.
   - `StateManager` tracks open orders/positions/balance from API + realtime callbacks.

## Key modules/services and responsibilities

- `scripts/engine/fast_engine.py`: canonical strategy semantics and trade generation.
- `scripts/configs/strategy_configs.py`: locked strategy parameters per instrument.
- `scripts/configs/portfolio_presets.py`: contract sizing presets and notes.
- `scripts/phoenix_live_pace_replay.py`: causal replay harness for live-like behavior checks.
- `projectx/main.py`: CLI orchestration, Phoenix poll loop, notifications, mode control.
- `projectx/strategy/phoenix_auto.py`: fresh-entry detection, risk/reward sizing, bar loading from local or Gateway.
- `projectx/execution/executor.py`: contract resolution, bracket conversion, dedupe, order submission.
- `projectx/risk/risk_manager.py`: pre-trade risk gate enforcement.
- `projectx/state/state_manager.py`: thread-safe in-memory account/order/position state.
- `projectx/api/client.py` + `api/auth.py`: Gateway HTTP/auth plumbing.
- `nt8/` and `csharp/`: parity implementations for platform validation.

## Known risks / failure modes

- **Live/backtest fill mismatch**
  - Backtest `touch` can show fills where live stop orders are invalid because market already crossed trigger.
- **Tick economics mismatch**
  - Live uses Gateway `tickValue` with integer tick rounding; research uses static `TICK_VALUES`.
- **Partial bar behavior**
  - Gateway retrieval can include partial bars (`includePartialBar=True`), causing timing differences versus closed-bar assumptions.
- **Data mapping assumptions**
  - MNQ strategy fed by NQ data and YM via MYM CSV in some paths; USD interpretation can drift if assumptions are not respected.
- **Operational mode mistakes**
  - Misconfigured `dry_run`/`--live-order` and account IDs can cause either no fills or unintended real orders.
- **Order-state races**
  - Arm-order lifecycle and sibling cancellation rely on maintenance loops and state sync; stale open orders can block entries.

## Practical onboarding checklist (AI/human)

1. Read `README.md`, `docs/LIVE_SCRIPTS.md`, and `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`.
2. Confirm Python env:
   - `pip install -r requirements.txt`
   - `pip install -r scripts/requirements.txt`
   - `pip install -r projectx/requirements.txt` (for live runner)
3. Validate data location (`Data-DataBento`) and run `scripts/smoke_vps_check.py`.
4. For research:
   - run one preset via `scripts/run_portfolio_preset.py`.
5. For parity:
   - run short-range causal replay (`phoenix_live_pace_replay.py --bars-window range_prefix`).
   - compare with contiguous backtest and inspect skip buckets/logs.
6. For live:
   - copy `projectx/.env.example` to `.env`, set credentials/account.
   - run `python -m projectx.main --list-accounts`.
   - start with `--phoenix-auto --phoenix-manual` or dry-run before `--live-order`.
7. Keep `context/RUNNING_CONTEXT.md` updated after each session.

## Immediate next milestones

1. **Parity stabilization milestone**
   - Produce repeatable short-window parity packs (backtest vs replay vs live-scan decisions) with explicit skip reasons.
2. **Execution behavior policy milestone**
   - Choose and lock entry policy (stop-at-trigger strictness vs market fallback) and document expected divergence envelope.
3. **Ops reliability milestone**
   - Harden unattended runbook (health heartbeat, restart strategy, alert routing, progress files).
4. **Validation automation milestone**
   - Add CI-style sanity job for config drift across Python/NT8/C# strategy constants.
5. **Report freshness milestone**
   - Regenerate critical `reports/` artifacts from pinned date ranges and record provenance.
