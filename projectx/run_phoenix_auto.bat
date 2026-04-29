@echo off
REM Run from repo root:  projectx\run_phoenix_auto.bat
REM Set PROJECTX_* and optional PROJECTX_WEBHOOK_URL in projectx\.env (see .env.example).
setlocal
cd /d "%~dp0.."
python -m projectx.main --phoenix-auto --live-order --phoenix-instruments MNQ,MGC,YM --phoenix-contracts MNQ=1,MGC=3,YM=1 --phoenix-poll-seconds 30
endlocal
