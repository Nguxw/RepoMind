@echo off
setlocal
cd /d "%~dp0"
python scripts\start_repomind.py %*
endlocal
