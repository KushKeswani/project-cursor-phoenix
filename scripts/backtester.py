#!/usr/bin/env python3
"""Run the minimal backtester and generate all reports and charts."""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_script_done import run_with_telegram

from configs.oos_defaults import DEFAULT_OOS_END, DEFAULT_OOS_START
from configs.strategy_configs import get_config
from configs.tick_config import INSTRUMENT_GRIDS, TICK_SIZES, TICK_VALUES
from engine.fast_engine import resample_to_bars, run_backtest

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
TRADE_COLUMNS = [
    "entry_ts",
    "exit_ts",
    "direction",
    "entry_price",
    "exit_price",
    "pnl_ticks",
    "entry_trigger",
    "entry_open",
    "entry_high",
    "entry_low",
    "entry_close",
    "exit_reason",
]


def resolve_data_dir(explicit_dir: str | None) -> Path:
    if explicit_dir:
        path = Path(explicit_dir).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Data dir not found: {path}")
        return path

    default_dir = SCRIPT_DIR.parent / "Data-DataBento"
    if default_dir.exists():
        return default_dir
    raise FileNotFoundError("Pass --data-dir pointing to normalized parquet files.")


def _canonicalize_ohlc_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse duplicate timestamps into one OHLC row per timestamp.

    Some parquet snapshots in this repo contain repeated minute stamps with distinct
    rows. That is not a valid bar series for the engine. We canonicalize the input
    before any further filtering so historical and live-replay code paths see the
    same minute-level semantics.
    """
    if df is None or df.empty:
        return df
    out = df.copy()
    if "datetime" in out.columns:
        out = out.set_index("datetime")
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    if not out.index.has_duplicates:
        return out

    agg: dict[str, str] = {}
    for col in out.columns:
        if col == "open":
            agg[col] = "first"
        elif col == "high":
            agg[col] = "max"
        elif col == "low":
            agg[col] = "min"
        elif col == "close":
            agg[col] = "last"
        elif col == "volume":
            agg[col] = "sum"
        else:
            agg[col] = "last"
    return out.groupby(out.index, sort=True).agg(agg)


# DataBento-style OHLCV CSV in Data-DataBento: ts_event UTC, open/high/low/close, symbol.
# NQ minute bars drive MNQ strategy (same index; MNQ tick size from TICK_SIZES).
_DATABENTO_CSV_BY_INSTRUMENT: dict[str, str] = {
    "MNQ": "nq-data.csv",
    "MGC": "mgc-data.csv",
    "YM": "mym.csv",
    "CL": "mcl.csv",
}

_ET = ZoneInfo("America/New_York")


def _load_databento_csv_1m_bars(
    csv_path: Path,
    *,
    outright_prefix: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Load 1m OHLC, filter outrights (no spreads), aggregate to one row per minute ET.

    Uses chunked reads and UTC-row filtering when start/end are set so huge CSVs stay usable.
    """
    usecols = ["ts_event", "open", "high", "low", "close", "symbol"]
    lo_utc = hi_utc = None
    if start is not None and end is not None:
        s_et = pd.Timestamp(start)
        e_et = pd.Timestamp(end)
        lo_utc = (s_et - pd.Timedelta(days=2)).tz_localize(_ET).tz_convert("UTC")
        hi_utc = (e_et + pd.Timedelta(days=2)).tz_localize(_ET).tz_convert("UTC")

    parts: list[pd.DataFrame] = []
    reader = pd.read_csv(
        csv_path,
        usecols=lambda c: c in usecols,
        low_memory=False,
        chunksize=400_000,
    )
    for raw in reader:
        if raw.empty:
            continue
        ts_utc = pd.to_datetime(raw["ts_event"], utc=True)
        if lo_utc is not None:
            tmask = (ts_utc >= lo_utc) & (ts_utc <= hi_utc)
            raw = raw.loc[tmask].copy()
            ts_utc = ts_utc.loc[tmask]
            if raw.empty:
                continue

        sym = raw["symbol"].astype(str)
        smask = sym.str.startswith(outright_prefix) & ~sym.str.contains("-", regex=False)
        raw = raw.loc[smask]
        ts_utc = ts_utc.loc[smask]
        if raw.empty:
            continue

        for col in ("open", "high", "low", "close"):
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
        raw = raw.dropna(subset=["open", "high", "low", "close"])
        ts_utc = ts_utc.loc[raw.index]
        raw = raw[(raw["open"] > 0) & (raw["high"] > 0)]
        ts_utc = ts_utc.loc[raw.index]
        if raw.empty:
            continue

        ts_et = ts_utc.dt.tz_convert(_ET).dt.tz_localize(None)
        raw = raw.assign(minute_et=ts_et.dt.floor("min"))
        g = raw.groupby("minute_et", sort=False)
        parts.append(
            g.agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
            )
        )

    if not parts:
        return pd.DataFrame(columns=["open", "high", "low", "close"])

    merged = pd.concat(parts).sort_index()
    out = merged.groupby(merged.index).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
    )
    out.index.name = "datetime"
    return out


def load_bars(instrument: str, data_dir: Path, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pq = data_dir / f"{instrument}.parquet"
    csv_name = _DATABENTO_CSV_BY_INSTRUMENT.get(instrument)
    csv_path = (data_dir / csv_name) if csv_name else None

    if pq.exists():
        df = pd.read_parquet(pq)
        df = _canonicalize_ohlc_frame(df)
    elif csv_path is not None and csv_path.is_file():
        outright = {
            "MNQ": "NQ",
            "MGC": "MGC",
            "YM": "MYM",
            "CL": "MCL",
        }[instrument]
        if instrument == "YM":
            warnings.warn(
                "Loading YM bars from MYM CSV (mym.csv): prices match Dow index; "
                "TICK_SIZES/TICK_VALUES are still YM mini — USD PnL may not match micro-Dow economics.",
                UserWarning,
                stacklevel=2,
            )
        df = _load_databento_csv_1m_bars(
            csv_path,
            outright_prefix=outright,
            start=start,
            end=end,
        )
        df = _canonicalize_ohlc_frame(df)
    else:
        tried = f"{pq.name}"
        if csv_path is not None:
            tried += f" or {csv_path.name}"
        raise FileNotFoundError(
            f"Missing data for {instrument}: expected {data_dir / instrument}.parquet "
            f"or DataBento CSV ({tried})."
        )

    df = df.sort_index()
    df = df[(df.index >= start) & (df.index <= end)]

    cfg = get_config(instrument)
    grid = INSTRUMENT_GRIDS[instrument]
    bars = resample_to_bars(
        df,
        cfg.bar_minutes,
        session_start_hour=grid["session_start"],
        session_end_hour=grid["session_end"],
    )
    return df, bars


def empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLUMNS)


def raw_trades_frame(result: dict) -> pd.DataFrame:
    trades = pd.DataFrame(result.get("trades", []))
    if trades.empty:
        return empty_trades()
    out = trades.copy()
    out["entry_ts"] = pd.to_datetime(out["entry_ts"])
    out["exit_ts"] = pd.to_datetime(out["exit_ts"])
    return out


def scaled_trades(raw_trades: pd.DataFrame, instrument: str, contracts: int) -> pd.DataFrame:
    if raw_trades.empty:
        return pd.DataFrame(
            columns=[
                "entry_ts",
                "exit_ts",
                "direction",
                "pnl_ticks",
                "pnl_usd",
                "exit_date",
                "exit_month",
                "equity",
            ]
        )

    trades = raw_trades.copy()
    trades["pnl_usd"] = trades["pnl_ticks"].astype(float) * TICK_VALUES[instrument] * contracts
    trades["exit_date"] = trades["exit_ts"].dt.normalize()
    trades["exit_month"] = trades["exit_ts"].dt.to_period("M").dt.to_timestamp()
    trades = trades.sort_values("exit_ts").reset_index(drop=True)
    trades["equity"] = trades["pnl_usd"].cumsum()
    return trades


def daily_pnl(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    return trades.groupby("exit_date")["pnl_usd"].sum().sort_index()


def monthly_pnl(trades: pd.DataFrame) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float)
    return trades.groupby("exit_month")["pnl_usd"].sum().sort_index()


def daily_sharpe(series: pd.Series, annual_rf: float = 0.0) -> float:
    if series.empty or len(series) < 2:
        return 0.0
    daily_rf = annual_rf / 252.0
    excess = series.astype(float) - daily_rf
    std = float(excess.std(ddof=0))
    if std <= 1e-12:
        return 0.0
    return float((excess.mean() / std) * np.sqrt(252.0))


def trade_sharpe(pnls: np.ndarray) -> float:
    if len(pnls) < 2:
        return 0.0
    std = float(np.std(pnls, ddof=0))
    if std <= 1e-12:
        return 0.0
    return float((float(np.mean(pnls)) / std) * np.sqrt(min(len(pnls), 252)))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = equity.cummax() - equity
    return float(dd.max()) if len(dd) else 0.0


def business_days(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return len(pd.date_range(start.normalize(), end.normalize(), freq="B"))


def trade_metrics(pnls_usd: np.ndarray) -> dict[str, float]:
    n = len(pnls_usd)
    if n == 0:
        return {
            "n_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "sharpe": 0.0,
        }
    wins = pnls_usd[pnls_usd > 0]
    losses = pnls_usd[pnls_usd < 0]
    gross_win = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    return {
        "n_trades": int(n),
        "win_rate": float(len(wins) / n * 100.0),
        "profit_factor": float(gross_win / gross_loss) if gross_loss > 0 else 0.0,
        "expectancy": float(np.mean(pnls_usd)),
        "sharpe": trade_sharpe(pnls_usd.astype(float)),
    }


def merged_scaled_trades(
    raw_trades_by_inst: dict[str, pd.DataFrame], contracts: dict[str, int]
) -> pd.DataFrame:
    """All legs scaled and concatenated, sorted by exit_ts (portfolio-level processing)."""
    frames: list[pd.DataFrame] = []
    for instrument in INSTRUMENTS:
        trades = scaled_trades(raw_trades_by_inst[instrument], instrument, contracts[instrument])
        if trades.empty:
            continue
        chunk = trades.copy()
        chunk["instrument"] = instrument
        frames.append(chunk)
    if not frames:
        return pd.DataFrame(
            columns=[
                "entry_ts",
                "exit_ts",
                "direction",
                "pnl_ticks",
                "pnl_usd",
                "exit_date",
                "exit_month",
                "equity",
                "instrument",
            ]
        )
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values("exit_ts", kind="mergesort").reset_index(drop=True)


def apply_daily_lockout(
    trades: pd.DataFrame,
    *,
    daily_profit_lock_usd: float | None,
    daily_loss_lock_usd: float | None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Walk trades in exit_ts order. Per calendar day (exit_date, naive local from bar data),
    include each trade until the day's cumulative realized pnl crosses +profit cap or −loss cap;
    include the crossing trade, then drop later trades that day. Disabled if both caps None.
    """
    if trades.empty or (daily_profit_lock_usd is None and daily_loss_lock_usd is None):
        return trades, {
            "n_trades_kept": float(len(trades)),
            "n_trades_dropped": 0.0,
            "days_profit_locked": 0.0,
            "days_loss_locked": 0.0,
        }

    eps = 1e-9
    profit_cap = daily_profit_lock_usd
    loss_cap = daily_loss_lock_usd
    locked_dates: set[pd.Timestamp] = set()
    day_cum: dict[pd.Timestamp, float] = {}
    days_profit_locked = 0
    days_loss_locked = 0
    keep_idx: list[int] = []

    for i, row in trades.iterrows():
        d = row["exit_date"]
        if d in locked_dates:
            continue
        pnl = float(row["pnl_usd"])
        cum = day_cum.get(d, 0.0) + pnl
        day_cum[d] = cum
        keep_idx.append(i)
        hit_profit = profit_cap is not None and cum >= profit_cap - eps
        hit_loss = loss_cap is not None and cum <= -loss_cap + eps
        if hit_profit:
            locked_dates.add(d)
            days_profit_locked += 1
        if hit_loss:
            locked_dates.add(d)
            days_loss_locked += 1

    filtered = trades.loc[keep_idx].copy()
    n_kept = len(filtered)
    n_drop = len(trades) - n_kept
    return filtered, {
        "n_trades_kept": float(n_kept),
        "n_trades_dropped": float(n_drop),
        "days_profit_locked": float(days_profit_locked),
        "days_loss_locked": float(days_loss_locked),
    }


def portfolio_daily_monthly_from_merged(merged: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    if merged.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    daily = merged.groupby("exit_date")["pnl_usd"].sum().sort_index()
    monthly = merged.groupby("exit_month")["pnl_usd"].sum().sort_index()
    return daily, monthly


def combine_daily_series(raw_trades_by_inst: dict[str, pd.DataFrame], contracts: dict[str, int]) -> pd.Series:
    parts = []
    for instrument in INSTRUMENTS:
        trades = scaled_trades(raw_trades_by_inst[instrument], instrument, contracts[instrument])
        daily = daily_pnl(trades)
        if daily.empty:
            continue
        parts.append(daily.rename(instrument))
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).fillna(0.0).sum(axis=1).sort_index()


def combine_monthly_series(raw_trades_by_inst: dict[str, pd.DataFrame], contracts: dict[str, int]) -> pd.Series:
    parts = []
    for instrument in INSTRUMENTS:
        trades = scaled_trades(raw_trades_by_inst[instrument], instrument, contracts[instrument])
        monthly = monthly_pnl(trades)
        if monthly.empty:
            continue
        parts.append(monthly.rename(instrument))
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).fillna(0.0).sum(axis=1).sort_index()


def combine_trade_pnls(raw_trades_by_inst: dict[str, pd.DataFrame], contracts: dict[str, int]) -> np.ndarray:
    arrays = []
    for instrument in INSTRUMENTS:
        trades = scaled_trades(raw_trades_by_inst[instrument], instrument, contracts[instrument])
        if trades.empty:
            continue
        arrays.append(trades["pnl_usd"].to_numpy(dtype=float))
    if not arrays:
        return np.array([], dtype=float)
    return np.concatenate(arrays)


def profile_backtest_stats(
    raw_full_by_inst: dict[str, pd.DataFrame],
    raw_oos_by_inst: dict[str, pd.DataFrame],
    contracts: dict[str, int],
    *,
    daily_profit_lock_usd: float | None = None,
    daily_loss_lock_usd: float | None = None,
) -> dict[str, object]:
    use_lockout = daily_profit_lock_usd is not None or daily_loss_lock_usd is not None

    if not use_lockout:
        full_daily = combine_daily_series(raw_full_by_inst, contracts)
        oos_daily = combine_daily_series(raw_oos_by_inst, contracts)
        full_monthly = combine_monthly_series(raw_full_by_inst, contracts)
        oos_monthly = combine_monthly_series(raw_oos_by_inst, contracts)
        full_trade_metrics = trade_metrics(combine_trade_pnls(raw_full_by_inst, contracts))
        oos_trade_metrics = trade_metrics(combine_trade_pnls(raw_oos_by_inst, contracts))
        lock_stats_full: dict[str, float] = {}
        lock_stats_oos: dict[str, float] = {}
        merged_full_oos: tuple[pd.DataFrame, pd.DataFrame] | None = None
    else:
        m_full = merged_scaled_trades(raw_full_by_inst, contracts)
        m_oos = merged_scaled_trades(raw_oos_by_inst, contracts)
        m_full_f, lock_stats_full = apply_daily_lockout(
            m_full,
            daily_profit_lock_usd=daily_profit_lock_usd,
            daily_loss_lock_usd=daily_loss_lock_usd,
        )
        m_oos_f, lock_stats_oos = apply_daily_lockout(
            m_oos,
            daily_profit_lock_usd=daily_profit_lock_usd,
            daily_loss_lock_usd=daily_loss_lock_usd,
        )
        merged_full_oos = (m_full_f, m_oos_f)
        full_daily, full_monthly = portfolio_daily_monthly_from_merged(m_full_f)
        oos_daily, oos_monthly = portfolio_daily_monthly_from_merged(m_oos_f)
        full_pn = m_full_f["pnl_usd"].to_numpy(dtype=float) if not m_full_f.empty else np.array([], dtype=float)
        oos_pn = m_oos_f["pnl_usd"].to_numpy(dtype=float) if not m_oos_f.empty else np.array([], dtype=float)
        full_trade_metrics = trade_metrics(full_pn)
        oos_trade_metrics = trade_metrics(oos_pn)

    out: dict[str, object] = {
        "contracts": contracts,
        "full_daily": full_daily,
        "oos_daily": oos_daily,
        "full_monthly": full_monthly,
        "oos_monthly": oos_monthly,
        "full_total_pnl": float(full_daily.sum()) if not full_daily.empty else 0.0,
        "oos_total_pnl": float(oos_daily.sum()) if not oos_daily.empty else 0.0,
        "full_max_dd": max_drawdown(full_daily.cumsum()),
        "oos_max_dd": max_drawdown(oos_daily.cumsum()),
        "full_monthly_avg": float(full_monthly.mean()) if not full_monthly.empty else 0.0,
        "oos_monthly_avg": float(oos_monthly.mean()) if not oos_monthly.empty else 0.0,
        "full_trade_metrics": full_trade_metrics,
        "oos_trade_metrics": oos_trade_metrics,
        "daily_profit_lock_usd": daily_profit_lock_usd,
        "daily_loss_lock_usd": daily_loss_lock_usd,
        "lockout_stats_full": lock_stats_full,
        "lockout_stats_oos": lock_stats_oos,
        "merged_full_filtered": merged_full_oos[0] if merged_full_oos else None,
        "merged_oos_filtered": merged_full_oos[1] if merged_full_oos else None,
    }
    return out


def bust_probability(
    daily_pnl: pd.Series,
    *,
    n_sims: int,
    eval_days: int,
    eod_dd: float,
    dll: float,
    seed: int,
) -> dict[str, float]:
    if daily_pnl.empty:
        return {
            "bust_pct": 100.0,
            "p10": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "avg_monthly": 0.0,
            "reach_7k_pct": 0.0,
        }

    vals = daily_pnl.to_numpy(dtype=float)
    months = eval_days / 21.0
    rng = np.random.default_rng(seed)
    final_pnls = np.zeros(n_sims, dtype=float)
    busted = np.zeros(n_sims, dtype=bool)

    for idx in range(n_sims):
        sample = vals[rng.integers(0, len(vals), size=eval_days)]
        equity = 0.0
        peak = 0.0
        bust = False
        for pnl in sample:
            equity += float(pnl)
            peak = max(peak, equity)
            if peak - equity >= eod_dd or pnl <= -dll:
                bust = True
                break
        final_pnls[idx] = equity
        busted[idx] = bust

    monthly = final_pnls / months
    return {
        "bust_pct": float(busted.mean() * 100.0),
        "p10": float(np.percentile(monthly, 10)),
        "p25": float(np.percentile(monthly, 25)),
        "p50": float(np.percentile(monthly, 50)),
        "p75": float(np.percentile(monthly, 75)),
        "p90": float(np.percentile(monthly, 90)),
        "avg_monthly": float(monthly.mean()),
        "reach_7k_pct": float((monthly >= 7000.0).mean() * 100.0),
    }


def contracts_at_scale(scale: float) -> dict[str, int]:
    return {
        instrument: max(1, int(round(BASE_CONTRACTS[instrument] * scale)))
        for instrument in INSTRUMENTS
    }


def determine_risk_profiles(
    raw_oos_by_inst: dict[str, pd.DataFrame],
    *,
    n_sims: int,
    eval_days: int,
    eod_dd: float,
    dll: float,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    matrix = []
    seen_contracts: set[tuple[int, int, int, int]] = set()

    for step in range(41):
        scale = round(1.0 + step * 0.05, 2)
        contracts = contracts_at_scale(scale)
        key = tuple(contracts[instrument] for instrument in INSTRUMENTS)
        if key in seen_contracts:
            continue
        seen_contracts.add(key)

        daily = combine_daily_series(raw_oos_by_inst, contracts)
        mc = bust_probability(
            daily,
            n_sims=n_sims,
            eval_days=eval_days,
            eod_dd=eod_dd,
            dll=dll,
            seed=seed,
        )
        row = {
            "scale": scale,
            "label_scale": f"{scale:.2f}x",
            "CL": contracts["CL"],
            "MGC": contracts["MGC"],
            "MNQ": contracts["MNQ"],
            "YM": contracts["YM"],
            **mc,
        }
        matrix.append(row)
        if mc["bust_pct"] > 35.0:
            break

    low = matrix[0]
    med = low
    high = low
    for row in matrix:
        if row["bust_pct"] <= 10.0:
            med = row
        if row["bust_pct"] <= 20.0:
            high = row

    profiles = {
        "Low": low,
        "Med": med,
        "High": high,
    }
    return matrix, profiles


def plot_trade_equity(trades: pd.DataFrame, title: str, out_path: Path) -> None:
    fig = plt.figure(figsize=(11, 4))
    plt.plot(trades["exit_ts"], trades["equity"], linewidth=1.4, color="#1f2937")
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_daily_equity(daily: pd.Series, title: str, out_path: Path) -> None:
    equity = daily.cumsum()
    fig = plt.figure(figsize=(11, 4))
    plt.plot(equity.index, equity.values, linewidth=1.4, color="#1f2937")
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_monthly_bars(monthly: pd.Series, title: str, out_path: Path) -> None:
    colors = ["#2e7d32" if value >= 0 else "#c62828" for value in monthly.values]
    fig = plt.figure(figsize=(11, 4))
    plt.bar(monthly.index, monthly.values, color=colors, width=20)
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("PnL ($)")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def write_instrument_report(
    out_path: Path,
    metrics: pd.DataFrame,
    *,
    data_dir: Path,
    full_start: str,
    full_end: str,
    oos_start: str,
    oos_end: str,
    risk_free_rate: float,
) -> None:
    lines = [
        "# Instrument Performance Report",
        "",
        "## Scope",
        "",
        f"- Data dir: `{data_dir}`",
        f"- Full window: {full_start} to {full_end}",
        f"- OOS window: {oos_start} to {oos_end}",
        f"- Contract sizing: CL 1, MGC 5, MNQ 5, YM 1",
        f"- Daily Sharpe risk-free rate: {risk_free_rate * 100:.1f}%",
        "",
        "## Sharpe Ratios",
        "",
        "| Instrument | Full Trade Sharpe | Full Daily Sharpe | OOS Trade Sharpe | OOS Daily Sharpe |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in metrics.iterrows():
        lines.append(
            f"| {row['instrument']} | {row['full_trade_sharpe_rf0']:.2f} | {row['full_daily_sharpe_rf3']:.2f} | "
            f"{row['oos_trade_sharpe_rf0']:.2f} | {row['oos_daily_sharpe_rf3']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Full-Period Performance",
            "",
            "| Instrument | Trades | WR | PF | Total PnL | Trade Max DD | Daily Max DD | EV/Trade | Trades/Trading Day | Trades/Business Day |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in metrics.iterrows():
        lines.append(
            f"| {row['instrument']} | {int(row['full_trades'])} | {row['full_win_rate']:.2f}% | {row['full_profit_factor']:.2f} | "
            f"${row['full_total_pnl_usd']:,.2f} | ${row['full_trade_max_dd_usd']:,.2f} | ${row['full_daily_max_dd_usd']:,.2f} | "
            f"${row['full_ev_per_trade_usd']:,.2f} | {row['full_trades_per_trading_day']:.2f} | {row['full_trades_per_business_day']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## OOS Performance",
            "",
            "| Instrument | Trades | WR | PF | Total PnL | Trade Max DD | Daily Max DD | EV/Trade | Trades/Trading Day | Trades/Business Day |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for _, row in metrics.iterrows():
        lines.append(
            f"| {row['instrument']} | {int(row['oos_trades'])} | {row['oos_win_rate']:.2f}% | {row['oos_profit_factor']:.2f} | "
            f"${row['oos_total_pnl_usd']:,.2f} | ${row['oos_trade_max_dd_usd']:,.2f} | ${row['oos_daily_max_dd_usd']:,.2f} | "
            f"${row['oos_ev_per_trade_usd']:,.2f} | {row['oos_trades_per_trading_day']:.2f} | {row['oos_trades_per_business_day']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Monthly Stability",
            "",
            "| Instrument | Best Month | Worst Month | Positive Months | Sample Start | Sample End |",
            "|---|---:|---:|---:|---|---|",
        ]
    )
    for _, row in metrics.iterrows():
        lines.append(
            f"| {row['instrument']} | ${row['full_best_month_usd']:,.2f} | ${row['full_worst_month_usd']:,.2f} | "
            f"{row['full_positive_month_pct']:.1f}% | {pd.Timestamp(row['sample_start']).date()} | {pd.Timestamp(row['sample_end']).date()} |"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_risk_report(
    out_path: Path,
    matrix: list[dict[str, object]],
    profiles: dict[str, dict[str, object]],
    profile_stats: dict[str, dict[str, object]],
    *,
    mc_sims: int,
    eval_days: int,
) -> None:
    lines = [
        "# Combined Portfolio Risk Profiles",
        "",
        "Low, Med, and High are defined at the combined portfolio level.",
        "",
        "## Tier Rules",
        "",
        "| Tier | Target Bust % | Contract Logic |",
        "|---|---:|---|",
        "| Low | Current baseline | CL 1, MGC 5, MNQ 5, YM 1 |",
        "| Med | <= 10% | Highest whole-contract portfolio under the target |",
        "| High | <= 20% | Highest whole-contract portfolio under the target |",
        "",
        f"- Monte Carlo sims: {mc_sims}",
        f"- Eval length: {eval_days} trading days",
        f"- EOD trailing DD: ${EOD_DD:,.0f}",
        f"- DLL: ${DLL:,.0f}",
        "",
        "## Tier Summary",
        "",
        "| Tier | Scale Label | CL | MGC | MNQ | YM | Bust % | P10 | P25 | P50 | P75 | P90 | Avg/mo | Reach $7K % |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ["Low", "Med", "High"]:
        row = profiles[name]
        lines.append(
            f"| {name} | {row['label_scale']} | {row['CL']} | {row['MGC']} | {row['MNQ']} | {row['YM']} | "
            f"{row['bust_pct']:.2f}% | ${row['p10']:,.0f} | ${row['p25']:,.0f} | ${row['p50']:,.0f} | "
            f"${row['p75']:,.0f} | ${row['p90']:,.0f} | ${row['avg_monthly']:,.0f} | {row['reach_7k_pct']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "## Backtest Stats",
            "",
            "| Tier | Period | Total PnL | Avg Monthly | Max DD | Trades | WR | PF | Expectancy | Sharpe |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name in ["Low", "Med", "High"]:
        stats = profile_stats[name]
        full_metrics = stats["full_trade_metrics"]
        oos_metrics = stats["oos_trade_metrics"]
        lines.append(
            f"| {name} | Full | ${stats['full_total_pnl']:,.2f} | ${stats['full_monthly_avg']:,.2f} | "
            f"${stats['full_max_dd']:,.2f} | {full_metrics['n_trades']} | {full_metrics['win_rate']:.2f}% | "
            f"{full_metrics['profit_factor']:.2f} | ${full_metrics['expectancy']:,.2f} | {full_metrics['sharpe']:.2f} |"
        )
        lines.append(
            f"| {name} | OOS | ${stats['oos_total_pnl']:,.2f} | ${stats['oos_monthly_avg']:,.2f} | "
            f"${stats['oos_max_dd']:,.2f} | {oos_metrics['n_trades']} | {oos_metrics['win_rate']:.2f}% | "
            f"{oos_metrics['profit_factor']:.2f} | ${oos_metrics['expectancy']:,.2f} | {oos_metrics['sharpe']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Scale Matrix",
            "",
            "| Scale | CL | MGC | MNQ | YM | Bust % | P25 | P50 | P75 | Avg/mo | Reach $7K % |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in matrix:
        lines.append(
            f"| {row['label_scale']} | {row['CL']} | {row['MGC']} | {row['MNQ']} | {row['YM']} | "
            f"{row['bust_pct']:.2f}% | ${row['p25']:,.0f} | ${row['p50']:,.0f} | ${row['p75']:,.0f} | "
            f"${row['avg_monthly']:,.0f} | {row['reach_7k_pct']:.1f}% |"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--reports-dir", default=str(SCRIPT_DIR.parent / "reports"))
    parser.add_argument("--full-start", default="2020-01-01")
    parser.add_argument("--full-end", default="2026-12-31")
    parser.add_argument("--oos-start", default=DEFAULT_OOS_START)
    parser.add_argument("--oos-end", default=DEFAULT_OOS_END)
    parser.add_argument("--risk-free-rate", type=float, default=0.03)
    parser.add_argument("--mc-sims", type=int, default=5000)
    parser.add_argument("--eval-days", type=int, default=EVAL_DAYS)
    parser.add_argument("--mc-seed", type=int, default=42)
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    reports_dir = Path(args.reports_dir).expanduser().resolve()
    visuals_dir = reports_dir / "visuals"
    instruments_dir = visuals_dir / "instruments"
    profiles_dir = visuals_dir / "portfolio_risk_profiles"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir.mkdir(parents=True, exist_ok=True)

    metrics_rows = []
    raw_full_by_inst: dict[str, pd.DataFrame] = {}
    raw_oos_by_inst: dict[str, pd.DataFrame] = {}

    for instrument in INSTRUMENTS:
        raw_full_df, bars_full = load_bars(instrument, data_dir, args.full_start, args.full_end)
        _, bars_oos = load_bars(instrument, data_dir, args.oos_start, args.oos_end)

        cfg = get_config(instrument)
        full_result = run_backtest(cfg, bars_full, TICK_SIZES[instrument], return_trades=True)
        oos_result = run_backtest(cfg, bars_oos, TICK_SIZES[instrument], return_trades=True)

        raw_full_trades = raw_trades_frame(full_result)
        raw_oos_trades = raw_trades_frame(oos_result)
        raw_full_by_inst[instrument] = raw_full_trades
        raw_oos_by_inst[instrument] = raw_oos_trades

        full_trades = scaled_trades(raw_full_trades, instrument, BASE_CONTRACTS[instrument])
        oos_trades = scaled_trades(raw_oos_trades, instrument, BASE_CONTRACTS[instrument])
        daily_full = daily_pnl(full_trades)
        daily_oos = daily_pnl(oos_trades)
        monthly_full = monthly_pnl(full_trades)

        if not full_trades.empty:
            plot_trade_equity(
                full_trades,
                f"{instrument} Equity Curve",
                instruments_dir / f"{instrument}_equity_curve.png",
            )
            plot_monthly_bars(
                monthly_full,
                f"{instrument} Monthly PnL",
                instruments_dir / f"{instrument}_monthly_pnl.png",
            )

        full_trading_days = int(full_trades["exit_date"].nunique()) if not full_trades.empty else 0
        oos_trading_days = int(oos_trades["exit_date"].nunique()) if not oos_trades.empty else 0
        full_business_days = business_days(raw_full_df.index.min(), raw_full_df.index.max()) if not raw_full_df.empty else 0
        oos_business_days = business_days(pd.Timestamp(args.oos_start), pd.Timestamp(args.oos_end))

        metrics_rows.append(
            {
                "instrument": instrument,
                "config_id": CONFIG_IDS[instrument],
                "contracts": BASE_CONTRACTS[instrument],
                "sample_start": raw_full_df.index.min() if not raw_full_df.empty else pd.NaT,
                "sample_end": raw_full_df.index.max() if not raw_full_df.empty else pd.NaT,
                "full_trades": int(full_result["n_trades"]),
                "full_win_rate": float(full_result["win_rate"]),
                "full_profit_factor": float(full_result["profit_factor"]),
                "full_trade_sharpe_rf0": float(full_result["sharpe"]),
                "full_daily_sharpe_rf3": daily_sharpe(daily_full, args.risk_free_rate),
                "full_total_pnl_usd": float(full_trades["pnl_usd"].sum()) if not full_trades.empty else 0.0,
                "full_trade_max_dd_usd": float(full_result["max_dd"] * TICK_VALUES[instrument] * BASE_CONTRACTS[instrument]),
                "full_daily_max_dd_usd": max_drawdown(daily_full.cumsum()),
                "full_ev_per_trade_usd": float(full_trades["pnl_usd"].mean()) if not full_trades.empty else 0.0,
                "full_trades_per_trading_day": float(len(full_trades) / full_trading_days) if full_trading_days else 0.0,
                "full_trades_per_business_day": float(len(full_trades) / full_business_days) if full_business_days else 0.0,
                "full_best_month_usd": float(monthly_full.max()) if not monthly_full.empty else 0.0,
                "full_worst_month_usd": float(monthly_full.min()) if not monthly_full.empty else 0.0,
                "full_positive_month_pct": float((monthly_full > 0).mean() * 100.0) if not monthly_full.empty else 0.0,
                "oos_trades": int(oos_result["n_trades"]),
                "oos_win_rate": float(oos_result["win_rate"]),
                "oos_profit_factor": float(oos_result["profit_factor"]),
                "oos_trade_sharpe_rf0": float(oos_result["sharpe"]),
                "oos_daily_sharpe_rf3": daily_sharpe(daily_oos, args.risk_free_rate),
                "oos_total_pnl_usd": float(oos_trades["pnl_usd"].sum()) if not oos_trades.empty else 0.0,
                "oos_trade_max_dd_usd": float(oos_result["max_dd"] * TICK_VALUES[instrument] * BASE_CONTRACTS[instrument]),
                "oos_daily_max_dd_usd": max_drawdown(daily_oos.cumsum()),
                "oos_ev_per_trade_usd": float(oos_trades["pnl_usd"].mean()) if not oos_trades.empty else 0.0,
                "oos_trades_per_trading_day": float(len(oos_trades) / oos_trading_days) if oos_trading_days else 0.0,
                "oos_trades_per_business_day": float(len(oos_trades) / oos_business_days) if oos_business_days else 0.0,
            }
        )

    metrics = pd.DataFrame(metrics_rows).sort_values("instrument")
    matrix, selected_profiles = determine_risk_profiles(
        raw_oos_by_inst,
        n_sims=args.mc_sims,
        eval_days=args.eval_days,
        eod_dd=EOD_DD,
        dll=DLL,
        seed=args.mc_seed,
    )

    profile_stats: dict[str, dict[str, object]] = {}
    for name in ["Low", "Med", "High"]:
        profile_row = selected_profiles[name]
        contracts = {instrument: int(profile_row[instrument]) for instrument in INSTRUMENTS}
        stats = profile_backtest_stats(raw_full_by_inst, raw_oos_by_inst, contracts)
        profile_stats[name] = stats
        plot_daily_equity(
            stats["full_daily"],
            f"{name} Risk Combined Portfolio Equity Curve",
            profiles_dir / f"{name.lower()}_combined_equity_curve.png",
        )
        plot_monthly_bars(
            stats["full_monthly"],
            f"{name} Risk Combined Portfolio Monthly PnL",
            profiles_dir / f"{name.lower()}_combined_monthly_pnl.png",
        )

    instrument_csv = reports_dir / "instrument_performance.csv"
    risk_csv = reports_dir / "risk_profile_matrix.csv"
    instrument_report = reports_dir / "INSTRUMENT_PERFORMANCE_REPORT.md"
    risk_report = reports_dir / "RISK_PROFILE_REPORT.md"

    metrics.to_csv(instrument_csv, index=False)
    pd.DataFrame(matrix).to_csv(risk_csv, index=False)
    write_instrument_report(
        instrument_report,
        metrics,
        data_dir=data_dir,
        full_start=args.full_start,
        full_end=args.full_end,
        oos_start=args.oos_start,
        oos_end=args.oos_end,
        risk_free_rate=args.risk_free_rate,
    )
    write_risk_report(
        risk_report,
        matrix,
        selected_profiles,
        profile_stats,
        mc_sims=args.mc_sims,
        eval_days=args.eval_days,
    )

    print(f"Saved: {instrument_csv}")
    print(f"Saved: {instrument_report}")
    print(f"Saved: {risk_csv}")
    print(f"Saved: {risk_report}")
    print(f"Saved visuals under: {visuals_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="backtester"))
