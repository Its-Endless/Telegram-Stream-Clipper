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

if exist "%FLAG%" del /f /q "%FLAG%"

echo ==================================================
echo   STARTING MODE 2 - LOCAL-ONLY STREAM CLIP FACTORY
echo   Saving clips to: "%ROOT%\LOCAL_CLIPS"
echo   Press Ctrl+C anytime to stop.
echo ==================================================
echo.

if exist "%PYEXE%" (
    "%PYEXE%" "%SCRIPT%"
) else (
    py -3.12 "%SCRIPT%" || python "%SCRIPT%"
)

echo.
echo [INFO] Local Clip Factory stopped.
pause