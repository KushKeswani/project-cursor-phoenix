# Tradovate + NinjaTrader 8 — live checklist (Phoenix V4)

Use this before **Monday** (or any live session) so **data** and **session** match what the strategy and ProjectX assume (**US/Eastern** windows in `docs/INSTRUMENT_TIMEFRAMES.md`).

## 1. Connection

- [ ] NinjaTrader 8: **Connections** → Tradovate configured (login, environment: sim vs live as intended).
- [ ] Status shows **Connected** for the connection you will trade on.
- [ ] If you use **separate** data vs execution, note which series the **chart** uses (prefer **exchange-aligned** futures for MNQ/MGC/YM).

## 2. Instrument / contract

- [ ] Chart symbol is the **intended front contract** (e.g. MNQ **06-26** or current roll) — same idea as ProjectX contract search.
- [ ] **Instrument details** in NT: tick size **0.25** (MNQ), **0.10** (MGC), **1.0** (YM) — if wrong, stops and PnL will be off.
- [ ] Tradovate instrument names may differ slightly by feed; use the **CME** micro/mini future your broker lists for that symbol.

## 3. Bar type and session (critical for parity)

- [ ] **Bar period** matches the strategy: **5** min (MNQ, YM), **8** min (MGC), **12** min (CL if used).
- [ ] **Trading hours template** on the chart includes **08:00 ET** session start so pre-range bars exist (see `nt8/README.md`).
- [ ] **Timezone**: chart should reflect **exchange / Eastern** as you expect. If bars look shifted vs ProjectX logs, adjust strategy **Timezone Offset (minutes)** on the strategy parameters (same field as research NT8 notes).

## 4. Strategy instance

- [ ] Strategy: **RangeBreakout MNQ** / **MGC** / **YM** (from `live_implementation/Strategies` after sync + compile).
- [ ] **Contracts** and **Max entries per day** set to your risk plan.
- [ ] **Export Trades to CSV** (optional) for post-trade comparison with Python exports.

## 5. Sim vs live

- [ ] Confirm you are in **Tradovate sim** or **live** intentionally; Phoenix on ProjectX may be **practice/sim** even with `--live-order` depending on account — do not assume parity across two brokers without checking account type.

## 6. What Tradovate “handling data” means here

- NinjaTrader receives **ticks/bars** from the connection you assign to the chart. Tradovate provides **real-time** data compatible with NT’s series; the **V4 strategy** does not contain Tradovate-specific API calls — compatibility is at the **NinjaTrader platform** level (connection + instrument + session).
- If **historical** backtests on Tradovate data differ from `Data-DataBento` research, that is expected; this checklist is for **live forward** alignment with **session and bar settings**.

## 7. After the session

- [ ] Compare fills and times to `projectx/logs/projectx.log` if running Phoenix in parallel.
- [ ] Optional: `python3 scripts/verify_nt8_fidelity.py` with exported NT CSVs.
