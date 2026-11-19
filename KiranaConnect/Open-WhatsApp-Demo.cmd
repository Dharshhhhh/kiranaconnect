@echo off
cd /d "%~dp0"
start "KiranaConnect server" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0Start-Windows.ps1"
echo Waiting for KiranaConnect. Keep the server window open.
powershell -NoProfile -Command "$deadline=(Get-Date).AddMinutes(5); while ((Get-Date) -lt $deadline) { try { $r=Invoke-WebRequest 'http://127.0.0.1:8000/openapi.json' -UseBasicParsing -TimeoutSec 2; if ($r.Content.Contains('/api/customer/message')) { Start-Process 'http://127.0.0.1:8000/?customer'; Start-Process 'http://127.0.0.1:8000/'; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; Write-Host 'Check the server window for setup errors.'; exit 1"
if errorlevel 1 pause
