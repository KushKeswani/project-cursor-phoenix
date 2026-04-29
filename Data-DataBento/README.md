# Data-DataBento

Place **minute OHLC** inputs here for backtests and replay.

## What to add

**Option A — Parquet (recommended)**  
Per-instrument files: `CL.parquet`, `MGC.parquet`, `MNQ.parquet`, `YM.parquet`  
(Column expectations and index rules: see `docs/DATABENTO_KNOWLEDGE.md`.)

**Option B — DataBento-style CSV**  
`nq-data.csv`, `mgc-data.csv`, `mym.csv`, `mcl.csv` as documented in `docs/DATABENTO_KNOWLEDGE.md`.

**Option C — Pull from ProjectX Gateway**

```bash
pip install -r projectx/requirements.txt
# Configure projectx/.env from projectx/.env.example and config/settings.yaml
python projectx/pull_bars.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD --out-dir Data-DataBento
```

## This bundle

Large market CSVs/parquet files are **not** shipped in the Project Cursor snapshot (size).  
`normalization_summary.csv` is a small provenance manifest when present.

Copy data from your DataBento export, ProjectX pull, or the full Agent Phoenix repo workstation.
