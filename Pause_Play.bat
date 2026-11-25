@echo off
title Stream Clip Factory - Pause / Play Control
set "ROOT=D:\Automation Youtube Clipping"
set "FLAG=%ROOT%\PAUSE.flag"
set "SCRIPT=%ROOT%\auto_clip_factory.py"

if not exist "%SCRIPT%" (
    echo [ERROR] Missing file: "%SCRIPT%"
    pause
    exit /b 1
)

powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(py|python|python3)(\.exe)?$' -and $_.CommandLine -like '*auto_clip_factory.py*' }; if ($p) { exit 0 } else { exit 1 }"
set "IS_RUNNING=%errorlevel%"

if "%IS_RUNNING%"=="0" (
    if exist "%FLAG%" (
        del /f /q "%FLAG%"
        echo ==================================================
        echo   RESUMED / PLAYING - Factory window is active!
        echo ==================================================
    ) else (
        echo PAUSED > "%FLAG%"
        echo ==================================================
        echo   PAUSED - Factory window is now on hold.
        echo   Double-click Pause_Play.bat again to resume.
        echo ==================================================
    )
    timeout /t 3 >nul
    exit /b 0
)

if exist "%FLAG%" del /f /q "%FLAG%"
echo ==================================================
echo   LAUNCHING 24/7 STREAM CLIP FACTORY WINDOW...
echo ==================================================
start "24/7 Stream Clip Factory" /D "%ROOT%" cmd /k "py -3.12 "%SCRIPT%" || python "%SCRIPT%""
timeout /t 2 >nul
