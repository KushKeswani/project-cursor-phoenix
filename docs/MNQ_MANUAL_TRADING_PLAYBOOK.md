# MNQ — Manual Trading Playbook

Single reference for the **locked** MNQ range-breakout strategy: rules aligned with `scripts/configs/strategy_configs.py`, `scripts/engine/fast_engine.py`, and reported backtest / execution-realism metrics in this repo.

**All session times are US Eastern (ET).**

---

## 1. Locked configuration (code reference)

| Setting | Value |
|---------|--------|
| Instrument | MNQ |
| Bar size | **5** minutes |
| Range window | **9:35–9:55** |
| Trade window | **11:00–13:00** |
| Close flat | **16:55** |
| Entry offset | **+2 ticks** above range high (long), **−2 ticks** below range low (short) |
| Stop loss | **80** ticks |
| Profit target | **240** ticks (3:1 vs SL) |
| Breakeven | **Off** |
| Trailing stop | **Off** |
| Max entries per day | **2** |
| Weekend | **No** trades Sat/Sun (`excluded_weekdays` in config) |

Config ID used in backtester: `MNQ_5m_1100_1300_SL80_RR3.0_T0_ME2_D0`.

Comment in repo (trade-window optimization): peak-liquidity window **11:00–13:00**; sweep noted **~$257k OOS at 0-tick slippage**, **~$244k at 3-tick**, PF **~3.14 / ~2.94** (see `strategy_configs.py` header).

---

## 2. Tick math (MNQ)

From `scripts/configs/tick_config.py`:

| Item | Value |
|------|--------|
| Tick size (price) | **0.25** index points |
| Tick value | **$0.50** per contract per tick |
| 80-tick SL | **20.00** points ≈ **$40** per contract |
| 240-tick PT | **60.00** points ≈ **$120** per contract |
| 2-tick offset | **0.50** points from range high/low |

Verify tick size and value on your broker’s spec sheet.

---

## 3. Manual trading checklist (session day)

Use this as a step-by-step list.

1. **Confirm session** — RTH-style day; **skip Saturday/Sunday**.
2. **9:35–9:55** — **Build the range**: track the **highest high** and **lowest low** during this window (matches bar-based backtest: each bar updates the range while `range_start ≤ bar_start < range_end`).
3. **After 9:55** — **Lock** range high and range low for the day.
4. **Compute levels**
   - **Long level** = range high **+ 2 ticks** (e.g. +0.50 if tick = 0.25).
   - **Short level** = range low **− 2 ticks**.
5. **Arm (reset) logic** (same idea as the algo)
   - **Long** is eligible only after price has traded **below** the long level (long “armed”).
   - **Short** is eligible only after price has traded **above** the short level (short “armed”).
6. **11:00–13:00 only** — Look for entries:
   - **Long**: armed and price **reaches or crosses above** the long level (conceptually a **buy stop** at the long level).
   - **Short**: armed and price **reaches or crosses below** the short level (conceptually a **sell stop** at the short level).
7. **If both sides could trigger on the same bar** — The Python engine applies a deterministic tie-break (**open** vs. levels, then the **closer** level). For manual trading, define your rule in advance (e.g. same tie-break or “first touch”).
8. **Stops and targets** — On fill: **stop 80 ticks** adverse, **limit/target 240 ticks** favorable. **No** breakeven move and **no** trail in this config.
9. **Max two entries** for the day — Align with the system’s max entries and cooldown/re-arm behavior after exits.
10. **16:55** — **Flatten** any open position (matches `close_all_minutes`).

**Optional:** Session filter in code uses bars between **8:00** and **18:00** for MNQ (`INSTRUMENT_GRIDS`); entries still only in **11:00–13:00** after the range is ready.

---

## 4. Entry / exit logic (algorithm summary)

Matches `fast_engine` / `strategy_configs` behavior:

- Range is built only while bar start time falls inside **9:35–9:55**.
- After the first bar with **start ≥ 9:55**, the range is finalized and **ATR-adaptive** logic does **not** apply to MNQ (MNQ uses fixed tick SL/PT).
- Entries require the **armed** state and a **stop-market** style trigger through the level.
- After a stop or target exit, the engine sets **cooldown** and re-arms using **close** vs. levels on the next step — manual traders should wait for a clean reset consistent with that idea before a second entry.

---

## 5. Reported results — metrics

Statistics below come from **this repository’s exports**. They are **historical / backtest / robustness-study** figures, not a guarantee of future performance. Read **contract counts** carefully.

### 5.1 Execution realism review — MNQ baseline **5 contracts**

Source: `reports/execution_realism_review/strategy_stability_summary.csv` (MNQ row). Total PnL is for the **5 MNQ** baseline bundle in that study.

| Metric | Value |
|--------|--------|
| Baseline total PnL (USD) | $257,547.50 |
| Baseline profit factor | 3.14 |
| Baseline daily Sharpe | 6.06 |
| Baseline trades / business day | ~1.39 |
| Slippage 3-tick total PnL (USD) | $244,122.50 |
| Slippage 3-tick profit factor | 2.94 |
| Slippage 3-tick daily Sharpe | 5.74 |
| Slippage retention vs baseline (%) | ~94.8% |
| Next-bar delay total PnL (USD) | $1,627.50 |
| Next-bar profit factor | 1.01 |
| Next-bar daily Sharpe | 0.08 |
| Next-bar retention (%) | ~0.63% |
| Limit-retest total PnL (USD) | $11,550.00 |
| Limit-retest profit factor | 1.11 |
| Limit-retest daily Sharpe | 0.62 |
| Limit-retest retention (%) | ~4.48% |
| Slippage assessment | Stable |
| Delay assessment | Moderate |
| Limit assessment | Moderate |
| Overall assessment | Moderate |

**OOS window and scaling note:** totals below are described over roughly **2023-01-01 to 2025-06-30** (~30 months). **Max drawdown ~$8,687 per 1 MNQ contract** in that window (execution-realism-style assumptions used when those figures were produced).

**Rough per-contract total (execution realism total ÷ 5):** ~**$51.5k** over that OOS window for **1 MNQ** if you linearly scale the **$257,547.50** figure (verify with raw trade CSVs if you need exact 1-lot stats).

---

### 5.2 Snapshot — MNQ @ **3 contracts** (Balanced portfolio preset)

**OOS 2023-01-01 to 2025-06-30**, Python engine, **Balanced** profile with **MNQ = 3 contracts** (from an archived deep-stats run; regenerate comparable tables with `run_portfolio_preset` / `backtester` if needed).

| Metric | Value |
|--------|--------|
| Contracts | 3 |
| Trades | 903 |
| Total PnL | $154,528.50 |
| Win rate | 52.38% |
| Profit factor | 3.14 |
| Expectancy (USD/trade) | $171.13 |
| Wins / losses | 473 / 430 |
| Gross win / gross loss | $226,699.50 / $72,171.00 |
| Avg win / avg loss | $479.28 / −$167.84 |
| Max win / max loss | $10,684.50 / −$4,972.50 |
| Max win streak / max loss streak | 11 / 6 |
| Long PnL / short PnL | $82,398.00 / $72,130.50 |
| Avg hold | 68.7 min |
| PnL P5 / P50 / P95 | −$120 / $74 / $777 |

To approximate **1 contract** from this block, divide **dollar** figures by **3** (trades count unchanged).

---

## 6. Why this variant is simpler for manual trading

- Fixed **SL / PT** only — no ATR, no breakeven, no trailing stop.
- Main operational risks: **correct range**, **correct offset**, **arm-then-breakout** discipline, and **fill quality** vs. backtest assumptions.

---

## 7. Regenerating or extending stats

- Portfolio + instrument breakdown: `python3 scripts/run_portfolio_preset.py --profile Balanced --data-dir Data-DataBento`
- Full multi-symbol sweep: `python3 scripts/backtester.py --data-dir Data-DataBento`

---

## 8. Related docs

- `docs/STRATEGY_LOGIC_EXPLAINED.md` — portfolio-wide one-liner for all four instruments
- `scripts/configs/strategy_configs.py` — authoritative numeric config
- `scripts/engine/fast_engine.py` — breakout engine and entry/arm logic
