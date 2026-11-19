@echo off
cd /d "%~dp0"
py -3.12 server.py --open
if errorlevel 1 pause
