@echo off
setlocal
REM Run on Windows after reviewing/approving project hooks; does NOT launch Codex.
REM Python must be available in this shell (Anaconda Prompt recommended).
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0app_control_v32.py" watch --notify
echo.
echo Watchdog stopped. Codex App is independent and is not closed by this script.
pause
