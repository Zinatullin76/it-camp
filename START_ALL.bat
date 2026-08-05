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
python -m pip install -r elou_avt_twin\requirements.txt
start "ELOU-AVT BACKEND" cmd /k "cd /d %~dp0elou_avt_twin && call .venv\Scripts\activate.bat && python api_server.py"
timeout /t 3 /nobreak >nul
if exist "elou_avt_web\package.json" (
  start "ELOU-AVT WEB" cmd /k "cd /d %~dp0elou_avt_web && npm run dev"
)
echo Backend: http://127.0.0.1:8000/docs
echo Health:  http://127.0.0.1:8000/health
echo Web UI:  http://localhost:5173
endlocal
