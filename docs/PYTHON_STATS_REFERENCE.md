# Python stats — minimal reference

The repo is trimmed to **batch backtest** + **live-pace replay**. Source of truth for rules: `scripts/engine/fast_engine.py`, `scripts/configs/strategy_configs.py`, `scripts/configs/tick_config.py`.

---

## 1. Engine (`fast_engine.run_backtest`)

- Per-instrument closed trades, `pnl_ticks`, optional `return_trades=True`
- `ExecutionOptions` for entry fill mode (`touch`, `touch_legacy`, `touch_strict`)

---

## 2. Backtester (`backtester.py`)

- Loads parquet via `load_bars`, resamples, runs `run_backtest` per symbol
- `scaled_trades`, `daily_pnl`, `monthly_pnl`, `trade_metrics`, `max_drawdown`, `bust_probability`
- Constants: `EOD_DD`, `DLL`, `EVAL_DAYS` (Monte Carlo defaults)
- CLI generates instrument + portfolio CSV/MD and charts under `reports/` (paths printed on run)

---

## 3. Portfolio preset (`run_portfolio_preset.py`)

- `PORTFOLIO_PRESETS` in `scripts/configs/portfolio_presets.py`
- Outputs: `{slug}_backtest_summary.csv`, `{slug}_instrument_breakdown.csv`, `{PROFILE}_BACKTEST_REPORT.md`, visuals under `reports/visuals/portfolio_risk_profiles/`
- Monte Carlo uses `EOD_DD` / `DLL` unless overridden with `--eod-dd` / `--dll`

---

## 4. Live-pace replay (`phoenix_live_pace_replay.py`)

- Calls `projectx.strategy.phoenix_auto.run_scan_once` with `gateway_sim=True` and local parquet
- **Hit stats** in JSON: steps, fingerprints, `signals`
- **Optional** `live_backtest_trades`: WR / PF / PnL from per-step `run_backtest` on the same trimmed bars (omit with `--no-live-trade-stats`)

---

## 5. Regenerate commands

| Output | Command |
|--------|---------|
| Default backtest sweep + charts | `python3 scripts/backtester.py --data-dir Data-DataBento` |
| One preset report + MC | `python3 scripts/run_portfolio_preset.py --profile Balanced_50k_survival --data-dir Data-DataBento` |
| Live replay stats (one sizing) | `python3 scripts/phoenix_live_pace_replay.py --year 2026 --data-dir Data-DataBento --step-mode bar --no-sleep` |
| Live replay for every preset | `python3 scripts/run_live_replay_all_portfolio_presets.py --year 2026 --data-dir Data-DataBento` |
