@echo off
title Mode 2 - Local-Only Stream Clip Factory
set "ROOT=D:\Automation Youtube Clipping"
set "FLAG=%ROOT%\LOCAL_PAUSE.flag"
set "SCRIPT=%ROOT%\local_clip_factory.py"

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*local_clip_factory.py*' }; if ($p) { exit 0 } else { exit 1 }"
if "%errorlevel%"=="0" (
    if exist "%FLAG%" (
        del /f /q "%FLAG%"
        echo RESUMED Local Clip Factory!
    ) else (
        echo PAUSED > "%FLAG%"
        echo PAUSED Local Clip Factory! Double-click Start_Local_Mode.bat again to resume.
    )
    timeout /t 3 >nul
    exit /b 0
)

if exist "%FLAG%" del /f /q "%FLAG%"
start "Mode 2 - Local Clip Factory" /D "%ROOT%" cmd /k "py -3.12 "%SCRIPT%" || python "%SCRIPT%""