@echo off
REM Starts the Karyakarta backend on port 8765 (8000 is blocked on this machine).
REM --reload-dir app: only code changes reload (not .venv, storage or demo_cache).
REM --timeout-graceful-shutdown 2: open live-update (SSE) streams from browser tabs never close on their own; without
REM   a timeout a reload waits for them forever and the server stops answering.
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --timeout-graceful-shutdown 2 --host 0.0.0.0 --port 8765
