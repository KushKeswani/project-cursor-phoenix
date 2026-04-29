# Backtest expected baseline — timeframes and reference PnL

This document records **strategy timeframes** (ET) for each Phoenix instrument and **one frozen reference run** of `fast_engine` on local `Data-DataBento` parquet so you can compare NinjaTrader or other tools against the same assumptions.

**Important:** These dollar figures are **not** a promise of live or NT performance. They are **research baselines**: touch fills, **zero slippage** in the engine, and optional **\$1.24 round-turn commission per trade** deducted for a rough “net” column. NinjaTrader will differ (data series, session template, simulator, bid/ask, fees).

---

## 1. Timeframes by instrument (all times US Eastern)

Source: `scripts/configs/strategy_configs.py`, `scripts/configs/tick_config.py` (`INSTRUMENT_GRIDS`). Bar time = **open** (left-labeled), matching `resample_to_bars` and NT8 strategies when the chart session is aligned.

| Instrument | Bar period | Session (1m→bar resample) | Opening range | Trade window | Flatten (close-all) | Tick size |
|------------|------------|---------------------------|---------------|--------------|---------------------|-----------|
| **CL** | **12 min** | 08:00–18:00 | 09:00–09:30 | 10:30–12:30 | from **16:55** | 0.01 |
| **MGC** | **8 min** | 08:00–17:00 | 09:00–09:30 | **12:00–13:00** | from **16:55** | 0.10 |
| **MNQ** | **5 min** | 08:00–18:00 | **09:35–09:55** | **11:00–13:00** | from **16:55** | 0.25 |
| **YM** | **5 min** | 08:00–18:00 | 09:00–09:30 | **11:00–13:00** | from **16:55** | 1.0 |

Weekends excluded in engine (`excluded_weekdays` Sat/Sun).

**NinjaTrader:** use the bar period in the first column and a **session template starting 08:00 ET** (and instrument-specific end, e.g. CL through 18:00) so opening-range bars exist. See `docs/INSTRUMENT_TIMEFRAMES.md` for commands and NT strategy names.

---

## 2. Reference results — frozen window (local data)

| Field | Value |
|-------|--------|
| **Data** | `Data-DataBento/` (`{CL,MGC,MNQ,YM}.parquet` pipeline via `load_bars`) |
| **Date range** | **2020-01-01** → **2025-12-31** |
| **Contracts** | **1** per instrument |
| **Engine** | `scripts/engine/fast_engine.py` — `ExecutionOptions(entry_fill_mode="touch")`, **0 slippage ticks** |
| **Commission** | **\$1.24** subtracted per **round-turn** per trade for an approximate **net** (same convention as `scripts/mnq_nt_style_sanity.py`). Set to \$0 in code if you want gross-only. |

### Expected trade counts and PnL (regenerate after data updates)

Run locally to refresh numbers:

```bash
python3 scripts/mnq_nt_style_sanity.py --data-dir Data-DataBento --start 2020-01-01 --end 2025-12-31
```

MNQ-only stress rows (0 / +1 / +2 tick slippage) print to stdout.

**Snapshot captured in repo (touch, 0 slip, \$1.24 RT):**

| Instrument | Resampled bars (approx) | Trades | Gross \$ | Comm \$ (1× RT) | Net \$ |
|------------|---------------------------|--------|---------|-------------------|--------|
| CL | 51,487 | 1,696 | 355,660.00 | 2,103.04 | 353,556.96 |
| MGC | 102,203 | 1,192 | 64,910.77 | 1,478.08 | 63,432.69 |
| MNQ | 163,364 | 2,168 | 111,477.50 | 2,688.32 | 108,789.18 |
| YM | 160,455 | 2,243 | 722,280.00 | 2,781.32 | 719,498.68 |

*YM gross/net are in **\$** using repo `TICK_VALUES["YM"]` (\$5/pt) on mini Dow economics.*

---

## 3. How to reproduce / parity

**MNQ stress (slippage scenarios):**

```bash
python3 scripts/mnq_nt_style_sanity.py --data-dir Data-DataBento --start 2020-01-01 --end 2025-12-31
```

**Python vs C# engine (same bars, should match on touch):**

```bash
python3 scripts/compare_cs_engine_vs_python.py --instrument MNQ --data-dir Data-DataBento --start 2020-01-01 --end 2025-12-31
```

Swap `--instrument` for `CL`, `MGC`, or `YM`.

---

## 4. Why NinjaTrader may not match this table

- Different **historical data** (vendor, continuous contract rules).
- **Session / timezone** on chart not aligned with 08:00 ET start.
- **Simulator** fills vs touch-fill research model.
- **Commissions and slippage** set in NT Strategy Analyzer.
- **Bar period** mismatch (e.g. 1m chart vs 5m strategy).

Align **timeframes (section 1)**, **dates**, and **instrument**, then compare trade lists or use `scripts/verify_nt8_fidelity.py` after exporting trades from both sides.
