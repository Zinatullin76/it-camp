$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"
$tmp = Join-Path $env:TEMP "opencode"
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$out = Join-Path $tmp "be_out.log"
$err = Join-Path $tmp "be_err.log"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500

Start-Process -FilePath $py -ArgumentList "api_server.py" -WorkingDirectory $root `
  -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
    $sw.Stop()
    Write-Output "Backend OK: $($h.ok) (up after $([math]::Round($sw.Elapsed.TotalSeconds, 1))s)"
    exit 0
  } catch { }
}
Write-Error "Backend did not become healthy within 60s"
exit 1
