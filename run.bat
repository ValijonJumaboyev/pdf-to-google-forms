@echo off
title Auto Form Tool
color 0A

echo ========================================
echo        AUTO FORM AUTOMATION TOOL
echo ========================================
echo.

cd /d %~dp0

echo [*] Activating environment...
call .venv\Scripts\activate

echo [*] Initializing...
ping 127.0.0.1 -n 2 >nul

echo [*] Loading modules...
ping 127.0.0.1 -n 2 >nul

echo [*] Starting GUI...
ping 127.0.0.1 -n 2 >nul

:: Launch GUI and close terminal
start "" pythonw main.py

exit