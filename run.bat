@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Audio extractor
set "RC=0"

python -c "import yt_dlp, faster_whisper" 2>nul
if errorlevel 1 (
    echo First run: installing yt-dlp and faster-whisper...
    python -m pip install --quiet yt-dlp faster-whisper
    if errorlevel 1 (
        echo.
        echo Setup failed. Check that Python is installed and you are online.
        set "RC=1"
        goto :end
    )
)

rem extract.py asks for the link and the folder name itself.
rem Dropping a video file onto this .bat passes its path as the first argument.
if "%~1"=="" (
    python extract.py
) else (
    python extract.py "%~1"
)
set "RC=%errorlevel%"

:end
echo.
if not "%RC%"=="0" echo *** Nothing was produced. Read the message above for the reason. ***
pause
exit /b %RC%
