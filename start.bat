@echo off
rem VigilSiddhi - start the backend and the web app in their own windows, then open the browser.
cd /d "%~dp0"
if not exist "backend\.venv\Scripts\python.exe" (
    echo VigilSiddhi is not installed yet. Run install.bat first.
    pause
    exit /b 1
)
start "VigilSiddhi backend" /d "%~dp0backend" cmd /k .venv\Scripts\python.exe main.py
start "VigilSiddhi frontend" /d "%~dp0frontend" cmd /k npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
echo Starting VigilSiddhi ... the browser opens in about 15 seconds.
echo Keep the two new windows open while you use it; close them to stop VigilSiddhi.
timeout /t 15 /nobreak >nul
start "" http://127.0.0.1:5173
