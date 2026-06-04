@echo off
setlocal
cd /d "%~dp0"
python scripts\stop_repomind.py %*
endlocal
