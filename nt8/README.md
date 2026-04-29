# NinjaTrader 8 — Phoenix range-breakout (V4)

These strategies mirror the same **bar-engine rules** as Phoenix live and research: `scripts/engine/fast_engine.py` with parameters from `scripts/configs/strategy_configs.py` (`get_config`). They are **not** a copy of ProjectX polling, Telegram, or broker API code—only the intraday range → trade window → breakout stops → SL/PT/BE/trail logic.

**Bar periods, ET windows, and example run commands:** see `docs/INSTRUMENT_TIMEFRAMES.md`.

**Live / Tradovate bundle (synced copy + checklist):** `live_implementation/` — run `scripts/sync_nt8_live_implementation.ps1` (Windows) or `scripts/sync_nt8_live_implementation.sh` (macOS/Linux) from the repo root, then read `live_implementation/TRADOVATE_LIVE_CHECKLIST.md`.

## Install

1. NinjaTrader 8 → **Tools** → **Edit NinjaScript** → **Strategy** → **New**, or copy the `.cs` files into your NinjaScript strategies folder, for example:
  - `Documents\NinjaTrader 8\bin\Custom\Strategies\`
2. Copy all files from this directory’s `Strategies/` into that folder.
3. In NinjaScript Editor, **Compile** (F5). Fix any namespace conflicts if you already have strategies with the same class names.
4. On a chart, choose the instrument-appropriate strategy:
  - **RangeBreakout CL** — 12-minute bars, session template that includes **08:00** exchange time for CL (see below).
  - **RangeBreakout MGC** — 8-minute bars.
  - **RangeBreakout MNQ** — 5-minute bars.
  - **RangeBreakout YM** — 5-minute bars.
5. Optional: enable **Export Trades to CSV** for parity checks. CSVs are written under `Documents/NinjaTrader 8/RangeBreakoutTrades/`.

## Session and bar time

Bars are gated using **bar start** time (NinjaTrader stamps **end** time; the code subtracts the bar period) so session windows align with Python’s left-labeled bars. If results diverge from Python, check **trading hours template** (e.g. CL needs a template starting at **8:00 AM** so 9:00–9:30 range bars exist), bar size, and **Timezone Offset (minutes)** on the strategy if your data series is not exchange-local.

## Match Python backtests (same trades / PnL)

The strategy code is aligned with `scripts/engine/fast_engine.py` and **`get_config()`** in `scripts/configs/strategy_configs.py`. In particular, **stop loss, breakeven, and trail** use a **persistent** stop level bar-to-bar (not reset to the initial stop each bar), and instrument **range / trade / close** windows come from the built-in preset—do not rely on editing hidden MNQ defaults on the base class.

### What you must align manually

1. **Bar period** — Must match Python: CL **12m**, MGC **8m**, MNQ **5m**, YM **5m** (`docs/INSTRUMENT_TIMEFRAMES.md`).
2. **Trading hours template** — Must include the full session window (e.g. **08:00** start for CL/MNQ/YM so the opening-range bars exist).
3. **Timezone** — Data should be exchange-time **ET**; use **Timezone Offset (minutes)** on the strategy only if your series is shifted.
4. **Same test window** — Backtest the **same symbol and calendar range** you used in Python (Databento-derived 1m → resampled bars in Python vs NT chart series).

### Export NT8 trades

In the strategy, enable **Export Trades to CSV**. Files appear under:

`Documents/NinjaTrader 8/RangeBreakoutTrades/` (e.g. `MNQ_nt8_trades_*.csv`).

### Export Python reference trades

Lay out per-instrument CSVs exactly like the verifier expects:

`reports/trade_executions/oos/instruments/{CL|MGC|MNQ|YM}_trade_executions.csv`

(or pass `--scope full`). Populate those from your backtester run (same OOS dates as NT8). If your pipeline writes elsewhere, symlink or copy into that tree, or pass `--python-dir` to the script.

### Compare

```bash
python3 scripts/verify_nt8_fidelity.py \
  --python-dir reports/trade_executions \
  --nt8-dir "$HOME/Documents/NinjaTrader 8/RangeBreakoutTrades" \
  --scope oos
```

### Remaining mismatches (normal)

- **MGC ATR(14)** at range seal can differ slightly between NT8’s indicator series and Python’s `compute_bar_atr` on the same bars.
- **Ambiguous intrabar paths**: NT8’s fill model may order wicks differently than the engine’s **SL before PT** rule on rare bars; expect near-match, not always identical ticks.
- **Flatten at day/session change** may use a slightly different exit price vs Python’s `resolve_flatten_exit` when 1m data is embedded in Python but not in NT8.

For line-by-line semantics, see `BACKUPS/Agent-Pheonix-python_algos-main/docs/NT8_CONVERSION_SPEC.md` (mapping table and bar-time rules).

## Live Phoenix (ProjectX) vs NT8


| Piece           | ProjectX Phoenix                                 | NT8 here                  |
| --------------- | ------------------------------------------------ | ------------------------- |
| Signal / levels | `run_scan_once` → `fresh_entries_for_latest_bar` | `OnBarUpdate` same rules  |
| Data            | Gateway history + optional local parquet         | Chart series              |
| Orders          | API brackets, arm orders, dedupe                 | NinjaTrader managed stops |
| Alerts          | Telegram, logs                                   | NinjaTrader only          |


Use NT8 for simulation/live on NinjaTrader-connected accounts; keep ProjectX for your current Gateway workflow.