#!/bin/bash
# Video Converter for iPhone - macOS/Linux Launcher
# This script makes it easy to run the video converter on macOS/Linux

echo "Starting Video Converter for iPhone..."
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python from https://www.python.org/"
    echo "Or on macOS: brew install python"
    echo "Or on Ubuntu/Debian: sudo apt install python3"
    echo
    exit 1
fi

# Check if FFmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ERROR: FFmpeg is not installed or not in PATH"
    echo "Please install FFmpeg:"
    echo "macOS: brew install ffmpeg"
    echo "Ubuntu/Debian: sudo apt install ffmpeg"
    echo "CentOS/RHEL: sudo yum install ffmpeg"
    echo
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Run the video converter
$PYTHON_CMD video_converter.py

# Check if there was an error
if [ $? -ne 0 ]; then
    echo
    echo "An error occurred. Check the messages above."
    read -p "Press Enter to continue..."
fi 