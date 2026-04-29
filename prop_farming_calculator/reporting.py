"""Write CLI report artifacts (Markdown + CSV)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.0f}"


def _fmt_pct(x: float) -> str:
    return f"{x:.1f}%"


def _fmt_days(x: float) -> str:
    if x != x:  # NaN
        return "—"
    return f"{x:.1f}"


def _fmt_float(x: float, *, nd: int = 1, empty: str = "—") -> str:
    if x != x:  # NaN
        return empty
    return f"{x:.{nd}f}"


def _pick_primary_horizon_block(
    horizon_results: list[dict[str, Any]],
    preferred_label: str,
) -> dict[str, Any] | None:
    """Match CLI `--cohort-horizon` label; fall back to 6 Months or median-length horizon."""
    if not horizon_results:
        return None
    pref = (preferred_label or "").strip()
    for b in horizon_results:
        if str(b.get("horizon_label", "")).strip() == pref:
            return b
    pl = pref.lower()
    for b in horizon_results:
        if str(b.get("horizon_label", "")).strip().lower() == pl:
            return b
    for b in horizon_results:
        if str(b.get("horizon_label", "")).strip() == "6 Months":
            return b
    sorted_b = sorted(
        horizon_results,
        key=lambda x: float(x.get("horizon_trading_days", 0)),
    )
    return sorted_b[len(sorted_b) // 2]


def write_reports(
    out_dir: Path,
    *,
    meta: dict[str, Any],
    horizon_results: list[dict[str, Any]],
    funnel_labels: dict[str, str],
    cohort_df: pd.DataFrame | None,
    pool_diag: dict[str, float],
    monthly: pd.Series,
    daily_summary: dict[str, Any],
    warnings: list[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_path = out_dir / "run_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")

    if warnings:
        (out_dir / "warnings.txt").write_text("\n".join(warnings) + "\n", encoding="utf-8")

    # --- horizons_summary.csv ---
    summary_keys = [
        "horizon_label",
        "horizon_trading_days",
        "audition_pass_pct",
        "avg_payout_events_per_trader",
        "avg_prop_firm_fees_per_trader",
        "avg_total_payouts_per_trader",
        "avg_total_expenses_per_trader",
        "avg_net_profit_per_trader",
        "avg_roi_pct",
        "pct_positive_roi",
        "eval_starts_scaled",
        "farm_est_total_fees",
        "farm_est_net",
        "mean_days_to_pass_eval_conditional_mc",
        "mean_days_to_first_payout_trading",
        "mean_funded_trading_days_to_first_payout",
        "mean_days_between_payouts_conditional",
        "pct_simulations_with_any_payout",
        "mean_eval_days_used_single_lifecycle",
    ]
    rows = []
    for block in horizon_results:
        row = {k: block.get(k) for k in summary_keys if k in block}
        rows.append(row)
    pd.DataFrame(rows).to_csv(out_dir / "horizons_summary.csv", index=False)

    cohort_meta = meta.get("cohort") or {}
    primary_label = str(cohort_meta.get("horizon_label", "6 Months"))
    primary_block = _pick_primary_horizon_block(horizon_results, primary_label)
    roll_pass = pool_diag.get("mc_eval_pass_pct") if pool_diag else None
    overall_payload: dict[str, Any] = {
        "primary_horizon_label": primary_block.get("horizon_label") if primary_block else None,
        "primary_horizon_trading_days": primary_block.get("horizon_trading_days")
        if primary_block
        else None,
        "requested_cohort_horizon_label": primary_label,
        "audition_pass_pct_mc_single_lifecycle": float(primary_block["audition_pass_pct"])
        if primary_block and primary_block.get("audition_pass_pct") is not None
        else None,
        "audition_pass_pct_rolling_history": float(roll_pass)
        if roll_pass is not None
        else None,
        "mean_trading_days_to_pass_audition_mc": float(
            primary_block.get("mean_days_to_pass_eval_conditional_mc", float("nan"))
        )
        if primary_block
        else None,
        "mean_trading_days_to_first_payout_mc": float(
            primary_block.get("mean_days_to_first_payout_trading", float("nan"))
        )
        if primary_block
        else None,
        "mean_funded_trading_days_to_first_payout_mc": float(
            primary_block.get("mean_funded_trading_days_to_first_payout", float("nan"))
        )
        if primary_block
        else None,
        "pct_simulations_with_any_payout_mc": float(
            primary_block.get("pct_simulations_with_any_payout", float("nan"))
        )
        if primary_block
        else None,
        "notes": (
            "MC columns: single-lifecycle Monte Carlo for the primary horizon only. "
            "Pass rate is over all sim paths. Days-to-pass is mean over paths that pass. "
            "Days-to-payout is mean over paths with at least one payout (trading days). "
            "rolling_history pass % uses every contiguous eval window on the actual daily pool."
        ),
    }
    (out_dir / "overall_headline.json").write_text(
        json.dumps(overall_payload, indent=2, default=str),
        encoding="utf-8",
    )

    # --- funnel_by_horizon.csv ---
    funnel_rows: list[dict[str, Any]] = []
    for block in horizon_results:
        hl = block.get("horizon_label", "")
        for k, lab in funnel_labels.items():
            key = f"funnel_pct__{k}"
            if key in block:
                funnel_rows.append(
                    {
                        "horizon_label": hl,
                        "bucket_key": k,
                        "bucket_label": lab,
                        "pct_of_simulations": block[key],
                    }
                )
    pd.DataFrame(funnel_rows).to_csv(out_dir / "funnel_by_horizon.csv", index=False)

    # --- cohort ---
    if cohort_df is not None and not cohort_df.empty:
        cohort_df.to_csv(out_dir / "cohort_multi_attempt.csv", index=False)

    # --- pool diagnostics ---
    if pool_diag:
        pd.Series(pool_diag).sort_index().to_csv(out_dir / "pool_diagnostics.csv")

    # --- monthly pnl ---
    if not monthly.empty:
        mdf = monthly.reset_index()
        mdf.columns = ["month", "pnl_usd"]
        mdf.to_csv(out_dir / "monthly_pnl.csv", index=False)

    # --- SUMMARY.md ---
    firm = meta.get("firm_name") or meta.get("firm_name_slug") or "—"
    lines: list[str] = [
        "# Prop firm profit farming report",
        "",
        f"**Firm / run label:** {firm}",
        "",
        f"Generated (UTC): `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "## Run configuration",
        "",
        "```json",
        json.dumps(meta, indent=2, default=str),
        "```",
        "",
    ]
    if warnings:
        lines.extend(["## Warnings", "", *[f"- {w}" for w in warnings], ""])

    lines.extend(
        [
            "## Daily pool",
            "",
            f"- Trading days: **{daily_summary.get('n_days', 0)}**",
            f"- Range: **{daily_summary.get('start', '')}** → **{daily_summary.get('end', '')}**",
            f"- Portfolio contracts key: **{daily_summary.get('portfolio_key', '')}**",
            f"- Trade size multiplier: **{daily_summary.get('trade_mult', 1.0)}×**",
            "",
        ]
    )

    if primary_block:
        phl = str(primary_block.get("horizon_label", "?"))
        ptd = int(float(primary_block.get("horizon_trading_days", 0)))
        mc_pass = float(primary_block.get("audition_pass_pct", 0.0))
        mc_d_pass = float(primary_block.get("mean_days_to_pass_eval_conditional_mc", float("nan")))
        mc_d_pay = float(primary_block.get("mean_days_to_first_payout_trading", float("nan")))
        mc_d_pay_f = float(
            primary_block.get("mean_funded_trading_days_to_first_payout", float("nan"))
        )
        pct_pay = float(primary_block.get("pct_simulations_with_any_payout", 0.0))
        lines.extend(
            [
                "## Overall headline (single-lifecycle Monte Carlo)",
                "",
                f"Primary horizon matches **`--cohort-horizon`** (`{primary_label}`): **{phl}** (~{ptd} trading days).",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| **Audition pass rate** | {_fmt_pct(mc_pass)} |",
                f"| **Avg trading days to pass** (mean over paths that pass) | {_fmt_days(mc_d_pass)} |",
                f"| **Avg trading days to first payout** (eval + funded; mean over paths with ≥1 payout) | {_fmt_days(mc_d_pay)} |",
                f"| Avg funded-only trading days to first payout | {_fmt_days(mc_d_pay_f)} |",
                f"| % MC paths with any payout | {_fmt_pct(pct_pay)} |",
                "",
            ]
        )
        if pool_diag and roll_pass is not None:
            lines.extend(
                [
                    f"For comparison, **rolling historical audition pass rate** (every `{int(meta.get('audition', {}).get('eval_window_days', 0) or 0)}`-day window on the real daily series, when eval days are in meta): **{_fmt_pct(float(roll_pass))}**.",
                    "",
                ]
            )
        elif pool_diag:
            lines.extend(
                [
                    f"Rolling historical audition pass rate: **{_fmt_pct(float(roll_pass))}** (`pool_diagnostics.csv` → `mc_eval_pass_pct`).",
                    "",
                ]
            )
        lines.extend(
            [
                "Also saved as **`overall_headline.json`** (machine-readable). Per-horizon detail follows below.",
                "",
            ]
        )

    if pool_diag:
        m_pass = float(pool_diag.get("mc_eval_mean_days_to_pass", 0.0))
        med_pass = float(pool_diag.get("mc_eval_median_days_to_pass", 0.0))
        roll_w = float(pool_diag.get("roll_rolling_windows", 0.0))
        lines.extend(
            [
                "## Timing — historical pool (rolling eval, every start day)",
                "",
                "These use your **actual daily PnL order**: each contiguous `eval_window_days` slice is scored once. They describe the audition only (not funded payout timing).",
                "",
                f"- Mean trading days to **pass** (conditional on pass): **{_fmt_float(m_pass)}**",
                f"- Median trading days to pass (conditional on pass): **{_fmt_float(med_pass)}**",
                f"- Rolling windows scored: **{int(roll_w)}**",
                "",
            ]
        )

    lines.extend(
        [
            "## Horizons (single-lifecycle Monte Carlo)",
            "",
        ]
    )

    for block in horizon_results:
        hl = block.get("horizon_label", "?")
        td = block.get("horizon_trading_days", 0)
        lines.append(f"### {hl} (~{int(td)} trading days)")
        lines.extend(
            [
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Audition pass rate | {_fmt_pct(float(block.get('audition_pass_pct', 0)))} |",
                f"| Avg trading days to pass audition | {_fmt_days(float(block.get('mean_days_to_pass_eval_conditional_mc', float('nan'))))} (mean over MC paths that pass) |",
                f"| Avg trading days to first payout | {_fmt_days(float(block.get('mean_days_to_first_payout_trading', float('nan'))))} (mean over MC paths with ≥1 payout; eval + funded) |",
                f"| Avg funded trading days to first payout | {_fmt_days(float(block.get('mean_funded_trading_days_to_first_payout', float('nan'))))} (after pass; same paths as row above) |",
                f"| Avg days between payouts (if ≥2) | {_fmt_days(float(block.get('mean_days_between_payouts_conditional', float('nan'))))} |",
                f"| % simulations with any payout | {_fmt_pct(float(block.get('pct_simulations_with_any_payout', 0)))} |",
                f"| Avg payouts per trader (events) | {float(block.get('avg_payout_events_per_trader', 0)):.2f} |",
                f"| Avg prop firm fees (1 acct) | {_fmt_money(float(block.get('avg_prop_firm_fees_per_trader', 0)))} |",
                f"| Avg total payouts (1 acct) | {_fmt_money(float(block.get('avg_total_payouts_per_trader', 0)))} |",
                f"| Avg total expenses incl. VPS (1 acct) | {_fmt_money(float(block.get('avg_total_expenses_per_trader', 0)))} |",
                f"| Avg net profit (1 acct) | {_fmt_money(float(block.get('avg_net_profit_per_trader', 0)))} |",
                f"| Avg ROI | {_fmt_pct(float(block.get('avg_roi_pct', 0)))} |",
                f"| % positive ROI | {_fmt_pct(float(block.get('pct_positive_roi', 0)))} |",
                f"| Throughput-scaled est. net | {_fmt_money(float(block.get('farm_est_net', 0)))} |",
                f"| Mean eval days used (all MC outcomes, any end state) | {_fmt_float(float(block.get('mean_eval_days_used_single_lifecycle', 0)))} |",
                "",
                "**Where simulations end (% of paths):**",
                "",
            ]
        )
        fz = [
            (k, lab, float(block.get(f"funnel_pct__{k}", 0.0)))
            for k, lab in funnel_labels.items()
            if float(block.get(f"funnel_pct__{k}", 0.0)) > 0.001
        ]
        fz.sort(key=lambda x: -x[2])
        for _k, lab, pct in fz:
            lines.append(f"- {lab}: {_fmt_pct(pct)}")
        lines.append("")

    lines.extend(
        [
            "## Files in this folder",
            "",
            "| File | Description |",
            "|------|-------------|",
            "| `run_meta.json` | Full parameters for reproducibility |",
            "| `horizons_summary.csv` | One row per horizon (main KPIs) |",
            "| `overall_headline.json` | Pass %, avg days to pass & to payout at `--cohort-horizon` (+ rolling pass %) |",
            "| `funnel_by_horizon.csv` | Failure / outcome funnel by horizon |",
            "| `cohort_multi_attempt.csv` | Per-trader multi-attempt simulation |",
            "| `pool_diagnostics.csv` | Historical + rolling eval (contiguous windows) |",
            "| `monthly_pnl.csv` | Loaded series monthly PnL |",
            "| `SUMMARY.md` | This report |",
            "",
        ]
    )

    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
