#!/usr/bin/env python3
"""Run pinned evaluation flows from ``evaluation_kit.yaml`` (goals.md §1, §5).

Steps:
  1. Export canonical ``reports/trade_executions/<scope>/instruments/*.csv`` (OOS or full).
  2. Optionally run ``prop_farming_calculator`` baseline runs for each preset (slow).

Does **not** replace full backtest/replay pipelines — it refreshes trade CSV inputs + optional MC baselines.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit", type=Path, default=REPO_ROOT / "evaluation_kit.yaml")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument(
        "--prop-baseline",
        action="store_true",
        help="Run prop_farming_calculator for each preset in the kit (writes under reports/evaluation_kit/)",
    )
    p.add_argument("--n-sims", type=int, default=None, help="Override kit prop_farming_baseline.n_sims")
    args = p.parse_args()

    kit_path = args.kit.expanduser().resolve()
    doc = yaml.safe_load(kit_path.read_text(encoding="utf-8"))

    py = sys.executable
    if not args.skip_export:
        oos = doc.get("oos_export") or {}
        start = oos.get("start")
        end = oos.get("end")
        if not start or not end:
            raise SystemExit("evaluation_kit.yaml: missing oos_export.start/end")
        cmd = [
            py,
            str(SCRIPT_DIR / "export_trade_executions.py"),
            "--reports-root",
            str(REPO_ROOT / "reports"),
            "--scope",
            "oos",
            "--start",
            str(start),
            "--end",
            str(end),
        ]
        data_dir = doc.get("data_dir")
        if data_dir:
            cmd.extend(["--data-dir", str(REPO_ROOT / str(data_dir))])
        print("Running:", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))

    # Verify four CSVs exist
    inst_dir = REPO_ROOT / "reports" / "trade_executions" / "oos" / "instruments"
    names = ["CL", "MGC", "MNQ", "YM"]
    missing = [f"{n}_trade_executions.csv" for n in names if not (inst_dir / f"{n}_trade_executions.csv").is_file()]
    if missing:
        print("WARNING: missing execution CSVs:", ", ".join(missing), flush=True)
    else:
        print(f"OK trade_executions/oos present under {inst_dir}", flush=True)

    if args.prop_baseline:
        base_cfg = doc.get("prop_farming_baseline") or {}
        n_sims = int(args.n_sims or base_cfg.get("n_sims") or 1500)
        seed = int(base_cfg.get("seed") or 42)
        horizon = str(base_cfg.get("cohort_horizon") or "6 Months")
        prefix = str(base_cfg.get("firm_name_prefix") or "EvalKit")
        presets = base_cfg.get("firm_presets") or {}
        out_root = REPO_ROOT / "reports" / "evaluation_kit" / "prop_baseline"
        out_root.mkdir(parents=True, exist_ok=True)

        cli = REPO_ROOT / "prop_farming_calculator" / "cli.py"
        exec_root = REPO_ROOT / "reports"

        for preset_key, spec in presets.items():
            port = spec.get("portfolio")
            firm_preset = spec.get("firm_preset")
            if not port or not firm_preset:
                continue
            slug = preset_key.replace(" ", "_")
            out_dir = out_root / slug
            cmd = [
                py,
                str(cli),
                "--firm-name",
                f"{prefix}_{slug}",
                "--execution-reports-dir",
                str(exec_root),
                "--scope",
                "oos",
                "--portfolio",
                str(port),
                "--firm-preset",
                str(firm_preset),
                "--n-sims",
                str(n_sims),
                "--seed",
                str(seed),
                "--out",
                str(out_dir),
                "--cohort-horizon",
                horizon,
            ]
            print("Running prop baseline:", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))

    print("evaluation_kit run complete.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
