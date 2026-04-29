# ProjectX live vs NinjaTrader `live_implementation`

This is a **concept map**, not a line-for-line port. ProjectX is **Python + Gateway REST + optional RTC**; NinjaTrader is **NinjaScript + your broker connection (Tradovate)**.

| Concern | ProjectX (`projectx.main`) | NinjaTrader V4 (`live_implementation/Strategies`) |
|--------|------------------------------|---------------------------------------------------|
| Signal / levels | `run_scan_once` → `fresh_entries` on Gateway or local bars | `OnBarUpdate` in `RangeBreakoutStrategyV4` (same window math intent) |
| Data | TopstepX / ProjectX **History** + `search_contracts` / `retrieveBars` | **Chart series** (Tradovate or other) |
| Orders | `OrderManager`, brackets, `--live-order`, `dry_run` in settings | NT **EnterLong/Short**, stops/targets per strategy code |
| Risk / prop | `risk` in `settings.yaml` | **You** size `Contracts` + account rules in Tradovate |
| Monday workflow | VPS: `python -m projectx.main --phoenix-auto --live-order` (after `.env`) | NT: enable strategy on **MNQ/MGC/YM** charts after checklist |

**Same Phoenix economics** (windows, SL/PT/trail rules) are defined in:

- Python: `scripts/configs/strategy_configs.py` + `fast_engine.py`
- NT: `RangeBreakoutStrategyV4.cs` + per-instrument subclasses in this folder

If behavior diverges, first verify **bar period, session template, and timezone** on the chart (`TRADOVATE_LIVE_CHECKLIST.md`), then run `scripts/compare_cs_engine_vs_python.py` on **saved OHLC** to isolate engine vs data.
