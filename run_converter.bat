@echo off
REM Video Converter for iPhone - Windows Launcher
REM This batch file makes it easy to run the video converter on Windows

echo Starting Video Converter for iPhone...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Check if FFmpeg is installed
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: FFmpeg is not installed or not in PATH
    echo Please install FFmpeg from https://ffmpeg.org/download.html
    echo.
    pause
    exit /b 1
)

REM Run the video converter
python video_converter.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo An error occurred. Check the messages above.
    pause
) 