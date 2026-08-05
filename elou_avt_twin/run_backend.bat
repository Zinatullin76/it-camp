@echo off
cd /d "%~dp0"
py -3 -m venv .venv 2>nul
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python api_server.py
