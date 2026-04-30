#!/usr/bin/env python3
"""
Offline Phoenix scan using ProjectX ``run_scan_once`` with **local parquet** only.

Satisfies goals.md §6 **offline** stack checks without Gateway credentials:
same bar load + ``fresh_entries_for_latest_bar`` path as live when ``--phoenix-data-dir`` is used.

Example::

  python scripts/phoenix_local_scan_once.py --data-dir Data-DataBento \\
    --instruments MNQ --contracts 1 --as-of-et \"2025-06-03 12:00:00\"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from configs.strategy_configs import get_config  # noqa: E402
from configs.tick_config import TICK_SIZES, TICK_VALUES  # noqa: E402
from engine.fast_engine import ExecutionOptions  # noqa: E402

ET = ZoneInfo("America/New_York")


def _stub_imap(instruments: list[str]) -> dict[str, dict[str, str]]:
    """Minimal instrument map (Gateway fields unused when loading from data_dir)."""
    return {i.upper(): {"symbol": i.upper(), "search_text": i.upper()} for i in instruments}


def _parse_sizes(instruments: list[str], contracts_csv: str) -> dict[str, int]:
    nums = [int(x.strip()) for x in contracts_csv.split(",") if x.strip()]
    if len(nums) != len(instruments):
        raise SystemExit(
            f"contracts length {len(nums)} != instruments length {len(instruments)}"
        )
    return {instruments[i].upper(): nums[i] for i in range(len(instruments))}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument(
        "--instruments",
        required=True,
        help="Comma-separated CL,MGC,MNQ,YM subset",
    )
    p.add_argument("--contracts", required=True, help="Comma ints aligned to --instruments")
    p.add_argument(
        "--as-of-et",
        required=True,
        help='Timestamp America/New_York, e.g. "2025-06-03 12:00:00"',
    )
    p.add_argument(
        "--entry-fill-mode",
        default="touch",
        choices=("touch", "touch_legacy", "touch_strict", "next_bar_open", "stop_market"),
    )
    p.add_argument(
        "--replay-range-start-et",
        default=None,
        help="Optional ET datetime; if set, load bars from this instant through --as-of-et (causal window).",
    )
    p.add_argument("--json-out", type=Path, default=None, help="Write hits + diagnostics JSON here")
    args = p.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"data-dir not found: {data_dir}")

    instruments = [x.strip().upper() for x in args.instruments.split(",") if x.strip()]
    sizes = _parse_sizes(instruments, args.contracts)
    imap = _stub_imap(instruments)

    as_of = datetime.strptime(args.as_of_et.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET)

    replay_start = None
    if args.replay_range_start_et:
        replay_start = datetime.strptime(
            args.replay_range_start_et.strip(), "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=ET)

    from projectx.strategy.phoenix_auto import run_scan_once

    exec_opts = ExecutionOptions(entry_fill_mode=str(args.entry_fill_mode))

    hits, diag_by, audit_by, bars_by = run_scan_once(
        instruments=instruments,
        sizes=sizes,
        data_dir=data_dir,
        client=None,
        gateway_sim=True,
        imap=imap,
        as_of_et=as_of,
        tick_sizes=TICK_SIZES,
        tick_values=TICK_VALUES,
        get_config_fn=get_config,
        collect_diagnostics=True,
        opening_range_addon_fetch=False,
        execution_options=exec_opts,
        replay_range_start_et=replay_start,
    )

    summary = {
        "as_of_et": as_of.isoformat(),
        "instruments": instruments,
        "contracts": sizes,
        "n_hits": len(hits),
        "hits_preview": [
            {
                "instrument": h[0],
                "direction": h[1].get("direction"),
                "entry_ts": str(h[1].get("entry_ts")),
            }
            for h in hits[:20]
        ],
        "diagnostic_kinds": {
            k: [d.get("kind") for d in v[:12]] for k, v in diag_by.items()
        },
        "bars_last_ts": {
            k: (str(df.index[-1]) if len(df) else None) for k, df in bars_by.items()
        },
    }
    print(json.dumps(summary, indent=2, default=str))

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {args.json_out}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
