@echo off
title Company Operating System (COS) - XAUUSDT Master
color 0E

echo ==========================================================
echo   COMPANY OPERATING SYSTEM (COS) - XAUUSDT STARTUP SCRIPT
echo ==========================================================
echo.

:: 1. Check Python installation
echo [STEP 1] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found in your system PATH! Please install Python.
    pause
    exit /b 1
)
echo [SUCCESS] Python is installed.
echo.

:: 2. Check essential files
echo [STEP 2] Verifying core directory and file structure...
if not exist "api\main.py" (
    echo [ERROR] File "api\main.py" is missing! Make sure you are in the root directory.
    pause
    exit /b 1
)
if not exist "dashboard\index.html" (
    echo [ERROR] File "dashboard\index.html" is missing!
    pause
    exit /b 1
)
echo [SUCCESS] All files and structures verified.
echo.

:: 3. Initializing Database (Just in case)
echo [STEP 3] Initializing SQLite database...
python -m company.database.init_db
if %errorlevel% neq 0 (
    echo [WARNING] Database initialization failed. Attempting to continue...
)
echo [SUCCESS] Database status ready.
echo.

:: 4. Start Uvicorn Server in background
echo [STEP 4] Starting FastAPI Uvicorn Server on http://localhost:8000 ...
start "COS-FastAPI-Server" cmd /k "set PYTHONPATH=.&& python -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

:: 5. Open Web Browser
echo.
echo Waiting for 3 seconds to let server initialize...
timeout /t 3 /nobreak >nul

echo [STEP 5] Opening Dashboard in Google Chrome...
start chrome "http://localhost:8000/"

echo.
echo ==========================================================
echo   COS XAUUSDT SYSTEM IS RUNNING IN BACKGROUND WINDOW!
echo ==========================================================
echo.
pause
