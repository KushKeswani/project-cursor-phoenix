#!/usr/bin/env python3
"""
Compare Phoenix live-pace / realism replay closed trades to a ProjectX / Tradovate
`trades_export.csv` for the same calendar span.

Writes CSV + concise markdown under --out-dir (default: reports/benchmarks/).

Example (after running run_phoenix_realism_harness for the same window + preset):

  python3 scripts/compare_realism_replay_vs_projectx_fills.py \\
    --projectx-csv REAL_PROJECT_X_APRIL/trades_export.csv \\
    --replay-trades-csv reports/live_realism/balanced_50k_survival/2026_03_28_to_2026_04_28/phoenix_live_replay_trades.csv
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Roots must be matched longest-first (e.g. MNQ before M if we ever add single-letter).
_INSTRUMENT_ROOTS: tuple[str, ...] = ("MGC", "MNQ", "MYM", "MES", "CL", "YM", "NQ", "ES")
_CONTRACT_RE = re.compile(r"^([A-Z]+)")


def _root_symbol(contract_name: str) -> str:
    s = str(contract_name).strip().upper()
    for root in sorted(_INSTRUMENT_ROOTS, key=len, reverse=True):
        if s.startswith(root):
            return root
    m = _CONTRACT_RE.match(s)
    return m.group(1) if m else s


def _parse_px_dt(series: pd.Series) -> pd.Series:
    """ProjectX export uses e.g. '04/13/2026 12:44:19 -04:00' (ET offset)."""
    return pd.to_datetime(series, format="%m/%d/%Y %H:%M:%S %z", errors="coerce")


def load_projectx_trades(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "instrument",
                "entry_et",
                "exit_et",
                "direction",
                "size",
                "pnl_usd",
                "fees_usd",
            ]
        )
    req = {"ContractName", "EnteredAt", "ExitedAt", "Type", "Size", "PnL"}
    missing = req - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    out = pd.DataFrame()
    out["instrument"] = df["ContractName"].map(_root_symbol)
    out["entry_et"] = _parse_px_dt(df["EnteredAt"]).dt.tz_convert(ET)
    out["exit_et"] = _parse_px_dt(df["ExitedAt"]).dt.tz_convert(ET)
    out["direction"] = df["Type"].astype(str).str.lower().str.strip()
    out["size"] = pd.to_numeric(df["Size"], errors="coerce").fillna(0).astype(int)
    out["pnl_usd"] = pd.to_numeric(df["PnL"], errors="coerce").fillna(0.0)
    fees = pd.to_numeric(df.get("Fees", 0), errors="coerce").fillna(0.0)
    out["fees_usd"] = fees
    out = out.dropna(subset=["entry_et", "exit_et"])
    return out


def load_replay_trades(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return df
    ent = pd.to_datetime(df["entry_ts_et"])
    exi = pd.to_datetime(df["exit_ts_et"])
    if ent.dt.tz is None:
        ent = ent.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
    else:
        ent = ent.dt.tz_convert(ET)
    if exi.dt.tz is None:
        exi = exi.dt.tz_localize(ET, ambiguous="infer", nonexistent="shift_forward")
    else:
        exi = exi.dt.tz_convert(ET)
    out = df.copy()
    out["entry_et"] = ent
    out["exit_et"] = exi
    out["direction"] = out["direction"].astype(str).str.lower().str.strip()
    out["size"] = pd.to_numeric(out["contracts"], errors="coerce").fillna(0).astype(int)
    out["pnl_usd"] = pd.to_numeric(out["pnl_usd"], errors="coerce").fillna(0.0)
    return out


def _stats(pnl: pd.Series) -> dict:
    pnl = pnl.astype(float)
    wins = (pnl > 0).sum()
    n = int(len(pnl))
    if n == 0:
        return {"n": 0, "total_pnl": 0.0, "win_rate": float("nan")}
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    if gl > 1e-12:
        pf: float | None = gp / gl
    elif gp > 1e-12:
        pf = None
    else:
        pf = 0.0
    return {
        "n": n,
        "total_pnl": float(pnl.sum()),
        "win_rate": wins / n,
        "profit_factor": pf,
    }


@dataclass
class MatchRow:
    px_idx: int
    replay_idx: int
    entry_delta_sec: float
    pnl_px: float
    pnl_replay: float


def greedy_match(
    px: pd.DataFrame,
    replay: pd.DataFrame,
    *,
    entry_tol_sec: int,
) -> tuple[list[MatchRow], set[int], set[int]]:
    px_i = px.sort_values("entry_et").reset_index(drop=True)
    r_i = replay.sort_values("entry_et").reset_index(drop=True)
    used_px: set[int] = set()
    used_r: set[int] = set()
    matches: list[MatchRow] = []

    for pi, prow in px_i.iterrows():
        if pi in used_px:
            continue
        best: tuple[float, int] | None = None  # (abs_delta_sec, ridx)
        for ri, rrow in r_i.iterrows():
            if ri in used_r:
                continue
            if prow["instrument"] != rrow["instrument"]:
                continue
            if prow["direction"] != rrow["direction"]:
                continue
            if int(prow["size"]) != int(rrow["size"]):
                continue
            delta = abs((prow["entry_et"] - rrow["entry_et"]).total_seconds())
            if delta > entry_tol_sec:
                continue
            if best is None or delta < best[0]:
                best = (delta, ri)
        if best is not None:
            _, ri = best
            rrow = r_i.loc[ri]
            matches.append(
                MatchRow(
                    px_idx=int(pi),
                    replay_idx=int(ri),
                    entry_delta_sec=float(best[0]),
                    pnl_px=float(prow["pnl_usd"]),
                    pnl_replay=float(rrow["pnl_usd"]),
                )
            )
            used_px.add(pi)
            used_r.add(ri)

    return matches, used_px, used_r


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--projectx-csv",
        type=Path,
        default=REPO_ROOT / "REAL_PROJECT_X_APRIL" / "trades_export.csv",
    )
    p.add_argument("--replay-trades-csv", type=Path, required=True)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "benchmarks",
    )
    p.add_argument(
        "--entry-match-seconds",
        type=int,
        default=180,
        help="Max |entry_et replay - entry_et broker| for a pair (default 180).",
    )
    p.add_argument(
        "--exclude-replay-exit-reasons",
        default="close_all_flatten",
        help="Comma-separated exit_reason substrings to drop from replay (empty to keep all).",
    )
    args = p.parse_args()

    px_path = args.projectx_csv.expanduser().resolve()
    rp_path = args.replay_trades_csv.expanduser().resolve()
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    px = load_projectx_trades(px_path)
    replay = load_replay_trades(rp_path)

    if px.empty:
        raise SystemExit(f"No rows in {px_path}")

    day_first = px["entry_et"].min().normalize()
    day_last = px["exit_et"].max().normalize()
    replay_win = replay[
        (replay["exit_et"] >= day_first) & (replay["entry_et"] <= day_last + timedelta(days=1))
    ].copy()

    sub_excl = [s.strip() for s in str(args.exclude_replay_exit_reasons or "").split(",") if s.strip()]
    if sub_excl and "exit_reason" in replay_win.columns:
        mask = pd.Series(True, index=replay_win.index)
        for sub in sub_excl:
            mask &= ~replay_win["exit_reason"].astype(str).str.contains(sub, na=False)
        replay_filtered = replay_win[mask].copy()
    else:
        replay_filtered = replay_win.copy()

    st_px = _stats(px["pnl_usd"])
    st_rp_all = _stats(replay_win["pnl_usd"])
    st_rp_filt = _stats(replay_filtered["pnl_usd"])

    matches, used_px, used_r = greedy_match(
        px.reset_index(drop=True),
        replay_filtered.reset_index(drop=True),
        entry_tol_sec=args.entry_match_seconds,
    )

    match_pnls = pd.DataFrame(
        [
            {
                "entry_delta_sec": m.entry_delta_sec,
                "pnl_projectx": m.pnl_px,
                "pnl_replay": m.pnl_replay,
                "pnl_delta_replay_minus_px": m.pnl_replay - m.pnl_px,
            }
            for m in matches
        ]
    )

    summary = {
        "projectx_csv": str(px_path),
        "replay_csv": str(rp_path),
        "px_calendar_first_entry_et": day_first.isoformat(),
        "px_calendar_last_exit_et": day_last.isoformat(),
        "projectx_trades": st_px,
        "replay_in_window_all_exit_reasons": st_rp_all,
        "replay_in_window_excluding": {"patterns": sub_excl, **_stats(replay_filtered["pnl_usd"])},
        "greedy_entry_matches_tol_sec": args.entry_match_seconds,
        "matched_pairs": len(matches),
        "unmatched_projectx": int(len(px) - len(used_px)),
        "unmatched_replay_filtered": int(len(replay_filtered) - len(used_r)),
    }
    if len(match_pnls):
        summary["matched_total_pnl_projectx"] = float(match_pnls["pnl_projectx"].sum())
        summary["matched_total_pnl_replay"] = float(match_pnls["pnl_replay"].sum())
        summary["mean_abs_pnl_delta_matched"] = float(
            (match_pnls["pnl_replay"] - match_pnls["pnl_projectx"]).abs().mean()
        )
        summary["mean_entry_delta_sec_matched"] = float(match_pnls["entry_delta_sec"].mean())

    base = "realism_replay_vs_projectx_april"
    json_path = out_dir / f"{base}_summary.json"

    def _json_safe(o: object) -> object:
        if isinstance(o, dict):
            return {str(k): _json_safe(v) for k, v in o.items()}
        if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
            return None
        if isinstance(o, (list, tuple)):
            return [_json_safe(v) for v in o]
        return o

    json_path.write_text(json.dumps(_json_safe(summary), indent=2), encoding="utf-8")

    if len(match_pnls):
        match_path = out_dir / f"{base}_matched_pairs.csv"
        # add instrument from px index
        px_sorted = px.sort_values("entry_et").reset_index(drop=True)
        r_sorted = replay_filtered.sort_values("entry_et").reset_index(drop=True)
        rows = []
        for m in matches:
            pi, ri = m.px_idx, m.replay_idx
            rows.append(
                {
                    "instrument": px_sorted.loc[pi, "instrument"],
                    "direction": px_sorted.loc[pi, "direction"],
                    "size": int(px_sorted.loc[pi, "size"]),
                    "entry_et_projectx": px_sorted.loc[pi, "entry_et"].isoformat(),
                    "entry_et_replay": r_sorted.loc[ri, "entry_et"].isoformat(),
                    "entry_delta_sec": m.entry_delta_sec,
                    "pnl_projectx": m.pnl_px,
                    "pnl_replay": m.pnl_replay,
                    "exit_reason_replay": r_sorted.loc[ri].get("exit_reason", ""),
                }
            )
        pd.DataFrame(rows).to_csv(match_path, index=False)

    # Markdown
    def _fmt_st(title: str, d: dict) -> list[str]:
        return [
            f"### {title}",
            "",
            f"- Trades: **{d['n']}**",
            f"- Total PnL: **${d['total_pnl']:,.2f}**",
            f"- Win rate: **{100.0 * d['win_rate']:.2f}%**" if d["n"] else "- Win rate: —",
            "",
        ]

    lines = [
        "# Realism replay vs Project X fills",
        "",
        f"- **Broker / export:** `{px_path}`",
        f"- **Replay trades:** `{rp_path}`",
        f"- **Comparison window (from export):** {day_first.date()} → {day_last.date()} ET (by entry span)",
        f"- **Greedy match:** same instrument, direction, size; entry times within **±{args.entry_match_seconds}s**",
        f"- **Replay subset:** rows with exits in window; excluded `exit_reason` containing: {sub_excl or '(none)'}",
        "",
        "## Aggregate PnL and counts",
        "",
    ]
    lines.extend(_fmt_st("Project X (export)", st_px))
    lines.extend(_fmt_st("Replay — all reasons in window", st_rp_all))
    lines.extend(_fmt_st("Replay — excluding flatten-style rows", st_rp_filt))
    lines.extend(
        [
            "## One-to-one entry matching",
            "",
            f"- **Matched pairs:** {len(matches)} / {len(px)} broker rows",
            f"- **Unmatched broker rows:** {summary['unmatched_projectx']}",
            f"- **Unmatched replay rows (after filter):** {summary['unmatched_replay_filtered']}",
            "",
        ]
    )
    if len(match_pnls):
        lines.extend(
            [
                f"- Matched total PnL — broker: **${summary['matched_total_pnl_projectx']:,.2f}**",
                f"- Matched total PnL — replay: **${summary['matched_total_pnl_replay']:,.2f}**",
                f"- Mean |ΔPnL| per matched pair: **${summary['mean_abs_pnl_delta_matched']:,.2f}**",
                f"- Mean entry time delta: **{summary['mean_entry_delta_sec_matched']:.1f}s**",
                "",
                f"Detail: `{out_dir / f'{base}_matched_pairs.csv'}`",
                "",
            ]
        )
    lines.extend(
        [
            "**Read carefully:** replay emits many `close_all_flatten` legs and bar-timestamped fills; "
            "broker CSV is tick-timestamped with fees. Portfolio totals rarely match exactly; "
            "the match table shows how many discrete round-trips line up on time/direction/size.",
            "",
            f"*Machine-readable summary: `{json_path}`*",
        ]
    )
    md_path = out_dir / f"{base}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    if len(match_pnls):
        print(f"Wrote {match_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
