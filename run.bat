@echo off
title Locket Gold Mini App Loader
echo --------------------------------------------------
echo   🚀 STARTING LOCKET GOLD MINI APP SYSTEM
echo --------------------------------------------------

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b
)

:: Create Virtual Environment if not exists
if not exist venv (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

:: Install/Update dependencies
echo [INFO] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

:: Set Environment Variables
set WEB_APP_URL=http://localhost:8000
:: Note: For Telegram to see this, use ngrok: ngrok http 8000

:: Start the application
echo [INFO] Starting Bot and API Server...
python main.py

pause
