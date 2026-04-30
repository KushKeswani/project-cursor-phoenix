#!/usr/bin/env python3
"""
Run ``phoenix_live_pace_replay.py`` once per ``PORTFOLIO_PRESETS`` contract map.

Writes:
  * ``reports/config_snapshots/`` — YAML copies + ``prop_and_portfolio_parameters.json``
  * ``reports/live_replay_by_profile/<preset_slug>.json`` — per-preset replay stats
  * ``reports/live_replay_by_profile/MANIFEST.json`` — run index

Parallel: by default uses ``max(1, os.cpu_count() - 1)`` worker processes so one logical
core stays free. Override with ``--workers N`` or ``--sequential``.

Telegram: ``--telegram-every-minutes 5`` (or ``--telegram-every-seconds 300``) sends status
updates via ``projectx/notify/telegram.py`` (set ``PROJECTX_TELEGRAM_BOT_TOKEN`` and
``PROJECTX_TELEGRAM_CHAT_ID`` in ``projectx/.env``). This **enables live trade stats** automatically.
Use ``--fresh-output`` so progress counts are not inflated by old JSON files.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from telegram_script_done import run_with_telegram

from backtester import DLL, EOD_DD, EVAL_DAYS  # noqa: E402
from configs.portfolio_presets import (  # noqa: E402
    FOUR_TIER_PROFILES,
    INSTRUMENTS,
    PORTFOLIO_PRESETS,
    PRESET_DISPLAY_TITLES,
    PRESET_NOTES,
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return s.strip("_") or "preset"


def _active_instruments_contracts(contracts: dict[str, int]) -> tuple[str, str]:
    active = [i for i in INSTRUMENTS if int(contracts.get(i, 0)) > 0]
    if not active:
        raise ValueError("Preset has no positive contract counts")
    inst = ",".join(active)
    ctr = ",".join(str(int(contracts[i])) for i in active)
    return inst, ctr


def _parquet_min_max_ts(path: Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    df = pd.read_parquet(path)
    if isinstance(df.index, pd.DatetimeIndex) or pd.api.types.is_datetime64_any_dtype(
        getattr(df.index, "dtype", None)
    ):
        s = pd.to_datetime(df.index)
    elif "datetime" in df.columns:
        s = pd.to_datetime(df["datetime"])
    else:
        raise ValueError(f"No datetime index or 'datetime' column in {path}")
    return pd.Timestamp(s.min()), pd.Timestamp(s.max())


def intersect_calendar_span_from_parquets(data_dir: Path) -> tuple[str, str]:
    """
    Return (start_date, end_date) as YYYY-MM-DD strings: overlap where every instrument
    with a ``<SYM>.parquet`` in ``INSTRUMENTS`` has bars (max of mins, min of maxes).
    """
    spans: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    missing: list[str] = []
    for inst in INSTRUMENTS:
        pq = data_dir / f"{inst}.parquet"
        if not pq.is_file():
            missing.append(inst)
            continue
        spans.append(_parquet_min_max_ts(pq))
    if not spans:
        raise SystemExit(
            f"No parquet files found under {data_dir} for {INSTRUMENTS} — "
            "cannot use --full-data-range."
        )
    if missing:
        print(
            f"Note: no {', '.join(missing)}.parquet — span uses remaining instruments only.",
            flush=True,
        )
    t0 = max(lo for lo, _ in spans)
    t1 = min(hi for _, hi in spans)
    if t0.normalize() > t1.normalize():
        raise SystemExit(
            f"Parquet date ranges do not overlap (computed start {t0.date()} > end {t1.date()})."
        )
    return t0.strftime("%Y-%m-%d"), t1.strftime("%Y-%m-%d")


def _write_config_snapshots(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "backtester_monte_carlo_defaults": {
            "EOD_DD_usd": float(EOD_DD),
            "DLL_usd": float(DLL),
            "EVAL_DAYS": int(EVAL_DAYS),
        },
        "portfolio": {
            "instruments_order": list(INSTRUMENTS),
            "presets": {k: dict(v) for k, v in PORTFOLIO_PRESETS.items()},
            "preset_notes": dict(PRESET_NOTES),
            "preset_display_titles": dict(PRESET_DISPLAY_TITLES),
            "four_tier_profiles": dict(FOUR_TIER_PROFILES),
        },
    }
    px_yaml = REPO_ROOT / "projectx" / "config" / "settings.yaml"
    if px_yaml.is_file():
        snap["projectx_settings_yaml"] = px_yaml.read_text(encoding="utf-8")

    embedded: dict[str, str] = {}
    for src_rel in (
        "scripts/configs/prop_firm_rules_phoenix.yaml",
        "scripts/configs/prop_firm_rules.example.yaml",
        "scripts/configs/funded_payout_rules.example.yaml",
    ):
        p = REPO_ROOT / src_rel
        if p.is_file():
            dst = out_dir / Path(src_rel).name
            shutil.copy2(p, dst)
            embedded[src_rel] = p.read_text(encoding="utf-8")
    snap["embedded_yaml_files"] = embedded

    rules_md = out_dir / "PROP_RULES_AND_STATS_OUTLINE.md"
    if rules_md.is_file():
        snap["prop_rules_outline_markdown"] = rules_md.read_text(encoding="utf-8")

    (out_dir / "prop_and_portfolio_parameters.json").write_text(
        json.dumps(snap, indent=2),
        encoding="utf-8",
    )


def _telegram_configured() -> bool:
    tok = (
        os.environ.get("PROJECTX_TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    ).strip()
    chat = (
        os.environ.get("PROJECTX_TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID") or ""
    ).strip()
    return bool(tok and chat)


def _fmt_duration(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # nan
        return "n/a"
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 120:
        return f"{m}m {sec}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _telegram_status_daemon(
    stop: threading.Event,
    interval_s: float,
    prof_dir: Path,
    slugs: list[str],
    total: int,
    range_label: str,
    t0: float,
) -> None:
    """Background: periodic Telegram with bar % / ETA (.progress.json) and preset done % / ETA."""
    if interval_s <= 0:
        return
    root = REPO_ROOT
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from projectx.utils.helpers import load_dotenv_for_projectx
        from projectx.notify.telegram import send_telegram_if_configured
    except Exception as exc:
        print(f"Telegram status thread: import failed ({exc})", flush=True)
        return
    load_dotenv_for_projectx()
    while not stop.wait(timeout=interval_s):
        elapsed_sec = max(1e-6, time.perf_counter() - t0)
        em, es = int(elapsed_sec) // 60, int(elapsed_sec) % 60
        lines = [
            f"Phoenix live replay — {range_label}",
            f"Elapsed {em}m {es}s",
        ]

        slot_pcts: list[float] = []
        eta_bars: list[float] = []
        done_lines: list[str] = []
        n_done = 0

        for slug in slugs:
            jp = prof_dir / f"{slug}.json"
            prog = prof_dir / f"{slug}.progress.json"
            if jp.is_file():
                try:
                    data = json.loads(jp.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    done_lines.append(f"{slug}: (JSON incomplete)")
                    slot_pcts.append(0.0)
                    continue
                n_done += 1
                slot_pcts.append(100.0)
                lt = data.get("live_backtest_trades") or {}
                n_tr = lt.get("n_trades", "?")
                pnl = lt.get("total_pnl_usd", "?")
                wall = data.get("wall_seconds", "?")
                done_lines.append(f"{slug}: DONE wall={wall}s trades={n_tr} PnL={pnl}")
                continue

            if prog.is_file():
                try:
                    pr = json.loads(prog.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    slot_pcts.append(0.0)
                    done_lines.append(f"{slug}: (progress unreadable)")
                    continue
                pct = float(pr.get("pct_timeline") or 0.0)
                slot_pcts.append(min(100.0, max(0.0, pct)))
                eta_b = pr.get("eta_seconds_bar_remaining")
                if isinstance(eta_b, (int, float)) and eta_b is not None and eta_b >= 0:
                    eta_bars.append(float(eta_b))
                live_acc = pr.get("live_trades_accumulated", "?")
                steps = pr.get("steps_executed", "?")
                tl = pr.get("timeline_points", "?")
                done_lines.append(
                    f"{slug}: bars {pct:.1f}% ({steps}/{tl}) trades_acc={live_acc}"
                )
            else:
                slot_pcts.append(0.0)
                done_lines.append(f"{slug}: starting… (no progress file yet)")

        overall_bar = sum(slot_pcts) / len(slot_pcts) if slot_pcts else 0.0
        preset_pct = int(round(100.0 * n_done / total)) if total else 0

        eta_preset_s: float | None = None
        if n_done >= total:
            eta_preset_s = 0.0
        elif n_done > 0:
            rate = n_done / elapsed_sec
            eta_preset_s = (total - n_done) / rate

        eta_bar_s = max(eta_bars) if eta_bars else None

        if eta_bar_s is not None and eta_preset_s is not None and n_done < total:
            eta_blend = max(eta_bar_s, eta_preset_s)
            eta_line = (
                f"ETA ~{_fmt_duration(eta_blend)} "
                f"(max of bar-step {_fmt_duration(eta_bar_s)} vs preset-rate {_fmt_duration(eta_preset_s)})"
            )
        elif eta_bar_s is not None and n_done < total:
            eta_line = f"ETA (bar replay, slowest job) ~{_fmt_duration(eta_bar_s)}"
        elif eta_preset_s is not None and n_done > 0 and n_done < total:
            eta_line = f"ETA (preset finish rate) ~{_fmt_duration(eta_preset_s)}"
        elif n_done >= total:
            eta_line = "ETA: complete"
        else:
            eta_line = "ETA: n/a (wait for first progress or preset JSON)"

        lines.append(
            f"Overall ~{overall_bar:.1f}% (avg bar timeline across presets) | "
            f"Presets JSON: {n_done}/{total} ({preset_pct}%)"
        )
        lines.append(eta_line)
        lines.append("—")
        lines.extend(done_lines[:14])
        send_telegram_if_configured("\n".join(lines))


def _send_telegram_bodies(*bodies: str) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        from projectx.utils.helpers import load_dotenv_for_projectx
        from projectx.notify.telegram import send_telegram_if_configured
    except Exception:
        return
    load_dotenv_for_projectx()
    for b in bodies:
        if b.strip():
            send_telegram_if_configured(b)


def _run_live_replay_preset_worker(payload: dict[str, object]) -> dict[str, object]:
    """Child process: run one replay subprocess (must be top-level for spawn)."""
    preset_name = str(payload["preset_name"])
    inst = str(payload["inst"])
    ctr = str(payload["ctr"])
    data_dir = str(payload["data_dir"])
    start_date = str(payload["start_date"])
    end_date = str(payload["end_date"])
    out_json = str(payload["out_json"])
    trades_csv = str(payload.get("trades_csv") or "")
    live_trade_stats = bool(payload["live_trade_stats"])
    bars_window = str(payload.get("bars_window") or "session_day")
    repo_root = str(payload["repo_root"])
    py = str(payload["python"])
    replay_py = str(payload["replay_py"])

    cmd = [
        py,
        replay_py,
        "--start-date",
        start_date,
        "--end-date",
        end_date,
        "--data-dir",
        data_dir,
        "--step-mode",
        "bar",
        "--no-sleep",
        "--quiet",
        "--instruments",
        inst,
        "--contracts",
        ctr,
        "--stats-out",
        out_json,
        "--bars-window",
        bars_window,
    ]
    if live_trade_stats and trades_csv:
        cmd.extend(["--trades-csv", trades_csv])
    if not live_trade_stats:
        cmd.append("--no-live-trade-stats")

    t0 = time.perf_counter()
    r = subprocess.run(
        cmd,
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    wall = time.perf_counter() - t0
    err_tail = ""
    if r.stderr:
        err_tail = r.stderr.strip()[-4000:]
    return {
        "preset": preset_name,
        "instruments": inst,
        "contracts": ctr,
        "stats_out": out_json,
        "trades_csv": trades_csv or None,
        "exit_code": int(r.returncode),
        "wall_seconds": round(wall, 3),
        "stderr_tail": err_tail if r.returncode != 0 else "",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--year",
        type=int,
        default=None,
        help="Single calendar year (used when neither --full-data-range nor --start-date/--end-date)",
    )
    p.add_argument(
        "--full-data-range",
        action="store_true",
        help="Use overlapping calendar span from CL/MNQ/MGC/YM parquet under data-dir",
    )
    p.add_argument(
        "--start-date",
        default=None,
        help="YYYY-MM-DD (only with --end-date; overrides --year / --full-data-range)",
    )
    p.add_argument(
        "--end-date",
        default=None,
        help="YYYY-MM-DD (only with --start-date)",
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "Data-DataBento",
        help="Parquet root (default: repo Data-DataBento)",
    )
    p.add_argument(
        "--reports-dir",
        type=Path,
        default=REPO_ROOT / "reports",
    )
    p.add_argument(
        "--live-trade-stats",
        action="store_true",
        help="Forward to replay (much slower; adds live_backtest_trades + trades CSV)",
    )
    p.add_argument(
        "--bars-window",
        choices=("session_day", "range_prefix"),
        default="session_day",
        help="Forward to phoenix_live_pace_replay.py (range_prefix: causal bars; best on short ranges)",
    )
    p.add_argument(
        "--telegram-every-seconds",
        type=float,
        default=0.0,
        metavar="SEC",
        help="If > 0, Telegram status every SEC (set PROJECTX_TELEGRAM_* in projectx/.env). Enables live trade stats.",
    )
    p.add_argument(
        "--telegram-every-minutes",
        type=float,
        default=None,
        metavar="MIN",
        help="If set, Telegram every N minutes (overrides --telegram-every-seconds). Enables live trade stats.",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel preset runs (default: CPU count minus 1, minimum 1)",
    )
    p.add_argument(
        "--sequential",
        action="store_true",
        help="Run presets one after another (ignore --workers)",
    )
    p.add_argument(
        "--fresh-output",
        action="store_true",
        help="Remove prior *.json, *_live_replay_trades.csv in live_replay_by_profile (clearer Telegram progress).",
    )
    args = p.parse_args()

    data_dir = args.data_dir.expanduser().resolve()
    if not data_dir.is_dir():
        raise SystemExit(f"data-dir not found: {data_dir}")

    if args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    elif args.full_data_range:
        start_date, end_date = intersect_calendar_span_from_parquets(data_dir)
        print(f"Full data range from parquets: {start_date} .. {end_date}", flush=True)
    elif args.year is not None:
        y = int(args.year)
        start_date = date(y, 1, 1).isoformat()
        end_date = date(y, 12, 31).isoformat()
    else:
        y = date.today().year
        start_date = date(y, 1, 1).isoformat()
        end_date = date(y, 12, 31).isoformat()
        print(f"Defaulting to calendar year {y} (use --full-data-range for all parquet data)", flush=True)

    if args.start_date and not args.end_date:
        p.error("--start-date requires --end-date")
    if args.end_date and not args.start_date:
        p.error("--end-date requires --start-date")

    if args.telegram_every_minutes is not None:
        telegram_sec = max(0.0, float(args.telegram_every_minutes) * 60.0)
    else:
        telegram_sec = max(0.0, float(args.telegram_every_seconds or 0.0))

    live_trade_stats = bool(args.live_trade_stats)
    if telegram_sec > 0:
        if not live_trade_stats:
            print(
                "Enabling live trade stats (needed for Telegram trade/PnL lines).",
                flush=True,
            )
        live_trade_stats = True
        args.live_trade_stats = True
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        try:
            from projectx.utils.helpers import load_dotenv_for_projectx

            load_dotenv_for_projectx()
        except Exception:
            pass
        if not _telegram_configured():
            print(
                "Warning: Telegram updates requested but PROJECTX_TELEGRAM_BOT_TOKEN / CHAT_ID "
                "(or TELEGRAM_* aliases) are not both set (see projectx/.env.example). Sends will be skipped.",
                flush=True,
            )

    ncpu = os.cpu_count() or 2
    if args.sequential:
        workers = 1
    elif args.workers is not None:
        workers = max(1, int(args.workers))
    else:
        workers = max(1, ncpu - 1)

    reports = args.reports_dir.expanduser().resolve()
    snap_dir = reports / "config_snapshots"
    prof_dir = reports / "live_replay_by_profile"
    prof_dir.mkdir(parents=True, exist_ok=True)

    if args.fresh_output:
        for fp in prof_dir.glob("*.json"):
            try:
                fp.unlink()
            except OSError:
                pass
        for fp in prof_dir.glob("*_live_replay_trades.csv"):
            try:
                fp.unlink()
            except OSError:
                pass
        for fp in prof_dir.glob("*.progress.json"):
            try:
                fp.unlink()
            except OSError:
                pass
        print(f"Cleared prior outputs under {prof_dir}", flush=True)

    _write_config_snapshots(snap_dir)
    print(f"Wrote config snapshots under {snap_dir}", flush=True)

    replay_py = SCRIPT_DIR / "phoenix_live_pace_replay.py"
    jobs: list[dict[str, object]] = []
    for preset_name in sorted(PORTFOLIO_PRESETS.keys()):
        contracts = PORTFOLIO_PRESETS[preset_name]
        try:
            inst, ctr = _active_instruments_contracts(contracts)
        except ValueError as e:
            print(f"SKIP {preset_name}: {e}", flush=True)
            continue
        slug = _slug(preset_name)
        out_json = prof_dir / f"{slug}.json"
        trades_csv_path = (
            str(prof_dir / f"{slug}_live_replay_trades.csv")
            if live_trade_stats
            else ""
        )
        jobs.append(
            {
                "preset_name": preset_name,
                "inst": inst,
                "ctr": ctr,
                "data_dir": str(data_dir),
                "start_date": start_date,
                "end_date": end_date,
                "out_json": str(out_json),
                "trades_csv": trades_csv_path,
                "live_trade_stats": live_trade_stats,
                "bars_window": str(args.bars_window),
                "repo_root": str(REPO_ROOT),
                "python": sys.executable,
                "replay_py": str(replay_py),
            }
        )

    if jobs:
        workers = min(workers, len(jobs))

    manifest: list[dict[str, object]] = []
    batch_t0 = time.perf_counter()
    range_label = f"{start_date}..{end_date}"
    slugs = [_slug(j["preset_name"]) for j in jobs]
    stop_telegram = threading.Event()
    tg_thread: threading.Thread | None = None
    if telegram_sec > 0 and jobs:
        tg_thread = threading.Thread(
            target=_telegram_status_daemon,
            kwargs={
                "stop": stop_telegram,
                "interval_s": telegram_sec,
                "prof_dir": prof_dir,
                "slugs": slugs,
                "total": len(jobs),
                "range_label": range_label,
                "t0": batch_t0,
            },
            name="phoenix-telegram-status",
            daemon=True,
        )
        tg_thread.start()
        _send_telegram_bodies(
            f"Phoenix replay started: {len(jobs)} presets, {range_label}. "
            f"Updates every {telegram_sec / 60.0:.1f} min (bar % + ETA from .progress.json per preset)."
        )

    exit_code = 0
    try:
        if workers == 1 or len(jobs) <= 1:
            for job in jobs:
                row = _run_live_replay_preset_worker(job)
                manifest.append(row)
                tag = "OK" if row["exit_code"] == 0 else "FAIL"
                print(
                    f"{tag} {row['preset']} ({row['wall_seconds']:.1f}s) -> {Path(str(row['stats_out'])).name}",
                    flush=True,
                )
                if row["exit_code"] != 0 and row.get("stderr_tail"):
                    print(row["stderr_tail"], flush=True)
                if row["exit_code"] != 0:
                    exit_code = int(row["exit_code"])
                    break
        else:
            print(
                f"Running {len(jobs)} presets with {workers} workers (logical CPUs reported: {ncpu}, left ~1 for OS/you).",
                flush=True,
            )
            with ProcessPoolExecutor(max_workers=workers) as ex:
                future_map = {ex.submit(_run_live_replay_preset_worker, j): j for j in jobs}
                for fut in as_completed(future_map):
                    row = fut.result()
                    manifest.append(row)
                    tag = "OK" if row["exit_code"] == 0 else "FAIL"
                    print(
                        f"{tag} {row['preset']} ({row['wall_seconds']:.1f}s) -> {Path(str(row['stats_out'])).name}",
                        flush=True,
                    )
                    if row["exit_code"] != 0 and row.get("stderr_tail"):
                        print(row["stderr_tail"], flush=True)
            manifest.sort(key=lambda r: str(r["preset"]))
            bad = [r for r in manifest if int(r["exit_code"]) != 0]
            if bad:
                exit_code = int(bad[0]["exit_code"])
    finally:
        stop_telegram.set()
        if tg_thread is not None:
            tg_thread.join(timeout=5.0)

    batch_wall = time.perf_counter() - batch_t0
    _write_manifest(
        prof_dir,
        manifest,
        args,
        data_dir,
        start_date,
        end_date,
        workers,
        batch_t0,
        telegram_seconds=telegram_sec,
    )

    if telegram_sec > 0 and jobs:
        ok_ct = sum(1 for r in manifest if int(r["exit_code"]) == 0)
        _send_telegram_bodies(
            f"Phoenix replay finished ({range_label}). "
            f"OK {ok_ct}/{len(jobs)} batch wall {batch_wall:.0f}s. "
            f"See reports/live_replay_by_profile/ + MANIFEST.json."
        )

    if exit_code != 0:
        return exit_code

    ok = [r for r in manifest if int(r["exit_code"]) == 0]
    if ok:
        times = [float(r["wall_seconds"]) for r in ok]
        avg = sum(times) / len(times)
        print(
            f"Wrote {len(manifest)} profiles under {prof_dir}. "
            f"Batch wall clock: {batch_wall:.1f}s. "
            f"Per-preset CPU time avg: {avg:.1f}s (sum {sum(times):.1f}s).",
            flush=True,
        )
    else:
        print(f"Wrote {len(manifest)} profiles under {prof_dir}.", flush=True)
    return 0


def _write_manifest(
    prof_dir: Path,
    manifest: list[dict[str, object]],
    args: argparse.Namespace,
    data_dir: Path,
    start_date: str,
    end_date: str,
    workers: int,
    batch_t0: float,
    *,
    telegram_seconds: float = 0.0,
) -> None:
    batch_wall = time.perf_counter() - batch_t0
    ok = [r for r in manifest if int(r["exit_code"]) == 0]
    times = [float(r["wall_seconds"]) for r in ok] if ok else []
    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "data_dir": str(data_dir),
        "live_trade_stats": bool(args.live_trade_stats),
        "bars_window": str(args.bars_window),
        "telegram_every_seconds": float(telegram_seconds) if telegram_seconds > 0 else None,
        "workers": int(workers),
        "logical_cpus": int(os.cpu_count() or 0),
        "batch_wall_seconds": round(batch_wall, 3),
        "per_preset_wall_seconds_avg": round(sum(times) / len(times), 3) if times else None,
        "per_preset_wall_seconds_sum": round(sum(times), 3) if times else None,
        "runs": manifest,
    }
    (prof_dir / "MANIFEST.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(run_with_telegram(main, script_name="run_live_replay_all_portfolio_presets"))
