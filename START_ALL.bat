@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo ELOU-AVT DIGITAL TWIN - START ALL
echo ============================================
if not exist "elou_avt_twin\.venv\Scripts\python.exe" (
  py -3 -m venv elou_avt_twin\.venv
)
call elou_avt_twin\.venv\Scripts\activate.bat
echo [1/3] Installing Python dependencies...
python -m pip install --upgrade pip
pip install -r elou_avt_twin\requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)
echo [2/3] Installing frontend dependencies...
if exist "elou_avt_web\package.json" (
  pushd elou_avt_web
  if not exist "node_modules" (
    call npm install
    if errorlevel 1 (
      echo ERROR: npm install failed. Is Node.js installed?
      popd
      pause
      exit /b 1
    )
  )
  popd
)
echo [3/3] Starting services...
start "ELOU-AVT BACKEND" cmd /k "cd /d %~dp0elou_avt_twin && call .venv\Scripts\activate.bat && python api_server.py"
timeout /t 3 /nobreak >nul
if exist "elou_avt_web\package.json" (
  start "ELOU-AVT WEB" cmd /k "cd /d %~dp0elou_avt_web && npm run dev"
)
echo Backend: http://127.0.0.1:8000/docs
echo Health:  http://127.0.0.1:8000/health
echo Web UI:  http://localhost:5173
endlocal
