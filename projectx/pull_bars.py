"""
Pull historical OHLC from ProjectX Gateway (History/retrieveBars) and write parquet
for the same layout ``scripts/backtester.load_bars`` expects (1m OHLC recommended).

Run from repository root::

  python -m projectx.pull_bars --start-date 2026-03-01 --end-date 2026-03-25 \\
    --out-dir Data-DataBento --merge

Uses ``projectx/config/settings.yaml`` and ``projectx/.env`` (same as ``python -m projectx.main``).
Account id is not required for history retrieval.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from zoneinfo import ZoneInfo

from projectx.api.auth import AuthConfig, ProjectXAuth
from projectx.api.client import ProjectXClient
from projectx.strategy.phoenix_auto import gateway_bars_to_df
from projectx.utils.contract_pick import pick_contract_from_search
from projectx.utils.helpers import load_settings

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def _instrument_map(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in cfg.get("trading", {}).get("instruments", []):
        sym = str(row.get("symbol", "")).upper()
        if sym:
            out[sym] = row
    return out


def _retrieve_chunk(
    client: ProjectXClient,
    *,
    contract_id: Any,
    live: bool,
    bar_minutes: int,
    start_utc: datetime,
    end_utc: datetime,
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
            f"retrieveBars: errorCode={data.get('errorCode')} "
            f"message={data.get('errorMessage')!r}"
        )
    return gateway_bars_to_df(data.get("bars") or [])


def _et_days(start_d: date, end_d: date) -> list[date]:
    out: list[date] = []
    d = start_d
    while d <= end_d:
        out.append(d)
        d += timedelta(days=1)
    return out


def pull_instrument(
    client: ProjectXClient,
    *,
    symbol: str,
    inst_cfg: dict[str, Any],
    live: bool,
    start_d: date,
    end_d: date,
    bar_minutes: int,
) -> pd.DataFrame:
    search_text = str(inst_cfg.get("search_text", symbol)).strip() or symbol
    rows = client.search_contracts(live, search_text)
    if not rows:
        raise RuntimeError(f"No contracts for search_text={search_text!r} (live={live})")
    pick = pick_contract_from_search(symbol, rows)
    contract_id = pick["id"]

    parts: list[pd.DataFrame] = []
    for d in _et_days(start_d, end_d):
        day_start_et = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=ET)
        day_end_et = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=ET)
        start_utc = day_start_et.astimezone(UTC)
        end_utc = day_end_et.astimezone(UTC)
        chunk = _retrieve_chunk(
            client,
            contract_id=contract_id,
            live=live,
            bar_minutes=bar_minutes,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        if not chunk.empty:
            parts.append(chunk)
    if not parts:
        return pd.DataFrame(columns=["open", "high", "low", "close"])
    out = pd.concat(parts, axis=0).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out


def _write_parquet(df: pd.DataFrame, path: Path, *, merge: bool) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Match typical Data-DataBento: UTC index, optional volume column omitted.
    w = df.copy()
    if w.index.tz is None:
        w.index = w.index.tz_localize(ET)
    w.index = w.index.tz_convert(UTC)
    w.index.name = "datetime"
    w = w.sort_index()
    if merge and path.is_file():
        old = pd.read_parquet(path)
        if "datetime" in old.columns:
            old = old.set_index("datetime")
        old.index = pd.to_datetime(old.index, utc=True)
        w = pd.concat([old, w]).sort_index()
        w = w[~w.index.duplicated(keep="last")]
    out_df = w.reset_index()
    out_df.to_parquet(path, index=False)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Pull OHLC bars from ProjectX Gateway into parquet (backtester layout)."
    )
    p.add_argument("--start-date", required=True, help="YYYY-MM-DD (America/New_York calendar day)")
    p.add_argument("--end-date", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("Data-DataBento"),
        help="Directory for <SYMBOL>.parquet (default: Data-DataBento)",
    )
    p.add_argument(
        "--instruments",
        default=None,
        help="Comma list (default: all symbols in settings trading.instruments)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Use live=true for contract search and retrieveBars (default: sim/practice)",
    )
    p.add_argument(
        "--bar-minutes",
        type=int,
        default=1,
        help="Bar size sent to Gateway unitNumber (default: 1 for 1m parquet + load_bars resample)",
    )
    p.add_argument(
        "--merge",
        action="store_true",
        help="If parquet exists, union by time and drop duplicate timestamps (keep newest)",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Override path to settings.yaml",
    )
    args = p.parse_args(argv)

    start_d = date.fromisoformat(args.start_date)
    end_d = date.fromisoformat(args.end_date)
    if end_d < start_d:
        print("end-date must be >= start-date", file=sys.stderr)
        return 1

    cfg = load_settings(args.config)
    cred = cfg.get("credentials", {})
    user_name = cred.get("user_name") or ""
    api_key = cred.get("api_key") or ""
    if not user_name or not api_key:
        print(
            "Set credentials.user_name and credentials.api_key (or PROJECTX_* env vars).",
            file=sys.stderr,
        )
        return 1

    base_url = cfg["api"]["base_url"]
    auth_cfg = AuthConfig(
        base_url=base_url,
        user_name=user_name,
        api_key=api_key,
        refresh_margin_seconds=float(
            cfg.get("auth", {}).get("refresh_margin_seconds", 1800)
        ),
        request_timeout=float(cfg.get("auth", {}).get("request_timeout_seconds", 30)),
    )
    auth = ProjectXAuth(auth_cfg)
    client = ProjectXClient(base_url, auth, timeout=auth_cfg.request_timeout)
    try:
        auth.get_token()
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        return 1

    imap = _instrument_map(cfg)
    if args.instruments:
        symbols = [x.strip().upper() for x in args.instruments.split(",") if x.strip()]
    else:
        symbols = list(imap.keys())
    if not symbols:
        print("No instruments to pull (check settings or --instruments).", file=sys.stderr)
        return 1

    live = bool(args.live)
    out_dir = Path(args.out_dir).expanduser().resolve()
    bm = max(1, int(args.bar_minutes))

    for sym in symbols:
        if sym not in imap:
            print(f"Unknown symbol {sym!r} (not in settings trading.instruments).", file=sys.stderr)
            return 1
        try:
            df = pull_instrument(
                client,
                symbol=sym,
                inst_cfg=imap[sym],
                live=live,
                start_d=start_d,
                end_d=end_d,
                bar_minutes=bm,
            )
        except Exception as e:
            print(f"{sym}: {e}", file=sys.stderr)
            return 1
        if df.empty:
            print(f"{sym}: no rows returned for range", file=sys.stderr)
            continue
        dest = out_dir / f"{sym}.parquet"
        _write_parquet(df, dest, merge=bool(args.merge))
        print(f"{sym}: wrote {len(df)} rows -> {dest}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
