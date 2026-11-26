@echo off
title Mode 2 - Local-Only Stream Clip Factory
set "ROOT=D:\Automation Youtube Clipping"
set "FLAG=%ROOT%\LOCAL_PAUSE.flag"
set "SCRIPT=%ROOT%\local_clip_factory.py"
set "PYEXE=C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe"

cd /d "%ROOT%"

if not exist "%SCRIPT%" (
    echo [ERROR] Missing file: "%SCRIPT%"
    pause
    exit /b 1
)

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*local_clip_factory.py*' }; if ($p) { exit 0 } else { exit 1 }"
if "%errorlevel%"=="0" (
    if exist "%FLAG%" (
        del /f /q "%FLAG%"
        echo ==================================================
        echo   RESUMED - Local Clip Factory is active again!
        echo ==================================================
    ) else (
        echo PAUSED > "%FLAG%"
        echo ==================================================
        echo   PAUSED - Local Clip Factory is now on hold.
        echo   Double-click Start_Local_Mode.bat again to resume.
        echo ==================================================
    )
    pause
    exit /b 0
)

if exist "%FLAG%" del /f /q "%FLAG%"

if exist "%PYEXE%" (
    "%PYEXE%" "%SCRIPT%"
) else (
    py -3.12 "%SCRIPT%" || python "%SCRIPT%"
)

echo.
echo [INFO] Local Clip Factory stopped.
pause