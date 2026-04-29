# Agent Phoenix — live trading logic, backtest parity, and preset reference

This document describes how **Phoenix** decides when to trade in production (`python -m projectx.main --phoenix-auto`), how that maps to the **Python fast engine** used for research and the **`scripts/backtester.py`** pipeline, and where numbers can diverge from **TradingView** or manual replay. Every behavioral claim below is tied to specific Python modules in this repository.

---

## 1. What “Phoenix” is in this repo

Phoenix is **not** a separate ML model: it is a **range-breakout scanner** that:

1. Loads **session OHLC** bars per instrument (Gateway History API when live, or local parquet/CSV when using `--phoenix-data-dir`).
2. Runs the same **`run_backtest`** logic as research (`scripts/engine/fast_engine.py`) on the full bar window.
3. Detects a **new** trade that appears only when the **latest bar** is included (diff against `bars.iloc[:-1]`).
4. Converts engine stop/target distance into **USD risk/reward** and sends **ProjectX** bracket orders (market or stop-at-trigger), optionally after **arming** buy-stop and sell-stop legs at the sealed range levels.

Core orchestration lives in `projectx/main.py` (`_phoenix_round`) and `projectx/strategy/phoenix_auto.py` (`run_scan_once`, `fresh_entries_for_latest_bar`).

---

## 2. End-to-end live loop (polling)

Each poll (default **30s**, `--phoenix-poll-seconds`):

1. **`run_scan_once`** loads bars and runs the engine with diagnostics enabled.
2. **`_phoenix_arm_maintenance`** cancels stale **arm** orders outside the strategy session or when a position exists.
3. On **`range_sealed`**, Telegram/log messages fire once per session day per instrument (dedupe file under state dir).
4. If **`phoenix_arm_orders`** is on and not manual/dry-run, the executor may place **paired buy-stop / sell-stop** legs at `long_level` / `short_level` with brackets sized from synthetic risk (see §6).
5. **`hits`** from `fresh_entries_for_latest_bar` drive **new entry** handling: dedupe by fingerprint, optional skip if resting stop is invalid vs last close, then **`execute_dollar_risk_bracket`**.

```783:798:projectx/main.py
        def _phoenix_round() -> None:
            hits, diag_by_inst, range_audit_by_inst, bars_by_inst = run_scan_once(
                instruments=instruments,
                sizes=sizes,
                data_dir=data_path,
                client=use_client,
                gateway_sim=gateway_sim,
                imap=imap,
                as_of_et=None,
                tick_sizes=TICK_SIZES,
                tick_values=TICK_VALUES,
                get_config_fn=phoenix_get_config,
                collect_diagnostics=True,
                opening_range_addon_fetch=not bool(args.phoenix_no_range_addon_fetch),
                execution_options=phoenix_execution_options,
            )
```

**“Fresh entry” definition** (this is what makes live polling equivalent to “did the last closed bar create a new backtest trade?”):

```73:111:projectx/strategy/phoenix_auto.py
def fresh_entries_for_latest_bar(
    bars: pd.DataFrame,
    cfg: Any,
    tick_size: float,
    diagnostics: Optional[List[dict[str, Any]]] = None,
    execution: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Trades present when including the last bar but not when excluding it.
    ...
    """
    from engine.fast_engine import ExecutionOptions, run_backtest

    if len(bars) < min_bars_for_phoenix(cfg):
        return []
    exec_opts = execution if execution is not None else ExecutionOptions()
    full = run_backtest(
        cfg,
        bars,
        tick_size,
        return_trades=True,
        execution=exec_opts,
        diagnostics=diagnostics,
    )
    prev = run_backtest(
        cfg, bars.iloc[:-1], tick_size, return_trades=True, execution=exec_opts
    )
    ...
    for x in t_full:
        k = (_normalize_entry_ts(x["entry_ts"]), x["direction"])
        if k not in keys_prev:
            out.append(x)
    return out
```

---

## 3. Bar construction (critical for TradingView)

### 3.1 Session filter and resampling

1-minute data is filtered to **session hours** only, then resampled with **`label="left", closed="left"`** — the bar timestamp is the **open** of the interval, consistent with internal docs (`docs/INSTRUMENT_TIMEFRAMES.md`).

```104:128:scripts/engine/fast_engine.py
def resample_to_bars(
    df: pd.DataFrame, bar_minutes: int,
    session_start_hour: int = 8, session_end_hour: int = 17,
) -> pd.DataFrame:
    ...
    hours = df.index.hour
    df = df[(hours >= session_start_hour) & (hours < session_end_hour)]
    ...
    resampled = df.resample(f"{bar_minutes}min", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
```

Session hour grids per symbol:

```19:25:scripts/configs/tick_config.py
INSTRUMENT_GRIDS = {
    "CL": {"bar_minutes": 12, "session_start": 8, "session_end": 18},
    "MGC": {"bar_minutes": 8, "session_start": 8, "session_end": 17},
    "MNQ": {"bar_minutes": 5, "session_start": 8, "session_end": 18},
    "YM": {"bar_minutes": 5, "session_start": 8, "session_end": 18},
    ...
}
```

**TradingView checklist:** use the same **bar length**, **America/New_York** session anchor, and confirm whether your platform labels the bar at **bar open** vs **bar close**; off-by-one-bar alignment will change range highs/lows and triggers.

### 3.2 Data source quirks (backtester PnL vs “true” micro PnL)

```69:76:scripts/backtester.py
# DataBento-style OHLCV CSV in Data-DataBento: ts_event UTC, open/high/low/close, symbol.
# NQ minute bars drive MNQ strategy (same index; MNQ tick size from TICK_SIZES).
_DATABENTO_CSV_BY_INSTRUMENT: dict[str, str] = {
    "MNQ": "nq-data.csv",
    "MGC": "mgc-data.csv",
    "YM": "mym.csv",
    "CL": "mcl.csv",
}
```

For **YM**, loading **MYM** prices with **YM** tick economics emits an explicit warning — USD PnL in backtests may not match micro-Dow economics:

```179:184:scripts/backtester.py
        if instrument == "YM":
            warnings.warn(
                "Loading YM bars from MYM CSV (mym.csv): prices match Dow index; "
                "TICK_SIZES/TICK_VALUES are still YM mini — USD PnL may not match micro-Dow economics.",
                UserWarning,
                stacklevel=2,
            )
```

---

## 4. Per-instrument strategy presets (`FastConfig`)

All values below come from `scripts/configs/strategy_configs.py` and `scripts/configs/tick_config.py`.

| Instrument | Bar (min) | Range window (ET) | Trade window (ET) | Max entries/day | Risk model | Notes from code comments |
|------------|-----------|-------------------|-------------------|-----------------|------------|---------------------------|
| **CL** | 12 | 09:00–09:30 | 10:30–12:30 | 2 | Fixed ticks: SL 45, PT 135 (3:1); BE + trail | “~941 trades OOS” in liquidity window |
| **MGC** | 8 | 09:00–09:30 | 12:00–13:00 | 1 | **ATR-adaptive**: `sl_atr_mult=1.0`, `pt_atr_mult=3.0`, trail `trail_atr_mult=1.2` | Comments compare ATR vs fixed tick baselines (~25.4k ticks / PF ~5.26 vs fixed 30/90 ticks) |
| **MNQ** | 5 | 09:35–09:55 | 11:00–13:00 | 2 | Fixed: SL 80, PT 240 (3:1); no BE/trail | Comments: “$257k OOS at 0-tick, $244k at 3-tick, PF 3.14/2.94” |
| **YM** | 5 | 09:00–09:30 | 11:00–13:00 | 2 | Fixed: SL 25, PT 75; BE + trail | Comments: “$267k OOS at 0-tick, $250k at 3-tick, PF 7.50/6.35” |

Tick **size** and **USD per tick** (used by Phoenix for `$` sizing when not overridden by Gateway contract model):

```3:17:scripts/configs/tick_config.py
TICK_SIZES = {
    "CL": 0.01,
    "MGC": 0.10,
    "MNQ": 0.25,
    "YM": 1.0,
    ...
}

TICK_VALUES = {
    "CL": 10.00,
    "MGC": 1.00,
    "MNQ": 0.50,
    "YM": 5.00,
    ...
}
```

**`entry_tick_offset`** (in ticks) widens/narrows breakout triggers from the raw range:

- MNQ: `entry_tick_offset=2` → long level = `range_high + 2 * 0.25`, short = `range_low - 2 * 0.25`.
- MGC: `15` ticks × `0.10` = **1.5 points** beyond the box.

---

## 5. Engine logic — range, entries, exits

### 5.1 Building and sealing the opening range

For each bar whose **open-time minute-of-day** falls in `[range_start_minutes, range_end_minutes)`, the engine updates running `range_high` / `range_low`. On the **first bar with `bar_min >= range_end`**, it seals, computes `long_level` / `short_level`, and (for ATR mode) sets SL/PT/trail from **ATR(14) at seal bar** (with fallbacks).

```420:460:scripts/engine/fast_engine.py
        # Range building
        if rs <= bar_min < re:
            building_range = True
            if highs[i] > range_high:
                range_high = highs[i]
            if lows[i] < range_low:
                range_low = lows[i]
            continue

        if building_range and bar_min >= re:
            if range_high > -np.inf:
                range_ready = True
                long_armed = True
                short_armed = True
                if use_atr:
                    day_atr = bar_atr[i] if not np.isnan(bar_atr[i]) else bar_atr[max(0, i-1)]
                    ...
                    sl_pts = cfg.sl_atr_mult * day_atr
                    pt_pts = cfg.pt_atr_mult * day_atr
                    trail_by_pts = cfg.trail_atr_mult * day_atr
                    trail_start_pts = trail_by_pts * 1.05 + 5 * tick_size
                if diagnostics is not None:
                    ll = float(range_high + offset_pts)
                    ss = float(range_low - offset_pts)
                    diagnostics.append(
                        {
                            "kind": "range_sealed",
                            ...
                            "long_level": ll,
                            "short_level": ss,
```

### 5.2 Entry signal (default `touch` mode)

Inside the trade window, with range ready and not in a position:

- **Long raw:** `long_armed and highs[i] >= long_level`
- **Short raw:** `short_armed and lows[i] <= short_level`

```613:627:scripts/engine/fast_engine.py
        # Entry
        if not in_position and entries_today < cfg.max_entries_per_day:
            long_raw = allow_long and long_armed and highs[i] >= long_level
            short_raw = allow_short and short_armed and lows[i] <= short_level
            if execution.entry_fill_mode == "touch_strict":
                long_hit = long_raw and _touch_fill_credible_long(
                    long_level, lows[i], tick_size
                )
                short_hit = short_raw and _touch_fill_credible_short(
                    short_level, highs[i], tick_size
                )
            else:
                # touch, touch_legacy, stop_market, next_bar_open: use raw bar vs level for entry signal
                long_hit = long_raw
                short_hit = short_raw
```

**Default fill price** for `touch` / zero slippage: long fills at **`long_level + entry_slippage_pts`** via `_fill_touch_buy` (and analog for short). With `ExecutionOptions.stop_slippage_ticks = 0` and no overrides, entry is **at the trigger price in points** (still subject to your broker in live).

```194:199:scripts/engine/fast_engine.py
def _fill_touch_buy(trigger_price: float, slippage_pts: float) -> float:
    return float(trigger_price + slippage_pts)

def _fill_touch_sell(trigger_price: float, slippage_pts: float) -> float:
    return float(trigger_price - slippage_pts)
```

**Simultaneous long+short hit** on the same bar uses **distance of the bar open** to each side to break the tie (or open on one side only):

```629:686:scripts/engine/fast_engine.py
            if long_hit and short_hit:
                if opens[i] >= long_level:
                    ...
                elif opens[i] <= short_level:
                    ...
                elif (long_level - opens[i]) <= (opens[i] - short_level):
                    ...  # long
                else:
                    ...  # short
```

### 5.3 Exits

- **Stop:** if low/high breaches `stop_price`, exit uses `_fill_touch_sell` / `_fill_touch_buy` on the stop **level** (or `stop_market` path if configured).
- **Profit target:** limit-style fill vs **bar open** (`_fill_limit_sell` / `_fill_limit_buy`).
- **Breakeven / trail:** as configured per instrument.
- **Flatten:** bars starting at or after `close_all_minutes` (16:55 ET) or last bar of session day force flat using minute-bar lookup when available.

---

## 6. How live orders differ from the idealized engine

### 6.1 Engine `$` risk/reward used for brackets

Phoenix computes **total** SL and TP dollars for the **actual position size** using the same tick distances the engine used at the entry bar index:

```114:145:projectx/strategy/phoenix_auto.py
def risk_reward_usd(
    instrument: str,
    cfg: Any,
    trade: dict[str, Any],
    bars: pd.DataFrame,
    contracts: int,
    tick_size: float,
    tick_value: float,
) -> tuple[float, float]:
    """Total $ SL and TP across ``contracts`` matching engine sizing at entry."""
    from engine.fast_engine import compute_bar_atr

    i = int(trade["entry_bar_idx"])
    if cfg.atr_adaptive:
        ...
        sl_pts = float(cfg.sl_atr_mult) * a
        tp_pts = float(cfg.pt_atr_mult) * a
    else:
        sl_pts = float(cfg.stop_loss_ticks) * tick_size
        tp_pts = float(cfg.profit_target_ticks) * tick_size

    sl_ticks = sl_pts / tick_size
    tp_ticks = tp_pts / tick_size
    risk_usd = sl_ticks * tick_value * float(contracts)
    reward_usd = tp_ticks * tick_value * float(contracts)
    return float(risk_usd), float(reward_usd)
```

### 6.2 Gateway tick model vs `TICK_VALUES`

Research uses **`TICK_VALUES` from `tick_config.py`**. Live **`execute_dollar_risk_bracket`** converts `$` to integer bracket ticks using **`ContractModel.tickValue` from the API**:

```123:141:projectx/execution/executor.py
        contract = self.resolve_contract(
            symbol_u, instrument_cfg, live=live_contracts
        )
        contract_id = contract["id"]
        tick_size = float(contract.get("tickSize") or 0.0)
        tick_value = float(contract.get("tickValue") or 0.0)
        ...
        sl_u, tp_u = dollar_risk_to_bracket_ticks(
            risk_usd=risk_usd,
            reward_usd=reward_usd,
            tick_value=tick_value,
            contracts=size,
        )
```

```151:169:projectx/utils/helpers.py
def dollar_risk_to_bracket_ticks(
    *,
    risk_usd: float,
    reward_usd: float,
    tick_value: float,
    contracts: int,
) -> tuple[int, int]:
    ...
    usd_per_tick = tick_value * float(contracts)
    sl_ticks = max(1, int(round(risk_usd / usd_per_tick)))
    tp_ticks = max(1, int(round(reward_usd / usd_per_tick)))
    return sl_ticks, tp_ticks
```

So **integer rounding** of tick counts and any **API vs CME-assumption tickValue mismatch** will change realized `$` vs the float math in `risk_reward_usd`.

### 6.3 Stop-at-trigger vs engine “touch fill”

With **`execution.phoenix_entry_order: limit`** (meaning **stop @ trigger**, not a passive limit), live can **skip** sending an order when the exchange would reject a resting stop because price has **already traded through** the trigger. The repo documents this explicitly:

```31:39:projectx/config/settings.yaml
  # With phoenix_entry_order: limit, ProjectX sends a resting **stop** at the engine trigger price.
  # If the last bar close is already through that level, the exchange treats the buy/sell stop as
  # invalid vs last — see entry_breakout_stop_valid in projectx/strategy/phoenix_auto.py. The engine
  # may still model a fill at the trigger (zero-slippage touch), so live can **skip** while backtest
  # shows a trade.
```

Validation:

```749:770:projectx/strategy/phoenix_auto.py
def entry_breakout_stop_valid(
    side: str,
    stop_trigger: float,
    last_reference: float,
    tick_size: float,
) -> bool:
    """Whether a resting buy/sell **stop** at ``stop_trigger`` is acceptable vs ``last_reference``.
    ...
    """
    ...
    if s in ("long", "buy"):
        return lr < st - buf
    if s in ("short", "sell"):
        return lr > st + buf
    return False
```

**Arm orders** (`execute_phoenix_arm_breakout_pair`) try to place stops **before** price runs through; legs can still be skipped when not valid vs last (`arm_exchange_valid_stop_legs`).

### 6.4 Partial bars from Gateway

`fetch_bars_gateway_for_instrument` requests **`includePartialBar: True`**. The live engine therefore sees the **in-progress** bar, while a strict “closed bar only” manual process may differ until the bar closes.

---

## 7. Python backtester — how metrics are built

Default instruments and **research contract counts** (not the same as portfolio presets — see §8):

```29:39:scripts/backtester.py
INSTRUMENTS = ["CL", "MGC", "MNQ", "YM"]
CONFIG_IDS = {
    "CL": "CL_12m_1030_1230_SL45_RR3.0_T10_ME2_D3",
    "MGC": "MGC_8m_900_ATR_SL1.0_RR3.0_ME1_D0",
    "MNQ": "MNQ_5m_1100_1300_SL80_RR3.0_T0_ME2_D0",
    "YM": "YM_5m_1100_1300_SL25_RR3.0_T25_ME2_D0",
}
BASE_CONTRACTS = {"CL": 1, "MGC": 5, "MNQ": 5, "YM": 1}
EOD_DD = 5000.0
DLL = 3000.0
EVAL_DAYS = 60
```

Per-trade USD:

```230:247:scripts/backtester.py
def scaled_trades(raw_trades: pd.DataFrame, instrument: str, contracts: int) -> pd.DataFrame:
    ...
    trades["pnl_usd"] = trades["pnl_ticks"].astype(float) * TICK_VALUES[instrument] * contracts
```

Aggregate stats use **exit-date** grouping for daily series and standard formulas, e.g.:

```297:317:scripts/backtester.py
def trade_metrics(pnls_usd: np.ndarray) -> dict[str, float]:
    ...
    return {
        "n_trades": int(n),
        "win_rate": float(len(wins) / n * 100.0),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else 0.0,
        "expectancy": float(np.mean(pnls_usd)),
        "sharpe": trade_sharpe(pnls_usd.astype(float)),
    }
```

**Slippage / fill mode:** pass `ExecutionOptions` into `run_backtest` (Phoenix uses `entry_fill_mode` from `--phoenix-entry-fill` / `execution.phoenix_entry_fill`). Default in engine is **`touch`** with **0** slippage ticks unless you change it.

---

## 8. Four portfolio presets (contract stacks)

These presets are **position sizing only**; they do **not** change `FastConfig` thresholds. Source: `scripts/configs/portfolio_presets.py`.

| Preset key | CL | MGC | MNQ | YM | Micro stack note |
|------------|-----|-----|-----|-----|-------------------|
| `Balanced_50k_high` | 0 | 5 | 4 | 1 | No CL; `MICRO_CAP` commentary: MNQ+MGC+YM ≤ 30 micros |
| `Balanced_50k_survival` | 0 | 3 | 1 | 1 | No CL |
| `Balanced_150k_high` | 1 | 11 | 3 | 1 | “Full four-leg mix” |
| `Balanced_150k_survival` | 1 | 7 | 2 | 1 | “~0.64× full Balanced” |

```23:44:scripts/configs/portfolio_presets.py
PORTFOLIO_PRESETS = {
    "Balanced_50k_high": {"CL": 0, "MGC": 5, "MNQ": 4, "YM": 1},
    "Balanced_50k_survival": {"CL": 0, "MGC": 3, "MNQ": 1, "YM": 1},
    "Balanced_150k_high": dict(_FULL_BALANCED),
    "Balanced_150k_survival": {"CL": 1, "MGC": 7, "MNQ": 2, "YM": 1},
}

PRESET_NOTES = {
    "Balanced_50k_high": (
        "50k high — no CL. CL 0 / MGC 5 / MNQ 4 / YM 1. Re-run MC with your EOD/DLL."
    ),
    ...
    "Balanced_150k_high": (
        "150k high — CL 1 / MGC 11 / MNQ 3 / YM 1. EOD $5k / DLL $3k MC band in past sweeps."
    ),
    "Balanced_150k_survival": (
        "150k survival — CL 1 / MGC 7 / MNQ 2 / YM 1 (~0.64× full Balanced). "
        "Typical MC band: EOD $5k / DLL $3k."
    ),
}
```

Live Phoenix contract counts come from **`--phoenix-contracts`** (parsed in `_parse_phoenix_contracts`), not automatically from these presets unless your deployment script sets them that way.

### 8.1 Frozen portfolio metrics in this repo (`reports/`)

The CSVs under `reports/` are **saved outputs** from a prior full run of the portfolio machinery (merged legs, same engine — regenerate with your data window before trusting them for forward decisions). They are useful as **internal consistency checks** when you compare TradingView or live fills.

**`reports/phoenix_master_extended_metrics.csv`** (selected columns; `FULL` = full sample, `OOS` = out-of-sample slice used when that report was built):

| Preset | Period | `total_pnl_usd` | `n_trades` | `trade_win_rate_pct` | `profit_factor` | `expectancy_usd` | `max_drawdown_usd` |
|--------|--------|-----------------:|----------:|---------------------:|----------------:|-----------------:|-------------------:|
| Balanced_50k_high | FULL | 1,632,943.62 | 7,596 | 47.24 | 4.91 | 214.97 | 6,638.58 |
| Balanced_50k_high | OOS | 599,828.73 | 3,308 | 44.04 | 4.59 | 181.33 | 6,638.58 |
| Balanced_50k_survival | FULL | 1,119,692.97 | 7,596 | 47.24 | 6.37 | 147.41 | 3,378.00 |
| Balanced_50k_survival | OOS | 394,449.94 | 3,308 | 44.04 | 5.76 | 119.24 | 3,378.00 |
| Balanced_150k_high | FULL | 2,349,925.57 | 7,596 | 64.57 | 4.57 | 309.36 | 8,370.00 |
| Balanced_150k_high | OOS | 885,950.11 | 3,308 | 65.93 | 4.31 | 267.82 | 5,759.38 |
| Balanced_150k_survival | FULL | 1,918,214.27 | 7,596 | 64.57 | 4.62 | 252.53 | 5,250.00 |
| Balanced_150k_survival | OOS | 732,740.03 | 3,308 | 65.93 | 4.33 | 221.51 | 3,963.01 |

Note: **`n_trades` is identical across presets** in this file because the same raw trade stream is merged with different contract weights; **win rate** can still differ when measured at the **portfolio** level because the merged stream differs — the CSV’s `trade_win_rate_pct` here reflects **per-leg trade outcomes** after scaling, not unweighted instrument counts.

**`reports/phoenix_master_payout_metrics.csv`** holds **payout / evaluation-style** summaries (e.g. `hist_total_withdrawn_usd`, Monte Carlo columns) for the same four presets — open that file for payout model parameters (`model` column).

---

## 9. Validating “botched numbers” — recommended workflow

1. **Lock fill assumptions:** run backtests with the same `ExecutionOptions.entry_fill_mode` as live (`touch` vs `touch_strict` vs slippage ticks). Definitions are in `ExecutionOptions` docstring in `fast_engine.py`.
2. **Replay causally:** use `scripts/generate_live_replay_vs_backtest_report.py` / `scripts/phoenix_live_pace_replay.py` (see module docstrings) to compare **live-paced** trade lists to contiguous `run_backtest` on the same window — this targets **lookahead** and **bar inclusion** bugs.
3. **TradingView:** rebuild **left-labeled** bars from 1m (or use TV only after confirming TV’s bar timestamps match Python’s `resample_to_bars` convention). Plot horizontal lines at **`long_level` / `short_level`** from the sealed range (see `Trading_View/range_box_indicator.pine` if you keep that in sync with `range_start_minutes` / `range_end_minutes` / offsets).
4. **Watch parity logs:** `projectx/main.py` logs lines like `Phoenix.parity kind=round` and skip reasons (`entry_breakout_stop_invalid`, `dedupe`, `risk`, etc.) — use these to explain a TV fill that Python marks as skipped.

---

## 10. Summary — largest sources of backtest vs live divergence

| Topic | Backtest / research | Live Phoenix |
|--------|----------------------|--------------|
| Triggered stop rejected | Engine may still “fill” at trigger with `touch` | `entry_breakout_stop_valid` → **no API order** |
| Tick `$` | `TICK_VALUES` in Python | Gateway **`tickValue`** + integer **`dollar_risk_to_bracket_ticks`** rounding |
| Bar source | Parquet / CSV rules in `load_bars` | Gateway bars + **`includePartialBar: True`** |
| YM from MYM CSV | Documented USD mismatch risk | N/A if you trade YM with correct contract |
| MNQ from NQ CSV | Index alignment; MNQ tick size applied | Live MNQ contract |

This file is descriptive only; it does not guarantee future performance or exchange behavior.
