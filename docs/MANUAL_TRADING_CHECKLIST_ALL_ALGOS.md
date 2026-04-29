# Manual trading checklist — all algos (range breakout)

**Session times: US Eastern (ET).** Skip **Saturday / Sunday** (same as `excluded_weekdays` in config).

**Idea (all four):** Build a **morning range** (high / low), then trade **breakouts** of that range (with tick **offset**). **Arm** first (price must trade to the “wrong” side of your trigger), then enter on **stop** through the level — not a fade back into the range.

**End of day:** Flatten by **4:55 PM ET** (or last bar you use).

**Tick sizes / $ per tick (verify on your broker):** CL **$10**, MGC **$1**, MNQ **$0.50**, YM **$5** (repo defaults).

---

## CL — Crude Oil

| Step | Check |
|------|--------|
| ☐ | **Chart:** **12-minute** bars (aligned to how you’ll define the range). |
| ☐ | **9:00–9:30** — Track **range high** and **range low** (update each bar in window). |
| ☐ | After **9:30** — Lock range for the day. |
| ☐ | **Long level** = range high **+ 0 ticks**. **Short level** = range low **− 0 ticks**. |
| ☐ | **Arm long** after price trades **below** long level; **arm short** after price trades **above** short level. |
| ☐ | **Trade only 10:30 AM – 12:30 PM** — Long: buy stop at long level when armed. Short: sell stop at short level when armed. |
| ☐ | **Stop:** **45 ticks**. **Target:** **135 ticks** (3:1). |
| ☐ | **Breakeven:** After **+30 ticks** favorable → stop ≈ **entry + 4 ticks** (long) / **entry − 4 ticks** (short). |
| ☐ | **Trail:** After **+15 ticks** favorable — trail **10 ticks** from best price, stepped in **5-tick** increments from entry. |
| ☐ | **Max 2** entries per day (respect cooldown / re-arm after exits). |
| ☐ | **4:55 PM** — flat. |

---

## MGC — Micro Gold

### Locked fixed ticks (no ATR) — **recommended for manual**

Repo constants: `MGC_MANUAL_FIXED_SL_TICKS` / `MGC_MANUAL_FIXED_PT_TICKS` in `scripts/configs/strategy_configs.py`.

| Step | Check |
|------|--------|
| ☐ | **Chart:** **8-minute** bars. |
| ☐ | **9:00–9:30** — Build range high / low. |
| ☐ | After **9:30** — Lock range (**no** ATR math). |
| ☐ | **Long level** = range high **+ 15 ticks**. **Short level** = range low **− 15 ticks**. |
| ☐ | **Arm** long / short (below long level / above short level) before breakout. |
| ☐ | **Trade only 12:00 PM – 1:00 PM** — Stops at levels. |
| ☐ | **Stop:** **30 ticks**. **Target:** **90 ticks** (3:1). **No** trail (simplest). |
| ☐ | **No** breakeven in this fixed preset. |
| ☐ | **Max 1** entry per day. |
| ☐ | **4:55 PM** — flat. |

**Why 30 / 90:** OOS backtest sweep (fixed 3:1, no trail) vs the live ATR algo — **30/90** is close to typical stop distance (~median loss ≈ 29 ticks), round numbers, and similar economics to ATR on the same window. **Alternatives:** **28 / 84** (slightly tighter), **35 / 105** (slightly wider). **Tighter still:** **18 / 54** (higher win rate / PF in sim, much smaller stops — more noise stops).

### Algo default (ATR-adaptive)

| Step | Check |
|------|--------|
| ☐ | After range lock — **ATR(14)** on **8m** at range completion. |
| ☐ | **SL ≈ 1× ATR**, **PT ≈ 3× ATR**, trail ≈ **1.2× ATR** after **~1.05× trail + 5 ticks** favorable. |

---

## MNQ — Micro Nasdaq

| Step | Check |
|------|--------|
| ☐ | **Chart:** **5-minute** bars. |
| ☐ | **9:35–9:55** — Build range high / low. |
| ☐ | After **9:55** — Lock range. |
| ☐ | **Long level** = range high **+ 2 ticks**. **Short level** = range low **− 2 ticks**. |
| ☐ | **Arm** then breakout (same arming rules as above). |
| ☐ | **Trade only 11:00 AM – 1:00 PM** — Stops at levels. |
| ☐ | **Stop:** **80 ticks**. **Target:** **240 ticks** (3:1). |
| ☐ | **No** breakeven, **no** trail. |
| ☐ | **Max 2** entries per day. |
| ☐ | **4:55 PM** — flat. |

---

## YM — Micro Dow

| Step | Check |
|------|--------|
| ☐ | **Chart:** **5-minute** bars. |
| ☐ | **9:00–9:30** — Build range high / low. |
| ☐ | After **9:30** — Lock range. |
| ☐ | **Long level** = range high **+ 5 ticks**. **Short level** = range low **− 5 ticks**. |
| ☐ | **Arm** then breakout. |
| ☐ | **Trade only 11:00 AM – 1:00 PM** — Stops at levels. |
| ☐ | **Stop:** **25 ticks**. **Target:** **75 ticks** (3:1). |
| ☐ | **Breakeven:** After **+82 ticks** favorable → stop **1 tick** past entry (long: entry+1; short: entry−1). |
| ☐ | **Trail:** After **+31 ticks** favorable — trail **25 ticks** from best, **5-tick** steps from entry. |
| ☐ | **Max 2** entries per day. |
| ☐ | **4:55 PM** — flat. |

---

## Quick reference

| Symbol | Bar | Range (ET) | Trade window (ET) | Offset | SL / PT (ticks) | BE / trail | Max/day |
|--------|-----|------------|-------------------|--------|------------------|------------|---------|
| **CL** | 12m | 9:00–9:30 | 10:30–12:30 | 0 | 45 / 135 | Yes / yes | 2 |
| **MGC** | 8m | 9:00–9:30 | 12:00–1:00 | 15 | **30 / 90** (manual) or ATR 1×/3× | optional trail off | 1 |
| **MNQ** | 5m | 9:35–9:55 | 11:00–1:00 | 2 | 80 / 240 | No / no | 2 |
| **YM** | 5m | 9:00–9:30 | 11:00–1:00 | 5 | 25 / 75 | Yes / yes | 2 |

Config source: `scripts/configs/strategy_configs.py` · Engine: `scripts/engine/fast_engine.py`.
