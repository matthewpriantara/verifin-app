Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   [VERIFIN BACKEND] Menjalankan Server Port 8000" -ForegroundColor Green
Write-Host "   Domain : https://verifin.pempekasliwongkito.my.id" -ForegroundColor Yellow
Write-Host "   Docs   : https://verifin.pempekasliwongkito.my.id/docs" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
}

Write-Host "[INFO] Memulai Uvicorn dengan Real-time Debug Logs..." -ForegroundColor Cyan
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug --access-log
