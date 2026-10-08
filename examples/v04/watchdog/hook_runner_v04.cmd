@echo off
setlocal
rem Set the exact Python path below if Codex does not inherit your Conda PATH.
rem Example: set "WATCHDOG_PYTHON=D:\00software\Anaconda\envs\torch_env\python.exe"
if not defined WATCHDOG_PYTHON set "WATCHDOG_PYTHON=python"
"%WATCHDOG_PYTHON%" "%~dp0hook_logger_v04.py"
