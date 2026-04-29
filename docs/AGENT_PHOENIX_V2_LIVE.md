# Agent Phoenix V2 — Live implementation (NinjaTrader 8 + ProjectX)

Single entry point for **production-style** execution: **NinjaTrader 8** (chart-attached strategies) and **ProjectX / Gateway** (Python API runner). Research and replay stay on `dev`; treat this doc as the **V2 live tab**—paths, checklists, and how the two stacks relate.

**V1 (research core):** Python `fast_engine` + parquet backtests + live-pace replay (`scripts/`).  
**V2 (live):** NT8 strategies **or** `projectx/` against your firm Gateway—same Phoenix range-breakout rules, different transport.

---

## Quick comparison

| | **NinjaTrader 8** | **ProjectX (Gateway)** |
|---|-------------------|-------------------------|
| **Code** | `nt8/Strategies/*.cs`, synced bundle `nt8/live_implementation/` | `projectx/` (`main.py`, `execution/`, `strategy/phoenix_auto.py`) |
| **Data** | Chart series | API history (+ optional local data for tests) |
| **Orders** | NinjaTrader managed stops / brackets | REST + hub listener; `--phoenix-auto`, `--live-order` |
| **Config** | Strategy parameters + chart template | `projectx/config/settings.yaml`, `projectx/.env` |
| **Parity check** | `scripts/verify_nt8_fidelity.py` | Compare to `phoenix_live_pace_replay` / `docs/LIVE_SCRIPTS.md` |

---

## 1. NinjaTrader 8 (live)

1. **Install / compile** — Follow **`nt8/README.md`**: copy strategies into NinjaTrader Custom Strategies folder, compile, attach **RangeBreakout CL / MGC / MNQ / YM** with the correct bar period.

2. **Tradovate / synced live bundle** — **`nt8/live_implementation/`** (checklist + `PROJECTX_PARITY.md`). Sync: `scripts/sync_nt8_live_implementation.ps1` (Windows) or `scripts/sync_nt8_live_implementation.sh`. Read **`nt8/live_implementation/TRADOVATE_LIVE_CHECKLIST.md`** before going live.

3. **Bar periods and ET windows** — **`docs/INSTRUMENT_TIMEFRAMES.md`**

4. **Optional CSV parity vs Python** — `python3 scripts/verify_nt8_fidelity.py --nt8-dir "<path>"`

---

## 2. ProjectX (Gateway live)

1. `pip install -r projectx/requirements.txt` — copy **`projectx/.env.example`** to **`projectx/.env`**. Set **`trading.account_id`** in **`projectx/config/settings.yaml`** or env.

2. API host: see **`projectx/config/settings.yaml`** (default Topstep-style; other firms may differ).

3. `execution.dry_run: true` = no real orders. **`--live-order`** sends live orders; **`--phoenix-auto --phoenix-manual`** = signals only.

4. From repo root: `python -m projectx.main --list-accounts` then `--phoenix-auto --phoenix-manual` or `--live-order`. See `python -m projectx.main --help`.

5. Risk/session: **`projectx/config/settings.yaml`** `risk:` block.

6. Full runbook: **`docs/LIVE_SCRIPTS.md`**

---

## 3. Git branch **agent-pheonix-v2**

Use branch **`agent-pheonix-v2`** for live-focused NT8 + ProjectX work; merge to `dev` when ready.

---

## 4. Disclaimer

Live trading has risk of loss. Confirm sim/eval accounts and firm rules before real orders.
