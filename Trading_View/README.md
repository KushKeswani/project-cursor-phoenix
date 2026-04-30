# TradingView — Phoenix visual layer (goals.md §8)

This folder ships **Pine v5** sources so the portable repo matches the parent Agent Phoenix layout (`Trading_View/*.pine`).

## Files

| File | Use |
|------|-----|
| `phoenix_range_mnq.pine` | Overlay indicator mirroring **MNQ** locked times (`range_start` 09:35–09:55 ET, trade window 11:00–13:00, `entry_tick_offset=2`, tick `0.25`). Apply on a **5-minute** chart; symbol can be `MNQ1!` or continuous proxy. |

Copy the `.pine` file into TradingView → Pine Editor → paste → Add to chart.

## Alert message fields (Phoenix terminology)

Configure alert **Webhook URL / notification** in TradingView; optional JSON-shaped strings for routing:

| `event` | Meaning |
|---------|---------|
| `range_sealed` | Opening range finished building; box highs/lows finalized for the session day. |
| `armed` | Range sealed **and** clock inside trade window (scanner would allow entries). |
| `breakout_touch` | Bar touched `long_level` or `short_level` (coarse; TV ≠ Python tick parity). |

TV **will not** match `scripts/engine/fast_engine.py` tick-for-tick; use for **visual / trader alerts** only (`goals.md` §8).

### Other instruments

Duplicate the indicator and set inputs to locked values from `scripts/configs/strategy_configs.py` (`bar_minutes`, range/trade minute grids, `entry_tick_offset`, tick size from `scripts/configs/tick_config.py`).
