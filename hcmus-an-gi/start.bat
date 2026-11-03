
@echo off
title HCMUS AN GI - START PROJECT

echo =====================================
echo       HCMUS AN GI - STARTING
echo =====================================

:: Start Backend FastAPI
start "Backend - FastAPI" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0backend-python'; & '.\venv\Scripts\python.exe' -m uvicorn app:app --reload --port 8000"

:: Start Frontend Vite
start "Frontend - Vite" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0'; npm.cmd run dev"

echo.
echo Da gui lenh khoi dong Frontend va Backend.
echo Khong dong hai cua so terminal khi dang su dung.
pause
