@echo off
setlocal

set ENV_DIR=%~dp0yugam_ml_env
set REQ_FILE=%~dp0requirements.txt

echo ============================================================
echo  Environment Setup
echo ============================================================
echo.

REM Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] python not found. Please install Python 3.10+ and add it to PATH.
    exit /b 1
)

REM Step 1: Create virtual environment
echo [1/3] Creating virtual environment at %ENV_DIR%...
python -m venv "%ENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    exit /b 1
)

REM Step 2: Upgrade pip
echo.
echo [2/3] Upgrading pip...
"%ENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip -q

REM Step 3: Install requirements
echo.
echo [3/3] Installing requirements from %REQ_FILE%...
"%ENV_DIR%\Scripts\pip.exe" install -r "%REQ_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    exit /b 1
)

echo.
echo ============================================================
echo  Setup complete!
echo  Activate the environment with:
echo    yugam_ml_env\Scripts\activate
echo ============================================================
pause
