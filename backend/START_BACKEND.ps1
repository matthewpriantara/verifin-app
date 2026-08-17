Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Menjalankan Backend Verifin (Port 8000)..." -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
}

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
