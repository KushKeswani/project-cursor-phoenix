# Prop firm profit farming calculator (CLI)

Monte Carlo prop-firm economics on exported trade CSVs. Results go to:

`**output/<sanitized-firm-name>/run_YYYYMMDD_HHMMSS/**`

Use `**--firm-name**` for every run so you can tell firms apart (folder + report title). Spaces and odd characters become underscores in the folder name.

---

## One-time setup

```bash
cd "/path/to/Agent Pheonix/prop_farming_calculator"
pip3 install -r requirements.txt
```

All examples below assume you are in that directory so `./run.sh` works.

---

## Quick run (non-interactive, flags only)

**Minimal:** name the firm, pick a portfolio tier.

```bash
./run.sh --firm-name "Topstep" --portfolio 50k-survival
```

**Faster smoke test** (fewer sims; good for checking paths and data load):

```bash
./run.sh --firm-name "MyFirm" --portfolio 50k-high --n-sims 300 --scope oos
```

**Full historical window** (longer pool, slower):

```bash
./run.sh --firm-name "Apex test" --portfolio 150k-survival --scope full
```

**No YAML preset** — only built-in defaults plus whatever you pass on the command line:

```bash
./run.sh --firm-name "Custom rules" --firm-preset none --portfolio 50k-survival \
  --audition-profit-target 3000 --audition-dd 2000 --eval-days 30 \
  --challenge-fee 109 --challenge-billing monthly
```

List every flag:

```bash
./run.sh --help
```

---

## Naming your firm (`--firm-name`)


| What you pass             | Where it shows up                                                       |
| ------------------------- | ----------------------------------------------------------------------- |
| `--firm-name "Topstep X"` | Report title and `run_meta.json`                                        |
| Same string (sanitized)   | Subfolder under `output/`, e.g. `output/Topstep_X/run_20260402_174656/` |


If you omit it, the default label is `**UnnamedFirm**`. Interactive mode (`-i`) will also ask for a firm name.

---

## Interactive mode (step-by-step)

```bash
./run.sh --interactive
# or
./run.sh -i
```

Prompts walk through options; other CLI flags are ignored except `--help`.

---

## Common flags (cheat sheet)


| Flag                      | Default                | Notes                                                                                     |
| ------------------------- | ---------------------- | ----------------------------------------------------------------------------------------- |
| `--firm-name`             | `UnnamedFirm`          | **Use this to tag the firm you are testing**                                              |
| `--portfolio`             | `50k-survival`         | `50k-survival`, `50k-high`, `150k-survival`, `150k-high` (aliases: `50k-low`, `150k-low`) |
| `--firm-preset`           | `phoenix_topstep_50k`  | Key from `presets.yaml`. Use `**none`** for YAML-free + flags only                        |
| `--presets-file`          | bundled `presets.yaml` | Override preset file path                                                                 |
| `--execution-reports-dir` | `<repo>/reports`       | Must contain `trade_executions/oos/instruments/*.csv` (or `full`)                         |
| `--scope`                 | `oos`                  | `oos` or `full`                                                                           |
| `--n-sims`                | `1500`                 | Lower for quick runs                                                                      |
| `--seed`                  | `42`                   | Reproducibility                                                                           |
| `--accounts`              | `1`                    | Throughput scaling                                                                        |
| `--start-frequency`       | `monthly`              | `monthly`, `weekly`, or `daily`                                                           |
| `--challenge-billing`     | `one_time`             | `one_time` or `monthly`                                                                   |
| `--no-vps`                | off                    | Omit VPS from expenses                                                                    |
| `--out`                   | (unset)                | Exact output dir; **overrides** `output/<firm>/run_…` layout                              |
| `--cohort-horizon`        | `6 Months`             | Must match a horizon label in the report                                                  |
| `--cohort-traders`        | `10`                   | Multi-attempt cohort CSV                                                                  |


### Audition / eval overrides

`--challenge-fee`, `--activation-fee`, `--audition-profit-target`, `--audition-dd`, `--eval-days`, `--audition-dll`, `--no-audition-dll`, `--audition-consistency-pct` (e.g. `40` for 40%), `--no-audition-consistency`

### Funded overrides

`--funded-balance`, `--funded-trail`, `--funded-max-payout` (Express-style gross cap per cycle), `--min-profit-day`, `--n-qual-days`, `--withdraw-fraction`, `--express-first-full-usd`, `--express-split`

### Note only (saved in `run_meta.json`)

`--funded-profit-target-note`

---

## Example: custom firm without presets file merge

```bash
./run.sh --firm-name "Apex clone" --firm-preset none --portfolio 50k-high \
  --audition-profit-target 3000 --audition-dd 2000 --funded-max-payout 3000 \
  --audition-consistency-pct 40 --challenge-fee 91
```

---

## Output files (each run folder)


| File                       | Description                         |
| -------------------------- | ----------------------------------- |
| `SUMMARY.md`               | Readable report                     |
| `run_meta.json`            | Full parameters (reproduce the run) |
| `horizons_summary.csv`     | KPIs by horizon                     |
| `funnel_by_horizon.csv`    | Where MC paths end                  |
| `cohort_multi_attempt.csv` | Per-trader sequential retries       |
| `pool_diagnostics.csv`     | Historical + rolling eval (start every day) + `mc_*` aliases |
| `monthly_pnl.csv`          | Loaded series                       |


---

## Preset keys (`--firm-preset`)

Defined under `presets:` in `presets.yaml` (e.g. `phoenix_topstep_50k`, `phoenix_lucid_50k`, `custom`). Run with a wrong key and the CLI prints valid keys.