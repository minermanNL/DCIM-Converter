# DCIM Video Optimizer - Setup and Usage Guide

## Prerequisites

### 1. Python 3.6 or higher
- Download and install from [python.org](https://www.python.org/downloads/)
- During installation, make sure to check "Add Python to PATH"

### 2. Install Python Dependencies
Open a command prompt/terminal and run:
```bash
pip install -r requirements.txt
```

This will install:
- `tkinterdnd2` - For drag and drop functionality
- Other required Python packages

### 3. FFmpeg
FFmpeg is required for video conversion. Install it based on your operating system:

#### Windows
1. Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract the downloaded ZIP file to a folder (e.g., `C:\ffmpeg`)
3. Add FFmpeg to your system PATH:
   - Open System Properties → Advanced → Environment Variables
   - Under "System Variables", find and select "Path", then click "Edit"
   - Click "New" and add the path to the `bin` folder (e.g., `C:\ffmpeg\bin`)
   - Click "OK" to save all dialogs
   - Restart any open command prompts

#### macOS
```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Or using MacPorts
sudo port install ffmpeg
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

## Installation

1. **Download the code**
   - Option 1: Clone the repository (if using Git):
     ```bash
     git clone https://github.com/minermanNL/DCIM-Converter.git
     cd DCIM-Converter
     ```
   - Option 2: Download and extract the ZIP file from GitHub

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Installation**
   Run the test script to check if everything is set up correctly:
   ```bash
   python test_setup.py
   ```

4. (Optional) Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

### Windows
1. **Using Command Prompt/PowerShell**
   - Navigate to the project directory
   - Run: `python video_converter.py`

2. **Using the Batch File** (Recommended for non-technical users)
   - Double-click `run_converter.bat`
   - This will automatically set up the environment and run the application

### macOS/Linux
1. **Using Terminal**
   - Navigate to the project directory
   - Make the script executable:
     ```bash
     chmod +x run_converter.sh
     ```
   - Run the application:
     ```bash
     ./run_converter.sh
     ```
2. Run the application:
   ```bash
   ./run_converter.sh
   ```
   OR
   ```bash
   python3 video_converter.py
   ```

## Using the Application

1. **Source Folder**: Click "Browse" to select the DCIM folder containing your videos
   - Default: `~/OneDrive/Pictures/DCIM`

2. **Output Folder**: Choose where to save the converted videos
   - Default: `~/Desktop/Converted_Videos`

3. **Scan for Videos**: Click to find all video files in the source folder

4. **Conversion Options**:
   - Quality: Select between High, Medium, or Low
   - Resolution: Set maximum output resolution
   - Other options: Configure additional conversion settings

5. **Convert**: Start the conversion process

6. **Progress**: Monitor the conversion progress in the log window

## Command Line Usage

For advanced users, you can run the converter from the command line:

```bash
python video_converter.py --source /path/to/source --output /path/to/output --quality high
```

### Command Line Options
- `--source`: Source directory (default: ~/OneDrive/Pictures/DCIM)
- `--output`: Output directory (default: ~/Desktop/Converted_Videos)
- `--quality`: Quality setting [high|medium|low] (default: high)
- `--resolution`: Maximum resolution (e.g., 1080, 720, 480)
- `--threads`: Number of conversion threads (default: 2)

## Troubleshooting

### FFmpeg Not Found
- Ensure FFmpeg is installed and added to your system PATH
- Restart your terminal/command prompt after installation

### Permission Issues
On macOS/Linux, you might need to make the script executable:
```bash
chmod +x video_converter.py
```

### Python Not Found
- Ensure Python is installed and added to your system PATH
- On Windows, check "Add Python to PATH" during installation

## Support

For issues and feature requests, please [open an issue](https://github.com/yourusername/dcim-video-optimizer/issues) on GitHub.

## License

This project is open source and available under the [MIT License](LICENSE).
