# CODEBASE_BREAKDOWN

Technical map of this repository focused on where to make changes safely and how runtime paths connect.

## Repo top-level responsibilities

- `scripts/`: research, backtest, replay, parity, and reporting CLIs.
- `projectx/`: live execution runner, Gateway API integration, risk/state/order orchestration.
- `nt8/`: NinjaTrader strategy ports and live implementation notes.
- `csharp/`: C# backtest ports per instrument plus shared engine core.
- `docs/`: operating guides, parity notes, and strategy references.
- `reports/`: generated outputs (stats snapshots, comparisons, simulation summaries).
- `Trading_View/`: Pine scripts + exported CSVs for chart-level reconciliation.
- `tests/`: smoke/test coverage for scripts and workflows.

## Core runtime flows

### 1) Research backtest flow (`scripts/backtester.py`)

1. `resolve_data_dir` picks data directory.
2. `load_bars` ingests parquet or DataBento CSV and resamples by instrument grid.
3. `get_config` returns locked `FastConfig`.
4. `run_backtest` generates trades and metrics.
5. `scaled_trades`, `trade_metrics`, and report helpers write outputs under `reports/`.

Primary files:

- `scripts/backtester.py`
- `scripts/engine/fast_engine.py`
- `scripts/configs/strategy_configs.py`
- `scripts/configs/tick_config.py`

### 2) Portfolio preset flow

- `scripts/run_portfolio_preset.py` runs one preset from `scripts/configs/portfolio_presets.py`.
- `scripts/run_live_replay_all_portfolio_presets.py` runs replay across all presets.

Preset definitions:

- `Balanced_50k_high`
- `Balanced_50k_survival`
- `Balanced_150k_high`
- `Balanced_150k_survival`

### 3) Live-pace replay flow

- `scripts/phoenix_live_pace_replay.py` replays Phoenix polling on local data.
- Uses `projectx.strategy.phoenix_auto.run_scan_once` (same scan path as live runner).
- Supports:
  - `session_day` window (fast daily reset)
  - `range_prefix` window (causal cumulative history; slower but better parity fidelity)

### 4) Live execution flow (`python -m projectx.main --phoenix-auto`)

1. Load settings/env and authenticate Gateway (`projectx/api/auth.py`, `projectx/api/client.py`).
2. Build account state (`StateManager`) and risk gate (`RiskManager`).
3. Poll Phoenix scanner (`run_scan_once`) for new entries.
4. Apply dedupe + session logic.
5. Convert strategy risk/reward to Gateway bracket ticks.
6. Submit/cancel orders through `Executor` + `OrderManager`.
7. Emit logs + optional Telegram/webhook notifications.

## Folder-by-folder map

### `scripts/`

- `engine/fast_engine.py`
  - source-of-truth strategy engine and bar semantics.
- `configs/strategy_configs.py`
  - locked instrument strategy parameters (trade windows, stops, ATR/fixed logic).
- `configs/tick_config.py`
  - tick sizes/values and resample session grids.
- `backtester.py`
  - baseline backtesting + trade/stat pipelines.
- `run_portfolio_preset.py`
  - one preset evaluation pipeline.
- `phoenix_live_pace_replay.py`
  - live-like replay harness.
- `generate_live_replay_vs_backtest_report.py`
  - parity reporting between replay and backtest.
- `verify_nt8_fidelity.py`
  - NT8 export comparison.
- `compare_cs_engine_vs_python.py`
  - C# vs Python engine parity.
- `run_prop_sim_backtest_vs_live_compare.py`, `prop_firm_sim.py`, `firm_funded_path.py`
  - prop-firm simulation and pathing analysis.
- `smoke_vps_check.py`
  - install/runtime sanity checks for deployment boxes.
- `telegram_script_done.py`
  - wrapper used by CLIs to send completion/error notifications.

### `projectx/`

- `main.py`
  - central CLI entrypoint and mode router (`--phoenix-auto`, `--session`, account listing, test modes).
- `strategy/phoenix_auto.py`
  - fresh-entry detection, local/Gateway bar loading, risk/reward conversion helper logic.
- `execution/executor.py`
  - bracket construction, contract resolution, API order calls, per-contract locking/dedupe.
- `execution/order_manager.py`
  - order lifecycle helper functions.
- `risk/risk_manager.py`
  - max loss, drawdown, session, max trades, kill-switch checks.
- `state/state_manager.py`
  - synchronized balance/positions/open orders/daily stats and cache.
- `api/auth.py`, `api/client.py`, `api/endpoints.py`
  - auth token flow and REST wrappers.
- `realtime/listener.py`
  - SignalR user hub listener integration.
- `signal_runner.py`
  - JSON inbox file watcher for signal-based execution.
- `notify/telegram.py`, `notify/webhook.py`
  - alert delivery.
- `config/settings.yaml`
  - runtime config (URLs, execution behavior, risk thresholds).
- `.env.example`
  - environment variable template for credentials and notifications.

### `nt8/`

- `Strategies/*.cs`
  - NT8 strategy ports aligned with Python engine rules.
- `README.md`
  - install + parity alignment instructions.
- `live_implementation/`
  - synchronized live deployment bundle and Tradovate checklist.

### `csharp/`

- `RangeBreakout.Core/`
  - shared C# engine logic.
- `<Instrument>.Backtest/`
  - separate executable per instrument with hardcoded strategy constants.
- `README.md`
  - build/run/parity guidance.

### `docs/`

High-value docs for contributors:

- `LIVE_SCRIPTS.md`: operational runbook for replay/live/VPS.
- `PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`: detailed divergence analysis.
- `INSTRUMENT_TIMEFRAMES.md`: bar periods + session windows.
- `PYTHON_STATS_REFERENCE.md`: quick metric/script reference.
- `STRATEGY_LOGIC_EXPLAINED.md`: strategy semantics and rationale.

### `reports/`

- Generated artifacts from backtests, replay audits, and prop simulations.
- Useful for historical context; treat as snapshots unless regenerated for current window/config.

### `Trading_View/`

- Pine indicators/strategies and exported CSVs used for manual chart parity checks.
- Contains many local artifacts; review cleanliness before commits.

## Configuration + environment surfaces

- Root deps: `requirements.txt`
- Script deps: `scripts/requirements.txt`
- Live runner deps: `projectx/requirements.txt`
- Live config: `projectx/config/settings.yaml`
- Secrets/credentials: `projectx/.env` (from `.env.example`)
- Optional alert env vars:
  - `PROJECTX_TELEGRAM_BOT_TOKEN`
  - `PROJECTX_TELEGRAM_CHAT_ID`
  - `PROJECTX_WEBHOOK_URL`

## Key "change hotspots" by task

- Adjust strategy behavior: `scripts/configs/strategy_configs.py`, then validate in `fast_engine.py`.
- Adjust fill/parity behavior: `scripts/engine/fast_engine.py`, `projectx/strategy/phoenix_auto.py`, `projectx/main.py`.
- Adjust live order policy: `projectx/execution/executor.py`, `projectx/config/settings.yaml`.
- Adjust risk guardrails: `projectx/risk/risk_manager.py`, `projectx/config/settings.yaml`.
- Add/new replay diagnostics: `scripts/phoenix_live_pace_replay.py`, `projectx/main.py`.
- Extend notifications: `projectx/notify/*`, `scripts/telegram_script_done.py`.

## Practical onboarding quickstart (technical)

1. Install dependencies in a fresh venv.
2. Run `scripts/smoke_vps_check.py`.
3. Execute one backtest preset and inspect outputs.
4. Run short-window replay with `range_prefix`.
5. Read parity doc and inspect skip categories in Phoenix logs.
6. Configure `.env` + account ID; run `--list-accounts`.
7. Start `--phoenix-auto --phoenix-manual` before any live-order session.

## Common pitfalls for new contributors

- Confusing strategy logic (`fast_engine`) with broker/execution logic (`projectx/execution`).
- Assuming report files are always current; many are static snapshots.
- Ignoring ET session windows and left-labeled bar semantics during external comparison (TV/NT8).
- Running long causal replay windows without realizing performance cost.
- Changing live flags without understanding dry-run vs real order path.
