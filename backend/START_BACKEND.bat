@echo off
title Verifin Backend Server (FastAPI)
color 0A
echo ===================================================
echo   [VERIFIN BACKEND] Menjalankan Server Port 8000
echo   Status : LIVE and LISTENING (0.0.0.0:8000)
echo   Domain : https://verifin.pempekasliwongkito.my.id
echo   Docs   : https://verifin.pempekasliwongkito.my.id/docs
echo ===================================================
echo.
cd /d "%~dp0"

set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo Virtual environment tidak ditemukan! Mencoba python sistem...
)

echo [INFO] Memulai Uvicorn dengan Real-time Debug Logs...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug --access-log
pause
