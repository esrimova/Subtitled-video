@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Audio extractor (browser)

python -c "import yt_dlp, faster_whisper" 2>nul
if errorlevel 1 (
    echo First run: installing yt-dlp and faster-whisper...
    python -m pip install --quiet yt-dlp faster-whisper
    if errorlevel 1 (
        echo.
        echo Setup failed. Check that Python is installed and you are online.
        pause
        exit /b 1
    )
)

python -I -X utf8 app\server.py %*
echo.
echo The app has stopped.
pause
