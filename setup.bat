@echo off
title Classroom AI - Setup
echo.
echo  ================================================
echo    Classroom Engagement AI System - Setup
echo  ================================================
echo.

:: == Kiem tra Python ==
echo [1/4] Kiem tra Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Python CHUA cai dat!
    echo.
    echo   Hay tai Python 3.12 tai:
    echo   https://www.python.org/downloads/
    echo.
    echo   QUAN TRONG: Khi cai, PHAI tick "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
python --version
echo   [OK] Python da cai

:: == Kiem tra Node.js ==
echo.
echo [2/4] Kiem tra Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Node.js CHUA cai dat!
    echo.
    echo   Hay tai Node.js LTS tai:
    echo   https://nodejs.org/
    echo.
    pause
    exit /b 1
)
node --version
echo   [OK] Node.js da cai

:: == Cai Python packages ==
echo.
echo [3/4] Cai dat Python packages (mat 5-10 phut)...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo   [!] Co loi khi cai pip packages.
    pause
    exit /b 1
)
echo   [OK] Python packages xong

:: == Cai Frontend ==
echo.
echo [4/4] Cai dat Frontend packages...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo   [!] Co loi khi cai npm packages.
    pause
    exit /b 1
)
cd ..
echo   [OK] Frontend packages xong

:: == Tao thu muc data ==
if not exist "data" mkdir data
if not exist "data\face_embeddings" mkdir data\face_embeddings

:: == Mo Firewall ==
echo.
echo [Firewall] Mo port 5173 va 8001...
netsh advfirewall firewall add rule name="Classroom AI Frontend" dir=in action=allow protocol=tcp localport=5173 >nul 2>&1
netsh advfirewall firewall add rule name="Classroom AI Backend" dir=in action=allow protocol=tcp localport=8001 >nul 2>&1
echo   [OK] Firewall rules da them

echo.
echo  ================================================
echo    CAI DAT HOAN TAT!
echo.
echo    Chay "start.bat" de khoi dong he thong
echo  ================================================
echo.
pause
