#!/usr/bin/env python3
"""Compare TradingView PhxRB list export to reports/mnq_trades_python_for_tv_compare.csv.

TV exports use UTF-8 BOM; this script opens TV paths with encoding utf-8-sig.

Examples:
  python scripts/compare_tv_phxrb_to_python_trades.py
  python scripts/compare_tv_phxrb_to_python_trades.py \\
    --tv "Trading_View/PhxRB_CME_MINI_MNQ1!_2026-04-15_e2b35.csv"
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def parse_tv_roundtrips(path: Path) -> list[dict]:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    by_id: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_id[int(r["Trade #"])].append(r)
    out: list[dict] = []
    for n in sorted(by_id):
        ent = ex = None
        for p in by_id[n]:
            t = p["Type"].lower()
            if "entry" in t:
                ent = p
            elif "exit" in t:
                ex = p
        if not ent or not ex:
            continue
        side = "long" if "long" in ent["Type"].lower() else "short"
        et = datetime.strptime(ent["Date and time"], "%Y-%m-%d %H:%M")
        xt = datetime.strptime(ex["Date and time"], "%Y-%m-%d %H:%M")
        out.append(
            {
                "id": n,
                "entry": et,
                "exit": xt,
                "dir": side,
                "ep": float(ent["Price USD"]),
                "xp": float(ex["Price USD"]),
                "pnl_usd": float(ex["Net P&L USD"]),
            }
        )
    return out


def parse_python(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            et = datetime.strptime(row["entry_ts"][:16], "%Y-%m-%d %H:%M")
            xt = datetime.strptime(row["exit_ts"][:16], "%Y-%m-%d %H:%M")
            out.append(
                {
                    "entry": et,
                    "exit": xt,
                    "dir": row["direction"].strip(),
                    "ep": float(row["entry_price"]),
                    "xp": float(row["exit_price"]),
                    "ticks": float(row["pnl_ticks"]),
                    "reason": row["exit_reason"],
                }
            )
    return out


def entry_key(x: dict) -> tuple[str, str]:
    return (x["entry"].strftime("%Y-%m-%d %H:%M"), x["dir"])


def default_tv_path(root: Path) -> Path:
    pattern = "PhxRB_CME_MINI_MNQ1!_*.csv"
    cands = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise SystemExit(f"No TV files matching {root}/{pattern}")
    return cands[0]


def _rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--tv",
        type=Path,
        default=None,
        help="TV export CSV (default: newest Trading_View/PhxRB_CME_MINI_MNQ1!_*.csv)",
    )
    ap.add_argument(
        "--py",
        type=Path,
        default=root / "reports" / "mnq_trades_python_for_tv_compare.csv",
        help="Python compare CSV",
    )
    args = ap.parse_args()
    tv_path = args.tv if args.tv is not None else default_tv_path(root / "Trading_View")
    py_path = args.py if args.py.is_absolute() else root / args.py

    tv = parse_tv_roundtrips(tv_path)
    py = parse_python(py_path)
    if not tv:
        raise SystemExit("No round trips parsed from TV file.")

    d0, d1 = tv[0]["entry"].date(), tv[-1]["entry"].date()
    py_f = [x for x in py if d0 <= x["entry"].date() <= d1]

    tv_m = defaultdict(list)
    for x in tv:
        tv_m[entry_key(x)].append(x)
    py_m = defaultdict(list)
    for x in py_f:
        py_m[entry_key(x)].append(x)

    ks_tv, ks_py = set(tv_m), set(py_m)
    both, only_tv, only_py = ks_tv & ks_py, ks_tv - ks_py, ks_py - ks_tv

    exit_diff = 0
    for k in both:
        t, p = tv_m[k][0], py_m[k][0]
        if t["exit"].strftime("%Y-%m-%d %H:%M") != p["exit"].strftime("%Y-%m-%d %H:%M"):
            exit_diff += 1

    print("TV file:", _rel(tv_path.resolve(), root))
    print("Python file:", _rel(py_path.resolve(), root))
    print()
    print("TV round trips:", len(tv), "  entry span:", d0, "->", d1)
    print("Python rows in span:", len(py_f))
    print()
    print("Match on (entry ET minute, direction):")
    print("  both:", len(both), "  only TV:", len(only_tv), "  only Python:", len(only_py))
    print("  exit minute differs (among both):", exit_diff)
    if only_tv:
        print("\nSample only-TV (up to 8):")
        for k in sorted(only_tv)[:8]:
            x = tv_m[k][0]
            print(f"  {k[0]} {k[1]} entry={x['ep']:.2f}")
    if only_py:
        print("\nSample only-Python (up to 8):")
        for k in sorted(only_py)[:8]:
            x = py_m[k][0]
            print(f"  {k[0]} {k[1]} entry={x['ep']:.2f}")


if __name__ == "__main__":
    main()
