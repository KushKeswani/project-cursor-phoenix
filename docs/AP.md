# AP — Agent Phoenix: prop data spec and algo comparison deliverables

This note is meant to be **shared** (e.g. with a friend comparing strategies). It ties together:

1. **What each column in the master spreadsheet means** (for filling gaps and sanity checks).
2. **What every algo / portfolio run should output** so comparisons are apples-to-apples.
3. **Where the live prop-firm table lives** in the repo.

---

## Master prop-firm table (source of truth)

**File:** [`prop_firm_accounts_master.csv`](prop_firm_accounts_master.csv)

- One row per **Firm × Account Name × Account Size** (notional label).
- Cells may be `Unknown` — simulation code should skip or approximate only where documented.
- **You** maintain accuracy vs current firm docs; re-export CSV when rules change.

### Column glossary

| Column | Use in simulation |
|--------|-------------------|
| Firm | Display / grouping |
| Account Name | Plan tier (eval vs funded path if mixed) |
| Account Size | Marketing notional ($25k, $50k, …) — not always margin |
| Profit Target | Eval pass threshold ($) |
| Max Drawdown | Trailing or static cap ($) for eval (see type) |
| Drawdown Type (EOD or Intraday) | **Critical:** intraday rules are not fully modeled on daily-only P&amp;L |
| Daily Loss Limit | Hard/soft DLL — note soft-breach in Notes |
| Consistency Rule | % of profit / best-day caps — needs exact parser per firm |
| Min / Max Trading Days | Eval calendar / activity gates |
| Max Contracts | Cap vs your backtest size |
| Payout Minimum | Funded bucket threshold ($) |
| Min Days Between Payouts | Cadence |
| Max Payout Per Request | Cap per withdrawal |
| Profit Split % | May be staged (`100 then 90`, `80 to 95`) — needs rule engine |
| Funded Max Drawdown / Type / DLL / Consistency | Post-eval survival + payouts |
| Fees | Activation, monthly, etc. — net economics |
| Notes | Source quirks (soft breach, progressive targets, …) |

---

## Deliverables checklist (per algo / portfolio)

Report **FULL** and **OOS** (or state single window) with identical date ranges when comparing two algos.

### A. Scope

- [ ] Data directory / symbol coverage  
- [ ] Execution model (e.g. zero-slippage stop touch)  
- [ ] **Contracts:** CL / MGC / MNQ / YM counts  

### B. Combined daily P&amp;L — calendar buckets

For **day, week, month, quarter, year** (each bucket = sum of daily P&amp;L in that period):

- [ ] **% green** — % of buckets with total P&amp;L &gt; 0  
- [ ] **Average** bucket P&amp;L  
- [ ] **Median** bucket P&amp;L  
- [ ] **Best** bucket P&amp;L  
- [ ] **Worst** bucket P&amp;L  
- [ ] **Std** (optional)  
- [ ] **N** periods  
- [ ] **Total P&amp;L** (should match sum of dailies)  

### C. Trade-level quality

- [ ] Win rate (%)  
- [ ] Profit factor  
- [ ] Expectancy ($/trade)  
- [ ] Trade Sharpe (if reported)  
- [ ] Daily Sharpe on combined daily series  

### D. Risk

- [ ] Max drawdown on **daily** equity (combined)  
- [ ] Optional: trade-level max DD  

### E. Prop evaluation (per row in `prop_firm_accounts_master.csv` you care about)

- [ ] Monte Carlo **pass %**, **bust %** (trailing vs DLL if split), **expire %**  
- [ ] Median **days to pass** (among passes)  
- [ ] Optional: rolling historical window pass rate  
- [ ] Document simplifications (e.g. EOD-only, cumulative P&amp;L from zero)  

### F. Prop funded — payout model (when parameters known)

- [ ] Payout count, average / median payout size  
- [ ] Payouts per trading year  
- [ ] Longest gap (calendar days) with no payout  
- [ ] **Net to trader** after split + fees (when split is single % or implemented staged rule)  

### G. Cash vs prop

- [ ] **Cash:** gross backtest P&amp;L at stated contracts  
- [ ] **Prop:** rule-filtered path + payout cadence (approximate until all columns filled)  

---

## Repo commands (Python reports)

See [`PYTHON_STATS_REFERENCE.md`](PYTHON_STATS_REFERENCE.md) — Agent Phoenix, complete merged report, funded payout report, PDF export.

---

## Disclaimer

Prop rules change. The CSV is a **working capture**, not legal advice. Simulations are **models**; verify critical numbers with each firm before trading or buying evaluations.
