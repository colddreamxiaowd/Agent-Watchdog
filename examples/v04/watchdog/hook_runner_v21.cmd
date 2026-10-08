@echo off
setlocal
REM New opt-in runner, does NOT overwrite the old hook_runner.cmd
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0execution_v2.py" hook
REM Observer failure must not block Codex.
exit /b 0
