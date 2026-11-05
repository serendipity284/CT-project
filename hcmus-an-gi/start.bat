@echo off
title HCMUS AN GI - START PROJECT

echo ========================================================
echo                 HCMUS AN GI - STARTING
echo ========================================================

:: Start Backend FastAPI
echo [1/2] Khoi dong Backend (FastAPI)...
start "Backend - FastAPI" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0backend-python'; & '.\venv\Scripts\python.exe' -m uvicorn app:app --reload --port 8000"

:: Start Frontend Vite
echo [2/2] Khoi dong Frontend (Vite)...
start "Frontend - Vite" powershell -NoExit -Command "Set-Location -LiteralPath '%~dp0'; npm.cmd run dev"

echo.
echo ========================================================
echo  * Frontend: http://localhost:8080
echo  * Backend:  http://localhost:8000 (API Docs: http://localhost:8000/docs)
echo.
echo  Luu y: Hay dam bao MySQL trong XAMPP da duoc Start!
echo  Khong dong hai cua so terminal khi dang su dung web.
echo ========================================================
pause
