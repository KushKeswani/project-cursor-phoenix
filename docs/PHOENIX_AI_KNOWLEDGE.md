# Phoenix AI knowledge index

Standalone workspace: read **`CONTEXT_FOR_AGENT.md`** at the Project Cursor root first (setup, `.env`, commands). Single entrypoint below for **models and developers**: what exists, where it lives, and which longer doc to read next.

## Mental model

Agent Phoenix ties three runtimes to one strategy definition:

1. **Research** — `scripts/engine/fast_engine.py::run_backtest` on historical bars from `Data-DataBento/`.
2. **Replay** — `scripts/phoenix_live_pace_replay.py` drives `projectx/strategy/phoenix_auto.py::run_scan_once` on local files (simulates live polling).
3. **Live** — `python -m projectx.main --phoenix-auto` uses the same Phoenix logic with Gateway bars and optional orders.

## File map (edit here when changing behavior)

| Concern | Primary files |
|---------|----------------|
| Entries/exits / range logic | `scripts/engine/fast_engine.py` |
| Locked parameters per symbol | `scripts/configs/strategy_configs.py` |
| Tick sizes, grids, presets | `scripts/configs/tick_config.py`, `portfolio_presets.py` |
| Batch backtest CLI | `scripts/backtester.py`, `scripts/run_portfolio_preset.py` |
| Replay CLI | `scripts/phoenix_live_pace_replay.py` |
| Phoenix scan + fresh entries | `projectx/strategy/phoenix_auto.py` |
| Orders, brackets, contracts | `projectx/execution/executor.py`, `order_manager.py` |
| Risk gates | `projectx/risk/risk_manager.py` |
| Gateway API | `projectx/api/client.py`, `auth.py` |
| Pull bars into parquet | `projectx/pull_bars.py` |
| NT8 strategies | `nt8/Strategies/*.cs`, `nt8/live_implementation/` |

## Data

All bar-file expectations (parquet names, DataBento CSV columns, symbol filters, MYM vs YM caveat): **`docs/DATABENTO_KNOWLEDGE.md`**.

## Prop economics

Monte Carlo prop-firm farming on exported trades: **`prop_farming_calculator/`** (CLI, `presets.yaml`, outputs under `output/<firm>/run_*`). Goals and task checklist: **`goals.md`** §3–5.

## Parity and ops

- Live vs backtest differences: **`docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`**
- Commands, VPS: **`docs/LIVE_SCRIPTS.md`**
- NT8 + ProjectX live one-pager: **`docs/AGENT_PHOENIX_V2_LIVE.md`**
- High-level goals and risks: **`context/PROJECT_BRIEF.md`**, **`context/CODEBASE_BREAKDOWN.md`**

## Root README

Setup and command cheat sheet: **`../README.md`** (repository root of this bundle).
