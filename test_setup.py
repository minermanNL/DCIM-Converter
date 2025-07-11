#!/usr/bin/env python3
"""
Test Setup Script for Video Converter
This script verifies that all required dependencies are installed and working.
"""

import sys
import subprocess
import tkinter as tk
from tkinter import messagebox
import json
from pathlib import Path
import os

def test_python_version():
    """Test if Python version is compatible"""
    print("Testing Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 6:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} is too old. Need Python 3.6+")
        return False

def test_tkinter():
    """Test if tkinter is available"""
    print("Testing tkinter availability...")
    try:
        # Try to create a simple window
        root = tk.Tk()
        root.withdraw()  # Hide the window
        root.destroy()
        print("✓ tkinter is available")
        return True
    except Exception as e:
        print(f"✗ tkinter is not available: {e}")
        return False

def test_tkinterdnd2():
    """Test if tkinterdnd2 is available"""
    print("Testing tkinterdnd2 availability...")
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        # Try to create a simple window with TkinterDnD
        root = TkinterDnD.Tk()
        root.withdraw()  # Hide the window
        root.destroy()
        print("✓ tkinterdnd2 is available")
        return True
    except Exception as e:
        print(f"✗ tkinterdnd2 is not available: {e}")
        print("  Install it with: pip install tkinterdnd2")
        return False

def test_ffmpeg():
    """Test if FFmpeg is installed and accessible"""
    print("Testing FFmpeg installation...")
    try:
        # Test ffmpeg command
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, check=True)
        
        # Extract version info
        version_line = result.stdout.split('\n')[0]
        print(f"✓ FFmpeg found: {version_line}")
        
        # Test ffprobe command
        result = subprocess.run(['ffprobe', '-version'], 
                              capture_output=True, text=True, check=True)
        print("✓ FFprobe is available")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ FFmpeg command failed: {e}")
        return False
    except FileNotFoundError:
        print("✗ FFmpeg not found. Please install FFmpeg and add it to PATH")
        return False

def test_required_modules():
    """Test if all required Python modules are available"""
    print("Testing required Python modules...")
    required_modules = [
        'tkinter',
        'tkinterdnd2',
        'subprocess',
        'json',
        'pathlib',
        'os',
        'queue',
        'threading',
        'configparser',
        'shutil',
        're',
        'webbrowser',
        'datetime'
    ]
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module} is available")
        except ImportError:
            print(f"✗ {module} is missing")
            missing_modules.append(module)
    
    return len(missing_modules) == 0

def test_file_permissions():
    """Test file system permissions"""
    print("Testing file system permissions...")
    
    # Test read permissions on DCIM folder
    dcim_path = Path.home() / "OneDrive" / "Pictures" / "DCIM"
    if dcim_path.exists():
        if dcim_path.is_dir() and os.access(dcim_path, os.R_OK):
            print(f"✓ Can read from DCIM folder: {dcim_path}")
        else:
            print(f"✗ Cannot read from DCIM folder: {dcim_path}")
            return False
    else:
        print(f"! DCIM folder not found at expected location: {dcim_path}")
        print("  You can still use the application by selecting a different folder")
    
    # Test write permissions on Desktop
    desktop_path = Path.home() / "Desktop"
    if desktop_path.exists():
        test_file = desktop_path / "test_write_permission.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Delete test file
            print(f"✓ Can write to Desktop: {desktop_path}")
        except Exception as e:
            print(f"✗ Cannot write to Desktop: {e}")
            return False
    else:
        print("! Desktop folder not found at expected location")
        print("  You can still use the application by selecting a different output folder")
    
    return True

def main():
    """Main test function"""
    print("=" * 60)
    print("Video Converter Setup Test")
    print("=" * 60)
    
    tests = [
        ("Python Version", test_python_version),
        ("Tkinter", test_tkinter),
        ("TkinterDnD2", test_tkinterdnd2),
        ("FFmpeg", test_ffmpeg),
        ("Required Modules", test_required_modules),
        ("File Permissions", test_file_permissions)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! You're ready to use the Video Converter.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please address the issues above.")
        
        # Provide specific help for common issues
        print("\nCommon solutions:")
        print("- FFmpeg not found: Install from https://ffmpeg.org/download.html")
        print("- Tkinter not available: Install python3-tk package (Linux)")
        print("- Permission issues: Run as administrator or change folders")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    main() 