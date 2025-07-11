#!/usr/bin/env python3
"""
Video Converter for iPhone Compatibility
Converts video files in DCIM folder to iPhone-compatible formats

Open Source Video Converter
Version: 1.0.0
License: MIT
GitHub: https://github.com/minermanNL/DCIM-Converter
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
import configparser
import webbrowser

# Application constants
APP_NAME = "Video Converter for iPhone"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Open Source Community"
APP_LICENSE = "MIT"
APP_GITHUB = "https://github.com/minermanNL/DCIM-Converter"

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Queue for thread communication
        self.log_queue = queue.Queue()
        
        # Variables
        self.source_folder = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.video_files = []
        self.is_converting = False
        self.is_scanning = False
        self.conversion_thread = None
        self.scanning_thread = None
        
        # UI State variables
        self.show_logs = tk.BooleanVar(value=False)
        self.logs_frame = None
        
        # Load settings
        self.load_settings()
        
        # Set default paths if not loaded from settings
        if not self.source_folder.get():
            self.source_folder.set(os.path.join(os.path.expanduser("~"), "OneDrive", "Pictures", "DCIM"))
        if not self.output_folder.get():
            self.output_folder.set(os.path.join(os.path.expanduser("~"), "Desktop", "Converted_Videos"))
        
        self.setup_ui()
        self.check_ffmpeg()
        
        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        """Setup the user interface"""
        # Configure styles
        self.setup_styles()
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Header frame with title and menu
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        header_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(header_frame, text=f"{APP_NAME} v{APP_VERSION}", 
                               font=("Segoe UI", 18, "bold"), style="Title.TLabel")
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # Menu buttons
        menu_frame = ttk.Frame(header_frame)
        menu_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Button(menu_frame, text="Settings", command=self.show_settings, 
                  style="Small.TButton").grid(row=0, column=0, padx=(0, 5))
        ttk.Button(menu_frame, text="About", command=self.show_about, 
                  style="Small.TButton").grid(row=0, column=1)
        
        # Source folder selection
        ttk.Label(main_frame, text="Source Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.source_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_source).grid(row=1, column=2, pady=5)
        
        # Output folder selection
        ttk.Label(main_frame, text="Output Folder:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_output).grid(row=2, column=2, pady=5)
        
        # Scan controls frame
        scan_frame = ttk.Frame(main_frame)
        scan_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.scan_button = ttk.Button(scan_frame, text="🔍 Scan for Videos", 
                                     command=self.scan_videos, style="Accent.TButton")
        self.scan_button.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_scan_button = ttk.Button(scan_frame, text="Cancel", 
                                           command=self.cancel_scan, state='disabled')
        self.cancel_scan_button.grid(row=0, column=1, padx=(0, 10))
        
        # Scanning progress
        self.scan_progress = ttk.Progressbar(scan_frame, mode='indeterminate', length=200)
        self.scan_progress.grid(row=0, column=2, padx=(10, 0))
        
        self.scan_status = ttk.Label(scan_frame, text="", foreground="blue")
        self.scan_status.grid(row=0, column=3, padx=(10, 0))
        
        # Video list frame
        list_frame = ttk.LabelFrame(main_frame, text="Found Videos", padding="10")
        list_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Video list controls
        list_controls = ttk.Frame(list_frame)
        list_controls.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(list_controls, text="Select All", command=self.select_all_videos, 
                  style="Small.TButton").grid(row=0, column=0, padx=(0, 5))
        ttk.Button(list_controls, text="Select None", command=self.select_no_videos, 
                  style="Small.TButton").grid(row=0, column=1, padx=(0, 5))
        
        self.video_count_label = ttk.Label(list_controls, text="No videos found")
        self.video_count_label.grid(row=0, column=2, padx=(20, 0))
        
        # Treeview for video list
        columns = ('Select', 'File', 'Size', 'Format', 'Status')
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        # Define headings
        self.video_tree.heading('Select', text='✓')
        self.video_tree.heading('File', text='File Path')
        self.video_tree.heading('Size', text='Size (MB)')
        self.video_tree.heading('Format', text='Format')
        self.video_tree.heading('Status', text='Status')
        
        # Configure column widths
        self.video_tree.column('Select', width=40)
        self.video_tree.column('File', width=350)
        self.video_tree.column('Size', width=80)
        self.video_tree.column('Format', width=80)
        self.video_tree.column('Status', width=120)
        
        # Bind double-click to toggle selection
        self.video_tree.bind('<Double-1>', self.toggle_video_selection)
        
        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.video_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # Update row configuration
        list_frame.rowconfigure(1, weight=1)
        
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
        
        # Convert controls frame
        convert_frame = ttk.Frame(main_frame)
        convert_frame.grid(row=6, column=0, columnspan=3, pady=20)
        
        self.convert_button = ttk.Button(convert_frame, text="🎬 Convert Selected Videos", 
                                       command=self.start_conversion, style="Accent.TButton")
        self.convert_button.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_convert_button = ttk.Button(convert_frame, text="Cancel", 
                                              command=self.cancel_conversion, state='disabled')
        self.cancel_convert_button.grid(row=0, column=1, padx=(0, 10))
        
        # Show logs toggle
        ttk.Checkbutton(convert_frame, text="Show Logs", variable=self.show_logs,
                       command=self.toggle_logs).grid(row=0, column=2, padx=(20, 0))
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=8, column=0, columnspan=3, pady=5)
        
        # Configure grid weights for resizing
        main_frame.rowconfigure(4, weight=1)
        
        # Create logs frame (initially hidden)
        self.create_logs_frame(main_frame)
        
        # Start log queue processing
        self.process_log_queue()
        
    def setup_styles(self):
        """Setup custom styles for the UI"""
        style = ttk.Style()
        
        # Configure styles for better appearance
        style.configure("Title.TLabel", foreground="#2c3e50", font=("Segoe UI", 18, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Small.TButton", font=("Segoe UI", 9))
        
        # Try to use modern theme if available
        try:
            style.theme_use('clam')
        except:
            pass
            
    def create_logs_frame(self, parent):
        """Create the logs frame (initially hidden)"""
        self.logs_frame = ttk.LabelFrame(parent, text="Conversion Log", padding="10")
        self.logs_frame.columnconfigure(0, weight=1)
        self.logs_frame.rowconfigure(0, weight=1)
        
        # Log text area
        self.log_text = scrolledtext.ScrolledText(self.logs_frame, height=6, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
    def toggle_logs(self):
        """Toggle the visibility of the logs panel"""
        if self.show_logs.get():
            self.logs_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
            self.root.geometry("900x850")  # Expand window
            # Configure grid weight for logs
            self.logs_frame.master.rowconfigure(9, weight=1)
        else:
            self.logs_frame.grid_remove()
            self.root.geometry("900x700")  # Shrink window
            # Remove grid weight for logs
            self.logs_frame.master.rowconfigure(9, weight=0)
            
    def load_settings(self):
        """Load settings from config file"""
        config = configparser.ConfigParser()
        config_file = Path.home() / '.video_converter_settings.ini'
        
        if config_file.exists():
            try:
                config.read(config_file)
                if 'Paths' in config:
                    self.source_folder.set(config['Paths'].get('source_folder', ''))
                    self.output_folder.set(config['Paths'].get('output_folder', ''))
                if 'UI' in config:
                    self.show_logs.set(config['UI'].getboolean('show_logs', False))
            except Exception as e:
                print(f"Error loading settings: {e}")
                
    def save_settings(self):
        """Save settings to config file"""
        config = configparser.ConfigParser()
        config['Paths'] = {
            'source_folder': self.source_folder.get(),
            'output_folder': self.output_folder.get()
        }
        config['UI'] = {
            'show_logs': str(self.show_logs.get())
        }
        
        config_file = Path.home() / '.video_converter_settings.ini'
        try:
            with open(config_file, 'w') as f:
                config.write(f)
        except Exception as e:
            print(f"Error saving settings: {e}")
            
    def show_settings(self):
        """Show settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Center the window
        settings_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="Settings", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Quality presets
        ttk.Label(main_frame, text="Default Quality:").grid(row=1, column=0, sticky=tk.W, pady=5)
        quality_combo = ttk.Combobox(main_frame, values=["high", "medium", "low"], state="readonly")
        quality_combo.set(self.quality_var.get())
        quality_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Auto-save settings
        auto_save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Auto-save settings", variable=auto_save_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        def save_and_close():
            self.quality_var.set(quality_combo.get())
            self.save_settings()
            settings_window.destroy()
            
        ttk.Button(button_frame, text="Save", command=save_and_close).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=settings_window.destroy).grid(row=0, column=1)
        
        main_frame.columnconfigure(1, weight=1)
        settings_window.columnconfigure(0, weight=1)
        settings_window.rowconfigure(0, weight=1)
        
    def show_about(self):
        """Show about dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.geometry("450x350")
        about_window.transient(self.root)
        about_window.grab_set()
        
        # Center the window
        about_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # App info
        ttk.Label(main_frame, text=APP_NAME, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, pady=(0, 10))
        ttk.Label(main_frame, text=f"Version: {APP_VERSION}").grid(row=1, column=0, pady=2)
        ttk.Label(main_frame, text=f"Author: {APP_AUTHOR}").grid(row=2, column=0, pady=2)
        ttk.Label(main_frame, text=f"License: {APP_LICENSE}").grid(row=3, column=0, pady=2)
        
        # Description
        desc_text = ("A free, open-source video converter that transforms your videos "
                    "into iPhone-compatible formats. Supports batch processing and "
                    "maintains folder structure.")
        ttk.Label(main_frame, text=desc_text, wraplength=400, justify=tk.LEFT).grid(row=4, column=0, pady=20)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, pady=10)
        
        def open_github():
            webbrowser.open(APP_GITHUB)
            
        ttk.Button(button_frame, text="🌐 GitHub", command=open_github).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=about_window.destroy).grid(row=0, column=1)
        
        about_window.columnconfigure(0, weight=1)
        about_window.rowconfigure(0, weight=1)
        
    def select_all_videos(self):
        """Select all videos for conversion"""
        for i, video_info in enumerate(self.video_files):
            video_info['selected'] = True
            if i < len(self.video_tree.get_children()):
                item = self.video_tree.get_children()[i]
                values = list(self.video_tree.item(item, 'values'))
                values[0] = "✓"
                self.video_tree.item(item, values=values)
                
    def select_no_videos(self):
        """Deselect all videos"""
        for i, video_info in enumerate(self.video_files):
            video_info['selected'] = False
            if i < len(self.video_tree.get_children()):
                item = self.video_tree.get_children()[i]
                values = list(self.video_tree.item(item, 'values'))
                values[0] = ""
                self.video_tree.item(item, values=values)
                
    def toggle_video_selection(self, event):
        """Toggle selection of a video when double-clicked"""
        item = self.video_tree.selection()[0]
        index = self.video_tree.index(item)
        
        if index < len(self.video_files):
            self.video_files[index]['selected'] = not self.video_files[index].get('selected', False)
            values = list(self.video_tree.item(item, 'values'))
            values[0] = "✓" if self.video_files[index]['selected'] else ""
            self.video_tree.item(item, values=values)
            
    def cancel_scan(self):
        """Cancel the scanning operation"""
        self.is_scanning = False
        
    def cancel_conversion(self):
        """Cancel the conversion operation"""
        self.is_converting = False

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
        """Start scanning for video files in a separate thread"""
        if self.is_scanning:
            messagebox.showwarning("Warning", "Scanning already in progress!")
            return
            
        source_path = Path(self.source_folder.get())
        if not source_path.exists():
            messagebox.showerror("Error", "Source folder does not exist!")
            return
            
        # Start scanning
        self.is_scanning = True
        self.scan_button.config(state='disabled')
        self.cancel_scan_button.config(state='normal')
        self.scan_progress.start()
        self.scan_status.config(text="Scanning...")
        
        # Start scanning thread
        self.scanning_thread = threading.Thread(target=self.scan_videos_thread)
        self.scanning_thread.daemon = True
        self.scanning_thread.start()
        
    def scan_videos_thread(self):
        """Scan for video files in the source folder (runs in separate thread)"""
        try:
            self.log_queue.put(('log', "Scanning for video files..."))
            self.video_files = []
            
            # Clear existing items
            self.log_queue.put(('clear_tree', None))
            
            source_path = Path(self.source_folder.get())
            
            # Video file extensions
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
            
            found_count = 0
            
            # Recursively find video files
            for file_path in source_path.rglob('*'):
                if not self.is_scanning:  # Check if scanning was cancelled
                    break
                    
                if file_path.is_file() and file_path.suffix.lower() in video_extensions:
                    try:
                        # Update scan status
                        self.log_queue.put(('scan_status', f"Scanning... Found {found_count} videos"))
                        
                        # Get file size in MB
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        
                        # Get video info
                        video_info = self.get_video_info(str(file_path))
                        format_info = video_info.get('format', 'Unknown')
                        
                        # Add to list
                        video_data = {
                            'path': str(file_path),
                            'size': size_mb,
                            'format': format_info,
                            'status': 'Ready',
                            'selected': True  # Default to selected
                        }
                        self.video_files.append(video_data)
                        
                        # Add to treeview
                        relative_path = str(file_path.relative_to(source_path))
                        tree_values = (
                            "✓",  # Selected by default
                            relative_path,
                            f"{size_mb:.1f}",
                            format_info,
                            'Ready'
                        )
                        self.log_queue.put(('add_tree_item', tree_values))
                        
                        found_count += 1
                        
                    except Exception as e:
                        self.log_queue.put(('log', f"Error processing {file_path}: {str(e)}"))
                        
            # Scanning complete
            self.log_queue.put(('log', f"Found {len(self.video_files)} video files"))
            self.log_queue.put(('scan_complete', len(self.video_files)))
            
        except Exception as e:
            self.log_queue.put(('log', f"Error during scanning: {str(e)}"))
            self.log_queue.put(('scan_complete', 0))
        
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
            
        # Check if any videos are selected
        selected_videos = [v for v in self.video_files if v.get('selected', False)]
        if not selected_videos:
            messagebox.showwarning("Warning", "No videos selected for conversion! Please select at least one video.")
            return
            
        # Create output directory
        output_path = Path(self.output_folder.get())
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Start conversion thread
        self.is_converting = True
        self.convert_button.config(state='disabled')
        self.cancel_convert_button.config(state='normal')
        self.conversion_thread = threading.Thread(target=self.convert_videos)
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
        
    def convert_videos(self):
        """Convert selected videos to iPhone-compatible format"""
        # Get only selected videos
        selected_videos = [(i, v) for i, v in enumerate(self.video_files) if v.get('selected', False)]
        total_files = len(selected_videos)
        
        if total_files == 0:
            self.log_queue.put(('log', "No videos selected for conversion"))
            self.log_queue.put(('conversion_done', None))
            return
            
        converted_count = 0
        failed_count = 0
        
        for processed, (original_index, video_info) in enumerate(selected_videos):
            if not self.is_converting:  # Check if conversion was cancelled
                break
                
            try:
                # Update progress
                progress = (processed / total_files) * 100
                self.log_queue.put(('progress', progress))
                self.log_queue.put(('status', f"Converting {processed+1}/{total_files}: {Path(video_info['path']).name}"))
                
                # Convert video
                success = self.convert_single_video(video_info)
                
                # Update status in treeview
                status = 'Converted' if success else 'Failed'
                self.log_queue.put(('update_tree', original_index, status))
                
                if success:
                    converted_count += 1
                else:
                    failed_count += 1
                
            except Exception as e:
                self.log_queue.put(('log', f"Error converting {video_info['path']}: {str(e)}"))
                self.log_queue.put(('update_tree', original_index, 'Failed'))
                failed_count += 1
                
        # Conversion complete
        self.log_queue.put(('progress', 100))
        
        if self.is_converting:  # Only show completion message if not cancelled
            completion_msg = f"Conversion complete! {converted_count} converted"
            if failed_count > 0:
                completion_msg += f", {failed_count} failed"
            self.log_queue.put(('status', completion_msg))
            self.log_queue.put(('log', completion_msg))
        else:
            self.log_queue.put(('status', 'Conversion cancelled'))
            self.log_queue.put(('log', 'Conversion cancelled by user'))
            
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
                        values[4] = status  # Update status column (adjusted for new Select column)
                        self.video_tree.item(item, values=values)
                        
                elif message_type == 'conversion_done':
                    self.is_converting = False
                    self.convert_button.config(state='normal')
                    self.cancel_convert_button.config(state='disabled')
                    
                elif message_type == 'clear_tree':
                    for item in self.video_tree.get_children():
                        self.video_tree.delete(item)
                        
                elif message_type == 'add_tree_item':
                    self.video_tree.insert('', 'end', values=data)
                    
                elif message_type == 'scan_status':
                    self.scan_status.config(text=data)
                    
                elif message_type == 'scan_complete':
                    count = data
                    self.is_scanning = False
                    self.scan_button.config(state='normal')
                    self.cancel_scan_button.config(state='disabled')
                    self.scan_progress.stop()
                    
                    if count > 0:
                        self.scan_status.config(text=f"Found {count} videos")
                        self.video_count_label.config(text=f"Found {count} videos ({count} selected)")
                    else:
                        self.scan_status.config(text="No videos found")
                        self.video_count_label.config(text="No videos found")
                    
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
        if self.is_converting or self.is_scanning:
            operations = []
            if self.is_converting:
                operations.append("conversion")
            if self.is_scanning:
                operations.append("scanning")
            
            operation_text = " and ".join(operations)
            if messagebox.askokcancel("Quit", f"{operation_text.capitalize()} in progress. Are you sure you want to quit?"):
                self.is_converting = False
                self.is_scanning = False
                self.save_settings()
                self.root.destroy()
        else:
            self.save_settings()
            self.root.destroy()

def main():
    """Main function to run the application"""
    root = tk.Tk()
    app = VideoConverter(root)
    
    # Start the GUI
    root.mainloop()

if __name__ == "__main__":
    main() 