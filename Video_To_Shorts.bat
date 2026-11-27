@echo off
title Clean Video-to-Shorts Generator (No Captions / No Title Bar)
set "ROOT=D:\Automation Youtube Clipping"
set "SCRIPT=%ROOT%\video_to_shorts.py"
set "PYEXE=C:\Users\shubh\AppData\Local\Programs\Python\Python312\python.exe"

cd /d "%ROOT%"

if not exist "%SCRIPT%" (
    echo [ERROR] Missing file: "%SCRIPT%"
    pause
    exit /b 1
)

if exist "%PYEXE%" (
    "%PYEXE%" "%SCRIPT%"
) else (
    py -3.12 "%SCRIPT%" || python "%SCRIPT%"
)

echo.
pause