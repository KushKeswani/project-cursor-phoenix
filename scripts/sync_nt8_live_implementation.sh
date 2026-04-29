#!/usr/bin/env bash
# Sync NinjaTrader V4 strategies from nt8/Strategies into nt8/live_implementation/Strategies
# and optionally into your NinjaTrader Custom\Strategies folder (Tradovate live testing).
#
# Usage (from repo root):
#   bash scripts/sync_nt8_live_implementation.sh
#   NINJATRADER_STRATEGIES_DIR="$HOME/Documents/NinjaTrader 8/bin/Custom/Strategies" bash scripts/sync_nt8_live_implementation.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_ROOT/nt8/Strategies"
DST="$REPO_ROOT/nt8/live_implementation/Strategies"

if [[ ! -d "$SRC" ]]; then
  echo "Missing source: $SRC" >&2
  exit 1
fi

mkdir -p "$DST"
shopt -s nullglob
for f in "$SRC"/*.cs "$SRC"/*.csv; do
  cp -f "$f" "$DST/"
  echo "Copied $(basename "$f")"
done

if [[ -n "${NINJATRADER_STRATEGIES_DIR:-}" ]]; then
  NT="${NINJATRADER_STRATEGIES_DIR/#\~/$HOME}"
  mkdir -p "$NT"
  for f in "$DST"/*.cs "$DST"/*.csv; do
    [[ -e "$f" ]] || continue
    cp -f "$f" "$NT/"
    echo " -> NT: $NT/$(basename "$f")"
  done
fi

echo "Done. Strategies: $DST"
echo "See nt8/live_implementation/README.md and TRADOVATE_LIVE_CHECKLIST.md"
