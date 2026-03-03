@echo off
title "AttendPro - Attendance & Payroll System"
color 0A

echo.
echo  ============================================
echo   AttendPro -- Attendance ^& Payroll System
echo  ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Please install Python 3.9+ from https://python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

:: Activate venv
if not exist "venv\" (
    echo  [*] First run -- setting up virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo  [*] Installing dependencies ^(one-time, may take 1-2 mins^)...
    pip install -r requirements.txt
    
    echo.
    echo  [*] Would you like a Desktop shortcut so you can launch
    echo      AttendPro like a real app ^(no browser URL needed^)?
    echo.
    choice /C YN /M "  Create Desktop shortcut + tray icon"
    if errorlevel 2 goto LAUNCH
    python create_shortcut.py
    goto END
) else (
    call venv\Scripts\activate.bat
    :: Check for missing dependencies silently
    echo  [*] Verifying dependencies...
    pip install -r requirements.txt --quiet
)

:LAUNCH
echo  [*] Starting AttendPro...
echo  [*] The app will open in your browser automatically.
echo  [*] A tray icon will appear in the bottom-right corner.
echo  [*] Close this window or right-click tray icon to Quit.
echo.

:: Check if tray.py is actually runnable
venv\Scripts\python.exe -c "import pystray, PIL, flask, apscheduler" >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Critical libraries are missing even after pip install.
    echo  Attempting a forced repair...
    venv\Scripts\pip.exe install -r requirements.txt
)

:: Use pythonw to hide this console after launch
start "" venv\Scripts\pythonw.exe tray.py

:: Wait a bit to see if it crashes immediately
timeout /t 3 >nul
tasklist /FI "IMAGENAME eq pythonw.exe" | findstr /I "pythonw.exe" >nul
if errorlevel 1 (
    echo  [ERROR] AttendPro failed to stay open. 
    echo  Starting in DEBUG mode to show the error:
    echo.
    venv\Scripts\python.exe tray.py
    pause
    exit /b 1
)

echo  [SUCCESS] AttendPro is running.
timeout /t 2 >nul
exit

:END
pause
