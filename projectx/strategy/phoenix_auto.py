"""
Detect fresh Phoenix range-breakout entries by diffing fast_engine backtests
(with vs without the latest bar), then size $ risk/reward for ProjectX brackets.

Bars source: local ``scripts`` parquet (Data-DataBento layout) or Gateway History API.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from projectx.utils.contract_pick import pick_contract_from_search

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def min_bars_for_phoenix(cfg: Any) -> int:
    """Minimum resampled bars before ``run_scan_once`` / ``fresh_entries`` run.

    Historically a flat **12** (implicitly ~1h at 5m). MGC uses **8m** bars, so fewer
    rows cover the same clock time; a flat 12 delays MGC until much later in the
    session even when the Gateway contract and history are healthy.

    Keep ``prev = bars.iloc[:-1]`` with at least **10** rows so ``run_backtest`` does
    not short-circuit (see ``fast_engine.n < 10``), hence floor **11** total bars.
    """
    bm = max(1, int(getattr(cfg, "bar_minutes", 5)))
    scaled = int(math.ceil(12 * 5 / float(bm)))
    return max(11, scaled)


def in_strategy_session(now_et: datetime, cfg: Any) -> bool:
    """True if ET time is on a traded weekday and inside trade_start–trade_end (same as FastConfig)."""
    wd = now_et.weekday()
    if wd in (cfg.excluded_weekdays or set()):
        return False
    m = now_et.hour * 60 + now_et.minute
    return bool(cfg.trade_start_minutes <= m < cfg.trade_end_minutes)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_scripts_on_path() -> Path:
    root = repo_root()
    sd = root / "scripts"
    p = str(sd)
    if p not in sys.path:
        sys.path.insert(0, p)
    return root


def _normalize_entry_ts(ts: Any) -> str:
    return pd.Timestamp(ts).isoformat()


def trade_fingerprint(inst: str, t: dict[str, Any]) -> str:
    return f"{inst}|{_normalize_entry_ts(t['entry_ts'])}|{t['direction']}"


def fresh_entries_for_latest_bar(
    bars: pd.DataFrame,
    cfg: Any,
    tick_size: float,
    diagnostics: Optional[List[dict[str, Any]]] = None,
    execution: Optional[Any] = None,
) -> list[dict[str, Any]]:
    """Trades present when including the last bar but not when excluding it.

    If ``diagnostics`` is a list, the **full** run appends engine timeline events
    (range_sealed, pending_entry, entry_fill) for story / terminal output.
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
    t_full = full.get("trades") or []
    t_prev = prev.get("trades") or []
    keys_prev = {
        (_normalize_entry_ts(x["entry_ts"]), x["direction"]) for x in t_prev
    }
    out = []
    for x in t_full:
        k = (_normalize_entry_ts(x["entry_ts"]), x["direction"])
        if k not in keys_prev:
            out.append(x)
    return out


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
        highs = bars["high"].values.astype(np.float64)
        lows = bars["low"].values.astype(np.float64)
        closes = bars["close"].values.astype(np.float64)
        atr = compute_bar_atr(highs, lows, closes, 14)
        a = float(atr[i]) if i < len(atr) and not np.isnan(atr[i]) else float(atr[max(0, i - 1)])
        if np.isnan(a) or a < tick_size:
            a = tick_size
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


def trim_resampled_bars_to_as_of(bars: pd.DataFrame, as_of_et: datetime) -> pd.DataFrame:
    """Clip resampled OHLC to ``as_of_et`` (same rules as ``load_local_bars_day`` trim)."""
    if bars is None or bars.empty:
        return bars
    ao = pd.Timestamp(as_of_et)
    if ao.tzinfo is None:
        ao = ao.tz_localize(ET)
    else:
        ao = ao.tz_convert(ET)
    idx = bars.index
    if getattr(idx, "tz", None) is None:
        ao_cmp = ao.tz_localize(None)
    else:
        ao_cmp = ao.tz_convert(idx.tz)
    return bars[bars.index <= ao_cmp]


def load_local_bars_day(
    instrument: str,
    data_dir: Path,
    day: datetime,
    as_of_et: datetime,
) -> pd.DataFrame:
    ensure_scripts_on_path()
    from backtester import load_bars

    d = day.date().isoformat()
    _, bars = load_bars(instrument, data_dir, f"{d} 00:00:00", f"{d} 23:59:59")
    if bars.empty:
        return bars
    return trim_resampled_bars_to_as_of(bars, as_of_et)


def load_local_bars_range_through_as_of(
    instrument: str,
    data_dir: Path,
    range_start_et: datetime,
    as_of_et: datetime,
) -> pd.DataFrame:
    """
    Session bars from ``range_start_et``'s calendar date through ``as_of_et``'s date,
    then clipped to timestamps ``<= as_of_et``.

    Use for **causal replay**: the engine sees all history since the experiment start,
    with no lookahead past ``as_of_et`` (closer to continuous backtest / live than
    ``load_local_bars_day``, which resets each session day).
    """
    ensure_scripts_on_path()
    from backtester import load_bars

    rs = range_start_et.astimezone(ET) if range_start_et.tzinfo else range_start_et.replace(tzinfo=ET)
    ao = as_of_et.astimezone(ET) if as_of_et.tzinfo else as_of_et.replace(tzinfo=ET)
    if ao.date() < rs.date():
        return pd.DataFrame()
    start_s = f"{rs.date().isoformat()} 00:00:00"
    end_s = f"{ao.date().isoformat()} 23:59:59"
    _, bars = load_bars(instrument, data_dir, start_s, end_s)
    if bars is None or bars.empty:
        return pd.DataFrame()
    return trim_resampled_bars_to_as_of(bars, as_of_et)


def gateway_bars_to_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    recs = []
    for b in rows:
        ts = pd.Timestamp(b["t"])
        if ts.tzinfo is None:
            ts = ts.tz_localize(UTC)
        ts = ts.tz_convert(ET)
        recs.append(
            {
                "datetime": ts,
                "open": float(b["o"]),
                "high": float(b["h"]),
                "low": float(b["l"]),
                "close": float(b["c"]),
            }
        )
    df = pd.DataFrame(recs).set_index("datetime").sort_index()
    out = df.rename(columns={"open": "open", "high": "high", "low": "low", "close": "close"})
    return out[["open", "high", "low", "close"]]


def _merge_ohlc_frames(*frames: pd.DataFrame) -> pd.DataFrame:
    non_empty = [f for f in frames if f is not None and not f.empty]
    if not non_empty:
        return pd.DataFrame()
    out = pd.concat(non_empty, axis=0).sort_index()
    out = out.groupby(out.index, sort=True).last()
    return out[["open", "high", "low", "close"]]


def _retrieve_gateway_ohlc(
    client: Any,
    contract_id: Any,
    live: bool,
    bar_minutes: int,
    start_utc: datetime,
    end_utc: datetime,
    grid: dict[str, int],
) -> pd.DataFrame:
    body = {
        "contractId": contract_id,
        "live": live,
        "startTime": start_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endTime": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unit": 2,
        "unitNumber": int(bar_minutes),
        "limit": 2500,
        "includePartialBar": True,
    }
    data = client.retrieve_bars(body)
    if not data.get("success") or data.get("errorCode", -1) != 0:
        raise RuntimeError(
            f"retrieveBars: {data.get('errorCode')} {data.get('errorMessage')}"
        )
    ohlc = gateway_bars_to_df(data.get("bars") or [])
    if ohlc.empty:
        return ohlc
    hours = ohlc.index.hour
    sh, eh = grid["session_start"], grid["session_end"]
    return ohlc[(hours >= sh) & (hours < eh)]


def opening_range_addon_window_utc(
    cfg: Any, as_of_et: datetime
) -> Optional[Tuple[datetime, datetime]]:
    """UTC bounds for a dedicated retrieve covering the opening range + seal bars."""
    d = as_of_et.date()
    rs = int(cfg.range_start_minutes)
    re = int(cfg.range_end_minutes)
    bar_m = int(cfg.bar_minutes)
    h0, m0 = divmod(rs, 60)
    h1, m1 = divmod(re, 60)
    win_start_et = datetime.combine(d, time(h0, m0), tzinfo=ET)
    seal_end_et = datetime.combine(d, time(h1, m1), tzinfo=ET) + timedelta(
        minutes=bar_m * 4
    )
    cap_et = min(seal_end_et, as_of_et)
    if cap_et <= win_start_et:
        return None
    return win_start_et.astimezone(UTC), cap_et.astimezone(UTC)


def fetch_bars_gateway_for_instrument(
    client: Any,
    instrument: str,
    instrument_cfg: dict[str, Any],
    *,
    live: bool,
    as_of_et: datetime,
    opening_range_addon_fetch: bool = True,
) -> pd.DataFrame:
    ensure_scripts_on_path()
    from configs.strategy_configs import get_config
    from configs.tick_config import INSTRUMENT_GRIDS

    cfg = get_config(instrument)
    grid = INSTRUMENT_GRIDS[instrument]
    search_text = instrument_cfg.get("search_text", instrument)
    rows = client.search_contracts(live, search_text)
    if not rows:
        raise RuntimeError(f"No contracts for {search_text!r} (live={live})")
    pick = pick_contract_from_search(instrument, rows)
    # Gateway uses string contract ids (e.g. CON.F.US.MNQ.M26), same as order payloads.
    contract_id = pick["id"]

    day_start_et = as_of_et.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = day_start_et.astimezone(UTC)
    end_utc = as_of_et.astimezone(UTC)

    day_ohlc = _retrieve_gateway_ohlc(
        client,
        contract_id,
        live,
        int(cfg.bar_minutes),
        start_utc,
        end_utc,
        grid,
    )
    frames: list[pd.DataFrame] = [day_ohlc]
    if opening_range_addon_fetch:
        addon = opening_range_addon_window_utc(cfg, as_of_et)
        if addon is not None:
            a0, a1 = addon
            range_ohlc = _retrieve_gateway_ohlc(
                client,
                contract_id,
                live,
                int(cfg.bar_minutes),
                a0,
                a1,
                grid,
            )
            if not range_ohlc.empty:
                frames.append(range_ohlc)
    out = _merge_ohlc_frames(*frames)
    return out


@dataclass
class DedupeStore:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> set[str]:
        if not self.path.is_file():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return set(data.get("keys", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def add(self, key: str) -> None:
        keys = self.load()
        keys.add(key)
        self.path.write_text(json.dumps({"keys": sorted(keys)}), encoding="utf-8")

    def remove_keys_starting_with(self, prefix: str) -> None:
        keys = self.load()
        new = {k for k in keys if not k.startswith(prefix)}
        self.path.write_text(json.dumps({"keys": sorted(new)}), encoding="utf-8")


def _minutes_to_hhmm(m: int) -> str:
    return f"{m // 60}:{m % 60:02d}"


def _last_bar_session_date_et(bars: pd.DataFrame) -> date:
    ts = bars.index[-1]
    ts_et = ts.tz_convert(ET) if ts.tzinfo else ts.tz_localize(ET)
    return ts_et.date()


def filter_diagnostics_last_session_day(
    diagnostics: List[dict[str, Any]], bars: pd.DataFrame
) -> List[dict[str, Any]]:
    if bars is None or bars.empty or not diagnostics:
        return []
    ld = _last_bar_session_date_et(bars)
    return [d for d in diagnostics if d.get("date") == str(ld)]


def _opening_range_label(cfg: Any) -> str:
    rs, re = int(cfg.range_start_minutes), int(cfg.range_end_minutes)
    return f"{_minutes_to_hhmm(rs)}–{_minutes_to_hhmm(re)} ET"


def aggregate_opening_range_from_bars(
    bars: pd.DataFrame,
    cfg: Any,
    session_date: date,
) -> Dict[str, Any]:
    """H/L over bars whose open time (ET) falls in [range_start, range_end), same as fast_engine."""
    if bars is None or bars.empty:
        return {"ok": False, "reason": "no_bars", "window_label": _opening_range_label(cfg)}
    rs, re = int(cfg.range_start_minutes), int(cfg.range_end_minutes)
    highs: List[float] = []
    lows: List[float] = []
    for ts in bars.index:
        ts_et = ts.tz_convert(ET) if ts.tzinfo else ts.tz_localize(ET)
        if ts_et.date() != session_date:
            continue
        bar_min = int(ts_et.hour) * 60 + int(ts_et.minute)
        if rs <= bar_min < re:
            highs.append(float(bars.loc[ts, "high"]))
            lows.append(float(bars.loc[ts, "low"]))
    if not highs:
        return {
            "ok": False,
            "reason": "no_bars_in_range_window",
            "window_label": _opening_range_label(cfg),
        }
    return {
        "ok": True,
        "window_label": _opening_range_label(cfg),
        "n_bars": len(highs),
        "raw_high": max(highs),
        "raw_low": min(lows),
    }


def build_range_audit(
    inst: str,
    bars: pd.DataFrame,
    cfg: Any,
    session_date: date,
    filtered_diag: List[dict[str, Any]],
    tick_size: float,
) -> Dict[str, Any]:
    agg = aggregate_opening_range_from_bars(bars, cfg, session_date)
    out: Dict[str, Any] = {"instrument": inst, **agg}
    if not agg.get("ok"):
        out["engine_match"] = None
        return out
    seal = next(
        (d for d in reversed(filtered_diag) if d.get("kind") == "range_sealed"),
        None,
    )
    tol = max(float(tick_size) * 0.5, 1e-9)
    if seal is None:
        out["engine_match"] = None
        out["engine_reason"] = "no_range_sealed_in_diag"
        return out
    eh = float(seal.get("range_high", 0) or 0)
    el = float(seal.get("range_low", 0) or 0)
    mh = abs(float(agg["raw_high"]) - eh) <= tol
    ml = abs(float(agg["raw_low"]) - el) <= tol
    out["engine_high"] = eh
    out["engine_low"] = el
    out["engine_match"] = bool(mh and ml)
    return out


def format_phoenix_story(
    inst: str,
    cfg: Any,
    diagnostics: List[dict[str, Any]],
    *,
    compact: bool = False,
) -> str:
    """Human-readable engine timeline (range window, seal, levels, pending, fills)."""
    if not diagnostics:
        return ""
    rs, re = int(cfg.range_start_minutes), int(cfg.range_end_minutes)
    ts_min, te_min = int(cfg.trade_start_minutes), int(cfg.trade_end_minutes)
    win = f"{_minutes_to_hhmm(rs)}–{_minutes_to_hhmm(re)} ET"
    trade_win = f"{_minutes_to_hhmm(ts_min)}–{_minutes_to_hhmm(te_min)} ET"
    lines: List[str] = []
    if compact:
        rs_events = [d for d in diagnostics if d.get("kind") == "range_sealed"]
        if rs_events:
            last = rs_events[-1]
            lines.append(
                f"[{inst}] range {win} → box {_fmt_px(last.get('range_low'))}-{_fmt_px(last.get('range_high'))} "
                f"| long≥{_fmt_px(last.get('long_level'))} short≤{_fmt_px(last.get('short_level'))} "
                f"| sealed {last.get('ts', '')[:19]}"
            )
        pend = [d for d in diagnostics if d.get("kind") == "pending_entry"]
        ent = [d for d in diagnostics if d.get("kind") == "entry_fill"]
        if pend:
            p = pend[-1]
            lines.append(
                f"[{inst}] PENDING {p.get('side', '').upper()} (next bar open) @ bar {p.get('ts', '')[:19]}"
            )
        if ent:
            e = ent[-1]
            lines.append(
                f"[{inst}] FILL {e.get('direction', '').upper()} @ {_fmt_px(e.get('entry_price'))} @ {e.get('ts', '')[:19]}"
            )
        return "\n".join(lines) if lines else ""

    lines.append(f"  --- {inst}  (range {win}, trade {trade_win}) ---")
    for d in diagnostics:
        k = d.get("kind")
        if k == "range_sealed":
            lines.append(
                f"  • RANGE SEALED @ {d.get('ts')}  |  box [{_fmt_px(d.get('range_low'))} – {_fmt_px(d.get('range_high'))}]"
            )
            lines.append(
                f"    Long triggers if price ≥ {_fmt_px(d.get('long_level'))}  |  "
                f"Short if price ≤ {_fmt_px(d.get('short_level'))}  (both sides armed after seal)"
            )
        elif k == "pending_entry":
            lines.append(
                f"  • PENDING {str(d.get('side')).upper()}  (fills next bar open)  signal bar @ {d.get('ts')}"
            )
        elif k == "entry_fill":
            lines.append(
                f"  • FILL {str(d.get('direction')).upper()}  entry={_fmt_px(d.get('entry_price'))}  "
                f"trigger={_fmt_px(d.get('entry_trigger'))}  (H/L bar {_fmt_px(d.get('entry_high'))}/"
                f"{_fmt_px(d.get('entry_low'))})  @ {d.get('ts')}"
            )
    return "\n".join(lines)


def _fmt_px(x: Any) -> str:
    """Human-readable prices for terminal/Telegram (no scientific notation)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "?"
    av = abs(v)
    if av >= 1000:
        s = f"{v:,.2f}"
        if s.endswith(".00"):
            return s[:-3]
        return s.rstrip("0").rstrip(".")
    if av >= 1:
        s = f"{v:,.2f}"
        if s.endswith(".00"):
            return s[:-3]
        return s.rstrip("0").rstrip(".")
    return f"{v:.4f}".rstrip("0").rstrip(".")


def opening_range_notification_parts(
    inst: str,
    cfg: Any,
    ev: dict[str, Any],
    audit: Optional[Dict[str, Any]] = None,
) -> tuple[str, str]:
    """(range_sealed_text, armed_text) — two separate Telegram bodies when sent back-to-back.

    Engine emits one ``range_sealed`` event (seal and arm occur together); we still split
    so Messages shows two bubbles: box + data check, then LONG/SHORT armed levels.
    """
    rs, re = int(cfg.range_start_minutes), int(cfg.range_end_minutes)
    win = f"{_minutes_to_hhmm(rs)}–{_minutes_to_hhmm(re)} ET"
    ts = str(ev.get("ts", ""))[:19]
    sealed_lines = [
        f"[{inst}] Range built & sealed ({win}) → box "
        f"{_fmt_px(ev.get('range_low'))}–{_fmt_px(ev.get('range_high'))} @ {ts}",
    ]
    if audit:
        if audit.get("ok"):
            mm = audit.get("engine_match")
            if mm is True:
                chk = "matches engine ✓"
            elif mm is False:
                chk = "RAW vs engine MISMATCH (check gateway bars)"
            else:
                chk = str(audit.get("engine_reason", "no engine range to compare"))
            sealed_lines.append(
                f"Data check ({audit.get('window_label', '?')}): {audit['n_bars']} bars | "
                f"H/L={_fmt_px(audit.get('raw_high'))}/{_fmt_px(audit.get('raw_low'))} | {chk}"
            )
        else:
            sealed_lines.append(
                f"Data check: {audit.get('reason', 'unknown')} — "
                f"{audit.get('window_label', _opening_range_label(cfg))}"
            )
    sealed = "\n".join(sealed_lines)
    armed = "\n".join(
        [
            f"[{inst}] LONG & SHORT armed (breakout):",
            f"  LONG:  price ≥ {_fmt_px(ev.get('long_level'))}",
            f"  SHORT: price ≤ {_fmt_px(ev.get('short_level'))}",
        ]
    )
    return sealed, armed


def format_range_built_armed_message(
    inst: str,
    cfg: Any,
    ev: dict[str, Any],
    audit: Optional[Dict[str, Any]] = None,
) -> str:
    """Single combined string (terminal / logs); use opening_range_notification_parts for two Telegram sends."""
    a, b = opening_range_notification_parts(inst, cfg, ev, audit)
    return f"{a}\n\n{b}"


def format_order_signal_message(
    inst: str,
    side: str,
    tr: dict[str, Any],
    *,
    use_limit: bool,
) -> str:
    """When a new entry signal fires (API or manual): direction and model entry price."""
    try:
        ep = float(tr.get("entry_price", 0) or 0)
    except (TypeError, ValueError):
        ep = 0.0
    mode = (
        "STOP @ engine trigger"
        if use_limit and ep > 0
        else "MARKET (brackets from fill)"
    )
    et = str(tr.get("entry_ts", ""))[:19]
    return f"[{inst}] ORDER SIGNAL {side.upper()} | model entry {_fmt_px(ep)} | {mode} | bar {et}"


def phoenix_telegram_sample_bodies(
    *,
    single_combined: bool = False,
    instruments: tuple[str, ...] = ("MNQ", "MGC"),
) -> list[str]:
    """Synthetic Phoenix-style Telegram texts (illustrative prices/times) for dry-run previews."""
    ensure_scripts_on_path()
    from configs.strategy_configs import get_config

    out: list[str] = []
    inst_csv = ",".join(instruments)
    out.append(
        f"Phoenix started (phoenix-auto) — {inst_csv} | poll=30.0s | "
        "dry_run (no API orders) | engine_fill=touch | account_id=12345 (practice/sim) "
        "| 2026-04-02 10:00:00 EDT"
    )
    for sym in instruments:
        cfg = get_config(sym)
        if sym == "MNQ":
            ev: dict[str, Any] = {
                "ts": "2026-04-02T10:15:00",
                "date": "2026-04-02",
                "range_low": 20100.25,
                "range_high": 20155.5,
                "long_level": 20156.0,
                "short_level": 20099.75,
            }
            wlab = "09:55–10:10 ET"
        elif sym == "MGC":
            ev = {
                "ts": "2026-04-02T10:05:00",
                "date": "2026-04-02",
                "range_low": 3020.5,
                "range_high": 3045.0,
                "long_level": 3045.5,
                "short_level": 3020.0,
            }
            wlab = "09:30–09:45 ET"
        else:
            ev = {
                "ts": "2026-04-02T10:10:00",
                "date": "2026-04-02",
                "range_low": 100.0,
                "range_high": 101.0,
                "long_level": 101.25,
                "short_level": 99.75,
            }
            wlab = "range window ET"
        audit: dict[str, Any] = {
            "ok": True,
            "n_bars": 12,
            "raw_high": ev["range_high"],
            "raw_low": ev["range_low"],
            "engine_match": True,
            "window_label": wlab,
        }
        if single_combined:
            out.append(format_range_built_armed_message(sym, cfg, ev, audit))
        else:
            sealed, armed = opening_range_notification_parts(sym, cfg, ev, audit)
            out.extend([sealed, armed])
    tr = {"entry_price": 20156.5, "entry_ts": "2026-04-02T12:05:03"}
    out.append(format_order_signal_message("MNQ", "long", tr, use_limit=True))
    out.append(
        "[SAMPLE] On a live entry, the next Telegram would include the full placement box "
        "(SL/TP ticks, contract count) after the ORDER SIGNAL line."
    )
    return out


def load_arm_order_state(path: Path) -> dict[str, Any]:
    """Persisted working arm orders: { "MGC": {"long_oid": 1, "short_oid": 2}, ... }."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_arm_order_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def last_range_sealed_for_session_day(
    diagnostics: List[dict[str, Any]], session_date: date
) -> Optional[dict[str, Any]]:
    """Most recent range_sealed event for ``session_date`` (ET session date string on diag)."""
    day_s = str(session_date)
    cands = [
        d
        for d in diagnostics
        if d.get("kind") == "range_sealed" and str(d.get("date")) == day_s
    ]
    return cands[-1] if cands else None


def arm_exchange_valid_stop_legs(
    last_reference: float,
    long_level: float,
    short_level: float,
    tick_size: float,
) -> tuple[bool, bool]:
    """Whether a buy stop at ``long_level`` and sell stop at ``short_level`` are valid vs last price.

    Exchanges reject a **buy stop** at or below the market ("above best bid"). A **sell stop**
    must sit below the market. ``last_reference`` is usually the latest bar close from History.
    """
    ls = float(long_level)
    ss = float(short_level)
    if ls <= ss or tick_size <= 0:
        return False, False
    buf = float(tick_size) * 0.5
    lr = float(last_reference)
    long_ok = lr < ls - buf
    short_ok = lr > ss + buf
    return long_ok, short_ok


def entry_breakout_stop_valid(
    side: str,
    stop_trigger: float,
    last_reference: float,
    tick_size: float,
) -> bool:
    """Whether a resting buy/sell **stop** at ``stop_trigger`` is acceptable vs ``last_reference``.

    Long: buy stop must be **above** the market → need last < trigger.
    Short: sell stop must be **below** the market → need last > trigger.
    """
    if tick_size <= 0:
        return False
    buf = float(tick_size) * 0.5
    st = float(stop_trigger)
    lr = float(last_reference)
    s = str(side).lower()
    if s in ("long", "buy"):
        return lr < st - buf
    if s in ("short", "sell"):
        return lr > st + buf
    return False


def arm_risk_reward_usd(
    inst: str,
    cfg: Any,
    bars: pd.DataFrame,
    contracts: int,
    tick_size: float,
    tick_value: float,
) -> tuple[float, float]:
    """Dollar SL/TP for a synthetic breakout at the last bar (ATR at same index as engine arm)."""
    if bars is None or len(bars) < min_bars_for_phoenix(cfg):
        return 0.0, 0.0
    synthetic = {"entry_bar_idx": len(bars) - 1, "direction": "long"}
    return risk_reward_usd(
        inst, cfg, synthetic, bars, contracts, tick_size, tick_value
    )


def run_scan_once(
    *,
    instruments: list[str],
    sizes: dict[str, int],
    data_dir: Optional[Path],
    client: Optional[Any],
    gateway_sim: bool,
    imap: dict[str, dict[str, Any]],
    as_of_et: Optional[datetime],
    tick_sizes: dict[str, float],
    tick_values: dict[str, float],
    get_config_fn: Callable[[str], Any],
    collect_diagnostics: bool = False,
    opening_range_addon_fetch: bool = True,
    execution_options: Optional[Any] = None,
    session_bar_cache: Optional[Dict[tuple[str, str], pd.DataFrame]] = None,
    replay_range_start_et: Optional[datetime] = None,
) -> tuple[
    list[tuple[str, dict[str, Any], float, float]],
    dict[str, list[dict[str, Any]]],
    dict[str, Dict[str, Any]],
    dict[str, pd.DataFrame],
]:
    """Returns (hits, diagnostics_by_instrument, range_audit_by_instrument).

    ``diagnostics_by_instrument`` maps each symbol to engine timeline events for the
    loaded bar window (when ``collect_diagnostics`` is True); otherwise empty dict.

    ``range_audit_by_instrument`` has raw H/L over the configured opening-range window
    vs engine (when ``collect_diagnostics`` is True).

    ``bars_by_instrument`` maps each symbol to the OHLC frame used for the scan (may be empty).

    If ``replay_range_start_et`` is set (local ``data_dir`` only), bars are loaded from that
    ET date through ``as_of_et`` (prefix window). Session-day cache is ignored in that case.
    """
    ensure_scripts_on_path()
    from backtester import load_bars as _load_bars_day_range
    from engine.fast_engine import ExecutionOptions as _ExecOpts

    _exec = execution_options if execution_options is not None else _ExecOpts()
    if as_of_et is None:
        as_of_et = datetime.now(ET)
    elif as_of_et.tzinfo is None:
        as_of_et = as_of_et.replace(tzinfo=ET)
    else:
        as_of_et = as_of_et.astimezone(ET)

    out: list[tuple[str, dict[str, Any], float, float]] = []
    diagnostics_by_inst: dict[str, list[dict[str, Any]]] = {}
    range_audit_by_inst: dict[str, Dict[str, Any]] = {}
    bars_by_inst: dict[str, pd.DataFrame] = {}
    for inst in instruments:
        inst = inst.strip().upper()
        if inst not in imap:
            continue
        cfg = get_config_fn(inst)
        # Always load bars + run engine: range_sealed / diagnostics can occur before
        # trade_start (e.g. YM/MGC opening range ends 9:30 ET). Entry logic stays
        # inside trade window in fast_engine; fresh_entries only diff real trades.
        tsz = float(tick_sizes[inst])
        tv = float(tick_values[inst])
        contracts = int(sizes.get(inst, 1))

        if data_dir is not None:
            if replay_range_start_et is not None:
                bars = load_local_bars_range_through_as_of(
                    inst, data_dir, replay_range_start_et, as_of_et
                )
            elif session_bar_cache is not None:
                ao_et = as_of_et.astimezone(ET) if as_of_et.tzinfo else as_of_et.replace(
                    tzinfo=ET
                )
                dkey = ao_et.date().isoformat()
                ckey = (inst, dkey)
                if ckey not in session_bar_cache:
                    _, bb = _load_bars_day_range(
                        inst,
                        data_dir,
                        f"{dkey} 00:00:00",
                        f"{dkey} 23:59:59",
                    )
                    session_bar_cache[ckey] = bb
                bars = trim_resampled_bars_to_as_of(session_bar_cache[ckey], as_of_et)
            else:
                bars = load_local_bars_day(inst, data_dir, as_of_et, as_of_et)
        elif client is not None:
            api_live = not gateway_sim
            bars = fetch_bars_gateway_for_instrument(
                client,
                inst,
                imap[inst],
                live=api_live,
                as_of_et=as_of_et,
                opening_range_addon_fetch=opening_range_addon_fetch,
            )
        else:
            raise ValueError("Need data_dir or authenticated client for bars")

        if bars is None or len(bars) < min_bars_for_phoenix(cfg):
            continue

        bars_by_inst[inst] = bars

        diag: Optional[list[dict[str, Any]]] = [] if collect_diagnostics else None
        fresh = fresh_entries_for_latest_bar(
            bars, cfg, tsz, diagnostics=diag, execution=_exec
        )
        if collect_diagnostics and diag is not None:
            diagnostics_by_inst[inst] = filter_diagnostics_last_session_day(diag, bars)
            sd = _last_bar_session_date_et(bars)
            range_audit_by_inst[inst] = build_range_audit(
                inst, bars, cfg, sd, diagnostics_by_inst[inst], tsz
            )
        for tr in fresh:
            r_usd, rw_usd = risk_reward_usd(
                inst, cfg, tr, bars, contracts, tsz, tv
            )
            out.append((inst, tr, r_usd, rw_usd))
    return out, diagnostics_by_inst, range_audit_by_inst, bars_by_inst
