#!/usr/bin/env python3
"""
Video Converter for iPhone Compatibility
Converts video files in DCIM folder to iPhone-compatible formats
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import json
from pathlib import Path
from datetime import datetime
import queue

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Converter for iPhone")
        self.root.geometry("800x600")
        
        # Queue for thread communication
        self.log_queue = queue.Queue()
        
        # Variables
        self.source_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.video_files = []
        self.is_converting = False
        self.conversion_thread = None
        
        # Set default paths
        self.source_folder.set(os.path.join(os.path.expanduser("~"), "OneDrive", "Pictures", "DCIM"))
        self.output_folder.set(os.path.join(os.path.expanduser("~"), "Desktop", "Converted_Videos"))
        
        self.setup_ui()
        self.check_ffmpeg()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Video Converter for iPhone", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Source folder selection
        ttk.Label(main_frame, text="Source Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.source_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_source).grid(row=1, column=2, pady=5)
        
        # Output folder selection
        ttk.Label(main_frame, text="Output Folder:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_output).grid(row=2, column=2, pady=5)
        
        # Scan button
        ttk.Button(main_frame, text="Scan for Videos", command=self.scan_videos).grid(row=3, column=0, columnspan=3, pady=20)
        
        # Video list frame
        list_frame = ttk.LabelFrame(main_frame, text="Found Videos", padding="10")
        list_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Treeview for video list
        columns = ('File', 'Size', 'Format', 'Status')
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        # Define headings
        self.video_tree.heading('File', text='File Path')
        self.video_tree.heading('Size', text='Size (MB)')
        self.video_tree.heading('Format', text='Format')
        self.video_tree.heading('Status', text='Status')
        
        # Configure column widths
        self.video_tree.column('File', width=400)
        self.video_tree.column('Size', width=80)
        self.video_tree.column('Format', width=80)
        self.video_tree.column('Status', width=120)
        
        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.video_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Conversion options frame
        options_frame = ttk.LabelFrame(main_frame, text="Conversion Options", padding="10")
        options_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Quality selection
        ttk.Label(options_frame, text="Quality:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.quality_var = tk.StringVar(value="medium")
        quality_combo = ttk.Combobox(options_frame, textvariable=self.quality_var, 
                                   values=["high", "medium", "low"], state="readonly", width=15)
        quality_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        # Resolution selection
        ttk.Label(options_frame, text="Max Resolution:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.resolution_var = tk.StringVar(value="1920x1080")
        resolution_combo = ttk.Combobox(options_frame, textvariable=self.resolution_var,
                                      values=["3840x2160", "1920x1080", "1280x720", "854x480"], 
                                      state="readonly", width=15)
        resolution_combo.grid(row=0, column=3, sticky=tk.W)
        
        # Convert button
        self.convert_button = ttk.Button(main_frame, text="Convert All Videos", 
                                       command=self.start_conversion, style="Accent.TButton")
        self.convert_button.grid(row=6, column=0, columnspan=3, pady=20)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=8, column=0, columnspan=3, pady=5)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Conversion Log", padding="10")
        log_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        main_frame.rowconfigure(4, weight=1)
        main_frame.rowconfigure(9, weight=1)
        
        # Start log queue processing
        self.process_log_queue()
        
    def check_ffmpeg(self):
        """Check if ffmpeg is installed"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self.log_message("FFmpeg found and ready to use")
        except (subprocess.CalledProcessError, FileNotFoundError):
            messagebox.showerror("FFmpeg Not Found", 
                               "FFmpeg is required for video conversion.\n\n"
                               "Please install FFmpeg:\n"
                               "1. Download from https://ffmpeg.org/download.html\n"
                               "2. Add to system PATH\n"
                               "3. Restart this application")
            
    def browse_source(self):
        """Browse for source folder"""
        folder = filedialog.askdirectory(title="Select Source Folder", 
                                       initialdir=self.source_folder.get())
        if folder:
            self.source_folder.set(folder)
            
    def browse_output(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(title="Select Output Folder",
                                       initialdir=self.output_folder.get())
        if folder:
            self.output_folder.set(folder)
            
    def scan_videos(self):
        """Scan for video files in the source folder"""
        self.log_message("Scanning for video files...")
        self.video_files = []
        
        # Clear existing items
        for item in self.video_tree.get_children():
            self.video_tree.delete(item)
            
        source_path = Path(self.source_folder.get())
        if not source_path.exists():
            messagebox.showerror("Error", "Source folder does not exist!")
            return
            
        # Video file extensions
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
        
        # Recursively find video files
        for file_path in source_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                try:
                    # Get file size in MB
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    
                    # Get video info
                    video_info = self.get_video_info(str(file_path))
                    format_info = video_info.get('format', 'Unknown')
                    
                    # Add to list
                    self.video_files.append({
                        'path': str(file_path),
                        'size': size_mb,
                        'format': format_info,
                        'status': 'Ready'
                    })
                    
                    # Add to treeview
                    relative_path = str(file_path.relative_to(source_path))
                    self.video_tree.insert('', 'end', values=(
                        relative_path,
                        f"{size_mb:.1f}",
                        format_info,
                        'Ready'
                    ))
                    
                except Exception as e:
                    self.log_message(f"Error processing {file_path}: {str(e)}")
                    
        self.log_message(f"Found {len(self.video_files)} video files")
        
    def get_video_info(self, file_path):
        """Get video information using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            # Extract format information
            format_name = info.get('format', {}).get('format_name', 'Unknown')
            return {'format': format_name.split(',')[0].upper()}
            
        except Exception:
            return {'format': 'Unknown'}
            
    def start_conversion(self):
        """Start the conversion process in a separate thread"""
        if self.is_converting:
            messagebox.showwarning("Warning", "Conversion already in progress!")
            return
            
        if not self.video_files:
            messagebox.showwarning("Warning", "No videos to convert! Please scan for videos first.")
            return
            
        # Create output directory
        output_path = Path(self.output_folder.get())
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Start conversion thread
        self.is_converting = True
        self.convert_button.config(state='disabled')
        self.conversion_thread = threading.Thread(target=self.convert_videos)
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
        
    def convert_videos(self):
        """Convert all videos to iPhone-compatible format"""
        total_files = len(self.video_files)
        
        for i, video_info in enumerate(self.video_files):
            if not self.is_converting:  # Check if conversion was cancelled
                break
                
            try:
                # Update progress
                progress = (i / total_files) * 100
                self.log_queue.put(('progress', progress))
                self.log_queue.put(('status', f"Converting {i+1}/{total_files}: {Path(video_info['path']).name}"))
                
                # Convert video
                success = self.convert_single_video(video_info)
                
                # Update status in treeview
                status = 'Converted' if success else 'Failed'
                self.log_queue.put(('update_tree', i, status))
                
            except Exception as e:
                self.log_queue.put(('log', f"Error converting {video_info['path']}: {str(e)}"))
                self.log_queue.put(('update_tree', i, 'Failed'))
                
        # Conversion complete
        self.log_queue.put(('progress', 100))
        self.log_queue.put(('status', 'Conversion complete!'))
        self.log_queue.put(('conversion_done', None))
        
    def convert_single_video(self, video_info):
        """Convert a single video file"""
        input_path = Path(video_info['path'])
        source_path = Path(self.source_folder.get())
        output_path = Path(self.output_folder.get())
        
        # Create relative path structure in output folder
        relative_path = input_path.relative_to(source_path)
        output_file = output_path / relative_path.with_suffix('.mp4')
        
        # Create output directory
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Skip if already exists
        if output_file.exists():
            self.log_queue.put(('log', f"Skipping {input_path.name} - already exists"))
            return True
            
        # Build ffmpeg command for iPhone compatibility
        cmd = self.build_ffmpeg_command(str(input_path), str(output_file))
        
        try:
            # Run ffmpeg
            self.log_queue.put(('log', f"Converting {input_path.name}..."))
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log_queue.put(('log', f"Successfully converted {input_path.name}"))
            return True
            
        except subprocess.CalledProcessError as e:
            self.log_queue.put(('log', f"Failed to convert {input_path.name}: {e.stderr}"))
            return False
            
    def build_ffmpeg_command(self, input_file, output_file):
        """Build ffmpeg command for iPhone compatibility"""
        # Base command
        cmd = ['ffmpeg', '-i', input_file, '-y']  # -y to overwrite output files
        
        # Video codec - H.264 for iPhone compatibility
        cmd.extend(['-c:v', 'libx264'])
        
        # Audio codec - AAC for iPhone compatibility
        cmd.extend(['-c:a', 'aac'])
        
        # Profile and level for iPhone compatibility
        cmd.extend(['-profile:v', 'high', '-level', '4.0'])
        
        # Pixel format for iPhone compatibility
        cmd.extend(['-pix_fmt', 'yuv420p'])
        
        # Quality settings based on selection
        quality_settings = {
            'high': ['-crf', '18'],
            'medium': ['-crf', '23'],
            'low': ['-crf', '28']
        }
        cmd.extend(quality_settings[self.quality_var.get()])
        
        # Resolution scaling if needed
        resolution = self.resolution_var.get()
        if resolution != "Original":
            cmd.extend(['-vf', f'scale={resolution}:force_original_aspect_ratio=decrease'])
            
        # Audio settings
        cmd.extend(['-ar', '44100', '-ab', '128k'])
        
        # Movflags for iPhone compatibility
        cmd.extend(['-movflags', '+faststart'])
        
        # Output file
        cmd.append(output_file)
        
        return cmd
        
    def process_log_queue(self):
        """Process messages from the conversion thread"""
        try:
            while True:
                message_type, data = self.log_queue.get_nowait()
                
                if message_type == 'log':
                    self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {data}\n")
                    self.log_text.see(tk.END)
                    
                elif message_type == 'progress':
                    self.progress_var.set(data)
                    
                elif message_type == 'status':
                    self.status_var.set(data)
                    
                elif message_type == 'update_tree':
                    index, status = data
                    if index < len(self.video_tree.get_children()):
                        item = self.video_tree.get_children()[index]
                        values = list(self.video_tree.item(item, 'values'))
                        values[3] = status  # Update status column
                        self.video_tree.item(item, values=values)
                        
                elif message_type == 'conversion_done':
                    self.is_converting = False
                    self.convert_button.config(state='normal')
                    
        except queue.Empty:
            pass
            
        # Schedule next check
        self.root.after(100, self.process_log_queue)
        
    def log_message(self, message):
        """Add a message to the log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"{timestamp} - {message}\n")
        self.log_text.see(tk.END)
        
    def on_closing(self):
        """Handle application closing"""
        if self.is_converting:
            if messagebox.askokcancel("Quit", "Conversion in progress. Are you sure you want to quit?"):
                self.is_converting = False
                self.root.destroy()
        else:
            self.root.destroy()

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = VideoConverter(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main() 