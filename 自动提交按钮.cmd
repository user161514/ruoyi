@echo off
chcp 65001 >nul
title Auto Commit -^> origin/dev
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0.scripts\git-sync.ps1"
echo.
echo ---- window kept open on purpose ----
pause
