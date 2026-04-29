"""Shared helpers: safe math, JSON-safe conversion, column normalization."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS_YEAR = 252
TRADING_DAYS_MONTH = 21


def safe_div(num: float, den: float, *, default: float = 0.0) -> float:
    if den is None or (isinstance(den, float) and (math.isnan(den) or abs(den) < 1e-15)):
        return default
    v = float(num) / float(den)
    if math.isnan(v) or math.isinf(v):
        return default
    return v


def nan_to_none(x: Any) -> Any:
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, dict):
        return {k: nan_to_none(v) for k, v in x.items()}
    if isinstance(x, list):
        return [nan_to_none(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        v = float(x) if isinstance(x, np.floating) else int(x)
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v
    return x


def normalize_trades(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    rename: dict[str, str] = {}
    for want in ("timestamp", "pnl", "direction", "duration"):
        for c in out.columns:
            cl = c.lower()
            if want == "timestamp" and cl in ("timestamp", "time", "entry_ts", "exit_ts", "date"):
                rename[c] = "timestamp"
                break
            if want == "pnl" and cl in ("pnl", "pnl_usd", "profit"):
                rename[c] = "pnl"
                break
            if want == "direction" and cl in ("direction", "side"):
                rename[c] = "direction"
                break
            if want == "duration" and cl in ("duration", "duration_sec", "hold_time"):
                rename[c] = "duration"
                break
    out = out.rename(columns=rename)
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"])
    if "pnl" in out.columns:
        out["pnl"] = pd.to_numeric(out["pnl"], errors="coerce")
    return out


def normalize_daily(df: pd.DataFrame | None) -> tuple[pd.Series, pd.Series]:
    """
    Returns (daily_pnl indexed by date, equity indexed by date).
    Equity = cumulative sum of daily_pnl if not provided.
    """
    if df is None or df.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    d = df.copy()
    rename = {}
    for c in d.columns:
        cl = c.lower().replace(" ", "_")
        if cl in ("date", "day", "timestamp"):
            rename[c] = "date"
        elif cl in ("daily_pnl", "pnl", "pnl_usd", "return"):
            rename[c] = "daily_pnl"
        elif cl in ("cumulative_equity", "equity", "cum_equity", "balance"):
            rename[c] = "cumulative_equity"
    d = d.rename(columns=rename)
    if "date" not in d.columns:
        raise ValueError("daily data requires a date column")
    d["date"] = pd.to_datetime(d["date"])
    d = d.sort_values("date").drop_duplicates("date", keep="last")
    d = d.set_index("date")
    pnl = pd.to_numeric(d["daily_pnl"], errors="coerce").fillna(0.0).astype(float)
    if "cumulative_equity" in d.columns:
        eq = pd.to_numeric(d["cumulative_equity"], errors="coerce").astype(float)
        eq = eq.ffill()
    else:
        eq = pnl.cumsum()
    return pnl, eq
