# Agent Phoenix — Project Cursor (bare-bones bundle)

Portable slice of **Agent Phoenix**: futures range-breakout research (**Python backtest**), **live-pace replay** (same scan path as ProjectX), **ProjectX / Gateway live runner**, and **NinjaTrader 8** strategy sources. Use this folder as a **standalone workspace** (no parent repo required) for humans or **AI assistants** changing strategy code, data plumbing, or live wiring.

**Public GitHub (clone on your Windows VPS):** [github.com/KushKeswani/project-cursor-phoenix](https://github.com/KushKeswani/project-cursor-phoenix).

**Agent onboarding:** read **`CONTEXT_FOR_AGENT.md`** first, then **`goals.md`**.

## Autonomous AI: run until the work is actually finished

If you use an **LLM or coding agent** (e.g. Cursor) on this repo, the intended default is: **keep going until the task is complete**, not stop after the first green test or the first blocker you notice.

**“Complete” means** (unless you the human say otherwise):

- Every validation path you were asked to run—see **`LLM_AUTONOMOUS_WORKER_PROMPT.md`** and **`CONTEXT_FOR_AGENT.md`**—has been attempted **in priority order** (baseline tests → backtest/replay when data exists → prop exports → etc.).
- Outcomes are recorded in **`AGENT_SESSION_LOG.md`** (append-only, with commands and artifact paths).
- Important milestones and blockers are summarized on **Telegram** when **`PROJECTX_TELEGRAM_BOT_TOKEN`** / **`PROJECTX_TELEGRAM_CHAT_ID`** are set in **`.env`** (see **`.env.example`**).
- You **do not declare income or edge targets met** without reproducible runs documented in the log (see **`goals.md`** §4).

**Stop the agent loop only when:** the user interrupts, or there is a **hard blocker inside this repo** (for example: no bar files under `Data-DataBento/` for backtests) *after* that blocker is written to the log and pinged on Telegram if configured.

**Practical autopilot without an LLM:** schedule **`python scripts/phoenix_agent_cycle.py`** (same as `python3` on Linux/macOS) via **Task Scheduler** on Windows or **cron** on Linux—see *VPS / sanity* below. That script runs pytest and smoke checks and can optionally run a portfolio backtest when data is present.

### Cloning on a Windows VPS

1. Install **[Python 3.10+](https://www.python.org/downloads/)** (check “Add python.exe to PATH”).
2. Clone the repo, open a terminal **in the repo root**, then:

   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r scripts\requirements.txt
   pip install -r projectx\requirements.txt
   pip install -r prop_farming_calculator\requirements.txt
   copy .env.example .env
   rem Edit .env — Telegram, Gateway, etc.
   py scripts\smoke_vps_check.py --skip-replay
   ```

3. Use **`py scripts\...`** or **`python scripts\...`** from the repo root the same way as the Unix examples in this file (`Data-DataBento` layout is unchanged—see **`docs/DATABENTO_KNOWLEDGE.md`**).

## What is included

| Area | Location | Role |
|------|-----------|------|
| Core engine | `scripts/engine/fast_engine.py` | Opening range, entries, exits (SL/PT/BE/trail/flatten). |
| Strategy configs | `scripts/configs/strategy_configs.py`, `tick_config.py`, `portfolio_presets.py`, `oos_defaults.py` | Locked params per instrument + portfolio presets. |
| Batch backtest CLI | `scripts/backtester.py`, `scripts/run_portfolio_preset.py` | Full reports/charts + single preset runs. |
| Live-pace replay | `scripts/phoenix_live_pace_replay.py`, `scripts/run_live_replay_all_portfolio_presets.py` | Steps `run_scan_once` over history like live polling. |
| ProjectX live | `projectx/` | Auth, risk, state, execution, `python -m projectx.main --phoenix-auto`. |
| NT8 | `nt8/` | `RangeBreakout*` strategies + CSV references per timeframe. |
| Tests | `tests/` | Help/smoke tests for scripts (some need data). |
| Knowledge | `docs/DATABENTO_KNOWLEDGE.md`, `context/*.md`, `docs/PHOENIX_*`, `docs/LIVE_SCRIPTS.md` | Data schema, parity, ops. |
| Goals & metrics rubric | **`goals.md`** | Targets, statistics checklist, prop-farming tasks. |
| Prop farming calculator | **`prop_farming_calculator/`** | Monte Carlo prop economics (fees, eval pass, payouts, ROI) from `reports/trade_executions/…`. |
| Agent pack | **`CONTEXT_FOR_AGENT.md`**, **`LLM_AUTONOMOUS_WORKER_PROMPT.md`** | Standalone onboarding + long-running LLM prompt. |
| Telegram (root) | **`telegram/`** | `chat_id_helper.py` + README — get `chat_id` for `.env` without using `projectx` code. |

## Environment (`.env` at this folder root)

This bundle is intended to live **alone**. Copy secrets into **`./.env`** (template: **`.env.example`**):

```bash
cp .env.example .env
```

Load order (same as `python -m projectx.main`): optional **`PROJECTX_DOTENV_PATH`** → **`<Project Cursor>/.env`** → **`projectx/.env`**. If the same key appears in both root and `projectx/.env`, **`projectx/.env` wins**.

Set **`PROJECTX_TELEGRAM_BOT_TOKEN`** and **`PROJECTX_TELEGRAM_CHAT_ID`** here for Telegram notifications without touching nested paths only.

## What is omitted (vs full repo)

- **`reports/`** generated outputs — recreate by running scripts.
- **`optimization/`**, **`csharp/`** .NET backtest ports — not required for Python + NT8 + ProjectX workflows here.
- **Large `Data-DataBento/*.csv` / `.parquet`** — see `Data-DataBento/README.md` and `docs/DATABENTO_KNOWLEDGE.md`; copy from your environment.

## Python environment

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r scripts/requirements.txt
pip install -r projectx/requirements.txt
pip install -r prop_farming_calculator/requirements.txt   # prop economics CLI
```

`requirements.txt` includes `python-dotenv` (repo-root `.env` loading), `pyarrow` for parquet; `scripts/requirements.txt` adds matplotlib for charts.

## Data (`Data-DataBento`)

Read **`docs/DATABENTO_KNOWLEDGE.md`** first. Minimum expectation: either **`MNQ.parquet`** (etc.) or the named **DataBento CSV** files for each instrument you run.

## Commands cheat sheet

### Portfolio preset backtest

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced_50k_survival --data-dir Data-DataBento
```

Profiles are defined in `scripts/configs/portfolio_presets.py`.

### Full multi-instrument backtester

```bash
python3 scripts/backtester.py --data-dir Data-DataBento
```

### Live-pace replay (Phoenix scan path, local data)

Fast bar stepping over a year:

```bash
python3 scripts/phoenix_live_pace_replay.py --year 2026 --data-dir Data-DataBento --step-mode bar --no-sleep
```

Shorter **causal** window (closer to continuous history):

```bash
python3 scripts/phoenix_live_pace_replay.py --start-date 2024-06-03 --end-date 2024-06-07 \
  --data-dir Data-DataBento --step-mode bar --no-sleep \
  --instruments MNQ,MGC,YM --contracts 1,1,1 --bars-window range_prefix
```

All presets → JSON under `reports/live_replay_by_profile/` (create `reports/` if missing):

```bash
python3 scripts/run_live_replay_all_portfolio_presets.py --year 2026 --data-dir Data-DataBento
```

### ProjectX (Gateway)

```bash
cp projectx/.env.example projectx/.env   # fill credentials
pip install -r projectx/requirements.txt
python -m projectx.main --list-accounts
python -m projectx.main --phoenix-auto --phoenix-manual    # print signals / placement only
# python -m projectx.main --phoenix-auto --live-order      # when ready — real orders
```

Settings: `projectx/config/settings.yaml`. Secrets: `.env` (not committed).

### NinjaTrader 8

Copy `nt8/Strategies/*.cs` into NinjaTrader **Documents → NinjaTrader 8 → bin → Custom → Strategies**, compile, attach per instrument (bar periods in `nt8/README.md` and `docs/INSTRUMENT_TIMEFRAMES.md`).

Optional parity check vs Python trades:

```bash
python3 scripts/verify_nt8_fidelity.py
```

### Prop firm farming calculator (Monte Carlo economics)

Requires **`reports/trade_executions/<oos|full>/instruments/*.csv`** (refresh via backtest export flows such as `scripts/run_prop_sim_backtest_vs_live_compare.py` when needed). Default `--execution-reports-dir` is repo root’s `reports/` — create/copy that tree next to this bundle or pass `--execution-reports-dir`.

```bash
cd prop_farming_calculator
pip install -r requirements.txt   # if not done above
./run.sh --firm-name "Phoenix" --portfolio 50k-survival --scope oos --n-sims 300
```

See **`prop_farming_calculator/README.md`**, **`prop_farming_calculator/CALCULATOR_BREAKDOWN.md`**, and **`goals.md`** §5 for metrics (`avg_roi_pct`, `pct_positive_roi`, `farm_est_net`, etc.) and task checklist.

### VPS / sanity (no data for basic check)

```bash
python3 scripts/smoke_vps_check.py --skip-replay
```

With data:

```bash
python3 scripts/smoke_vps_check.py
pytest tests/test_core_scripts.py -v
```

Optional: `PHOENIX_TEST_DATA_DIR` points pytest smoketests at your data folder.

## Architecture (three aligned environments)

1. **Backtest:** `run_backtest` in `fast_engine.py` on resampled bars.
2. **Replay:** `phoenix_live_pace_replay.py` calls `run_scan_once` / `fresh_entries` (`projectx/strategy/phoenix_auto.py`) on trimmed history.
3. **Live:** same Phoenix scan loop in `projectx/main.py` with Gateway bars and orders.

Parity caveats (stops vs close, tick rounding, partial bars): **`docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md`**.

## Doc index for AI / onboarding

| Doc | Use |
|-----|-----|
| **`goals.md`** | Statistics rubric (max DD, streaks, monthly profile), income targets, **prop farming tasks**. |
| **`CONTEXT_FOR_AGENT.md`** | Full standalone onboarding for agents (setup, paths, commands). |
| **`.env.example`** | Copy to **`.env`** at this root for Telegram / Gateway / test overrides. |
| **`LLM_AUTONOMOUS_WORKER_PROMPT.md`** | Ready-made prompt for an LLM scoped **only** to this folder: Telegram updates + **`AGENT_SESSION_LOG.md`** + test loops toward **`goals.md`**. |
| `docs/PHOENIX_AI_KNOWLEDGE.md` | **Start here** — one-page map + links to deeper docs. |
| `docs/DATABENTO_KNOWLEDGE.md` | Data files, CSV vs parquet, instrument mapping. |
| `context/PROJECT_BRIEF.md` | Goals and module responsibilities. |
| `context/CODEBASE_BREAKDOWN.md` | Flow-oriented map of the repo. |
| `docs/LIVE_SCRIPTS.md` | Live/replay commands, VPS notes. |
| `docs/PHOENIX_LIVE_TRADING_AND_BACKTEST_PARITY.md` | Where live and backtest differ. |
| `docs/AGENT_PHOENIX_V2_LIVE.md` | NT8 + ProjectX live checklist. |
| `docs/STRATEGY_LOGIC_EXPLAINED.md` | Strategy semantics. |
| `nt8/README.md` | NT8 install and strategy list. |

## Disclaimer

Research only; not financial advice.
