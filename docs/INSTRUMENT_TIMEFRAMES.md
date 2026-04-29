# Instrument timeframes — how to run each one

All session times below are **US Eastern (ET)**. Strategy logic uses **bar open time** (left-labeled bars), matching Python `resample_to_bars` and the C# / NT8 engines. Weekends are excluded (Saturday and Sunday).

Source of truth in code: `scripts/configs/strategy_configs.py`, `scripts/configs/tick_config.py` (`INSTRUMENT_GRIDS`).

---

## CL


| What                            | Value                                                                   |
| ------------------------------- | ----------------------------------------------------------------------- |
| **Chart / bar period**          | **12 minute**                                                           |
| **Session for 1m→bar resample** | 08:00–18:00 ET (`INSTRUMENT_GRIDS`)                                     |
| **Opening range**               | 09:00–09:30 ET                                                          |
| **Trade window**                | 10:30–12:30 ET                                                          |
| **Flatten (close-all zone)**    | From **16:55** ET onward (bar start ≥ 16:55 or last bar of session day) |
| **Tick size**                   | 0.01                                                                    |


**C# backtest** (hardcoded in `csharp/Cl.Backtest/Program.cs`):

```bash
dotnet run --project csharp/Cl.Backtest/Cl.Backtest.csproj -c Release -- --bars /path/to/cl_bars.csv --out /tmp/cl_trades.csv
```

**NinjaTrader 8:** strategy **RangeBreakout CL**, chart **12** minute bars, trading hours template that **starts at 08:00 ET** so 09:00 range bars exist.

---

## MGC


| What                            | Value                    |
| ------------------------------- | ------------------------ |
| **Chart / bar period**          | **8 minute**             |
| **Session for 1m→bar resample** | 08:00–17:00 ET           |
| **Opening range**               | 09:00–09:30 ET           |
| **Trade window**                | 12:00–13:00 ET           |
| **Flatten**                     | From **16:55** ET onward |
| **Tick size**                   | 0.10                     |


**C# backtest:**

```bash
dotnet run --project csharp/Mgc.Backtest/Mgc.Backtest.csproj -c Release -- --bars /path/to/mgc_bars.csv --out /tmp/mgc_trades.csv
```

**NinjaTrader 8:** **RangeBreakout MGC**, **8** minute bars, session template covering the range and trade windows (often **08:00–17:00** style for gold pit hours).

---

## MNQ


| What                            | Value                    |
| ------------------------------- | ------------------------ |
| **Chart / bar period**          | **5 minute**             |
| **Session for 1m→bar resample** | 08:00–18:00 ET           |
| **Opening range**               | 09:35–09:55 ET           |
| **Trade window**                | 11:00–13:00 ET           |
| **Flatten**                     | From **16:55** ET onward |
| **Tick size**                   | 0.25                     |


**C# backtest:**

```bash
dotnet run --project csharp/Mnq.Backtest/Mnq.Backtest.csproj -c Release -- --bars /path/to/mnq_bars.csv --out /tmp/mnq_trades.csv
```

**NinjaTrader 8:** **RangeBreakout MNQ**, **5** minute bars, **08:00** session start so the 09:35–09:55 range builds correctly.

---

## YM


| What                            | Value                    |
| ------------------------------- | ------------------------ |
| **Chart / bar period**          | **5 minute**             |
| **Session for 1m→bar resample** | 08:00–18:00 ET           |
| **Opening range**               | 09:00–09:30 ET           |
| **Trade window**                | 11:00–13:00 ET           |
| **Flatten**                     | From **16:55** ET onward |
| **Tick size**                   | 1.0                      |


**C# backtest:**

```bash
dotnet run --project csharp/Ym.Backtest/Ym.Backtest.csproj -c Release -- --bars /path/to/ym_bars.csv --out /tmp/ym_trades.csv
```

**NinjaTrader 8:** **RangeBreakout YM**, **5** minute bars, **08:00** session start.

---

## CSV / Python parity

Bars fed to the C# tools should be the same OHLC series as the backtester: resampled to the bar period above, `datetime` = bar **open**. Example parity check (touch fills):

```bash
python3 scripts/compare_cs_engine_vs_python.py --instrument MNQ \
  --data-dir Data-DataBento --start 2024-06-01 --end 2024-06-07 --fills touch
```

Swap `--instrument` for `CL`, `MGC`, or `YM` to match the executable under test.

---

## ProjectX / Phoenix live

Live polling uses Gateway history with the same **strategy windows** as this table; see `projectx/run_tomorrow_mnq_mgc_ym.sh` and `python -m projectx.main --help` for flags. Bar **period** is still defined by `get_config(symbol).bar_minutes` as above.