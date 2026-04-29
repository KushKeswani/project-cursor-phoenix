"""Load exported trade execution CSVs and build portfolio daily PnL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from _paths import ensure_scripts_on_path

ensure_scripts_on_path()

from backtester import INSTRUMENTS, merged_scaled_trades, portfolio_daily_monthly_from_merged
from configs.portfolio_presets import PORTFOLIO_PRESETS


def load_executions_from_dir(reports_root: Path, scope: str) -> dict[str, pd.DataFrame]:
    """
    Load per-instrument CSVs from ``reports/trade_executions/{scope}/instruments/``.
    Expected columns include entry_ts, exit_ts, pnl_ticks (and optional pnl_usd).
    """
    inst_dir = reports_root / "trade_executions" / scope / "instruments"
    out: dict[str, pd.DataFrame] = {}
    for inst in INSTRUMENTS:
        path = inst_dir / f"{inst}_trade_executions.csv"
        if not path.exists():
            out[inst] = pd.DataFrame()
            continue
        df = pd.read_csv(path)
        if df.empty:
            out[inst] = pd.DataFrame()
            continue
        df = df.copy()
        df["entry_ts"] = pd.to_datetime(df["entry_ts"])
        df["exit_ts"] = pd.to_datetime(df["exit_ts"])
        out[inst] = df
    return out


def build_daily_monthly(
    raw_by_inst: dict[str, pd.DataFrame],
    portfolio_preset: str,
    trade_size_multiplier: float,
) -> tuple[pd.Series, pd.Series, list[str]]:
    """
    Scale trades by ``PORTFOLIO_PRESETS`` contracts, merge, aggregate to daily/monthly.
    Applies ``trade_size_multiplier`` to daily (and recomputed monthly from merged trades).
    """
    warnings: list[str] = []
    if portfolio_preset not in PORTFOLIO_PRESETS:
        raise ValueError(f"Unknown portfolio preset '{portfolio_preset}'")

    missing = [i for i in INSTRUMENTS if raw_by_inst.get(i) is None or raw_by_inst[i].empty]
    if len(missing) == len(INSTRUMENTS):
        warnings.append("No instrument CSVs found — daily pool is empty.")
    elif missing:
        warnings.append(f"No CSV (skipped): {', '.join(missing)}")

    contracts = {i: int(PORTFOLIO_PRESETS[portfolio_preset][i]) for i in INSTRUMENTS}
    merged = merged_scaled_trades(raw_by_inst, contracts)
    if merged.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), warnings

    merged = merged.copy()
    merged["pnl_usd"] = merged["pnl_usd"].astype(float) * float(trade_size_multiplier)
    daily, monthly = portfolio_daily_monthly_from_merged(merged)
    return daily, monthly, warnings
