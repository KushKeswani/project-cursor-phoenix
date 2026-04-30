# Live scripts runbook (local replay + ProjectX)

Use this after copying the repo to a machine (e.g. **Windows VPS**) that will run **during market hours**. Paths below assume the **repository root** is your current directory.

## Prerequisites

- **Python 3.10+** (3.11+ recommended on Windows).
- **Data**: `Data-DataBento/` at repo root (parquet/CSV layout the backtester expects), or set `PHOENIX_TEST_DATA_DIR` to that folder for smoke tests.
- **Dependencies** (research + replay):

  ```bash
  pip install -r requirements.txt
  pip install -r scripts/requirements.txt
  ```

- **Live Gateway (ProjectX only)**:

  ```bash
  pip install -r projectx/requirements.txt
  ```

  Copy `projectx/.env.example` → `projectx/.env` and set credentials (see ProjectX docs / your firm).

### Windows notes

- Create venv: `python -m venv .venv`
- Activate: `.venv\Scripts\activate` (cmd) or `.venv\Scripts\Activate.ps1` (PowerShell).
- Use **forward slashes** or escaped paths in commands; `Data-DataBento` works as shown if your cwd is the repo root.
- For **Eastern market time**, set the VPS clock to **US Eastern** *or* keep UTC and remember logs/`as_of` in the stack are **America/New_York** where relevant.

## Verify install (smoke)

From repo root:

```bash
python scripts/smoke_vps_check.py
```

Or with pytest:

```bash
python -m pytest tests/test_live_scripts_smoke.py -v
```

If data is missing, the replay portion is **skipped** but CLI checks should still pass.

### Offline Phoenix scan (ProjectX code path, **no API keys**)

Runs `projectx.strategy.phoenix_auto.run_scan_once` against **local parquet** only:

```bash
python scripts/phoenix_local_scan_once.py --data-dir Data-DataBento \
  --instruments MNQ --contracts 1 --as-of-et "2025-06-03 11:30:00"
```

Optional JSON output: add `--json-out reports/phoenix_local_scan_hit.json`. Use `--replay-range-start-et` for causal bar prefixes.

---

## 1. Local live-pace replay (historical bars, no broker)

Same code path as Phoenix `run_scan_once` on disk — good for **signal / pacing** checks without API keys.

### Quick bar-step (fast, full year style)

```bash
python scripts/phoenix_live_pace_replay.py --year 2024 --data-dir Data-DataBento --step-mode bar --no-sleep
```

### Short window, **causal prefix** (closer to continuous backtest / live)

Use for **1 week–1 month** tests (slow if you use multi-year ranges):

```bash
python scripts/phoenix_live_pace_replay.py ^
  --start-date 2024-06-03 --end-date 2024-06-07 ^
  --data-dir Data-DataBento ^
  --step-mode bar --no-sleep ^
  --instruments MNQ,MGC,YM --contracts 1,1,1 ^
  --bars-window range_prefix ^
  --stats-out reports/replay_week.json ^
  --trades-csv reports/replay_week_trades.csv
```

(On bash/macOS, use `\` line continuations instead of `^`.)

| Flag | Meaning |
|------|--------|
| `--bars-window session_day` | Default: only the calendar day of each `as_of` (fast; not continuous cross-day state). |
| `--bars-window range_prefix` | Bars from `--start-date` through each `as_of` (causal; use short spans). |
| `--no-live-trade-stats` | Faster; omits per-step `run_backtest` PnL / `live_backtest_trades` in JSON. |
| (default) | Live trade stats **on** unless `--no-live-trade-stats`. |
| `--no-sleep` | Run as fast as CPU allows (typical for VPS batch). |
| `--sim-step-seconds` / `--speed` | Wall-clock pacing when not using `--no-sleep`. |

### All four portfolio presets (batch)

```bash
python scripts/run_live_replay_all_portfolio_presets.py --start-date 2024-06-01 --end-date 2024-06-30 --data-dir Data-DataBento --live-trade-stats --bars-window range_prefix
```

Outputs: `reports/live_replay_by_profile/<Preset>.json`, optional `*_live_replay_trades.csv`, `MANIFEST.json`.  
Add **`--live-trade-stats`** if you want WR/PF/PnL blocks and trade CSVs (slower). Default batch is stats JSON only, without per-step live PnL.

---

## 2. ProjectX live runner (Gateway, real or sim accounts)

Always run **from repository root** so imports resolve.

### List active accounts

```bash
python -m projectx.main --list-accounts
```

Include inactive:

```bash
python -m projectx.main --list-accounts --list-accounts-include-inactive
```

Set `PROJECTX_ACCOUNT_ID` in `projectx/.env` or `trading.account_id` in `projectx/config/settings.yaml`.

### Phoenix auto (signals + optional API orders)

- **Manual / no API order**: `--phoenix-auto --phoenix-manual`
- **Send orders**: `--phoenix-auto --live-order` (confirm `execution.dry_run` in settings)

See `python -m projectx.main --help` for the full flag set (risk, instruments, session).

### Dependencies reminder

```bash
pip install -r projectx/requirements.txt
```

---

## 3. Running during market hours on a VPS

1. **Smoke first**: `python scripts/smoke_vps_check.py`
2. **Data**: ensure `Data-DataBento` is present if you still run **replay** on the VPS; live **Gateway** mode uses API history + does not need local parquet for bars if configured that way.
3. **Scheduler**:
   - **Windows**: Task Scheduler → trigger at pre-market time → action `python.exe` with arguments `-m projectx.main ...`, start in repo root.
   - **Linux**: `cron` or `systemd` timer with same idea.
4. **Logs**: redirect stdout/stderr to a file if the runner is unattended.
5. **Don’t** run long `range_prefix` replay over **years** on a small VPS without `--max-steps` / short dates — it reloads a growing bar window every step.

---

## 4. Troubleshooting

| Issue | What to check |
|-------|----------------|
| `ModuleNotFoundError: projectx` | Run from repo root; `pip install -e .` not required if `PYTHONPATH` is cwd and you use `python -m projectx.main`. |
| `Data dir not found` | `--data-dir` path; copy `Data-DataBento` or fix path. |
| Replay very slow | Use `--step-mode bar`, `--no-sleep`, shorten dates, avoid `range_prefix` on long ranges. |
| ProjectX 401 | Refresh token / `.env` keys. |
| `--help` crashes with `UnicodeEncodeError` / `charmap` (cmd.exe) | Use **Windows Terminal**, or set `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8` before Python, or run `python scripts\smoke_vps_check.py` (it sets these for child checks). Argparse help strings in the repo avoid non-ASCII where possible. |

---

## 5. Related reports

- `scripts/generate_live_replay_vs_backtest_report.py` → `reports/LIVE_REPLAY_VS_BACKTEST.md`
- `scripts/run_prop_sim_backtest_vs_live_compare.py` → prop-firm sim comparison under `reports/prop_sim_compare/`
