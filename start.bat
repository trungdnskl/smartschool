@echo off
title Classroom AI - Running
echo.
echo  ================================================
echo    Classroom Engagement AI System
echo    Dang khoi dong...
echo  ================================================
echo.

:: Lay IP LAN
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /i "IPv4" ^| findstr "192.168"') do (
    set LAN_IP=%%a
)
set LAN_IP=%LAN_IP: =%

:: Khoi dong Backend
echo [1/2] Khoi dong Backend (AI Server)...
start "Classroom AI - Backend" cmd /k "cd /d %~dp0 && python backend/main.py"

:: Cho backend load
echo      Doi backend khoi dong (30 giay)...
timeout /t 30 /nobreak >nul

:: Khoi dong Frontend
echo [2/2] Khoi dong Frontend (Dashboard)...
start "Classroom AI - Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

timeout /t 5 /nobreak >nul

echo.
echo  ================================================
echo    HE THONG DA SAN SANG!
echo.
echo    May nay:   http://localhost:5173
echo    Mang LAN:  http://%LAN_IP%:5173
echo    API Docs:  http://localhost:8001/docs
echo.
echo    Dong cua so nay KHONG anh huong server
echo  ================================================
echo.

start http://localhost:5173
pause
