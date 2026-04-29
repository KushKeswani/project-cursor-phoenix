# DataBento and `Data-DataBento` knowledge

This document describes how **Agent Phoenix** expects historical OHLC data to be laid out under `Data-DataBento/`, whether it comes from [DataBento](https://databento.com/) exports, normalized parquet from another pipeline, or **ProjectX Gateway** pulls (`projectx/pull_bars.py`).

## Purpose

- **Research backtests** (`scripts/backtester.py`, `scripts/run_portfolio_preset.py`) read **1-minute** (or denser) OHLC, then **resample** to each instrument’s bar period inside `scripts/engine/fast_engine.py`.
- **Live-pace replay** (`scripts/phoenix_live_pace_replay.py`) uses the same bar-loading path as live Phoenix (`projectx/strategy/phoenix_auto.py`) against **local** files.
- **Live trading** can pull bars from the Gateway into the same parquet layout via `python projectx/pull_bars.py`.

## Preferred layout: parquet per instrument

For each traded symbol key **`CL`**, **`MGC`**, **`MNQ`**, **`YM`**, place:

| File | Contents |
|------|-----------|
| `Data-DataBento/CL.parquet` | Minute OHLC index for CL strategy |
| `Data-DataBento/MGC.parquet` | Minute OHLC for MGC |
| `Data-DataBento/MNQ.parquet` | Minute OHLC for MNQ |
| `Data-DataBento/YM.parquet` | Minute OHLC for YM |

**Index:** timezone-aware or naive datetime index in **America/New_York** session semantics after load (see `scripts/backtester.py::_canonicalize_ohlc_frame`). Duplicate timestamps are merged (first open, max high, min low, last close).

**Columns:** at minimum `open`, `high`, `low`, `close`. Volume is optional; if present it is aggregated when deduplicating.

Parquet is **preferred** for speed and smaller size versus huge CSVs.

## Alternative: DataBento-style CSV (GH archive exports)

If parquet is absent, `scripts/backtester.py::load_bars` falls back to fixed filenames:

| Instrument | CSV filename | Symbol filter (outright root) | Notes |
|------------|--------------|-------------------------------|--------|
| MNQ | `nq-data.csv` | Symbols starting with **`NQ`**, no `-` (no spreads) | NQ minute bars drive MNQ strategy; tick size comes from `scripts/configs/tick_config.py` for **MNQ**. |
| MGC | `mgc-data.csv` | **`MGC`** outright | |
| YM | `mym.csv` | **`MYM`** outright | Warning in code: MYM prices track micro Dow; **YM** mini tick economics in `TICK_*` may not match micro-Dow USD PnL exactly. |
| CL | `mcl.csv` | **`MCL`** outright | |

### CSV columns required

Loader uses: `ts_event`, `open`, `high`, `low`, `close`, `symbol`.

- **`ts_event`:** UTC timestamp (parseable by pandas).
- Rows are filtered to outright contracts (`symbol` starts with the prefix above and does not contain `-`).
- Bars are **floored to one minute in ET**, then aggregated OHLC per minute.

Implementation reference: `scripts/backtester.py` — `_load_databento_csv_1m_bars`, `_DATABENTO_CSV_BY_INSTRUMENT`.

## Normalization summary

`Data-DataBento/normalization_summary.csv` (when present) is a small manifest of row counts and date ranges from an offline normalization run. It is **not** required at runtime; it documents provenance.

## ProjectX Gateway → same folder

`projectx/pull_bars.py` writes **`<SYMBOL>.parquet`** under `--out-dir` (default `Data-DataBento`) using Gateway history, merged optionally with existing files (`--merge`). That produces the same layout backtests and replay expect.

Requirements: `projectx/config/settings.yaml` credentials (or `PROJECTX_*` env vars). See root **README** and `projectx/.env.example`.

## Size and licensing

Full-history CSVs from vendors are often **hundreds of MB to multiple GB per file**. This **Project Cursor** bundle ships **metadata and documentation only** for those heavy files—copy parquet/CSV from your licensed source or the parent repo machine.

## Quick validation

With data present:

```bash
python3 scripts/backtester.py --help
python3 scripts/run_portfolio_preset.py --profile Balanced_50k_survival --data-dir Data-DataBento
```

Short replay smoke (needs data covering the date range):

```bash
python3 scripts/phoenix_live_pace_replay.py --start-date 2024-06-03 --end-date 2024-06-04 \
  --data-dir Data-DataBento --step-mode bar --no-sleep --instruments MNQ --contracts 1 \
  --no-stats --bars-window range_prefix --max-steps 8
```

## Instrument grids and bar periods

Resampling uses per-instrument session grids from `scripts/configs/tick_config.py` (`INSTRUMENT_GRIDS`) and locked strategy parameters in `scripts/configs/strategy_configs.py`. See also `docs/INSTRUMENT_TIMEFRAMES.md`.
