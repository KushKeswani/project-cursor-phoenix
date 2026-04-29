# Portfolio sizing — $50k vs $150k, EOD drawdown, and Monte Carlo bust %

This note uses the same **Monte Carlo** definition as `scripts/backtester.py` → `bust_probability()`:

- **OOS** daily PnL from combined scaled trades produced by `run_portfolio_preset` / `backtester` (saved under `reports/` per run), **zero slippage** baseline.
- **60 trading days** (`EVAL_DAYS`) per simulation path.
- **Bust** if **either**:
  - **Trailing** loss from peak equity ≥ **EOD_DD**, or  
  - **Any single day** PnL ≤ **−DLL** (daily loss limit).

Simulations: **8,000** paths, seed **42** (same family as `run_portfolio_preset.py`).

---

## 1. Finding: **$2,000 EOD + bust &lt; 10% is not achievable** (this model)

We swept **Balanced-shaped** mixes `CL 1 × m, MGC 11 × m, MNQ 3 × m, YM 1 × m` (rounded, minimums) and **cannot** reach **bust ≤ 10%** with **EOD_DD = $2,000** for any size tested.

| Risk limit (example) | Smallest bust % seen (approx.) | Comment |
|------------------------|---------------------------------|---------|
| EOD $2,000 / DLL $1,200 (same 2:3 ratio as 5k/3k) | **~25%** | Even **CL 1 / MGC 3 / MNQ 1 / YM 1** (margin ~$22.9k) |
| EOD $2,000 / DLL $3,000** | **~18–19%** | Even **1 lot each** on all four (~$19.3k margin) |

**Why DLL $1,200 fails:** One **MNQ** lot can lose **~$1,700** in a day on OOS history (see worst-day stats). Any **DLL** below **~$1,700** per MNQ lot will **bust** constantly on the **single-day** rule, independent of the **$2k trailing** rule.

**Why $2k EOD still fails** even with **DLL $3,000:** Random **60-day** paths of resampled daily PnLs often **draw down more than $2,000** from a peak, so the **trailing** rule dominates.

**Conclusion (with CL in the mix):** To target **bust &lt; 10%** while still trading **crude**, you must **raise EOD** (and usually keep DLL at least **~$3,000** for a mix that includes MNQ), **not** only shrink position size.

**Update:** If you **drop CL** entirely, you *can* get **bust ~9–10%** with **EOD $2,000** — see **§8** and preset **`Balanced_50k`** (alias **`EOD2000_max_yield`**) / **`EOD2000_min_bust`**.

---

## 2. What *does* work for **bust &lt; 10%** (reference)

### Full **Balanced** (`CL 1, MGC 11, MNQ 3, YM 1`)

| EOD_DD | DLL | Approx. bust % (OOS, 8k sims) |
|--------|-----|-------------------------------|
| $5,000 | $3,000 | **~9.5%** (matches repo preset) |
| $4,500 | $3,000 | **~9.7%** |
| $4,000 | $3,000 | **~10.2%** (just over 10%) |
| $3,500 | $3,000 | **~11.2%** |
| $3,000 | $3,000 | **~13.3%** |
| $2,000 | $3,000 | **~41.6%** |

So **~$4,000–5,000 EOD** with **DLL $3,000** is the right band for **<10% bust** on this mix.

**Margin:** ~**$41,300** (CME-style initial margin estimate for full Balanced). Fits a **$50k** account if margin is **~82%** of capital (tight buffer).

### **~$19k / month** (scaled Balanced, approximate)

A **~0.64×** Balanced shape is **`CL 1, MGC 7, MNQ 2, YM 1`** (margin ~**$32,100**).

- OOS **average monthly** ~**$24.2k** (higher than “19k” — use as a rough scale, not exact).
- **Bust** with **$5,000 / $3,000** → **~9.3%** (slightly better than full Balanced).
- **Bust** with **$5,000 / $3,000** is the right band; **EOD ~$4,000 / DLL $3,000** → **~9.5%** bust.

---

## 3. **$50k account** — practical recommendation

| Goal | Suggestion |
|------|----------------|
| **Balanced** exposure + **bust &lt; 10%** in this MC | Use **full Balanced** or **1,7,2,1** with **EOD $5,000** (or **≥ ~$4,500**) and **DLL $3,000** — **not** **$2,000 EOD** with the same MC definition. |
| **Strict $2,000 EOD** | Expect **bust &gt; 20%** in this model unless you **change** the risk rules (e.g. longer eval, different bust definition, or no live MNQ at full size). |

---

## 4. **~$150k** account — **`Balanced_150k`** preset (full four-leg mix)

In this repo, **`Balanced_150k`** means the **same contracts as default `Balanced`**:

**`CL 1, MGC 11, MNQ 3, YM 1`** → margin ~**$41.3k** (CME-style est.).

That is the **notional “$150k account” labeling** for reports/visuals — it is **not** a larger contract count than `Balanced`.

**Monte Carlo** (repo defaults **EOD $5k / DLL $3k**): bust **~9.4%**, OOS **~$29.5k/mo** portfolio average (same as `Balanced`).

---

### 4b. **3× Balanced** — preset **`Balanced_3x`** (higher margin / 3× notional)

If you want **three times** the contract counts (for a much larger margin budget):

**`CL 3, MGC 33, MNQ 9, YM 3`** → margin ~**$123,900**.

**Scale prop limits 3×** with notional risk: **EOD $15,000**, **DLL $9,000**.

**Monte Carlo:** bust **~9.5%** — **same shape** as **1×** with **$5k / $3k** (linear scaling).

**OOS average monthly** (portfolio ~**$88.6k** / month) — **~3×** the **~$29.5k** full Balanced average.

**Do not** use arbitrary rounding (e.g. **4, 40, 11, 4**) **without** re-checking bust: uneven scaling can **raise** bust % vs **exact 3×**.

---

## 5. Reproduce

From repo root (adjust `--data-dir` if needed):

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced --oos-start 2023-01-01 --oos-end 2025-06-30
```

**Monte Carlo limits:** pass `--eod-dd` and `--dll` to match the account you are modeling (defaults remain **`scripts/backtester.py`** constants **5000 / 3000**). Example strict **$50k**-style MC on the combined series:

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced_50k --eod-dd 2000 --dll 2000
```

**Daily profit / loss lockout** (portfolio overlay — optional): after **+X** or **−Y** realized PnL in a calendar day (trades merged across legs in **exit_ts** order), later closed trades that **same day** are dropped from the backtest. Example:

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced_50k --daily-profit-lock 1500 --daily-loss-lock 1500
```

---

## 6. Summary

| Question | Answer |
|----------|--------|
| **$50k / $2k EOD / bust &lt; 10% / Balanced?** | **No** in this MC — **raise EOD** (and keep DLL **~$3k** for MNQ-sized daily risk) **or** accept **much higher** bust %. |
| **$50k / Balanced / bust &lt; 10%?** | **Yes** with **~$5k EOD** (repo default) and **~$41k margin**; tight vs **$50k** cash. |
| **~$150k label / full Balanced?** | Preset **`Balanced_150k`** = **`CL 1, MGC 11, MNQ 3, YM 1`** (same as **`Balanced`**); **~$41k** margin, **~$5k / $3k** MC. |
| **3× notional / ~$124k margin?** | **`Balanced_3x`**: **`CL 3, MGC 33, MNQ 9, YM 3`** + **EOD $15k / DLL $9k**; **~9.5%** bust. |

---

## 7. “3 minis max” = **30 micro contracts** (budget)

**Convention in this repo** (see `scripts/configs/portfolio_presets.py`):

- **1 E-mini** notional (e.g. NQ) ≈ **10 micro** contracts (e.g. MNQ) → **3 minis ⇒ cap 30 micros**.
- **Micro stack** = **MNQ + MGC + YM** (each counts **1**). **CL** is **not** a micro — it is a **separate** full-size lot and is **not** added into the **30** (count CL on its own for margin/risk).

**Examples**

| Profile | CL | MGC | MNQ | YM | Micro total (MGC+MNQ+YM) | Under 30? |
|--------|-----|-----|-----|-----|---------------------------|-----------|
| **Balanced** | 1 | 11 | 3 | 1 | **15** | Yes |
| **Balanced_50k_microcap** | 1 | 6 | 2 | 1 | **9** | Yes |

So the original **Balanced** mix (**15** micros) already respects a **30 micro** cap; the lighter **`Balanced_50k_microcap`** preset is for when you want **fewer** micro lots on a **~$50k** account, not because **15** exceeded **30**.

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced_50k_microcap
```

---

## 8. **EOD $2,000** — best contract sizing (this repo’s Monte Carlo)

**Assumption:** `bust_probability()` in `scripts/backtester.py` — **EOD $2,000** trailing from peak **or** any day **≤ −DLL** (use **DLL = $2,000** to match a strict prop), **60** trading days per path, **OOS** daily PnL from the same combined-series inputs the preset runner uses.

**Finding:** With **full Balanced** (`CL 1, MGC 11, MNQ 3, YM 1`), bust stays **~40%+** — **crude (CL)** plus size keeps **60-day** paths too volatile for a **$2k** trail.

**Workaround:** **Do not trade CL** (`CL = 0` in the preset). Then you can get **bust ≈ 9–10%** and still meaningful OOS monthly PnL.

| Preset | Contracts (CL / MGC / MNQ / YM) | ~Bust % | ~OOS avg month | ~Margin (CME est.) |
|--------|----------------------------------|--------|----------------|----------------------|
| **`Balanced_50k`** (`EOD2000_max_yield`) | **0 / 5 / 1 / 1** | **~9.7%** | **~$14.8k** | **~$20.0k** |
| **`EOD2000_min_bust`** | **0 / 2 / 1 / 1** | **~9.3%** | **~$12.3k** | **~$14.6k** |

**`MGC 6` / MNQ 1 / YM 1** (still no CL) pushes bust to **~10.3%** — just over a **10%** line.

**If you require CL:** the best **Balanced-shaped** shrink we tried was about **`CL 1, MGC 3, MNQ 1, YM 1`** — bust still **~19%** at **EOD $2k** (not fixable without **raising EOD** or **dropping CL**).

```bash
python3 scripts/run_portfolio_preset.py --profile Balanced_50k
python3 scripts/run_portfolio_preset.py --profile Balanced_150k   # same mix as Balanced; label for $150k reports
python3 scripts/run_portfolio_preset.py --profile Balanced_3x     # 3× contract counts
```

---

## 9. Survival presets, consistency, and uniform scaling

### 9.1 **`Balanced_50k_survival` / `Balanced_150k_survival`**

Extra presets in `scripts/configs/portfolio_presets.py` target **lower tail risk** than the high-MNQ **$50k** line or full **$150k** Balanced:

| Preset | CL | MGC | MNQ | YM | Note |
|--------|---:|----:|----:|---:|------|
| **Balanced_50k_survival** | 0 | 3 | 1 | 1 | Between `EOD2000_min_bust` and `Balanced_50k` |
| **Balanced_50k_survival_mgc4** | 0 | 4 | 1 | 1 | Slightly more MGC than survival |
| **Balanced_150k_survival** | 1 | 7 | 2 | 1 | Same shape as `Balanced_19k_approx` (~0.64× full Balanced) |
| **Balanced_150k_survival_nocl** | 0 | 8 | 2 | 1 | No crude — for DLL-sensitive sizing |

Re-run **`bust_probability`** with **`--eod-dd` / `--dll`** for your firm; numbers in preset notes are illustrative.

### 9.2 **Consistency rules vs uniform downscaling**

Many prop **consistency** rules compare **largest single winning day** to **cumulative profit**. If you scale **all** legs by the same factor \(k\), each day’s portfolio PnL scales by \(k\), so **that ratio is unchanged** on the same calendar path. **Changing the mix** (e.g. less MNQ, more MGC) changes the **shape** of daily PnL and can move consistency outcomes — verify on OOS by comparing preset outputs and daily PnL series from `run_portfolio_preset`.

### 9.3 **Daily lockout semantics**

- **Calendar day:** `exit_ts` normalized with `pandas` (same convention as `daily_pnl()`).
- **Ordering:** all scaled trades merged, sorted by **`exit_ts`**.
- **Crossing threshold:** the trade that crosses **+profit cap** or **−loss cap** is **kept**; subsequent trades that **session date** are **dropped** (research overlay only — not inside the per-instrument engine).
