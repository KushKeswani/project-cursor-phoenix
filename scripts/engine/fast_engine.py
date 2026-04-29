#!/usr/bin/env python3
"""
Fast NumPy-based range breakout engine for parameter sweeps.

Key speedups over range_breakout_engine.py:
  1. Uses numpy arrays instead of DataFrame iteration
  2. Pre-computes daily ranges once per range window config
  3. Tight inner loop with minimal overhead

Trade-off: slightly simplified trailing stop (same granularity as
the original engine but ~50x faster).
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any, List, Optional

import numpy as np
import pandas as pd

# Shared Sharpe for validation consistency
_ppr = Path(__file__).resolve().parent.parent.parent / "prop-portfolio-research"
if _ppr.exists() and str(_ppr) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_ppr))
try:
    from src.common.metrics import compute_sharpe as _compute_sharpe_shared
except ImportError:
    _compute_sharpe_shared = None


@dataclass
class FastConfig:
    instrument: str = ""
    bar_minutes: int = 5
    direction: str = "both"  # "both", "long", "short"
    entry_tick_offset: int = 0
    range_start_minutes: int = 570  # 9:30 = 9*60+30
    range_end_minutes: int = 595    # 9:55
    trade_start_minutes: int = 575  # 9:35
    trade_end_minutes: int = 890    # 14:50
    close_all_minutes: int = 1015   # 16:55
    stop_loss_ticks: float = 90
    profit_target_ticks: float = 290
    breakeven_on: bool = False
    breakeven_after_ticks: float = 30
    breakeven_offset: float = 0
    trail_on: bool = True
    trail_by_ticks: float = 170
    trail_start_after_ticks: float = 175
    trail_frequency: float = 50
    excluded_weekdays: set = None  # {0=Mon, ..., 4=Fri}
    max_entries_per_day: int = 3  # 2-3 tpd per plan
    # ATR-adaptive mode: when True, SL/PT/trail are ATR multiples instead of ticks
    atr_adaptive: bool = False
    sl_atr_mult: float = 1.5
    pt_atr_mult: float = 3.0
    trail_atr_mult: float = 1.5

    def __post_init__(self):
        if self.excluded_weekdays is None:
            self.excluded_weekdays = {5, 6}


@dataclass
class ExecutionOptions:
    """Execution realism settings layered on top of the strategy logic."""

    # "touch" = high>=long_level / low<=short_level (same as git initial commit; Balanced ~$2.3M+ full-sample research).
    # "touch_strict" = also require wick through trigger (low<=long, high>=short).
    # "touch_legacy" = alias of "touch".
    entry_fill_mode: str = "touch"  # "touch", "touch_strict", "touch_legacy", "stop_market", or "next_bar_open"
    stop_slippage_ticks: float = 0.0  # Used for both entry and stop exits unless overridden
    close_slippage_ticks: float = 0.0
    # Optional: override for entry-only or exit-only slippage (for diagnostics)
    entry_slippage_ticks: Optional[float] = None  # None = use stop_slippage_ticks
    exit_slippage_ticks: Optional[float] = None   # None = use stop_slippage_ticks


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def compute_bar_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                    period: int = 14) -> np.ndarray:
    """Compute ATR(period) on bar arrays. Returns array same length as input."""
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
    atr_out = np.full(n, np.nan)
    if n < period:
        return atr_out
    atr_out[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        atr_out[i] = (atr_out[i - 1] * (period - 1) + tr[i]) / period
    return atr_out


def resample_to_bars(
    df: pd.DataFrame, bar_minutes: int,
    session_start_hour: int = 8, session_end_hour: int = 17,
) -> pd.DataFrame:
    """
    Resample 1-min data to target bar size, filtering to session hours only.
    This dramatically reduces bar count (~3-4x) and speeds up backtests.
    """
    if "datetime" in df.columns:
        df = df.set_index("datetime")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    # Filter to session hours only (drop overnight bars)
    hours = df.index.hour
    df = df[(hours >= session_start_hour) & (hours < session_end_hour)]
    minute_bars = df[["open", "high", "low", "close"]].copy()

    if bar_minutes <= 1:
        return minute_bars
    resampled = df.resample(f"{bar_minutes}min", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    resampled.attrs["source_minute_bars"] = minute_bars
    return resampled


def build_flatten_lookup(bars: pd.DataFrame, close_all_minutes: int) -> dict:
    minute_bars = bars.attrs.get("source_minute_bars")
    if not isinstance(minute_bars, pd.DataFrame) or minute_bars.empty:
        minute_bars = bars[["open", "high", "low", "close"]].copy()

    lookup = {}
    for trade_date, group in minute_bars.groupby(minute_bars.index.date):
        minutes = np.array([ts.hour * 60 + ts.minute for ts in group.index], dtype=np.int32)
        exact_idx = np.where(minutes == close_all_minutes)[0]
        if len(exact_idx):
            idx = int(exact_idx[0])
        else:
            before_idx = np.where(minutes <= close_all_minutes)[0]
            idx = int(before_idx[-1]) if len(before_idx) else 0
        lookup[trade_date] = (group.index[idx], float(group["close"].iloc[idx]))
    return lookup


def resolve_flatten_exit(flatten_lookup: dict, trade_date, fallback_ts, fallback_close: float):
    return flatten_lookup.get(trade_date, (fallback_ts, float(fallback_close)))


def should_flatten_on_bar(ts: pd.Timestamp, bar_minutes: int, close_all_minutes: int) -> bool:
    start_minute = ts.hour * 60 + ts.minute
    return start_minute >= close_all_minutes or start_minute + bar_minutes >= close_all_minutes


def _fill_stop_market_buy(open_price: float, trigger_price: float, slippage_pts: float) -> float:
    if open_price >= trigger_price:
        return float(open_price + slippage_pts)
    return float(trigger_price + slippage_pts)


def _fill_stop_market_sell(open_price: float, trigger_price: float, slippage_pts: float) -> float:
    if open_price <= trigger_price:
        return float(open_price - slippage_pts)
    return float(trigger_price - slippage_pts)


def _fill_limit_sell(open_price: float, limit_price: float) -> float:
    if open_price >= limit_price:
        return float(open_price)
    return float(limit_price)


def _fill_limit_buy(open_price: float, limit_price: float) -> float:
    if open_price <= limit_price:
        return float(open_price)
    return float(limit_price)


def _fill_market_close(is_long: bool, price: float, slippage_pts: float) -> float:
    if is_long:
        return float(price - slippage_pts)
    return float(price + slippage_pts)


def _fill_market_open(is_long: bool, price: float, slippage_pts: float) -> float:
    if is_long:
        return float(price + slippage_pts)
    return float(price - slippage_pts)


def _fill_touch_buy(trigger_price: float, slippage_pts: float) -> float:
    return float(trigger_price + slippage_pts)


def _fill_touch_sell(trigger_price: float, slippage_pts: float) -> float:
    return float(trigger_price - slippage_pts)


def _touch_fill_credible_long(long_level: float, low: float, tick_size: float) -> bool:
    """Touch long at long_level requires the bar to trade at or below the trigger (no all-bar gap above)."""
    tol = max(float(tick_size) * 0.25, 1e-9)
    return float(low) <= float(long_level) + tol


def _touch_fill_credible_short(short_level: float, high: float, tick_size: float) -> bool:
    """Touch short at short_level requires the bar to trade at or above the trigger (no all-bar gap below)."""
    tol = max(float(tick_size) * 0.25, 1e-9)
    return float(high) >= float(short_level) - tol


def run_backtest(cfg: FastConfig, bars: pd.DataFrame, tick_size: float,
                 return_trades: bool = False,
                 execution: Optional[ExecutionOptions] = None,
                 diagnostics: Optional[List[dict[str, Any]]] = None) -> dict:
    """
    Run a single backtest. Returns performance metrics dict.

    bars: DataFrame with datetime index and open/high/low/close columns.
          Should already be resampled to cfg.bar_minutes.

    If return_trades=True, the returned dict includes a 'trades' key with
    a list of dicts: entry_ts, entry_bar_idx, exit_ts, exit_bar_idx,
    direction, entry_price, exit_price, entry_trigger (breakout stop price),
    entry_open/high/low/close (entry bar), pnl_ticks, exit_reason, etc.
    """
    execution = execution or ExecutionOptions()

    n = len(bars)
    if n < 10:
        return _empty_metrics(return_trades)

    # Extract numpy arrays for speed
    opens = bars["open"].values.astype(np.float64)
    highs = bars["high"].values.astype(np.float64)
    lows = bars["low"].values.astype(np.float64)
    closes = bars["close"].values.astype(np.float64)

    timestamps = bars.index
    minutes_of_day = np.array([ts.hour * 60 + ts.minute for ts in timestamps], dtype=np.int32)
    dates = np.array([ts.date() for ts in timestamps])
    weekdays = np.array([ts.weekday() for ts in timestamps], dtype=np.int32)

    offset_pts = cfg.entry_tick_offset * tick_size
    base_slip = execution.stop_slippage_ticks
    entry_slip = execution.entry_slippage_ticks if execution.entry_slippage_ticks is not None else base_slip
    exit_slip = execution.exit_slippage_ticks if execution.exit_slippage_ticks is not None else base_slip
    entry_slippage_pts = entry_slip * tick_size
    exit_slippage_pts = exit_slip * tick_size  # used for stop/trigger exits
    close_slippage_pts = execution.close_slippage_ticks * tick_size

    use_atr = cfg.atr_adaptive
    if use_atr:
        bar_atr = compute_bar_atr(highs, lows, closes, 14)
        # Defaults will be overridden per-day once ATR is known
        sl_pts = pt_pts = trail_by_pts = trail_start_pts = 0.0
        be_after_pts = cfg.breakeven_after_ticks * tick_size
        be_offset_pts = cfg.breakeven_offset * tick_size
        trail_freq_pts = cfg.trail_frequency * tick_size
    else:
        bar_atr = None
        sl_pts = cfg.stop_loss_ticks * tick_size
        pt_pts = cfg.profit_target_ticks * tick_size
        be_after_pts = cfg.breakeven_after_ticks * tick_size
        be_offset_pts = cfg.breakeven_offset * tick_size
        trail_by_pts = cfg.trail_by_ticks * tick_size
        trail_start_pts = cfg.trail_start_after_ticks * tick_size
        trail_freq_pts = cfg.trail_frequency * tick_size

    rs = cfg.range_start_minutes
    re = cfg.range_end_minutes
    ts_min = cfg.trade_start_minutes
    te_min = cfg.trade_end_minutes
    ca_min = cfg.close_all_minutes
    flatten_lookup = build_flatten_lookup(bars, ca_min)

    excluded = cfg.excluded_weekdays
    allow_long = cfg.direction in ("both", "long")
    allow_short = cfg.direction in ("both", "short")

    # Output arrays
    trade_pnls = []
    trade_dirs = []
    trade_details = [] if return_trades else None

    # Entry tracking (used when return_trades=True)
    entry_ts = None
    entry_bar_idx = 0
    entry_range_size_pts = 0.0  # for top-N ranking by range size
    entry_trigger = 0.0  # long_level (long) or short_level (short) at entry; for logs/exports

    # State
    current_date = None
    range_high = -np.inf
    range_low = np.inf
    range_ready = False
    building_range = False
    entries_today = 0

    # Position state
    in_position = False
    is_long = False
    entry_price = 0.0
    stop_price = 0.0
    pt_price = 0.0
    best_price = 0.0
    be_applied = False

    long_armed = False
    short_armed = False
    cooldown = False
    pending_entry = False
    pending_is_long = False
    pending_range_size_pts = 0.0

    def _reset_pending_entry() -> None:
        nonlocal pending_entry, pending_is_long, pending_range_size_pts
        pending_entry = False
        pending_is_long = False
        pending_range_size_pts = 0.0

    def _emit_trade(
        exit_ts_v: Any,
        exit_bi: int,
        exit_fill_v: float,
        pnl: float,
        reason: str,
    ) -> None:
        if trade_details is None:
            return
        eb = int(entry_bar_idx)
        trade_details.append(
            {
                "entry_ts": entry_ts,
                "entry_bar_idx": eb,
                "exit_ts": exit_ts_v,
                "exit_bar_idx": exit_bi,
                "direction": "long" if is_long else "short",
                "entry_price": float(entry_price),
                "exit_price": float(exit_fill_v),
                "entry_trigger": float(entry_trigger),
                "entry_open": float(opens[eb]),
                "entry_high": float(highs[eb]),
                "entry_low": float(lows[eb]),
                "entry_close": float(closes[eb]),
                "pnl_ticks": pnl / tick_size,
                "range_size_pts": entry_range_size_pts,
                "exit_reason": reason,
                "execution_mode": execution.entry_fill_mode,
                "stop_slippage_ticks": execution.stop_slippage_ticks,
            }
        )

    for i in range(n):
        bar_date = dates[i]
        bar_min = minutes_of_day[i]
        wd = weekdays[i]
        is_last_bar_of_date = i == n - 1 or dates[i + 1] != bar_date

        # New day reset
        if bar_date != current_date:
            if in_position and current_date is not None:
                exit_ts_value, exit_price_value = resolve_flatten_exit(
                    flatten_lookup,
                    current_date,
                    timestamps[i],
                    closes[i],
                )
                exit_fill = _fill_market_close(is_long, exit_price_value, close_slippage_pts)
                if is_long:
                    pnl = exit_fill - entry_price
                else:
                    pnl = entry_price - exit_fill
                trade_pnls.append(pnl / tick_size)
                trade_dirs.append(1 if is_long else -1)
                _emit_trade(exit_ts_value, i, exit_fill, pnl, "day_change_flatten")
                in_position = False

            current_date = bar_date
            range_high = -np.inf
            range_low = np.inf
            range_ready = False
            building_range = False
            long_armed = False
            short_armed = False
            cooldown = False
            entries_today = 0
            _reset_pending_entry()

        # Day filter
        if wd in excluded:
            continue

        # Close all
        if should_flatten_on_bar(timestamps[i], cfg.bar_minutes, ca_min) or is_last_bar_of_date:
            exit_ts_value, exit_price_value = resolve_flatten_exit(
                flatten_lookup,
                bar_date,
                timestamps[i],
                closes[i],
            )
            if in_position:
                exit_fill = _fill_market_close(is_long, exit_price_value, close_slippage_pts)
                if is_long:
                    pnl = exit_fill - entry_price
                else:
                    pnl = entry_price - exit_fill
                trade_pnls.append(pnl / tick_size)
                trade_dirs.append(1 if is_long else -1)
                _emit_trade(exit_ts_value, i, exit_fill, pnl, "close_all_flatten")
                in_position = False
            long_armed = False
            short_armed = False
            cooldown = False
            _reset_pending_entry()
            continue

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
                    if np.isnan(day_atr) or day_atr < tick_size:
                        day_atr = (range_high - range_low) if range_high > range_low else tick_size
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
                            "instrument": cfg.instrument,
                            "date": str(bar_date),
                            "ts": pd.Timestamp(timestamps[i]).isoformat(),
                            "range_minutes": (int(rs), int(re)),
                            "trade_minutes": (int(ts_min), int(te_min)),
                            "range_low": float(range_low),
                            "range_high": float(range_high),
                            "long_level": ll,
                            "short_level": ss,
                            "both_armed": True,
                        }
                    )
            building_range = False

        if not range_ready:
            continue

        if not (ts_min <= bar_min < te_min):
            continue

        long_level = range_high + offset_pts
        short_level = range_low - offset_pts

        if pending_entry and not in_position:
            entry_price = _fill_market_open(pending_is_long, opens[i], entry_slippage_pts)
            entries_today += 1
            in_position = True
            is_long = pending_is_long
            entry_trigger = float(long_level if is_long else short_level)
            best_price = entry_price
            be_applied = False
            entry_range_size_pts = pending_range_size_pts
            _reset_pending_entry()
            if return_trades:
                entry_ts = timestamps[i]
                entry_bar_idx = i
            if is_long:
                stop_price = entry_price - sl_pts
                pt_price = entry_price + pt_pts
                long_armed = False
            else:
                stop_price = entry_price + sl_pts
                pt_price = entry_price - pt_pts
                short_armed = False

        # Position management
        if in_position:
            if is_long:
                # Stop check
                if lows[i] <= stop_price:
                    if execution.entry_fill_mode == "stop_market":
                        exit_fill = _fill_stop_market_sell(opens[i], stop_price, exit_slippage_pts)
                    else:
                        exit_fill = _fill_touch_sell(stop_price, exit_slippage_pts)
                    pnl = exit_fill - entry_price
                    trade_pnls.append(pnl / tick_size)
                    trade_dirs.append(1)
                    _emit_trade(timestamps[i], i, exit_fill, pnl, "stop_loss")
                    in_position = False
                    long_armed = closes[i] < long_level
                    short_armed = closes[i] > short_level
                    cooldown = True
                    _reset_pending_entry()
                    continue

                # PT check
                if highs[i] >= pt_price:
                    exit_fill = _fill_limit_sell(opens[i], pt_price)
                    pnl = exit_fill - entry_price
                    trade_pnls.append(pnl / tick_size)
                    trade_dirs.append(1)
                    _emit_trade(timestamps[i], i, exit_fill, pnl, "profit_target")
                    in_position = False
                    long_armed = closes[i] < long_level
                    short_armed = closes[i] > short_level
                    cooldown = True
                    _reset_pending_entry()
                    continue

                # Update best price
                if highs[i] > best_price:
                    best_price = highs[i]

                move = best_price - entry_price

                # Breakeven
                if cfg.breakeven_on and not be_applied and move >= be_after_pts:
                    new_stop = entry_price + be_offset_pts
                    if new_stop > stop_price:
                        stop_price = new_stop
                    be_applied = True

                # Trail
                if cfg.trail_on and move >= trail_start_pts:
                    trail_stop = best_price - trail_by_pts
                    if trail_freq_pts > 0:
                        trail_stop = entry_price + int((trail_stop - entry_price) / trail_freq_pts) * trail_freq_pts
                    if trail_stop > stop_price:
                        stop_price = trail_stop

            else:  # Short position
                if highs[i] >= stop_price:
                    if execution.entry_fill_mode == "stop_market":
                        exit_fill = _fill_stop_market_buy(opens[i], stop_price, exit_slippage_pts)
                    else:
                        exit_fill = _fill_touch_buy(stop_price, exit_slippage_pts)
                    pnl = entry_price - exit_fill
                    trade_pnls.append(pnl / tick_size)
                    trade_dirs.append(-1)
                    _emit_trade(timestamps[i], i, exit_fill, pnl, "stop_loss")
                    in_position = False
                    long_armed = closes[i] < long_level
                    short_armed = closes[i] > short_level
                    cooldown = True
                    _reset_pending_entry()
                    continue

                if lows[i] <= pt_price:
                    exit_fill = _fill_limit_buy(opens[i], pt_price)
                    pnl = entry_price - exit_fill
                    trade_pnls.append(pnl / tick_size)
                    trade_dirs.append(-1)
                    _emit_trade(timestamps[i], i, exit_fill, pnl, "profit_target")
                    in_position = False
                    long_armed = closes[i] < long_level
                    short_armed = closes[i] > short_level
                    cooldown = True
                    _reset_pending_entry()
                    continue

                if lows[i] < best_price:
                    best_price = lows[i]

                move = entry_price - best_price

                if cfg.breakeven_on and not be_applied and move >= be_after_pts:
                    new_stop = entry_price - be_offset_pts
                    if new_stop < stop_price:
                        stop_price = new_stop
                    be_applied = True

                if cfg.trail_on and move >= trail_start_pts:
                    trail_stop = best_price + trail_by_pts
                    if trail_freq_pts > 0:
                        trail_stop = entry_price - int((entry_price - trail_stop) / trail_freq_pts) * trail_freq_pts
                    if trail_stop < stop_price:
                        stop_price = trail_stop

            continue

        # Cooldown
        if cooldown:
            cooldown = False
            if not long_armed and closes[i] < long_level:
                long_armed = True
            if not short_armed and closes[i] > short_level:
                short_armed = True
            continue

        # Re-arm
        if not long_armed and lows[i] < long_level:
            long_armed = True
        if not short_armed and highs[i] > short_level:
            short_armed = True

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

            entered = False
            if long_hit and short_hit:
                if opens[i] >= long_level:
                    if execution.entry_fill_mode == "next_bar_open":
                        pending_entry = True
                        pending_is_long = True
                        pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                        long_armed = False
                        entered = False
                    elif execution.entry_fill_mode == "stop_market":
                        entry_price = _fill_stop_market_buy(opens[i], long_level, entry_slippage_pts)
                    else:
                        entry_price = _fill_touch_buy(long_level, entry_slippage_pts)
                    if execution.entry_fill_mode != "next_bar_open":
                        is_long = True
                        entered = True
                elif opens[i] <= short_level:
                    if execution.entry_fill_mode == "next_bar_open":
                        pending_entry = True
                        pending_is_long = False
                        pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                        short_armed = False
                        entered = False
                    elif execution.entry_fill_mode == "stop_market":
                        entry_price = _fill_stop_market_sell(opens[i], short_level, entry_slippage_pts)
                    else:
                        entry_price = _fill_touch_sell(short_level, entry_slippage_pts)
                    if execution.entry_fill_mode != "next_bar_open":
                        is_long = False
                        entered = True
                elif (long_level - opens[i]) <= (opens[i] - short_level):
                    if execution.entry_fill_mode == "next_bar_open":
                        pending_entry = True
                        pending_is_long = True
                        pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                        long_armed = False
                        entered = False
                    elif execution.entry_fill_mode == "stop_market":
                        entry_price = _fill_stop_market_buy(opens[i], long_level, entry_slippage_pts)
                    else:
                        entry_price = _fill_touch_buy(long_level, entry_slippage_pts)
                    if execution.entry_fill_mode != "next_bar_open":
                        is_long = True
                        entered = True
                else:
                    if execution.entry_fill_mode == "next_bar_open":
                        pending_entry = True
                        pending_is_long = False
                        pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                        short_armed = False
                        entered = False
                    elif execution.entry_fill_mode == "stop_market":
                        entry_price = _fill_stop_market_sell(opens[i], short_level, entry_slippage_pts)
                    else:
                        entry_price = _fill_touch_sell(short_level, entry_slippage_pts)
                    if execution.entry_fill_mode != "next_bar_open":
                        is_long = False
                        entered = True
            elif long_hit:
                if execution.entry_fill_mode == "next_bar_open":
                    pending_entry = True
                    pending_is_long = True
                    pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                    long_armed = False
                elif execution.entry_fill_mode == "stop_market":
                    entry_price = _fill_stop_market_buy(opens[i], long_level, entry_slippage_pts)
                else:
                    entry_price = _fill_touch_buy(long_level, entry_slippage_pts)
                if execution.entry_fill_mode != "next_bar_open":
                    is_long = True
                    entered = True
            elif short_hit:
                if execution.entry_fill_mode == "next_bar_open":
                    pending_entry = True
                    pending_is_long = False
                    pending_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                    short_armed = False
                elif execution.entry_fill_mode == "stop_market":
                    entry_price = _fill_stop_market_sell(opens[i], short_level, entry_slippage_pts)
                else:
                    entry_price = _fill_touch_sell(short_level, entry_slippage_pts)
                if execution.entry_fill_mode != "next_bar_open":
                    is_long = False
                    entered = True

            if diagnostics is not None and pending_entry and not entered:
                diagnostics.append(
                    {
                        "kind": "pending_entry",
                        "instrument": cfg.instrument,
                        "date": str(bar_date),
                        "ts": pd.Timestamp(timestamps[i]).isoformat(),
                        "side": "long" if pending_is_long else "short",
                        "fills_next_bar_open": True,
                        "long_level": float(long_level),
                        "short_level": float(short_level),
                    }
                )

            if entered:
                entries_today += 1
                in_position = True
                entry_trigger = float(long_level if is_long else short_level)
                best_price = entry_price
                be_applied = False
                entry_range_size_pts = range_high - range_low if range_high > range_low else 0.0
                if return_trades:
                    entry_ts = timestamps[i]
                    entry_bar_idx = i
                if diagnostics is not None:
                    diagnostics.append(
                        {
                            "kind": "entry_fill",
                            "instrument": cfg.instrument,
                            "date": str(bar_date),
                            "ts": pd.Timestamp(timestamps[i]).isoformat(),
                            "direction": "long" if is_long else "short",
                            "entry_price": float(entry_price),
                            "entry_trigger": float(entry_trigger),
                            "long_level": float(long_level),
                            "short_level": float(short_level),
                            "entry_open": float(opens[i]),
                            "entry_high": float(highs[i]),
                            "entry_low": float(lows[i]),
                            "entry_close": float(closes[i]),
                        }
                    )
                if is_long:
                    stop_price = entry_price - sl_pts
                    pt_price = entry_price + pt_pts
                    long_armed = False
                else:
                    stop_price = entry_price + sl_pts
                    pt_price = entry_price - pt_pts
                    short_armed = False

    # Close any remaining position
    if in_position and n > 0:
        exit_fill = _fill_market_close(is_long, closes[n-1], close_slippage_pts)
        if is_long:
            pnl = exit_fill - entry_price
        else:
            pnl = entry_price - exit_fill
        trade_pnls.append(pnl / tick_size)
        trade_dirs.append(1 if is_long else -1)
        _emit_trade(timestamps[n - 1], n - 1, exit_fill, pnl, "end_of_data_flatten")

    result = _compute_metrics(np.array(trade_pnls), np.array(trade_dirs) if trade_dirs else np.array([]))
    if return_trades:
        result["trades"] = trade_details
    return result


def _compute_metrics(pnls: np.ndarray, dirs: np.ndarray) -> dict:
    """Compute performance metrics from trade PnL array (in ticks)."""
    if len(pnls) == 0:
        return _empty_metrics()

    n = len(pnls)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
    pf = gross_win / gross_loss if gross_loss > 0 else 0.0
    wr = len(wins) / n * 100

    # Max drawdown
    cum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    max_dd = abs(dd.min()) if len(dd) > 0 else 0

    # Sharpe: use shared compute_sharpe (trade-level when no dates)
    if _compute_sharpe_shared is not None:
        sharpe = _compute_sharpe_shared(pnls, dates=None, method="trade")
    elif n > 1 and pnls.std() > 0:
        sharpe = pnls.mean() / pnls.std() * np.sqrt(min(n, 252))
    else:
        sharpe = 0.0

    return {
        "n_trades": n,
        "n_long": int((dirs == 1).sum()) if len(dirs) > 0 else 0,
        "n_short": int((dirs == -1).sum()) if len(dirs) > 0 else 0,
        "win_rate": wr,
        "profit_factor": pf,
        "total_pnl": float(pnls.sum()),
        "avg_pnl": float(pnls.mean()),
        "max_dd": float(max_dd),
        "sharpe": float(sharpe),
        "pnls": pnls,
    }


def _empty_metrics(return_trades: bool = False) -> dict:
    m = {
        "n_trades": 0, "n_long": 0, "n_short": 0,
        "win_rate": 0.0, "profit_factor": 0.0,
        "total_pnl": 0.0, "avg_pnl": 0.0,
        "max_dd": 0.0, "sharpe": 0.0, "pnls": np.array([]),
    }
    if return_trades:
        m["trades"] = []
    return m
