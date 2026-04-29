#!/usr/bin/env bash
# Phoenix auto-trader: MNQ + MGC + YM at 50k_low (Balanced_50k_survival: 1 / 3 / 1).
# Entry: limit at engine entry_price by default (settings execution.phoenix_entry_order). For market: --phoenix-market-entry
# Scans all symbols whenever Phoenix runs; range-built Telegram alert fires when the
# engine seals the opening range (YM/MGC ~9:30 ET, MNQ ~9:55) on Mon–Fri only
# (weekend bars are excluded by the strategy — no range message Sat/Sun).
# API orders only on fresh entries: MNQ & YM 11:00–13:00, MGC 12:00–13:00 ET.
# Run from repo root, or:  bash projectx/run_tomorrow_mnq_mgc_ym.sh
# Terminal+Telegram: range-built once/day/symbol (+ data check line: bar count, raw H/L vs engine).
# Re-notify same day: add --phoenix-range-resend once. Gateway merges an extra retrieve for the opening-range window.
# No per-poll spam (use --phoenix-poll-status for that).

set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

exec python3 -m projectx.main \
  --phoenix-auto \
  --live-order \
  --phoenix-instruments MNQ,MGC,YM \
  --phoenix-contracts MNQ=1,MGC=3,YM=1 \
  --phoenix-poll-seconds 30
