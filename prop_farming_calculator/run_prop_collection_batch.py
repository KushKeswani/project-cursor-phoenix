#!/usr/bin/env python3
"""
Run the prop-farming Monte Carlo once per plan in docs/prop_firm_collection.filled.json
and emit a single markdown report (pool bootstrap + 12m horizon lifecycle stats).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_CALC = Path(__file__).resolve().parent
if str(_CALC) not in sys.path:
    sys.path.insert(0, str(_CALC))

from _paths import REPO_ROOT, ensure_scripts_on_path

ensure_scripts_on_path()

_SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from telegram_script_done import notify_script_finished

from configs.portfolio_presets import FOUR_TIER_PROFILES
from data_loader import build_daily_monthly, load_executions_from_dir
from simulation import (
    FarmSimParams,
    HORIZONS,
    build_eval_rules,
    pool_diagnostics,
    run_horizon_batch,
)

def _money(x: float) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "—"
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "—"
    return f"{x:.1f}%"


def _f1(x: float) -> str:
    if isinstance(x, float) and math.isnan(x):
        return "—"
    return f"{x:.1f}"


def _pick_portfolio_key(account_size_usd: int, choice: str) -> str:
    """Match contract-stack preset to account notional (50 vs 150) and survival vs high."""
    is_150 = int(account_size_usd) >= 100_000
    high = "high" in (choice or "").lower()
    if is_150:
        k = "150k_high" if high else "150k_low"
    else:
        k = "50k_high" if high else "50k_low"
    return FOUR_TIER_PROFILES[k]


def _synthetic_daily(seed: int = 42, n_days: int = 900) -> pd.Series:
    """Placeholder i.i.d. daily PnL when trade CSVs are absent (demo / wiring only)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-02", periods=n_days, freq="C")
    pnl = rng.normal(120.0, 950.0, size=n_days)
    return pd.Series(pnl, index=idx, dtype=float)


def _plan_farm(
    plan: dict,
    *,
    n_sims: int,
    seed: int,
    accounts: int,
    challenge_billing: str,
    use_vps: bool,
    vps_monthly: float,
    express_first: float,
    express_split: float,
) -> tuple[object, FarmSimParams]:
    ev = plan["evaluation"]
    fd = plan["funded"]
    act = ev.get("activation_fee_usd")
    challenge_fee = float(act) if act is not None else 99.0
    activation_fee = float(act) if act is not None else 0.0

    aud_target = float(ev["profit_target_usd"])
    aud_dd = float(ev["trailing_drawdown_usd"])
    aud_days = int(ev["eval_window_days_for_sim"])
    dll = ev.get("daily_loss_limit_usd")
    aud_dll = float(dll) if dll is not None else None
    cons = ev.get("consistency_max_best_day_fraction")
    cons_frac = float(cons) if cons is not None else None
    min_ev_days = ev.get("min_trading_days")
    aud_min_days = int(min_ev_days) if min_ev_days is not None else 1

    size_usd = float(plan["account_size_usd"])
    funded_trail = fd.get("max_or_trailing_drawdown_usd")
    funded_trail_v = float(funded_trail) if funded_trail is not None else aud_dd

    inc = fd.get("payout_increment_usd")
    min_profit = max(100.0, float(inc) * 0.2) if inc is not None else 150.0
    n_qual = fd.get("min_trading_days_between_payouts")
    n_qual_i = int(n_qual) if n_qual is not None else 5

    cap = fd.get("max_payout_per_request_usd")
    funded_cap = float(cap) if cap is not None else None

    rules = build_eval_rules(
        profit_target_usd=aud_target,
        trailing_drawdown_usd=aud_dd,
        eval_window_days=aud_days,
        daily_loss_limit_usd=aud_dll,
        consistency_max_best_day_fraction=cons_frac,
        min_trading_days=max(1, aud_min_days),
    )
    farm = FarmSimParams(
        n_sims=n_sims,
        seed=seed,
        n_accounts=accounts,
        start_frequency="monthly",
        challenge_fee_usd=challenge_fee,
        challenge_billing=challenge_billing,  # type: ignore[arg-type]
        activation_fee_usd=activation_fee,
        use_vps=use_vps,
        vps_monthly_usd=vps_monthly,
        min_profit_per_day_usd=min_profit,
        n_qualifying_days=n_qual_i,
        withdraw_fraction=0.5,
        funded_starting_balance_usd=size_usd,
        funded_trail_on_profit_usd=funded_trail_v,
        funded_payout_cap_usd=funded_cap,
        express_trader_first_full_usd=express_first,
        express_trader_split_after_first=express_split,
    )
    return rules, farm


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--collection-json",
        type=Path,
        default=REPO_ROOT / "docs" / "prop_firm_collection.filled.json",
    )
    p.add_argument(
        "--execution-reports-dir",
        type=Path,
        default=REPO_ROOT / "reports",
    )
    p.add_argument("--scope", choices=["oos", "full"], default="oos")
    p.add_argument(
        "--portfolio",
        default="50k-survival",
        help="Contract stack tier (50k-survival, 150k-survival, …); auto-maps by account size if unset logic applies",
    )
    p.add_argument("--trade-mult", type=float, default=1.0)
    p.add_argument("--n-sims", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--accounts", type=int, default=1)
    p.add_argument(
        "--challenge-billing", choices=["one_time", "monthly"], default="one_time"
    )
    p.add_argument("--no-vps", action="store_true")
    p.add_argument("--vps-monthly", type=float, default=199.0)
    p.add_argument("--express-first-full-usd", type=float, default=10_000.0)
    p.add_argument("--express-split", type=float, default=0.9)
    p.add_argument(
        "--out-md",
        type=Path,
        default=REPO_ROOT / "reports" / "PROP_FIRM_SIM_AGGREGATE_REPORT.md",
    )
    p.add_argument(
        "--allow-synthetic-pool",
        action="store_true",
        help="If execution CSVs are missing, use a labeled synthetic daily PnL pool (not real performance).",
    )
    p.add_argument(
        "--cap-eval-window-to-pool",
        action="store_true",
        help="If len(daily) < eval window, set W=len(daily) so eval+funded can run (not the firm’s official window).",
    )
    p.add_argument(
        "--no-telegram",
        action="store_true",
        help="Disable Telegram notifications (default: send when token + chat id are configured).",
    )
    args = p.parse_args()
    telegram_on = not bool(args.no_telegram)

    data = json.loads(args.collection_json.read_text(encoding="utf-8"))
    firms = data.get("firms", [])
    if not firms:
        print("No firms in collection JSON.", file=sys.stderr)
        if telegram_on:
            notify_script_finished(
                "run_prop_collection_batch",
                exit_code=1,
                detail="No firms in collection JSON.",
            )
        return 1

    n_plans_json = sum(len(f.get("plans") or []) for f in firms)

    exec_dir = args.execution_reports_dir.expanduser().resolve()
    raw = load_executions_from_dir(exec_dir, args.scope)
    lines: list[str] = [
        "# Prop firm simulation — aggregate report",
        "",
        f"Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "",
    ]
    if args.allow_synthetic_pool:
        lines.append(
            "> **Note:** `--allow-synthetic-pool` was set. If execution CSVs were missing, "
            "this run uses an **i.i.d. synthetic** daily PnL series — numbers are for **pipeline "
            "testing only**, not predictive of your trading."
        )
        lines.append("")
    if args.cap_eval_window_to_pool:
        lines.append(
            "> **Note:** `--cap-eval-window-to-pool` is on — eval window **W** is shrunk to **min(W, len(daily))** "
            "when the pool is short. Payouts can be non-zero but **do not match** official firm eval length."
        )
        lines.append("")

    lines.extend(
        [
            "## Method (read this first)",
            "",
            "- **Historical pool:** Daily PnL is bootstrapped from your `reports/trade_executions` CSVs "
            f"(`scope={args.scope}`), unless synthetic fallback applies (see top note). "
            "Each plan uses the **same** return distribution; only rule parameters differ.",
            "- **Eval phase:** Cumulative profit vs trailing drawdown (from peak profit), optional DLL, optional "
            "consistency (`best_day / cumulative_profit ≤ max_fraction` at pass).",
            "- **Funded phase:** Simplified Topstep-style engine (qualifying streak → withdrawal as a fraction of "
            "profits; optional **Express** gross cap + trader split when `max_payout_per_request_usd` is set). "
            "This is a **research proxy**, not a line-by-line clone of each firm’s UI.",
            "- **Horizon:** Metrics below for **12 Months** (~252 trading days) single-lifecycle MC unless noted.",
            "- **Rolling eval pass %:** For **every** trading day `t`, eval rules run on the **actual** next "
            f"`W` contiguous days (`W` = eval window). Key: `mc_eval_pass_pct`.",
            "- **Lifecycle MC (12m):** Each simulation draws a **random start** in the pool and uses **contiguous** "
            "calendar-ordered days for the eval window, then **contiguous** funded days (wrapping at the end of the "
            "series). This matches the rolling-window definition (same population of eval windows as “random start”), "
            "unlike older i.i.d. resampling which inflated pass rates.",
            "- **Payout columns ($ / % with payout):** Funded payouts exist only if the path **passes eval** and the "
            "simulator reaches the funded leg. If the pool has **fewer trading days than the eval window**, every "
            "path stops as **insufficient history** → **$0 payouts** (not a bug). Use more history, or "
            "`--cap-eval-window-to-pool` for a sandbox run.",
            "",
            "| Column | Meaning |",
            "|--------|---------|",
            "| Rolling eval pass % | % of start-days whose next W contiguous days pass (target + consistency, no trail/DLL breach before pass) |",
            "| Avg days to pass (rolling) | Mean days-to-pass among those passing windows only |",
            "| Lifecycle eval pass % | % of full horizon paths that pass eval at least once in the sampled lifecycle |",
            "| Avg monthly payout ($) | Mean total simulated payouts ÷ (horizon days / 21) |",
            "| Avg days to 1st payout | Mean trading days from sim start until first funded payout (paths with ≥1 payout) |",
            "| Avg days between payouts | Among paths with ≥2 payouts, mean spacing |",
            "| % sims w/ payout | Share of paths with any funded payout |",
            "| % sims: insufficient history | Stopped before eval could complete (pool shorter than eval window W) — funded leg never run |",
            "",
            "## Results by firm and plan",
            "",
        ]
    )

    # Load daily once per portfolio key we need
    portfolio_cache: dict[str, object] = {}
    summary_rows: list[dict[str, str | float]] = []
    meta = data.get("collection_meta") or {}
    if meta:
        lines.append(
            f"*Source rules JSON:* `{args.collection_json}` · "
            f"*schema* {meta.get('schema_version', '?')} · "
            f"*as of* {meta.get('last_updated', '?')}"
        )
        lines.append("")

    for firm in firms:
        fid = firm.get("id", "?")
        fname = firm.get("display_name", fid)
        lines.append(f"### {fname} (`{fid}`)")
        lines.append("")
        firm_runs = 0
        for plan in firm.get("plans", []):
            pkey = plan.get("plan_key", "?")
            label = plan.get("marketing_name") or pkey
            acc_lbl = plan.get("account_size_label", "")
            size = int(plan.get("account_size_usd") or 0)

            pk = _pick_portfolio_key(size, args.portfolio)
            if pk not in portfolio_cache:
                _, daily, warns = build_daily_monthly(
                    raw, pk, args.trade_mult
                )
                if daily.empty and args.allow_synthetic_pool:
                    salt = sum(ord(c) for c in pk) % 10_000
                    daily = _synthetic_daily(seed=args.seed + salt)
                    warns = [
                        f"Synthetic i.i.d. daily pool (no `trade_executions` for `{pk}`)."
                    ]
                if daily.empty:
                    lines.append(
                        f"#### {label} ({acc_lbl}) — **skipped** (empty daily pool for `{pk}`)\n"
                    )
                    if warns:
                        lines.append(f"- Warnings: {warns}\n")
                    portfolio_cache[pk] = None
                    continue
                portfolio_cache[pk] = (daily, warns)
            cached = portfolio_cache[pk]
            if cached is None:
                continue
            daily, warns = cached  # type: ignore[misc]
            warns = list(warns)

            rules, farm = _plan_farm(
                plan,
                n_sims=args.n_sims,
                seed=args.seed + (sum(ord(c) for c in pkey) % 10_000),
                accounts=args.accounts,
                challenge_billing=args.challenge_billing,
                use_vps=not args.no_vps,
                vps_monthly=args.vps_monthly,
                express_first=args.express_first_full_usd,
                express_split=args.express_split,
            )

            orig_eval_window = int(rules.eval_window_days)
            nd = len(daily)
            if args.cap_eval_window_to_pool and nd >= 1 and nd < orig_eval_window:
                rules = replace(rules, eval_window_days=nd)
                warns.append(
                    f"`--cap-eval-window-to-pool`: eval window {orig_eval_window}d → {nd}d (pool length) — "
                    "exploratory; official firm window not met."
                )

            ew = int(rules.eval_window_days)
            if nd < ew:
                warns.append(
                    f"Only {nd} trading days in pool; eval window is {ew}d — "
                    "rolling stats use 0 windows and lifecycle cannot score eval (insufficient history)."
                )

            diag = pool_diagnostics(
                daily,
                rules,
                n_sims=min(5000, args.n_sims),
                seed=args.seed,
            )
            hz_12 = next((h for h in HORIZONS if h[1] == "12 Months"), None)
            if hz_12 is None:
                hz_12 = HORIZONS[-2]
            _, _lbl, h_days = hz_12
            batch = run_horizon_batch(daily, h_days, rules, farm)

            mc_pass = float(diag.get("mc_eval_pass_pct", 0.0))
            mc_days_pass = float(diag.get("mc_eval_mean_days_to_pass", 0.0))
            life_pass = float(batch.get("audition_pass_pct", 0.0))
            avg_mo = float(batch.get("avg_monthly_payout_usd", 0.0))
            d_first = float(batch.get("mean_days_to_first_payout_trading", float("nan")))
            d_between = float(
                batch.get("mean_days_between_payouts_conditional", float("nan"))
            )
            pct_pay = float(batch.get("pct_simulations_with_any_payout", 0.0))
            pct_insuf = float(batch.get("funnel_pct__eval_insufficient_history", 0.0))

            funded_model = (
                "express_capped"
                if farm.funded_payout_cap_usd is not None
                else "classic"
            )
            lines.append(f"#### {label} — {acc_lbl} ({pkey})")
            lines.append("")
            lines.append(
                f"- **Portfolio contracts:** `{pk}` · **Funded model:** {funded_model} · "
                f"**Challenge fee:** {_money(farm.challenge_fee_usd)} ({args.challenge_billing}) · "
                f"**Activation:** {_money(farm.activation_fee_usd)}"
            )
            lines.append(
                f"- **Eval:** target {_money(rules.profit_target_usd)}, trail {_money(rules.trailing_drawdown_usd)}, "
                f"window {rules.eval_window_days}d, min days {rules.min_trading_days}"
            )
            if warns:
                lines.append(f"- **Data warnings:** {', '.join(warns)}")
            lines.append("")
            lines.append("| Stat | Value |")
            lines.append("|------|-------|")
            lines.append(f"| Rolling eval pass % | {_pct(mc_pass)} |")
            lines.append(f"| Avg days to pass (rolling, eval-only) | {_f1(mc_days_pass)} |")
            lines.append(f"| Lifecycle eval pass % (12m horizon) | {_pct(life_pass)} |")
            lines.append(f"| Avg monthly payout (trader, 12m) | {_money(avg_mo)} |")
            lines.append(f"| Avg days to first payout | {_f1(d_first)} |")
            lines.append(f"| Avg days between payouts (≥2 payouts) | {_f1(d_between)} |")
            lines.append(f"| % simulations with any payout | {_pct(pct_pay)} |")
            lines.append(
                f"| % sims: insufficient history (funded leg not reached) | {_pct(pct_insuf)} |"
            )
            lines.append("")
            if pct_insuf >= 50.0 and pct_pay < 0.5:
                lines.append(
                    "> **Why $0 payouts:** Almost all paths hit **insufficient history** — the daily pool has "
                    f"**{nd}** trading days but the eval needs **{orig_eval_window}** contiguous days to finish. "
                    "The funded simulator **never runs**, so payout stats stay at $0. "
                    "**Fix:** point `--execution-reports-dir` at exports with ≥ "
                    f"{orig_eval_window} trading days (add instruments / longer OOS), or run with "
                    "`--cap-eval-window-to-pool` to shrink W to the pool for exploration only."
                )
                lines.append("")

            summary_rows.append(
                {
                    "firm": str(fname),
                    "plan": f"{label} ({acc_lbl})",
                    "mc_pass_pct": mc_pass,
                    "mc_days_to_pass": mc_days_pass,
                    "life_pass_pct": life_pass,
                    "avg_monthly_payout_usd": avg_mo,
                    "days_to_first_payout": d_first,
                    "days_between_payouts": d_between,
                    "pct_any_payout": pct_pay,
                }
            )
            firm_runs += 1

    if summary_rows:
        lines.append("## Summary table (12 month horizon)")
        lines.append("")
        lines.append(
            "| Firm | Plan | Rolling eval pass % | Avg days to pass (roll) | "
            "Lifecycle pass % | Avg $/mo payout | Avg days to 1st payout | "
            "Avg days between payouts | % sims w/ payout |"
        )
        lines.append(
            "|------|------|---------------------|-------------------------|-----------------|----------------|----------------------|-------------------------|------------------|"
        )
        for r in summary_rows:
            lines.append(
                f"| {r['firm']} | {r['plan']} | {_pct(float(r['mc_pass_pct']))} | "
                f"{_f1(float(r['mc_days_to_pass']))} | {_pct(float(r['life_pass_pct']))} | "
                f"{_money(float(r['avg_monthly_payout_usd']))} | "
                f"{_f1(float(r['days_to_first_payout']))} | "
                f"{_f1(float(r['days_between_payouts']))} | "
                f"{_pct(float(r['pct_any_payout']))} |"
            )
        lines.append("")

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out_md}")
    if telegram_on:
        notify_script_finished(
            "run_prop_collection_batch",
            exit_code=0,
            detail=(
                f"firms={len(firms)} json_plans={n_plans_json} summary_rows={len(summary_rows)}\n"
                f"{args.out_md}"
            ),
        )
    return 0


if __name__ == "__main__":
    _no_telegram = "--no-telegram" in sys.argv
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as e:
        if not _no_telegram:
            notify_script_finished("run_prop_collection_batch", exit_code=1, exc=e)
        raise
