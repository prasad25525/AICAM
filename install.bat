@echo off
rem VigilSiddhi - one-time installer (Windows). Needs Python 3.11, Node.js 20+ and internet (about 4 GB of downloads).
setlocal
cd /d "%~dp0"
echo.
echo ===== VigilSiddhi - A Vision AI Platform : installer =====
echo.

rem --- Python 3.11 (the py launcher if present, else "python") ---
set "PY="
py -3.11 --version >nul 2>nul && set "PY=py -3.11"
if not defined PY (
    python --version 2>nul | findstr /b /c:"Python 3.11" >nul && set "PY=python"
)
if not defined PY (
    echo [X] Python 3.11 was not found.
    echo     Install it from https://www.python.org/downloads/release/python-3119/
    echo     and tick "Add python.exe to PATH" during setup. Then run install.bat again.
    goto :fail
)
echo [OK] Python: & %PY% --version

rem --- Node.js ---
node --version >nul 2>nul || (
    echo [X] Node.js was not found. Install the LTS version from https://nodejs.org/ and run install.bat again.
    goto :fail
)
echo [OK] Node.js: & node --version

rem --- Backend: virtual environment and libraries ---
echo.
echo [1/4] Creating the Python environment (backend\.venv) ...
if not exist "backend\.venv\Scripts\python.exe" (
    %PY% -m venv backend\.venv || goto :fail
)
echo [2/4] Installing the AI and server libraries - this takes 10-30 minutes the first time ...
backend\.venv\Scripts\python.exe -m pip install --upgrade pip || goto :fail
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt || goto :fail

rem --- AI models (about 2 GB; skipped if already there) ---
echo [2b/4] Downloading the AI models ...
pushd backend
.venv\Scripts\python.exe scripts\download_models.py || (popd & goto :fail)
popd

rem --- Settings file with a private signing key ---
if not exist "backend\.env" (
    echo [3/4] Creating backend\.env with a new private key ...
    copy /y "backend\.env.example" "backend\.env" >nul
    backend\.venv\Scripts\python.exe -c "import secrets,pathlib;p=pathlib.Path('backend/.env');p.write_text(p.read_text().replace('AICAM_SECRET_KEY=change-me','AICAM_SECRET_KEY='+secrets.token_urlsafe(32)))" || goto :fail
) else (
    echo [3/4] backend\.env already exists - kept as it is.
)

rem --- Frontend ---
echo [4/4] Installing the web app ...
pushd frontend
call npm ci || (popd & goto :fail)
popd

echo.
echo ===== Installed. Double-click start.bat to run VigilSiddhi. =====
echo Login: admin / admin123  (change it in backend\.env before real use - see INSTALL.md)
echo.
pause
exit /b 0

:fail
echo.
echo ===== Installation stopped. See the message above, fix it, and run install.bat again. =====
pause
exit /b 1
