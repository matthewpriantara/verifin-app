@echo off
title Verifin Backend Server (FastAPI)
echo ===================================================
echo   Menjalankan Backend Verifin (Port 8000)...
echo ===================================================
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo Virtual environment tidak ditemukan! Mencoba python sistem...
)

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
