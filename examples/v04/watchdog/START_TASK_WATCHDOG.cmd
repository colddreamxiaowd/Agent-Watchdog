@echo off
setlocal
REM Read-only task companion. Does not launch, control or trust Codex App.
REM Requires approved Task Contract and explicit session binding for task view.
REM Run from Anaconda Prompt if python is not on normal desktop PATH.
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0app_task_watch_v37.py" watch --notify
echo.
echo Watchdog stopped. Codex App continues independently.
pause
