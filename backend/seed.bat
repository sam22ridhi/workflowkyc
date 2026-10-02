@echo off
REM Demo data. Examples:
REM   seed.bat --reset                 5 cases, Sharma Foods empty (for a live upload demo)
REM   seed.bat --reset --hero-docs     also process the 8 Sharma Foods documents from the cache
REM   seed.bat --refresh-cache         live Sarvam + Cognee run, refreshes demo_cache\
cd /d %~dp0
.venv\Scripts\python.exe -m seed.seed_demo %*
