@echo off
echo =============================================
echo   Classroom AI - Mo Firewall cho LAN
echo =============================================
echo.

:: Check admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Can quyen Administrator!
    echo     Click chuot phai file nay ^> "Run as administrator"
    pause
    exit /b 1
)

echo [1/2] Mo port 5174 (Frontend)...
netsh advfirewall firewall add rule name="Classroom AI Frontend" dir=in action=allow protocol=tcp localport=5174
echo.

echo [2/2] Mo port 8001 (Backend)...
netsh advfirewall firewall add rule name="Classroom AI Backend" dir=in action=allow protocol=tcp localport=8001
echo.

echo =============================================
echo   XONG! May khac co the truy cap:
echo   http://192.168.100.20:5174
echo =============================================
pause
