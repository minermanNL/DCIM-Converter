# Video Converter for iPhone

A Python GUI application that converts video files in your DCIM folder to iPhone-compatible formats. The script recursively scans through all folders and subfolders to find video files and converts them using FFmpeg.

## Features

- **GUI Interface**: Easy-to-use graphical interface built with tkinter and tkinterdnd2
- **Drag and Drop**: Intuitive drag-and-drop support for folders
- **Recursive Scanning**: Automatically finds all video files in folders and subfolders
- **iPhone Compatibility**: Converts videos to H.264/AAC format optimized for iPhone
- **Batch Processing**: Converts multiple videos automatically
- **Progress Tracking**: Real-time progress bar and detailed logging
- **Quality Options**: Choose between high, medium, and low quality settings
- **Resolution Control**: Set maximum resolution for output videos
- **Folder Structure**: Maintains original folder structure in output

## Prerequisites

### 1. Python 3.6 or higher
Make sure Python is installed on your system. You can download it from [python.org](https://www.python.org/).

### 2. Install Python Dependencies
Install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 3. FFmpeg Installation
FFmpeg is required for video conversion. Install it based on your operating system:

#### Windows:
1. Download FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Extract the files to a folder (e.g., `C:\ffmpeg`)
3. Add the `bin` folder to your system PATH:
   - Open System Properties → Advanced → Environment Variables
   - Edit the PATH variable and add `C:\ffmpeg\bin`
   - Restart your command prompt/PowerShell

#### macOS:
```bash
# Using Homebrew (recommended)
brew install ffmpeg

# Or using MacPorts
sudo port install ffmpeg
```

#### Linux:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL/Fedora
sudo yum install ffmpeg
# or
sudo dnf install ffmpeg
```

## Installation

1. **Download the script files:**
   - `video_converter.py` - Main application
   - `requirements.txt` - Dependencies (optional)

2. **Verify FFmpeg installation:**
   ```bash
   ffmpeg -version
   ```
   This should display FFmpeg version information.

## Usage

### Running the Application

1. **Open a terminal/command prompt**
2. **Navigate to the script directory**
3. **Run the application:**
   ```bash
   python video_converter.py
   ```

### Using the GUI

1. **Set Source Folder**: 
   - Default is set to your DCIM folder
   - Click "Browse" to select a different folder

2. **Set Output Folder**:
   - Default is set to "Converted_Videos" on your Desktop
   - Click "Browse" to select a different output location

3. **Scan for Videos**:
   - Click "Scan for Videos" to find all video files
   - The application will recursively search through all subfolders

4. **Configure Conversion Options**:
   - **Quality**: Choose High (best quality), Medium (balanced), or Low (smaller files)
   - **Max Resolution**: Set maximum output resolution

5. **Start Conversion**:
   - Click "Convert All Videos" to begin
   - Monitor progress in the progress bar and log area

### Quality Settings

- **High Quality**: CRF 18 - Best quality, larger file sizes
- **Medium Quality**: CRF 23 - Good balance of quality and size
- **Low Quality**: CRF 28 - Smaller files, lower quality

### Supported Input Formats

- MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, 3GP

### Output Format

All videos are converted to:
- **Video Codec**: H.264 (High Profile, Level 4.0)
- **Audio Codec**: AAC (44.1kHz, 128kbps)
- **Container**: MP4
- **Pixel Format**: YUV420P (iPhone compatible)
- **Optimization**: Fast-start enabled for web/streaming

## File Structure

The application maintains your original folder structure:

```
DCIM/
├── Camera/
│   ├── video1.mp4
│   └── video2.avi
└── Screenshots/
    └── screen_record.mov

Output:
Converted_Videos/
├── Camera/
│   ├── video1.mp4 (converted)
│   └── video2.mp4 (converted)
└── Screenshots/
    └── screen_record.mp4 (converted)
```

## Troubleshooting

### Common Issues

1. **"FFmpeg Not Found" Error**:
   - Ensure FFmpeg is installed and added to your system PATH
   - Restart the application after installing FFmpeg

2. **Permission Errors**:
   - Make sure you have read access to source folder
   - Ensure write access to output folder

3. **Conversion Failures**:
   - Check the log area for detailed error messages
   - Some corrupted files may fail to convert

4. **GUI Not Appearing**:
   - Ensure tkinter is installed with Python
   - On Linux, install: `sudo apt install python3-tk`

### Performance Tips

- **Large Files**: Consider using "Medium" or "Low" quality for very large files
- **Batch Size**: The application processes files sequentially to avoid system overload
- **Disk Space**: Ensure sufficient free space in output folder (roughly same size as source)

## Technical Details

### iPhone Compatibility Settings

The converter uses these settings to ensure iPhone compatibility:

- **Video Codec**: libx264 with High Profile
- **Audio Codec**: AAC with 44.1kHz sample rate
- **Pixel Format**: yuv420p (required for iPhone)
- **Level**: 4.0 (supports up to 1080p)
- **Fast Start**: Enabled for better streaming performance

### Thread Safety

The application uses threading to prevent GUI freezing during conversion:
- Conversion runs in a separate thread
- Progress updates are safely communicated via queue
- GUI remains responsive during processing

## License

This project is provided as-is for personal use. Feel free to modify and distribute.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify FFmpeg installation
3. Check the application log for detailed error messages 