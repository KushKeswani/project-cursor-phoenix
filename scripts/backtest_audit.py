#!/usr/bin/env python3
"""
Backtest integrity audit — reproducible, conservative checks before trusting metrics.

This script does *not* prove future profitability. It *does* help ensure results are
not obviously bogus by:

1. **Reproducibility** — data path, config ids, date window, and a light file fingerprint
2. **Data quality** — monotonic 1m index, duplicates, RTH-stitched gaps, OHLC sanity
3. **Causal entries (sampled)** — each trade's entry is reproducible as a "new" signal only
   when the entry bar is included (same property live polling relies on; see
   `fresh_entries_for_latest_bar` in `projectx/strategy/phoenix_auto.py`)
4. **Execution sensitivity** — gross and commission-adjusted net under multiple
   `ExecutionOptions` (fill mode + slippage) so "headline" numbers are not a single point

Run from repo root, e.g.:

  python3 scripts/backtest_audit.py --data-dir Data-DataBento \\
    --start 2020-01-01 --end 2025-12-31 --out reports/backtest_audit.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT))

from backtester import (  # noqa: E402
    CONFIG_IDS,
    INSTRUMENTS,
    load_bars,
    raw_trades_frame,
    scaled_trades,
)
from configs.oos_defaults import DEFAULT_OOS_END, DEFAULT_OOS_START  # noqa: E402
from configs.strategy_configs import get_config  # noqa: E402
from configs.tick_config import INSTRUMENT_GRIDS, TICK_SIZES, TICK_VALUES  # noqa: E402
from engine.fast_engine import ExecutionOptions, run_backtest  # noqa: E402
from projectx.strategy.phoenix_auto import (  # noqa: E402
    min_bars_for_phoenix,
    _normalize_entry_ts,
)

DEFAULT_BASE_CONTRACTS: dict[str, int] = {"CL": 1, "MGC": 5, "MNQ": 5, "YM": 1}
DEFAULT_COMMISSION_RT_USD = 1.24
MAX_CAUSAL_SAMPLES = 50


@dataclass
class EnvSnapshot:
    python: str
    platform: str
    cwd: str
    user: Optional[str] = None


@dataclass
class DataFileFingerprint:
    path: str
    exists: bool
    size_bytes: Optional[int] = None
    mtime_utc: Optional[str] = None
    blake2b_64: Optional[str] = None
    n_rows_m2: Optional[int] = None


def _file_blake2b_64(path: Path, max_bytes: int = 1_000_000) -> str:
    h = hashlib.blake2b(digest_size=8)
    with open(path, "rb") as f:
        h.update(f.read(max_bytes))
    return h.hexdigest()


def _parquet_num_rows(path: Path) -> Optional[int]:
    try:
        import pyarrow.parquet as pq  # type: ignore[import-not-found]

        return int(pq.ParquetFile(str(path)).metadata.num_rows)  # type: ignore[union-attr]
    except Exception:
        return None


def fingerprint_parquet(path: Path) -> DataFileFingerprint:
    if not path.is_file():
        return DataFileFingerprint(str(path), exists=False)
    st = path.stat()
    n2 = _parquet_num_rows(path)
    mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
    b64: Optional[str] = None
    if st.st_size > 0 and st.st_size <= 50_000_000:
        b64 = _file_blake2b_64(path)
    return DataFileFingerprint(
        str(path),
        True,
        size_bytes=int(st.st_size),
        mtime_utc=mtime.isoformat(),
        blake2b_64=b64,
        n_rows_m2=n2,
    )


def audit_1m_data_quality(
    raw_1m: pd.DataFrame, *, name: str, gap_minutes_warn: int = 3
) -> dict[str, Any]:
    """Check raw minute bars from ``load_bars`` (first return value)."""
    if raw_1m is None or raw_1m.empty:
        return {"name": name, "ok": False, "error": "empty_1m_frame"}
    o = raw_1m
    dups = int(o.index.duplicated().sum())
    mono = bool(o.index.is_monotonic_increasing)
    idx = pd.to_datetime(o.index, errors="coerce")
    if hasattr(idx, "isna") and bool(idx.isna().any()):  # type: ignore[union-attr]
        bad_t = int(idx.isna().sum())  # type: ignore[union-attr]
    else:
        bad_t = 0
    ohlc_ok = True
    ohlc_msgs: list[str] = []
    for col in ("open", "high", "low", "close"):
        if col not in o.columns:
            ohlc_ok = False
            ohlc_msgs.append(f"missing_{col}")
    if ohlc_ok:
        h = o["high"].to_numpy(dtype=float, copy=False)
        l = o["low"].to_numpy(dtype=float, copy=False)
        if (h < l - 1e-9).any():
            ohlc_ok = False
            ohlc_msgs.append("high<low")
        c = o["close"].to_numpy(dtype=float, copy=False)
        if (c > h + 1e-6).any() or (c < l - 1e-6).any():
            ohlc_ok = False
            ohlc_msgs.append("close outside high/low")

    # Gap stats on sorted index (within loaded window)
    gap_warn = 0
    if len(o) > 1:
        delta = o.index[1:].to_numpy(dtype="datetime64[ns]") - o.index[:-1].to_numpy(
            dtype="datetime64[ns]"
        )
        delta_min = (
            (delta.astype("timedelta64[ns]").astype(np.int64) / 60_000_000_000.0)
            .astype(np.float64)
        )
        gap_warn = int((delta_min > float(gap_minutes_warn)).sum())
        p95_gap = float(np.nanpercentile(delta_min, 95)) if len(delta_min) else 0.0
    else:
        p95_gap = 0.0

    return {
        "name": name,
        "ok": ohlc_ok and bad_t == 0 and dups == 0 and mono,
        "n_rows_1m": int(len(o)),
        "duplicates": dups,
        "monotonic_index": mono,
        "na_timestamps": bad_t,
        "ohlc_sane": ohlc_ok,
        "ohlc_messages": ohlc_msgs,
        "gap_minute_bucket_over_warn": int(gap_warn),
        "gap_warn_threshold_minutes": gap_minutes_warn,
        "p95_consecutive_minute_delta": p95_gap,
    }


def _gross_net_usd(
    res: dict[str, Any], instrument: str, contracts: int, commission_rt: float
) -> tuple[int, float, float, float]:
    raw = raw_trades_frame(res)
    n = 0
    if raw.empty:
        return 0, 0.0, 0.0, 0.0
    sc = scaled_trades(raw, instrument, contracts)
    n = int(len(sc))
    gross = float(sc["pnl_usd"].sum()) if n else 0.0
    comm = commission_rt * n
    return n, gross, comm, gross - comm


def sensitivity_matrix(
    *,
    instrument: str,
    bars: pd.DataFrame,
    tick: float,
    contracts: int,
    commission_rt: float,
) -> list[dict[str, Any]]:
    """
    A small grid: fill mode × (stop/close) slippage. Reports gross and net.
    'touch' is the usual research default; 'next_bar_open' is stricter; 'touch_strict' requires wick.
    """
    fill_modes: tuple[str, ...] = ("touch", "touch_strict", "next_bar_open")
    slip_pairs: tuple[tuple[float, float], ...] = ((0, 0), (1, 1), (2, 2))
    rows: list[dict[str, Any]] = []
    for entry_fill_mode in fill_modes:
        for sl_stop, sl_close in slip_pairs:
            ex = ExecutionOptions(
                entry_fill_mode=entry_fill_mode,
                stop_slippage_ticks=sl_stop,
                close_slippage_ticks=sl_close,
            )
            res = run_backtest(
                get_config(instrument), bars, tick, return_trades=True, execution=ex
            )
            n, gross, comm, net = _gross_net_usd(res, instrument, contracts, commission_rt)
            m = res
            rows.append(
                {
                    "instrument": instrument,
                    "entry_fill_mode": entry_fill_mode,
                    "stop_slippage_ticks": sl_stop,
                    "close_slippage_ticks": sl_close,
                    "n_trades": n,
                    "gross_usd": round(gross, 2),
                    "commission_rt_usd": commission_rt,
                    "commission_total_usd": round(comm, 2),
                    "net_usd": round(net, 2),
                    "engine_n_trades": int(m.get("n_trades", 0) or 0),
                    "engine_profit_factor": float(m.get("profit_factor", 0.0) or 0.0),
                    "engine_max_dd_ticks": float(m.get("max_dd", 0.0) or 0.0),
                }
            )
    return rows


def _trade_key_row(row: Any) -> tuple[str, str]:
    d = row if isinstance(row, dict) else row.to_dict()  # type: ignore[union-attr]
    return (_normalize_entry_ts(d["entry_ts"]), str(d["direction"]))


def _keys_from_result(res: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (_normalize_entry_ts(t["entry_ts"]), str(t["direction"]))
        for t in (res.get("trades") or [])
    }


def sample_causal_verification(
    instrument: str,
    bars: pd.DataFrame,
    base_exec: ExecutionOptions,
) -> dict[str, Any]:
    """
    Prefix consistency: a trade with ``entry_bar_idx=ebi`` from the full run should (1) not
    exist when that entry bar is excluded, and (2) still appear in a *longer* prefix where the
    entry bar is *not* the last bar in the backtest. The last condition matters because
    ``run_backtest`` treats the final index as end-of-series and can differ from a mid-run bar.
    (Same reason live code diffs with vs without the last bar, but a slice of length ebi+1
    replicates a full run that **ends** on the entry -- not the same as a mid-historical entry.)
    """
    tick = float(TICK_SIZES[instrument])
    cfg = get_config(instrument)
    n = int(len(bars))
    n_min = int(min_bars_for_phoenix(cfg))
    if n < n_min:
        return {"ok": True, "skipped": True, "reason": "bars<min_bars_for_phoenix", "n_checked": 0}
    res = run_backtest(cfg, bars, tick, return_trades=True, execution=base_exec)
    tdf = raw_trades_frame(res)
    if tdf.empty:
        return {"ok": True, "skipped": False, "n_trades": 0, "n_checked": 0, "failures": []}
    tdf = tdf.sort_values("entry_ts")
    n_all = int(len(tdf))
    if n_all <= MAX_CAUSAL_SAMPLES:
        idxs = list(range(n_all))
    else:
        rng = np.random.default_rng(42)
        idxs = list(rng.choice(n_all, size=MAX_CAUSAL_SAMPLES, replace=False))
    failures: list[dict[str, str]] = []
    skipped_too_late: int = 0
    for j in idxs:
        row = tdf.iloc[j]
        ebi = int(row.get("entry_bar_idx", -1))  # type: ignore[union-attr]
        if ebi < 0:
            continue
        k = _trade_key_row(row)
        r_before = run_backtest(cfg, bars.iloc[:ebi], tick, return_trades=True, execution=base_exec)
        if k in _keys_from_result(r_before):
            failures.append(
                {
                    "entry_ts": k[0],
                    "direction": k[1],
                    "error": "trade_key_present_without_entry_bar",
                }
            )
            continue
        if ebi >= n - 1:
            skipped_too_late += 1
            continue
        pad_end = min(n, ebi + 1 + 200)
        if pad_end <= ebi + 1:
            skipped_too_late += 1
            continue
        r_pad = run_backtest(cfg, bars.iloc[:pad_end], tick, return_trades=True, execution=base_exec)
        if k not in _keys_from_result(r_pad):
            failures.append(
                {
                    "entry_ts": k[0],
                    "direction": k[1],
                    "error": "missing_in_padded_prefix",
                    "entry_bar_idx": str(ebi),
                }
            )
    return {
        "ok": len(failures) == 0,
        "skipped": False,
        "n_trades": n_all,
        "n_checked": len(idxs),
        "skipped_trades_on_final_bars": skipped_too_late,
        "failures": failures[:20],
    }


def run_instrument_block(
    instrument: str,
    data_dir: Path,
    start: str,
    end: str,
    commission_rt: float,
    base_contracts: int,
    skip_causal: bool,
) -> dict[str, Any]:
    raw_1m, bars = load_bars(instrument, data_dir, start, end)
    pq = data_dir / f"{instrument}.parquet"
    fpq = fingerprint_parquet(pq)
    dq = audit_1m_data_quality(raw_1m, name=instrument)
    tick = float(TICK_SIZES[instrument])
    base_exec = ExecutionOptions(entry_fill_mode="touch", stop_slippage_ticks=0.0, close_slippage_ticks=0.0)
    cfg = get_config(instrument)
    sens = sensitivity_matrix(
        instrument=instrument,
        bars=bars,
        tick=tick,
        contracts=base_contracts,
        commission_rt=commission_rt,
    )
    causal: dict[str, Any]
    if skip_causal:
        causal = {"skipped": True, "reason": "cli_skip_causal"}
    else:
        causal = sample_causal_verification(instrument, bars, base_exec)
    grid = INSTRUMENT_GRIDS.get(instrument, {})
    n_b = int(len(bars)) if bars is not None and len(bars) else 0
    _, g0, c0, n0 = _gross_net_usd(
        run_backtest(cfg, bars, tick, return_trades=True, execution=base_exec),
        instrument,
        base_contracts,
        commission_rt,
    )
    return {
        "instrument": instrument,
        "config_id": CONFIG_IDS.get(instrument),
        "data_parquet_fingerprint": asdict(fpq),
        "one_minute_quality": dq,
        "resampled_bars": n_b,
        "bar_minutes": int(cfg.bar_minutes) if cfg else 0,
        "session": {
            "start_hour": int(grid.get("session_start", 0)),
            "end_hour": int(grid.get("session_end", 0)),
        },
        "contracts": base_contracts,
        "tick_size": tick,
        "tick_value": float(TICK_VALUES.get(instrument, 0.0)),
        "commission_round_turn_usd": commission_rt,
        "baseline_touch_0slip": {
            "gross_usd": round(g0, 2),
            "net_usd": round(n0, 2),
            "commission_total_usd": round(c0, 2),
        },
        "sensitivity_matrix": sens,
        "causal_prefix_check": causal,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, required=True, help="Data directory (parquet/CSV as in backtester).")
    p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD) inclusive.")
    p.add_argument("--end", required=True, help="End date (YYYY-MM-DD) inclusive.")
    p.add_argument(
        "--instruments",
        nargs="*",
        default=list(INSTRUMENTS),
        help=f"Subset of {INSTRUMENTS} (default: all).",
    )
    p.add_argument(
        "--commission-rt",
        type=float,
        default=DEFAULT_COMMISSION_RT_USD,
        help=f"Assumed all-in round-turn $ per *trade* per position (default {DEFAULT_COMMISSION_RT_USD}). "
        "Futures: scale per your broker. Same multiplier applied to each leg's trade row.",
    )
    p.add_argument(
        "--base-contracts",
        type=str,
        default="",
        help="Optional: comma copy like 'MNQ:5,CL:1' overriding defaults for USD scaling "
        f"(default built-ins: {DEFAULT_BASE_CONTRACTS}).",
    )
    p.add_argument("--out", type=Path, help="Write JSON report to this path (UTF-8).")
    p.add_argument(
        "--skip-causal",
        action="store_true",
        help="Skip per-trade fresh-entry spot checks (faster; not recommended for final sign-off).",
    )
    p.add_argument(
        "--oos-start",
        default=DEFAULT_OOS_START,
        help="Optional: second window start for a short OOS summary (default from oos_defaults).",
    )
    p.add_argument(
        "--oos-end",
        default=DEFAULT_OOS_END,
        help="Optional: OOS end date.",
    )
    p.add_argument(
        "--run-oos",
        action="store_true",
        help="If set, also run a second audit block on --oos-start..--oos-end (same paths).",
    )
    args = p.parse_args()
    data_dir = args.data_dir.expanduser().resolve()
    if not data_dir.is_dir():
        print(f"data-dir not found: {data_dir}", file=sys.stderr)
        return 1

    contracts: dict[str, int] = dict(DEFAULT_BASE_CONTRACTS)
    if args.base_contracts.strip():
        for part in args.base_contracts.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, v = part.split(":", 1)
            contracts[k.strip().upper()] = max(1, int(v.strip()))
    for ins in args.instruments:
        if ins not in INSTRUMENTS:
            print(f"Unknown instrument: {ins}", file=sys.stderr)
            return 1
    comm = float(args.commission_rt)

    report: dict[str, Any] = {
        "title": "Agent Phoenix — backtest audit",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "date_window": {"start": args.start, "end": args.end},
        "data_dir": str(data_dir),
        "environment": asdict(
            EnvSnapshot(
                python=sys.version.split()[0],
                platform=sys.platform,
                cwd=os.getcwd(),
                user=os.environ.get("USER"),
            )
        ),
    }

    blocks: list[dict[str, Any]] = []
    for inst in args.instruments:
        blocks.append(
            run_instrument_block(
                inst,
                data_dir,
                args.start,
                args.end,
                comm,
                contracts[inst],
                bool(args.skip_causal),
            )
        )
    report["instruments"] = blocks

    if args.run_oos and args.oos_start and args.oos_end:
        oos_blocks: list[dict[str, Any]] = []
        for inst in args.instruments:
            b = run_instrument_block(
                inst,
                data_dir,
                str(args.oos_start),
                str(args.oos_end),
                comm,
                contracts[inst],
                bool(args.skip_causal),
            )
            b["window"] = "oos"
            b["date_window"] = {"start": str(args.oos_start), "end": str(args.oos_end)}
            oos_blocks.append(b)
        report["oos_instruments"] = oos_blocks

    # Summary: net under conservative row (next_bar_open, +2 slip) vs optimistic (touch, 0)
    summary_rows: list[dict[str, Any]] = []
    for b in blocks:
        inst = b["instrument"]
        sens = b.get("sensitivity_matrix") or []
        opt = next(
            (x for x in sens if x.get("entry_fill_mode") == "touch" and x.get("stop_slippage_ticks") == 0),
            None,
        )
        pess = next(
            (
                x
                for x in sens
                if x.get("entry_fill_mode") == "next_bar_open" and x.get("stop_slippage_ticks") == 2.0
            ),
            None,
        )
        summary_rows.append(
            {
                "instrument": inst,
                "optimistic_net_usd_touch_0slip": (opt or {}).get("net_usd"),
                "pessimistic_net_usd_nbo_2slip": (pess or {}).get("net_usd"),
            }
        )
    report["honesty_spread"] = {
        "description": "net_usd: optimistic=touch+0 slippage vs pessimistic=next_bar_open+2 tick slip "
        f"(same commission {comm} per trade row).",
        "per_instrument": summary_rows,
    }
    for b in blocks:
        dq = b.get("one_minute_quality") or {}
        if not dq.get("ok"):
            report["warnings"] = report.get("warnings") or []
            report["warnings"].append(f"data quality issues: {b.get('instrument')} — {dq}")

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.out:
        out_path = args.out.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"\nWrote: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
