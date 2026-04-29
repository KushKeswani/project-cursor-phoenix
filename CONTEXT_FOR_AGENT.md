# Context pack — Project Cursor standalone workspace

Use this file when an **automated agent** only sees the **Project Cursor** folder. Nothing outside this directory is assumed to exist.

## What this tree is

A **self-contained** slice of Agent Phoenix: Python range-breakout engine, backtests, live-pace replay, ProjectX runner, NT8 sources, prop farming calculator, and docs. Parent-repo paths are **not** required.

## Setup (first actions)

1. **Python**

   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   pip install -r scripts/requirements.txt
   pip install -r projectx/requirements.txt
   pip install -r prop_farming_calculator/requirements.txt
   ```

2. **Environment**

   ```bash
   cp .env.example .env
   # Edit .env — at minimum Telegram token/chat if you want notifications.
   ```

   Dotenv load order (see `projectx/utils/helpers.py`): optional `PROJECTX_DOTENV_PATH` → **repository root `.env`** → **`projectx/.env`**. Duplicate keys: **later wins** (`projectx/.env` overrides root).

3. **Market data**

   Place minute OHLC under `Data-DataBento/` per `docs/DATABENTO_KNOWLEDGE.md` (parquet or DataBento CSV names). Without data, many commands stop at “missing files” — document that in `AGENT_SESSION_LOG.md`.

## Goals and success criteria

Read **`goals.md`** first: statistics rubric (max DD, streaks, monthly profile), prop farming tasks, income targets (aspirational), ProjectX/NT8/TV notes.

## Where logic lives (optimization targets)

| Layer | Path |
|-------|------|
| Engine | `scripts/engine/fast_engine.py` |
| Params per symbol | `scripts/configs/strategy_configs.py` |
| Ticks / grids / presets | `scripts/configs/tick_config.py`, `portfolio_presets.py`, `oos_defaults.py` |
| Phoenix scan (live/replay) | `projectx/strategy/phoenix_auto.py` |
| Live CLI | `projectx/main.py` |
| Prop economics MC | `prop_farming_calculator/cli.py`, `simulation.py`, `presets.yaml` |

## Commands reference (minimal)

| Goal | Command |
|------|---------|
| Help smoke | `pytest tests/test_core_scripts.py -v` |
| Portfolio backtest | `python3 scripts/run_portfolio_preset.py --profile Balanced_50k_survival --data-dir Data-DataBento` |
| Full backtester | `python3 scripts/backtester.py --data-dir Data-DataBento` |
| Replay | `python3 scripts/phoenix_live_pace_replay.py --help` |
| ProjectX | `python -m projectx.main --help` ; Telegram test `python -m projectx.main --phoenix-telegram-test` |
| Prop farming | `cd prop_farming_calculator && ./run.sh --firm-name Test --portfolio 50k-survival --scope oos --n-sims 300` |

Inputs for farming: `reports/trade_executions/{oos|full}/instruments/*_trade_executions.csv` — generate via backtest export flows (see `scripts/run_prop_sim_backtest_vs_live_compare.py --help`).

## Documentation map

| File | Purpose |
|------|---------|
| `README.md` | Commands and layout |
| `goals.md` | Targets, metrics checklist, tasks |
| `LLM_AUTONOMOUS_WORKER_PROMPT.md` | Prompt for long-running LLM workers |
| `docs/DATABENTO_KNOWLEDGE.md` | Data layout |
| `docs/PHOENIX_AI_KNOWLEDGE.md` | Short index |
| `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md` | Live vs research |
| `docs/LIVE_SCRIPTS.md` | Ops / VPS |
| `context/PROJECT_BRIEF.md`, `context/CODEBASE_BREAKDOWN.md` | Architecture |
| `prop_farming_calculator/CALCULATOR_BREAKDOWN.md` | Farming economics |
| `nt8/README.md` | NinjaTrader |

## Logging / Telegram for agents

- Append-only journal: **`AGENT_SESSION_LOG.md`** (create at repo root; described in `LLM_AUTONOMOUS_WORKER_PROMPT.md`).
- Telegram: set **`PROJECTX_TELEGRAM_BOT_TOKEN`** and **`PROJECTX_TELEGRAM_CHAT_ID`** in **`.env`** at this repo root (or `projectx/.env`).
- **Your own bot:** create it with **[@BotFather](https://t.me/BotFather)** (Telegram app → search “BotFather” → `/newbot`). Then message your bot once and run **`python3 telegram/chat_id_helper.py`** from this folder to print your **`chat_id`** for `.env` (see **`telegram/README.md`** — **not** under `projectx`).

## Known gaps in this bundle

- **`Trading_View/`** Pine scripts may be absent — TV work is blocked unless you copy Pine from the full Agent Phoenix repo.
- **`reports/`** is usually empty until you run backtests / exporters — create as needed.
- Optional **`prop-portfolio-research`** path in `fast_engine.py` is only for shared Sharpe import if that folder exists; safe to ignore.

## Parity reminder

Research, replay, and live **will differ** (stops vs bar close, tick rounding, partial bars). Do not tune only on batch backtests without checking `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`.
