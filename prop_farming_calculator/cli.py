#!/usr/bin/env python3
"""Prop firm profit farming calculator — CLI. Writes reports under output/<firm>/run_<stamp>/ (or --out)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_CALC = Path(__file__).resolve().parent
if str(_CALC) not in sys.path:
    sys.path.insert(0, str(_CALC))

from _paths import REPO_ROOT, ensure_scripts_on_path

ensure_scripts_on_path()

import yaml

from configs.portfolio_presets import FOUR_TIER_PROFILES
from evidence_utils import build_data_manifest, git_provenance, runtime_provenance
from data_loader import build_daily_monthly, load_executions_from_dir
from reporting import write_reports
from simulation import (
    FUNNEL_LABELS,
    FarmSimParams,
    HORIZONS,
    build_cohort_rows,
    build_eval_rules,
    pool_diagnostics,
    run_horizon_batch,
)

PRESETS_PATH = _CALC / "presets.yaml"

# Human labels → FOUR_TIER_PROFILES keys (survival = low / lighter stack in repo).
PORTFOLIO_TIERS: dict[str, str] = {
    "50k-survival": "50k_low",
    "50k-high": "50k_high",
    "150k-survival": "150k_low",
    "150k-high": "150k_high",
    # backward compatible aliases
    "50k-low": "50k_low",
    "150k-low": "150k_low",
}

TIER_PRESET_HINT: dict[str, tuple[str, ...]] = {
    "50k-survival": ("50k",),
    "50k-high": ("50k",),
    "150k-survival": ("150k",),
    "150k-high": ("150k",),
}

# Interactive menu (number → portfolio CLI value)
INTERACTIVE_PORTFOLIO_CHOICES: list[tuple[str, str]] = [
    ("50k survival — lighter contract stack", "50k-survival"),
    ("50k high — larger stack", "50k-high"),
    ("150k survival — lighter contract stack", "150k-survival"),
    ("150k high — larger stack", "150k-high"),
]

# Baseline when not merging YAML, or as defaults before YAML overlay.
DEFAULT_BASE_PC: dict = {
    "audition_profit_target_usd": 3000.0,
    "audition_trailing_drawdown_usd": 2000.0,
    "audition_eval_days": 60,
    "audition_daily_loss_limit_usd": None,
    "audition_consistency_max_best_day_fraction": None,
    "funded_starting_balance_usd": 50_000.0,
    "funded_trail_on_profit_usd": 2000.0,
    "funded_profit_target_usd": None,
    "funded_payout_amount_usd": None,
    "challenge_fee_usd": 91.0,
    "activation_fee_usd": 0.0,
    "min_profit_per_day_usd": 150.0,
    "n_qualifying_days": 5,
    "withdraw_fraction": 0.5,
    "audition_min_trading_days": 1,
}


def _safe_firm_dir(name: str) -> str:
    s = re.sub(r"[^\w\-.]+", "_", (name or "").strip(), flags=re.UNICODE)
    s = s.strip("_")[:120]
    return s or "firm"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--firm-name",
        default="UnnamedFirm",
        help="Label for this run; reports go under output/<sanitized_name>/run_<timestamp>/",
    )
    p.add_argument(
        "--execution-reports-dir",
        type=Path,
        default=REPO_ROOT / "reports",
        help="Repo folder containing trade_executions/…",
    )
    p.add_argument("--scope", choices=["oos", "full"], default="oos")
    p.add_argument(
        "--portfolio",
        choices=list(PORTFOLIO_TIERS.keys()),
        default="50k-survival",
        help="Contract stack: 50k/150k × survival (lighter) or high",
    )
    p.add_argument(
        "--firm-preset",
        default="phoenix_topstep_50k",
        metavar="KEY",
        help="Merge rules from presets.yaml (use 'none' to skip YAML and use defaults + CLI flags only).",
    )
    p.add_argument("--presets-file", type=Path, default=PRESETS_PATH)
    p.add_argument(
        "--allow-preset-mismatch",
        action="store_true",
        help="Allow --portfolio tier and --firm-preset key family mismatch.",
    )
    p.add_argument("--trade-mult", type=float, default=1.0)
    p.add_argument(
        "--strict-required-instruments",
        action="store_true",
        help="Fail if any instrument with non-zero preset contracts has missing execution CSV.",
    )
    p.add_argument("--n-sims", type=int, default=1500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--accounts", type=int, default=1)
    p.add_argument(
        "--start-frequency",
        choices=["monthly", "weekly", "daily"],
        default="monthly",
    )
    p.add_argument("--challenge-billing", choices=["one_time", "monthly"], default="one_time")
    p.add_argument("--no-vps", action="store_true")
    p.add_argument("--vps-monthly", type=float, default=199.0)
    p.add_argument("--cohort-traders", type=int, default=10)
    p.add_argument(
        "--cohort-horizon",
        default="6 Months",
        help="Label matching simulation horizons (e.g. '6 Months', '12 Months').",
    )
    p.add_argument("--cohort-seed", type=int, default=12345)
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Exact output directory (overrides firm-name folder layout).",
    )

    g = p.add_argument_group("Audition / eval (override preset)")
    g.add_argument("--challenge-fee", type=float, default=None)
    g.add_argument("--activation-fee", type=float, default=None)
    g.add_argument("--audition-profit-target", type=float, default=None)
    g.add_argument("--audition-dd", type=float, default=None, help="Audition max trailing drawdown ($)")
    g.add_argument("--eval-days", type=int, default=None)
    g.add_argument("--audition-dll", type=float, default=None, help="Enable audition daily loss limit ($)")
    g.add_argument("--no-audition-dll", action="store_true", help="Force audition DLL off")
    g.add_argument(
        "--audition-consistency-pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Enable rule: max best-day win as %% of cumulative profit at pass (e.g. 40)",
    )
    g.add_argument("--no-audition-consistency", action="store_true", help="Force consistency rule off")

    g = p.add_argument_group("Funded phase (override preset)")
    g.add_argument("--funded-balance", type=float, default=None)
    g.add_argument("--funded-trail", type=float, default=None, help="Funded trailing drawdown on profit ($)")
    g.add_argument(
        "--funded-max-payout",
        type=float,
        default=None,
        metavar="USD",
        help="If set: funded leg uses capped gross withdrawals (Express-style) + trader split; omit for classic model.",
    )
    g.add_argument("--min-profit-day", type=float, default=None, help="Min $ day to count toward payout qualification")
    g.add_argument("--n-qual-days", type=int, default=None)
    g.add_argument("--withdraw-fraction", type=float, default=None, help="Fraction of balance considered per payout cycle")
    g.add_argument("--express-first-full-usd", type=float, default=10_000.0)
    g.add_argument("--express-split", type=float, default=0.9, help="Trader share of gross after first-full bucket")

    g = p.add_argument_group("Notes (saved in run_meta.json only; not used in MC)")
    g.add_argument(
        "--funded-profit-target-note",
        type=float,
        default=None,
        help="Optional full profit target ($) — recorded for your reference only",
    )
    p.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Walk through each setting with prompts (ignores other CLI flags except --help).",
    )
    return p.parse_args()


def _build_pc(args: argparse.Namespace, presets: dict) -> dict:
    pc = dict(DEFAULT_BASE_PC)
    fp = (args.firm_preset or "").strip()
    if fp.lower() not in ("", "none", "-"):
        if fp not in presets:
            print(
                f"Unknown --firm-preset '{fp}'. Keys: {sorted(presets.keys())}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        pc.update(presets[fp])
    return pc


def _prompt_line(label: str, default: str | None = None) -> str:
    hint = f" [{default}]" if default is not None else ""
    s = input(f"{label}{hint}: ").strip()
    if not s and default is not None:
        return str(default)
    return s


def _prompt_float(label: str, default: float | None = None) -> float | None:
    hint = f" [{default}]" if default is not None else ""
    while True:
        s = input(f"{label}{hint}: ").strip()
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            print("  Enter a number (or leave blank for default).")


def _prompt_int(label: str, default: int | None = None) -> int | None:
    hint = f" [{default}]" if default is not None else ""
    while True:
        s = input(f"{label}{hint}: ").strip()
        if not s:
            return default
        try:
            return int(s, 10)
        except ValueError:
            print("  Enter an integer (or leave blank for default).")


def _prompt_yes_no(label: str, *, default_yes: bool = True) -> bool:
    default = "Y/n" if default_yes else "y/N"
    s = input(f"{label} ({default}): ").strip().lower()
    if not s:
        return default_yes
    return s in ("y", "yes", "1", "true")


def run_interactive_wizard() -> argparse.Namespace:
    """Step-by-step prompts; returns a Namespace usable by run_from_args."""
    print("\n" + "=" * 60)
    print("  Prop firm profit farming — interactive setup")
    print("=" * 60)
    print("\nPress Enter to keep each [default].\n")

    firm_name = _prompt_line("Step 1 — Name this run / firm (folder under output/)", "MyFirm")
    exec_s = _prompt_line(
        "Step 2 — Folder with trade CSVs (…/reports)",
        str(REPO_ROOT / "reports"),
    )
    scope = _prompt_line("Step 3 — Data scope: oos or full", "oos")
    while scope not in ("oos", "full"):
        print("  Please type exactly: oos  or  full")
        scope = _prompt_line("Step 3 — Data scope", "oos")

    print("\nStep 4 — Portfolio (which contract stack to simulate)")
    for i, (desc, val) in enumerate(INTERACTIVE_PORTFOLIO_CHOICES, 1):
        print(f"  {i}. {desc}")
    p_pick = _prompt_line("  Enter 1–4", "1")
    try:
        idx = int(p_pick)
        portfolio = (
            INTERACTIVE_PORTFOLIO_CHOICES[idx - 1][1]
            if 1 <= idx <= len(INTERACTIVE_PORTFOLIO_CHOICES)
            else "50k-survival"
        )
    except ValueError:
        portfolio = "50k-survival"

    presets_path = Path(_prompt_line("Step 5 — Path to presets.yaml", str(PRESETS_PATH)))
    presets_path = presets_path.expanduser().resolve()
    if not presets_path.exists():
        print(f"  Warning: {presets_path} not found — using bundled presets.yaml if present.")
        presets_path = PRESETS_PATH.resolve()
    if not presets_path.exists():
        print(f"  Warning: no presets file — YAML templates disabled.")
        raw_yaml: dict = {}
        presets = {}
    else:
        raw_yaml = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
        presets = raw_yaml.get("presets", {})

    print("\nStep 6 — Starter rule set")
    print("  You can load a template from presets.yaml, then adjust numbers in the next steps.")
    use_yaml = _prompt_yes_no("  Load a template from presets.yaml?", default_yes=True)
    firm_preset = "none"
    if use_yaml and presets:
        keys = sorted(presets.keys())
        for i, k in enumerate(keys, 1):
            print(f"    {i:2}. {k}")
        pick = _prompt_line("  Preset number or exact key name", "phoenix_topstep_50k")
        if pick.isdigit():
            n = int(pick)
            if 1 <= n <= len(keys):
                firm_preset = keys[n - 1]
            else:
                firm_preset = pick if pick in presets else "phoenix_topstep_50k"
        else:
            firm_preset = pick if pick in presets else "phoenix_topstep_50k"
        if firm_preset not in presets:
            print(f"  Unknown preset — using built-in defaults only.")
            firm_preset = "none"
    elif use_yaml and not presets:
        print("  No presets in file — using built-in defaults.")
        firm_preset = "none"

    tmp = argparse.Namespace(firm_preset=firm_preset)
    pc = _build_pc(tmp, presets)

    trade_mult = float(_prompt_float("Step 7 — Trade size multiplier on the algo PnL", 1.0) or 1.0)

    print("\nStep 8 — Audition / evaluation")
    aud_target = float(
        _prompt_float("  8a — Profit target to pass ($)", float(pc["audition_profit_target_usd"]))
        or pc["audition_profit_target_usd"]
    )
    aud_dd = float(
        _prompt_float("  8b — Max trailing drawdown ($)", float(pc["audition_trailing_drawdown_usd"]))
        or pc["audition_trailing_drawdown_usd"]
    )
    eval_days = int(
        _prompt_int("  8c — Max eval window (calendar days)", int(pc["audition_eval_days"]))
        or pc["audition_eval_days"]
    )

    no_audition_dll = True
    audition_dll = None
    if _prompt_yes_no("  8d — Enable daily loss limit on audition days?", default_yes=False):
        no_audition_dll = False
        audition_dll = float(
            _prompt_float("      Limit ($) — lose more than this in a day = fail", 1000.0) or 1000.0
        )

    no_audition_consistency = True
    audition_consistency_pct = None
    if _prompt_yes_no(
        "  8e — Enable consistency rule (max best-day win as %% of profit at pass)?",
        default_yes=pc.get("audition_consistency_max_best_day_fraction") is not None,
    ):
        no_audition_consistency = False
        dflt_pct = (
            float(pc["audition_consistency_max_best_day_fraction"]) * 100.0
            if pc.get("audition_consistency_max_best_day_fraction") is not None
            else 40.0
        )
        audition_consistency_pct = float(
            _prompt_float("      Max best-day as %% of cumulative profit (e.g. 40)", dflt_pct) or dflt_pct
        )

    print("\nStep 9 — Fees (audition / challenge)")
    challenge_fee = float(
        _prompt_float("  Challenge / combine fee ($)", float(pc["challenge_fee_usd"]))
        or pc["challenge_fee_usd"]
    )
    activation_fee = float(
        _prompt_float("  Activation fee when you get funded ($)", float(pc["activation_fee_usd"]))
        or pc["activation_fee_usd"]
    )
    bill = _prompt_line("  Billing: 1 = one-time per attempt, 2 = monthly × horizon months", "1")
    challenge_billing = "monthly" if bill.strip() == "2" else "one_time"

    print("\nStep 10 — Funded account")
    funded_bal = float(
        _prompt_float("  Simulated funded balance ($)", float(pc["funded_starting_balance_usd"]))
        or pc["funded_starting_balance_usd"]
    )
    funded_trail = float(
        _prompt_float("  Trailing drawdown on profit ($)", float(pc["funded_trail_on_profit_usd"]))
        or pc["funded_trail_on_profit_usd"]
    )

    funded_max_payout = None
    if _prompt_yes_no(
        "  Cap each payout cycle (Express-style: min(%%×balance, max $))?",
        default_yes=False,
    ):
        funded_max_payout = float(
            _prompt_float("  Max gross withdrawal per payout cycle ($)", 3000.0) or 3000.0
        )

    express_first = 10_000.0
    express_split = 0.9
    if funded_max_payout is not None:
        express_first = float(
            _prompt_float(
                "  (Capped model) First $ to trader at 100%% before split — default 10000",
                10_000.0,
            )
            or 10_000.0
        )
        express_split = float(
            _prompt_float("  Your share of gross after that bucket (0–1, e.g. 0.9)", 0.9) or 0.9
        )

    print("\nStep 11 — Payout qualification (funded)")
    min_profit = float(
        _prompt_float("  Min winning day ($) to count toward qualification", float(pc["min_profit_per_day_usd"]))
        or pc["min_profit_per_day_usd"]
    )
    n_qual = int(
        _prompt_int("  Number of qualifying days needed before a payout", int(pc["n_qualifying_days"]))
        or pc["n_qualifying_days"]
    )
    withdraw_frac = float(
        _prompt_float("  Fraction of balance used for gross withdrawal calc (0–1)", float(pc["withdraw_fraction"]))
        or pc["withdraw_fraction"]
    )

    note_s = _prompt_line(
        "Step 12 — Optional note only: funded profit target ($) for your records (blank = skip)",
        "",
    )
    funded_profit_target_note = float(note_s) if note_s else None

    print("\nStep 13 — VPS overhead")
    use_vps = _prompt_yes_no("  Include monthly VPS cost in expenses?", default_yes=True)
    no_vps = not use_vps
    vps_monthly = (
        float(_prompt_float("  Monthly VPS ($)", 199.0) or 199.0) if use_vps else 199.0
    )

    print("\nStep 14 — Monte Carlo & throughput")
    n_sims = int(_prompt_int("  Number of simulation paths per horizon", 1500) or 1500)
    seed = int(_prompt_int("  Random seed", 42) or 42)
    accounts = int(_prompt_int("  Number of accounts (for scaling estimates)", 1) or 1)
    sf = _prompt_line("  New eval starts: 1=monthly  2=weekly  3=daily", "1")
    start_frequency = {"2": "weekly", "3": "daily"}.get(sf.strip(), "monthly")

    print("\nStep 15 — Multi-attempt cohort table")
    cohort_traders = int(_prompt_int("  How many trader rows to simulate", 10) or 10)
    print("  Cohort horizon (matches main report periods):")
    hz_labels = [lbl for _, lbl, _ in HORIZONS]
    for i, lbl in enumerate(hz_labels, 1):
        print(f"    {i}. {lbl}")
    hz_pick = _prompt_line("  Enter 1–6 or exact label (e.g. 6 Months)", "3")
    if hz_pick.isdigit() and 1 <= int(hz_pick) <= len(hz_labels):
        cohort_horizon = hz_labels[int(hz_pick) - 1]
    elif hz_pick in hz_labels:
        cohort_horizon = hz_pick
    else:
        cohort_horizon = "6 Months"
    cohort_seed = int(_prompt_int("  Cohort random seed", 12345) or 12345)

    custom_out = _prompt_yes_no("Step 16 — Set a custom output directory (else auto under output/<firm>/run_…)?", default_yes=False)
    out: Path | None = None
    if custom_out:
        op = _prompt_line("  Output directory path", "")
        out = Path(op).expanduser().resolve() if op.strip() else None

    # Build equivalent CLI (for copy-paste)
    cmd_parts = [
        "python3 cli.py",
        f'--firm-name "{firm_name}"',
        f"--portfolio {portfolio}",
        f'--firm-preset {firm_preset}',
        f"--trade-mult {trade_mult}",
        f"--n-sims {n_sims}",
        f"--seed {seed}",
    ]
    if funded_max_payout is not None:
        cmd_parts.append(f"--funded-max-payout {funded_max_payout}")

    print("\n" + "-" * 60)
    print("Summary")
    print("-" * 60)
    print(f"  Firm name:      {firm_name}")
    print(f"  CSV folder:     {exec_s}")
    print(f"  Portfolio:      {portfolio}")
    print(f"  YAML template:  {firm_preset}")
    print(f"  Audition:       ${aud_target:,.0f} target, ${aud_dd:,.0f} trail, {eval_days}d window")
    dll_s = f"${audition_dll:,.0f}" if audition_dll is not None else "off"
    cons_s = f"{audition_consistency_pct:.0f}%" if audition_consistency_pct is not None else "off"
    print(f"  DLL / consist.: {dll_s} / {cons_s}")
    cap_s = f"${funded_max_payout:,.0f} gross/cycle" if funded_max_payout else "classic (no cap)"
    print(f"  Funded:         ${funded_bal:,.0f} bal, ${funded_trail:,.0f} trail, {cap_s}")
    print(f"  MC paths:       {n_sims}  (seed {seed})")
    print("-" * 60)
    print("\nNon-interactive equivalent (approx.):")
    print(" ", " ".join(cmd_parts))
    print()

    if not _prompt_yes_no("Run simulation now?", default_yes=True):
        print("Cancelled.")
        raise SystemExit(0)

    return argparse.Namespace(
        firm_name=firm_name,
        execution_reports_dir=Path(exec_s),
        scope=scope,
        portfolio=portfolio,
        firm_preset=firm_preset,
        presets_file=presets_path,
        trade_mult=trade_mult,
        n_sims=n_sims,
        seed=seed,
        accounts=accounts,
        start_frequency=start_frequency,
        challenge_billing=challenge_billing,
        no_vps=no_vps,
        vps_monthly=vps_monthly,
        cohort_traders=cohort_traders,
        cohort_horizon=cohort_horizon,
        cohort_seed=cohort_seed,
        out=out,
        challenge_fee=challenge_fee,
        activation_fee=activation_fee,
        audition_profit_target=aud_target,
        audition_dd=aud_dd,
        eval_days=eval_days,
        audition_dll=audition_dll,
        no_audition_dll=no_audition_dll,
        audition_consistency_pct=audition_consistency_pct,
        no_audition_consistency=no_audition_consistency,
        funded_balance=funded_bal,
        funded_trail=funded_trail,
        funded_max_payout=funded_max_payout,
        min_profit_day=min_profit,
        n_qual_days=n_qual,
        withdraw_fraction=withdraw_frac,
        express_first_full_usd=express_first,
        express_split=express_split,
        funded_profit_target_note=funded_profit_target_note,
        strict_required_instruments=False,
        allow_preset_mismatch=False,
        interactive=False,
    )


def run_from_args(args: argparse.Namespace) -> int:
    presets_path = args.presets_file.expanduser().resolve()
    raw_yaml = yaml.safe_load(presets_path.read_text(encoding="utf-8"))
    presets = raw_yaml.get("presets", {})
    pc = _build_pc(args, presets)
    fp_for_check = (args.firm_preset or "").strip().lower()
    if fp_for_check not in ("", "none", "-") and not args.allow_preset_mismatch:
        hints = TIER_PRESET_HINT.get(args.portfolio, ())
        if hints and not any(h in fp_for_check for h in hints):
            print(
                f"Preset mismatch: portfolio tier '{args.portfolio}' and preset key "
                f"'{args.firm_preset}' do not appear aligned. Use --allow-preset-mismatch to override.",
                file=sys.stderr,
            )
            return 2

    tier_key = PORTFOLIO_TIERS[args.portfolio]
    portfolio_key = FOUR_TIER_PROFILES[tier_key]

    challenge_fee = float(
        args.challenge_fee if args.challenge_fee is not None else pc["challenge_fee_usd"]
    )
    activation_fee = float(
        args.activation_fee if args.activation_fee is not None else pc["activation_fee_usd"]
    )
    aud_target = float(
        args.audition_profit_target
        if args.audition_profit_target is not None
        else pc["audition_profit_target_usd"]
    )
    aud_dd = float(
        args.audition_dd if args.audition_dd is not None else pc["audition_trailing_drawdown_usd"]
    )
    aud_eval_days = int(args.eval_days if args.eval_days is not None else pc["audition_eval_days"])

    if args.no_audition_dll:
        aud_dll = None
    elif args.audition_dll is not None:
        aud_dll = float(args.audition_dll)
    else:
        v = pc.get("audition_daily_loss_limit_usd")
        aud_dll = float(v) if v is not None else None

    if args.no_audition_consistency:
        cons_frac = None
    elif args.audition_consistency_pct is not None:
        cons_frac = float(args.audition_consistency_pct) / 100.0
    elif pc.get("audition_consistency_max_best_day_fraction") is not None:
        cons_frac = float(pc["audition_consistency_max_best_day_fraction"])
    else:
        cons_frac = None

    funded_bal = float(
        args.funded_balance if args.funded_balance is not None else pc["funded_starting_balance_usd"]
    )
    funded_trail = float(
        args.funded_trail if args.funded_trail is not None else pc["funded_trail_on_profit_usd"]
    )
    min_profit = float(
        args.min_profit_day if args.min_profit_day is not None else pc["min_profit_per_day_usd"]
    )
    n_qual = int(args.n_qual_days if args.n_qual_days is not None else pc["n_qualifying_days"])
    withdraw_frac = float(
        args.withdraw_fraction if args.withdraw_fraction is not None else pc["withdraw_fraction"]
    )
    funded_cap = args.funded_max_payout

    exec_dir = args.execution_reports_dir.expanduser().resolve()
    raw = load_executions_from_dir(exec_dir, args.scope)
    daily, monthly, warns = build_daily_monthly(
        raw,
        portfolio_key,
        args.trade_mult,
        strict_required_instruments=bool(args.strict_required_instruments),
    )
    if any(w.startswith("ERROR:") for w in warns):
        for w in warns:
            print(w, file=sys.stderr)
        return 2

    if daily.empty:
        print("Daily PnL pool is empty. Check execution CSVs and path.", file=sys.stderr)
        return 1

    aud_min_days = int(pc.get("audition_min_trading_days", 1))
    rules = build_eval_rules(
        profit_target_usd=aud_target,
        trailing_drawdown_usd=aud_dd,
        eval_window_days=aud_eval_days,
        daily_loss_limit_usd=aud_dll,
        consistency_max_best_day_fraction=cons_frac,
        min_trading_days=aud_min_days,
    )

    farm = FarmSimParams(
        n_sims=int(args.n_sims),
        seed=int(args.seed),
        n_accounts=int(args.accounts),
        start_frequency=args.start_frequency,  # type: ignore[arg-type]
        challenge_fee_usd=challenge_fee,
        challenge_billing=args.challenge_billing,  # type: ignore[arg-type]
        activation_fee_usd=activation_fee,
        use_vps=not args.no_vps,
        vps_monthly_usd=float(args.vps_monthly),
        min_profit_per_day_usd=min_profit,
        n_qualifying_days=n_qual,
        withdraw_fraction=withdraw_frac,
        funded_starting_balance_usd=funded_bal,
        funded_trail_on_profit_usd=funded_trail,
        funded_payout_cap_usd=float(funded_cap) if funded_cap is not None else None,
        express_trader_first_full_usd=float(args.express_first_full_usd),
        express_trader_split_after_first=float(args.express_split),
    )

    if args.out:
        out_dir = args.out.expanduser().resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        firm_slug = _safe_firm_dir(args.firm_name)
        out_dir = (_CALC / "output" / firm_slug / f"run_{stamp}").resolve()

    input_csvs: list[Path] = []
    inst_dir = exec_dir / "trade_executions" / args.scope / "instruments"
    for inst in ("CL", "MGC", "MNQ", "YM"):
        p = inst_dir / f"{inst}_trade_executions.csv"
        if p.exists():
            input_csvs.append(p)
    data_manifest = build_data_manifest(input_csvs)

    horizon_results: list[dict] = []
    for _key, h_label, h_days in HORIZONS:
        res = run_horizon_batch(daily, h_days, rules, farm)
        res["horizon_label"] = h_label
        horizon_results.append(res)

    cohort_td = next(td for _, lbl, td in HORIZONS if lbl == args.cohort_horizon)
    cohort_df = build_cohort_rows(
        daily,
        cohort_td,
        rules,
        farm,
        n_traders=int(args.cohort_traders),
        base_seed=int(args.cohort_seed),
    )
    cohort_out = cohort_df if cohort_df is not None and not cohort_df.empty else None

    diag = pool_diagnostics(
        daily,
        rules,
        n_sims=min(5000, int(args.n_sims)),
        seed=int(args.seed),
    )

    fp_used = args.firm_preset.strip()
    if fp_used.lower() in ("none", "-"):
        fp_used = "none"

    meta = {
        "firm_name": args.firm_name,
        "firm_name_slug": _safe_firm_dir(args.firm_name),
        "execution_reports_dir": str(exec_dir),
        "scope": args.scope,
        "portfolio_tier": args.portfolio,
        "portfolio_key": portfolio_key,
        "firm_preset_yaml": fp_used,
        "presets_file": str(presets_path),
        "trade_mult": args.trade_mult,
        "n_sims": args.n_sims,
        "seed": args.seed,
        "accounts": args.accounts,
        "start_frequency": args.start_frequency,
        "challenge_fee_usd": challenge_fee,
        "challenge_billing": args.challenge_billing,
        "activation_fee_usd": activation_fee,
        "use_vps": not args.no_vps,
        "vps_monthly_usd": args.vps_monthly,
        "audition": {
            "profit_target_usd": aud_target,
            "trailing_drawdown_usd": aud_dd,
            "eval_window_days": aud_eval_days,
            "daily_loss_limit_usd": aud_dll,
            "consistency_max_best_day_fraction": cons_frac,
        },
        "funded": {
            "starting_balance_usd": funded_bal,
            "trail_on_profit_usd": funded_trail,
            "min_profit_per_day_usd": min_profit,
            "n_qualifying_days": n_qual,
            "withdraw_fraction": withdraw_frac,
            "max_gross_payout_per_cycle_usd": funded_cap,
            "funded_model": "express_capped" if funded_cap is not None else "classic",
            "express_trader_first_full_usd": float(args.express_first_full_usd),
            "express_trader_split_after_first": float(args.express_split),
            "profit_target_note_usd": args.funded_profit_target_note,
        },
        "cohort": {
            "traders": args.cohort_traders,
            "horizon_label": args.cohort_horizon,
            "trading_days": cohort_td,
            "seed": args.cohort_seed,
        },
        "output_dir": str(out_dir),
        "input_data_manifest": data_manifest,
        "provenance": {
            **git_provenance(REPO_ROOT),
            **runtime_provenance(),
        },
    }

    daily_summary = {
        "n_days": len(daily),
        "start": str(daily.index.min().date()),
        "end": str(daily.index.max().date()),
        "portfolio_key": portfolio_key,
        "trade_mult": args.trade_mult,
    }

    write_reports(
        out_dir,
        meta=meta,
        horizon_results=horizon_results,
        funnel_labels=FUNNEL_LABELS,
        cohort_df=cohort_out,
        pool_diag=diag,
        monthly=monthly,
        daily_summary=daily_summary,
        warnings=warns,
    )

    print(f"Firm: {args.firm_name}")
    print(f"Wrote reports to: {out_dir}")
    print(f"  {out_dir / 'SUMMARY.md'}")
    (out_dir / "data_manifest.json").write_text(
        json.dumps(data_manifest, indent=2),
        encoding="utf-8",
    )

    hz_pick = next((b for b in horizon_results if b.get("horizon_label") == "6 Months"), None)
    if hz_pick is None and horizon_results:
        hz_pick = horizon_results[len(horizon_results) // 2]
    if hz_pick is not None:
        import math as _math

        def _fday(x: float) -> str:
            return "—" if _math.isnan(x) else f"{x:.1f}"

        d_pass_mc = float(hz_pick.get("mean_days_to_pass_eval_conditional_mc", float("nan")))
        d_pay = float(hz_pick.get("mean_days_to_first_payout_trading", float("nan")))
        hlab = str(hz_pick.get("horizon_label", "?"))
        pool_pass = float(diag.get("mc_eval_mean_days_to_pass", float("nan")))
        print("")
        print(
            "Timing snapshot "
            f"({hlab} MC + pool rolling): "
            f"avg days to pass (historical pool) {_fday(pool_pass)} | "
            f"avg days to pass eval (MC, if pass) {_fday(d_pass_mc)} | "
            f"avg days to 1st payout (MC, if any payout) {_fday(d_pay)}"
        )

    return 0


def main() -> int:
    args = _parse_args()
    if args.interactive:
        try:
            args = run_interactive_wizard()
        except (EOFError, KeyboardInterrupt):
            print("\nInterrupted.", file=sys.stderr)
            return 130
    return run_from_args(args)


if __name__ == "__main__":
    _sd = _CALC.parent / "scripts"
    if str(_sd) not in sys.path:
        sys.path.insert(0, str(_sd))
    from telegram_script_done import run_with_telegram

    raise SystemExit(run_with_telegram(main, script_name="prop_farming_calculator.cli"))
