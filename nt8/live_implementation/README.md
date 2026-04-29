# NinjaTrader — live implementation (Phoenix parity)

This folder is a **deployable snapshot** of the **RangeBreakout V4** NinjaScript stack that mirrors the same **intraday windows and engine rules** as research (`scripts/engine/fast_engine.py`) and ProjectX Phoenix (`python -m projectx.main --phoenix-auto`). It is **not** the Python ProjectX Gateway code — it is the **NinjaTrader side** for **live or sim execution** (e.g. **Tradovate** through NinjaTrader).

## Contents

- `Strategies/` — copies of `nt8/Strategies/*.cs` and `*.csv` (CSV are optional references; logic is in `.cs`).
- `TRADOVATE_LIVE_CHECKLIST.md` — connection, data, and session checks for Tradovate.
- `PROJECTX_PARITY.md` — how this maps to ProjectX CLI flags.

## Refresh before a live session (Monday, etc.)

From repository root:

**Windows (PowerShell):**

```powershell
.\scripts\sync_nt8_live_implementation.ps1
```

**macOS / Linux:**

```bash
bash scripts/sync_nt8_live_implementation.sh
```

Optional: also push files into your NinjaTrader folder:

```powershell
$env:NINJATRADER_STRATEGIES_DIR = "$env:USERPROFILE\Documents\NinjaTrader 8\bin\Custom\Strategies"
.\scripts\sync_nt8_live_implementation.ps1
```

Then: **NinjaTrader → Tools → Edit NinjaScript → Compile** (F5).

## Strategies to attach (Phoenix book)

| Chart instrument | Strategy class | Bar period | Notes |
|------------------|----------------|------------|--------|
| MNQ | RangeBreakout MNQ | 5 min | Range 09:35–09:55 ET, trade 11:00–13:00 |
| MGC | RangeBreakout MGC | 8 min | Trade 12:00–13:00 ET |
| YM | RangeBreakout YM | 5 min | Range 09:00–09:30 ET, trade 11:00–13:00 |

Full ET table: `docs/INSTRUMENT_TIMEFRAMES.md`.

## Tradovate

NinjaTrader connects to **Tradovate** for execution and/or data. The strategies do not embed a broker name — any connection that provides **CME micro/mini futures** with correct **tick size** and **session** is valid. See `TRADOVATE_LIVE_CHECKLIST.md`.

## Canonical source

Edits belong in **`nt8/Strategies/`** first; run the sync script so this folder stays aligned.
