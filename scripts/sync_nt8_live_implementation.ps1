# Sync NinjaTrader V4 strategies into nt8/live_implementation/Strategies and optionally
# into NinjaTrader Custom\Strategies (Tradovate live testing).
#
# Usage (from repo root, PowerShell):
#   .\scripts\sync_nt8_live_implementation.ps1
#   $env:NINJATRADER_STRATEGIES_DIR = "$env:USERPROFILE\Documents\NinjaTrader 8\bin\Custom\Strategies"
#   .\scripts\sync_nt8_live_implementation.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Src = Join-Path $RepoRoot "nt8\Strategies"
$Dst = Join-Path $RepoRoot "nt8\live_implementation\Strategies"

if (-not (Test-Path $Src)) {
    Write-Error "Missing source: $Src"
}

New-Item -ItemType Directory -Force -Path $Dst | Out-Null
Get-ChildItem -Path $Src -File | Where-Object { $_.Extension -in ".cs", ".csv" } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $Dst -Force
    Write-Host "Copied $($_.Name)"
}

if ($env:NINJATRADER_STRATEGIES_DIR) {
    $Nt = $env:NINJATRADER_STRATEGIES_DIR
    New-Item -ItemType Directory -Force -Path $Nt | Out-Null
    Get-ChildItem -Path $Dst -File | Where-Object { $_.Extension -in ".cs", ".csv" } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $Nt -Force
        Write-Host " -> NT: $Nt\$($_.Name)"
    }
}

Write-Host "Done. Strategies: $Dst"
Write-Host "See nt8\live_implementation\README.md and TRADOVATE_LIVE_CHECKLIST.md"
