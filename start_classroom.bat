@echo off
chcp 65001 >nul
title Classroom Engagement Analysis System

echo =========================================
echo   Classroom Engagement Analysis System
echo   Hệ thống AI giám sát lớp học (NEHS)
echo =========================================
echo.

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python không tìm thấy. Vui lòng cài đặt Python 3.9+
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [INFO] Python version: %PYVER%

:: Check if venv exists, create if not
if not exist "venv" (
    echo [INFO] Tạo virtual environment...
    python -m venv venv
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install dependencies if needed
if not exist "venv\.deps_installed" (
    echo [INFO] Cài đặt dependencies...
    pip install -r requirements.txt
    echo done > venv\.deps_installed
)

:: Create data directory
if not exist "data" mkdir data

echo.
echo [INFO] Khởi động hệ thống...
echo [INFO] Dashboard: http://localhost:8001
echo [INFO] API Docs : http://localhost:8001/docs
echo [INFO] Nhấn Ctrl+C để dừng
echo.

:: Start the server
python backend\main.py

:: If server exits
echo.
echo [INFO] Hệ thống đã dừng.
pause
