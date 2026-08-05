Set-Location $PSScriptRoot
if (!(Test-Path .venv)) { py -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python api_server.py
