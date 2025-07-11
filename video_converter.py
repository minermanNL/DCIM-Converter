#!/usr/bin/env python3
"""
Video Converter for iPhone Compatibility
Converts video files in DCIM folder to iPhone-compatible formats

Open Source Video Converter
Version: 2.1.0 (Performance Optimized)
License: MIT
GitHub: https://github.com/minermanNL/DCIM-Converter
Author: Open Source Community (Performance Optimized by AI Assistant)
"""

# Import tkinterdnd2 before tkinter
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import json
import queue
import shutil
import re
import time
import configparser
from pathlib import Path
import sys
import webbrowser
import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from collections import deque

# Set DPI awareness for better high-DPI display
from ctypes import windll
try:
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# Application constants
APP_NAME = "Video Converter for iPhone"
APP_VERSION = "2.1.0"
APP_AUTHOR = "Open Source Community"
APP_LICENSE = "MIT"
APP_GITHUB = "https://github.com/minermanNL/DCIM-Converter"
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
QUALITY_PRESETS = {
    'high': '18',
    'medium': '23',
    'low': '28'
}
RESOLUTION_OPTIONS = ["Original", "3840x2160", "1920x1080", "1280x720", "854x480"]

# Performance constants
MAX_CONCURRENT_SCANS = min(4, multiprocessing.cpu_count())  # Limit concurrent file operations
BATCH_SIZE = 50  # Process files in batches to prevent UI freezing
UI_UPDATE_INTERVAL = 50  # Update UI every 50ms for smoother experience
QUEUE_PROCESS_LIMIT = 10  # Max queue items to process per cycle
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB threshold for large files

class SettingsManager:
    """Manages application settings using INI file."""
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = Path.home() / '.video_converter_settings.ini'
        self.load()

    def load(self):
        """Load settings from file."""
        if self.config_file.exists():
            self.config.read(self.config_file)

    def save(self):
        """Save settings to file."""
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def get(self, section, key, default=None):
        """Get a setting value."""
        return self.config.get(section, key, fallback=default)

    def set(self, section, key, value):
        """Set a setting value."""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Settings manager
        self.settings = SettingsManager()
        
        # Queues for thread communication (performance optimized)
        self.log_queue = queue.Queue(maxsize=500)  # Reduced size for better performance
        self.ui_queue = queue.Queue(maxsize=200)   # Separate queue for UI updates
        self.scan_queue = queue.Queue(maxsize=1000) # Queue for scan results
        
        # Variables
        self.source_folder = tk.StringVar(value=self.settings.get('Paths', 'source_folder', ''))
        self.output_folder = tk.StringVar(value=self.settings.get('Paths', 'output_folder', ''))
        self.quality_var = tk.StringVar(value=self.settings.get('Conversion', 'quality', 'medium'))
        self.resolution_var = tk.StringVar(value=self.settings.get('Conversion', 'resolution', '1920x1080'))
        self.delete_originals = tk.BooleanVar(value=self.settings.get('Conversion', 'delete_originals', False))
        self.include_compatible = tk.BooleanVar(value=self.settings.get('Scanning', 'include_compatible', False))
        self.show_logs = tk.BooleanVar(value=self.settings.get('UI', 'show_logs', False))
        
        # Default paths if not set
        if not self.source_folder.get():
            self.source_folder.set(os.path.join(os.path.expanduser("~"), "OneDrive", "Pictures", "DCIM"))
        if not self.output_folder.get():
            self.output_folder.set(os.path.join(os.path.expanduser("~"), "Desktop", "Converted_Videos"))
        
        # State
        self.video_files = []
        self.is_converting = False
        self.is_scanning = False
        self.conversion_thread = None
        self.scanning_thread = None
        
        # Performance optimization state
        self.pending_tree_updates = deque()  # Batch tree updates
        self.last_ui_update = 0  # Throttle UI updates
        self.scan_executor = None  # Thread pool for scanning
        self.video_info_cache = {}  # Cache video info to avoid repeated ffprobe calls
        
        self.setup_ui()
        self.check_ffmpeg()
        
        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start queue processing (performance optimized)
        self.process_queues()

    def setup_ui(self):
        """Setup the user interface."""
        # Configure styles
        self.setup_styles()
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        header_frame.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(header_frame, text=f"{APP_NAME} v{APP_VERSION}", font=("Segoe UI", 18, "bold"))
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        menu_frame = ttk.Frame(header_frame)
        menu_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Button(menu_frame, text="Settings", command=self.show_settings).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(menu_frame, text="Performance", command=self.show_performance).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(menu_frame, text="About", command=self.show_about).grid(row=0, column=2)
        
        # Source and Output folders
        self.create_folder_selection(main_frame)
        
        # Scan controls
        self.create_scan_controls(main_frame)
        
        # Video list
        self.create_video_list(main_frame)
        
        # Conversion options
        self.create_conversion_options(main_frame)
        
        # Convert controls
        self.create_convert_controls(main_frame)
        
        # Progress and status
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=8, column=0, columnspan=3, pady=5)
        
        # Logs frame (hidden initially)
        self.create_logs_frame(main_frame)
        
        # Drag-and-drop support
        # No need to register drop target with tkinterdnd2
        # The main window is already a drop target by default
        
        # Grid weights
        main_frame.rowconfigure(4, weight=1)

    def setup_styles(self):
        """Setup custom styles."""
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), background="#4CAF50", foreground="white")
        style.configure("Small.TButton", font=("Segoe UI", 9))

    def create_folder_selection(self, parent):
        """Create source and output folder selection UI."""
        ttk.Label(parent, text="Source Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(parent, textvariable=self.source_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(parent, text="Browse", command=self.browse_source).grid(row=1, column=2, pady=5)
        
        ttk.Label(parent, text="Output Folder:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(parent, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        ttk.Button(parent, text="Browse", command=self.browse_output).grid(row=2, column=2, pady=5)

    def create_scan_controls(self, parent):
        """Create scan controls UI."""
        scan_frame = ttk.Frame(parent)
        scan_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.scan_button = ttk.Button(scan_frame, text="🔍 Scan for Videos", command=self.scan_videos, style="Accent.TButton")
        self.scan_button.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_scan_button = ttk.Button(scan_frame, text="Cancel", command=self.cancel_scan, state='disabled')
        self.cancel_scan_button.grid(row=0, column=1, padx=(0, 10))
        
        self.scan_progress = ttk.Progressbar(scan_frame, mode='indeterminate', length=200)
        self.scan_progress.grid(row=0, column=2, padx=(10, 0))
        
        self.scan_status = ttk.Label(scan_frame, text="", foreground="blue")
        self.scan_status.grid(row=0, column=3, padx=(10, 0))

    def create_video_list(self, parent):
        """Create video list treeview UI."""
        list_frame = ttk.LabelFrame(parent, text="Found Videos", padding="10")
        list_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        
        list_controls = ttk.Frame(list_frame)
        list_controls.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(list_controls, text="Select All", command=self.select_all_videos).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(list_controls, text="Select None", command=self.select_no_videos).grid(row=0, column=1, padx=(0, 5))
        
        self.video_count_label = ttk.Label(list_controls, text="No videos found")
        self.video_count_label.grid(row=0, column=2, padx=(20, 0))
        
        self.total_size_label = ttk.Label(list_controls, text="Total Selected Size: 0 MB")
        self.total_size_label.grid(row=0, column=3, padx=(20, 0))
        
        columns = ('Select', 'File', 'Size', 'Format', 'Status', 'Progress')
        self.video_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        self.video_tree.heading('Select', text='✓')
        self.video_tree.heading('File', text='File Path', command=lambda: self.sort_tree('File'))
        self.video_tree.heading('Size', text='Size (MB)', command=lambda: self.sort_tree('Size'))
        self.video_tree.heading('Format', text='Format', command=lambda: self.sort_tree('Format'))
        self.video_tree.heading('Status', text='Status')
        self.video_tree.heading('Progress', text='Progress')
        
        self.video_tree.column('Select', width=40)
        self.video_tree.column('File', width=300)
        self.video_tree.column('Size', width=80)
        self.video_tree.column('Format', width=80)
        self.video_tree.column('Status', width=120)
        self.video_tree.column('Progress', width=80)
        
        self.video_tree.bind('<Double-1>', self.toggle_video_selection)
        self.video_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.video_tree.yview)
        self.video_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

    def create_conversion_options(self, parent):
        """Create conversion options UI."""
        options_frame = ttk.LabelFrame(parent, text="Conversion Options", padding="10")
        options_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(options_frame, text="Quality:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        quality_combo = ttk.Combobox(options_frame, textvariable=self.quality_var, values=list(QUALITY_PRESETS.keys()), state="readonly", width=15)
        quality_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(options_frame, text="Max Resolution:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        resolution_combo = ttk.Combobox(options_frame, textvariable=self.resolution_var, values=RESOLUTION_OPTIONS, state="readonly", width=15)
        resolution_combo.grid(row=0, column=3, sticky=tk.W)

    def create_convert_controls(self, parent):
        """Create convert controls UI."""
        convert_frame = ttk.Frame(parent)
        convert_frame.grid(row=6, column=0, columnspan=3, pady=20)
        
        self.convert_button = ttk.Button(convert_frame, text="🎬 Convert Selected Videos", command=self.start_conversion, style="Accent.TButton")
        self.convert_button.grid(row=0, column=0, padx=(0, 10))
        
        self.cancel_convert_button = ttk.Button(convert_frame, text="Cancel", command=self.cancel_conversion, state='disabled')
        self.cancel_convert_button.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Checkbutton(convert_frame, text="Show Logs", variable=self.show_logs, command=self.toggle_logs).grid(row=0, column=2, padx=(20, 0))

    def create_logs_frame(self, parent):
        """Create logs frame UI."""
        self.logs_frame = ttk.LabelFrame(parent, text="Conversion Log", padding="10")
        self.logs_frame.columnconfigure(0, weight=1)
        self.logs_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(self.logs_frame, height=6, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        clear_btn = ttk.Button(self.logs_frame, text="Clear Logs", command=lambda: self.log_text.delete(1.0, tk.END))
        clear_btn.grid(row=1, column=0, sticky=tk.E, pady=5)
        
        export_btn = ttk.Button(self.logs_frame, text="Export Logs", command=self.export_logs)
        export_btn.grid(row=1, column=0, sticky=tk.W, pady=5)

    def toggle_logs(self):
        """Toggle logs visibility."""
        if self.show_logs.get():
            self.logs_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
            self.root.geometry("900x850")
            self.logs_frame.master.rowconfigure(9, weight=1)
        else:
            self.logs_frame.grid_remove()
            self.root.geometry("900x700")
            self.logs_frame.master.rowconfigure(9, weight=0)

    def sort_tree(self, column):
        """Sort treeview by column."""
        items = [(self.video_tree.set(k, column), k) for k in self.video_tree.get_children('')]
        items.sort(key=lambda t: float(t[0]) if column == 'Size' else t[0])
        for index, (val, k) in enumerate(items):
            self.video_tree.move(k, '', index)

    def handle_drop(self, event):
        """Handle drag-and-drop for folders."""
        path = event.data
        if Path(path).is_dir():
            self.source_folder.set(path)
            messagebox.showinfo("Drop", f"Source folder set to: {path}")

    def show_settings(self):
        """Show settings dialog."""
        window = tk.Toplevel(self.root)
        window.title("Settings")
        window.geometry("400x400")
        window.transient(self.root)
        window.grab_set()
        
        frame = ttk.Frame(window, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(frame, text="Settings", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        ttk.Label(frame, text="Default Quality:").grid(row=1, column=0, sticky=tk.W, pady=5)
        quality_combo = ttk.Combobox(frame, textvariable=self.quality_var, values=list(QUALITY_PRESETS.keys()), state="readonly")
        quality_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(frame, text="Max Resolution:").grid(row=2, column=0, sticky=tk.W, pady=5)
        res_combo = ttk.Combobox(frame, textvariable=self.resolution_var, values=RESOLUTION_OPTIONS, state="readonly")
        res_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(frame, text="Delete originals after conversion", variable=self.delete_originals).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(frame, text="Include iPhone-compatible videos in scan", variable=self.include_compatible).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        def save():
            self.settings.set('Conversion', 'quality', self.quality_var.get())
            self.settings.set('Conversion', 'resolution', self.resolution_var.get())
            self.settings.set('Conversion', 'delete_originals', str(self.delete_originals.get()))
            self.settings.set('Scanning', 'include_compatible', str(self.include_compatible.get()))
            self.settings.save()
            window.destroy()
        
        ttk.Button(frame, text="Save", command=save).grid(row=5, column=0, pady=20)
        ttk.Button(frame, text="Cancel", command=window.destroy).grid(row=5, column=1, pady=20)
        
        frame.columnconfigure(1, weight=1)

    def show_performance(self):
        """Show performance monitoring dialog."""
        window = tk.Toplevel(self.root)
        window.title("Performance Monitor")
        window.geometry("500x400")
        window.transient(self.root)
        window.grab_set()
        
        frame = ttk.Frame(window, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(frame, text="Performance Statistics", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Performance stats
        stats_text = scrolledtext.ScrolledText(frame, height=15, width=60)
        stats_text.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Get performance info
        stats = self.get_performance_stats()
        stats_text.insert(tk.END, stats)
        stats_text.config(state='disabled')
        
        def refresh_stats():
            stats_text.config(state='normal')
            stats_text.delete(1.0, tk.END)
            stats_text.insert(tk.END, self.get_performance_stats())
            stats_text.config(state='disabled')
        
        ttk.Button(frame, text="Refresh", command=refresh_stats).grid(row=2, column=0, pady=10)
        ttk.Button(frame, text="Close", command=window.destroy).grid(row=2, column=1, pady=10)
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
    
    def get_performance_stats(self):
        """Get current performance statistics."""
        stats = []
        stats.append("=== PERFORMANCE STATISTICS ===\n")
        stats.append(f"Application Version: {APP_VERSION}\n")
        stats.append(f"Max Concurrent Scans: {MAX_CONCURRENT_SCANS}\n")
        stats.append(f"Batch Size: {BATCH_SIZE}\n")
        stats.append(f"UI Update Interval: {UI_UPDATE_INTERVAL}ms\n")
        stats.append(f"Queue Process Limit: {QUEUE_PROCESS_LIMIT}\n")
        stats.append(f"Large File Threshold: {LARGE_FILE_THRESHOLD / (1024*1024):.1f}MB\n\n")
        
        stats.append("=== CURRENT STATE ===\n")
        stats.append(f"Total Videos Found: {len(self.video_files)}\n")
        stats.append(f"Selected Videos: {sum(1 for v in self.video_files if v.get('selected', False))}\n")
        stats.append(f"Video Info Cache Size: {len(self.video_info_cache)}\n")
        stats.append(f"Is Scanning: {self.is_scanning}\n")
        stats.append(f"Is Converting: {self.is_converting}\n")
        stats.append(f"Scan Executor Active: {self.scan_executor is not None}\n\n")
        
        stats.append("=== QUEUE STATUS ===\n")
        stats.append(f"Log Queue Size: {self.log_queue.qsize()}\n")
        stats.append(f"UI Queue Size: {self.ui_queue.qsize()}\n")
        stats.append(f"Scan Queue Size: {self.scan_queue.qsize()}\n\n")
        
        stats.append("=== SYSTEM INFO ===\n")
        stats.append(f"CPU Count: {multiprocessing.cpu_count()}\n")
        
        try:
            import psutil
            process = psutil.Process()
            stats.append(f"Memory Usage: {process.memory_info().rss / (1024*1024):.1f}MB\n")
            stats.append(f"CPU Usage: {process.cpu_percent():.1f}%\n")
        except ImportError:
            stats.append("Memory/CPU info unavailable (install psutil for detailed stats)\n")
        
        return "".join(stats)

    def show_about(self):
        """Show about dialog."""
        window = tk.Toplevel(self.root)
        window.title("About")
        window.geometry("450x350")
        window.transient(self.root)
        window.grab_set()
        
        frame = ttk.Frame(window, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, pady=(0, 10))
        ttk.Label(frame, text=f"Version: {APP_VERSION} (Overhauled)").grid(row=1, column=0, pady=2)
        ttk.Label(frame, text=f"License: {APP_LICENSE}").grid(row=2, column=0, pady=2)
        
        desc = "Free tool to convert videos to iPhone formats. Supports batch processing, folder structure preservation, and more."
        ttk.Label(frame, text=desc, wraplength=400, justify=tk.LEFT).grid(row=3, column=0, pady=20)
        
        ttk.Button(frame, text="🌐 GitHub", command=lambda: webbrowser.open(APP_GITHUB)).grid(row=4, column=0)

    def export_logs(self):
        """Export logs to file."""
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if file:
            with open(file, 'w') as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Export", "Logs exported successfully.")

    def select_all_videos(self):
        """Select all videos with batch UI updates."""
        # Update data first
        for video in self.video_files:
            video['selected'] = True
        
        # Batch update UI
        self.batch_update_tree_selection("✓")
        self.update_total_size()

    def select_no_videos(self):
        """Deselect all videos with batch UI updates."""
        # Update data first
        for video in self.video_files:
            video['selected'] = False
        
        # Batch update UI
        self.batch_update_tree_selection("")
        self.update_total_size()
    
    def batch_update_tree_selection(self, select_value):
        """Efficiently update all tree items selection."""
        children = self.video_tree.get_children()
        for item in children:
            values = list(self.video_tree.item(item, 'values'))
            if values:
                values[0] = select_value
                self.video_tree.item(item, values=values)

    def toggle_video_selection(self, event):
        """Toggle video selection."""
        item = self.video_tree.selection()[0]
        index = self.video_tree.index(item)
        self.video_files[index]['selected'] = not self.video_files[index].get('selected', False)
        select = "✓" if self.video_files[index]['selected'] else ""
        self.update_tree_item(index, select=select)
        self.update_total_size()

    def update_tree_item(self, index, select=None, status=None, progress=None):
        """Update a treeview item."""
        if index < len(self.video_tree.get_children()):
            item = self.video_tree.get_children()[index]
            values = list(self.video_tree.item(item, 'values'))
            if select is not None:
                values[0] = select
            if status is not None:
                values[4] = status
            if progress is not None:
                values[5] = progress
            self.video_tree.item(item, values=values)

    def update_total_size(self):
        """Update total selected size label."""
        total_size = sum(v['size'] for v in self.video_files if v.get('selected', False))
        self.total_size_label.config(text=f"Total Selected Size: {total_size:.1f} MB")

    def check_ffmpeg(self):
        """Check if FFmpeg is installed."""
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=True)
            version = result.stdout.splitlines()[0]
            self.log_message(f"FFmpeg found: {version}", "success")
        except Exception:
            messagebox.showerror("FFmpeg Required", "FFmpeg not found. Download from https://ffmpeg.org/download.html and add to PATH.")
            sys.exit(1)

    def browse_source(self):
        """Browse for source folder."""
        folder = filedialog.askdirectory(initialdir=self.source_folder.get())
        if folder:
            self.source_folder.set(folder)

    def browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory(initialdir=self.output_folder.get())
        if folder:
            self.output_folder.set(folder)

    def scan_videos(self):
        """Start scanning thread."""
        if self.is_scanning:
            return
        source_path = Path(self.source_folder.get())
        if not source_path.exists():
            messagebox.showerror("Error", "Source folder does not exist!")
            return
        self.is_scanning = True
        self.scan_button.config(state='disabled')
        self.cancel_scan_button.config(state='normal')
        self.scan_progress.start()
        self.scan_status.config(text="Scanning...")
        self.scanning_thread = threading.Thread(target=self.scan_videos_thread)
        self.scanning_thread.daemon = True
        self.scanning_thread.start()

    def scan_videos_thread(self):
        """Scan for videos in thread with performance optimization."""
        self.ui_queue.put(('clear_tree', None))
        self.video_files = []
        source_path = Path(self.source_folder.get())
        found_count = 0
        
        # First pass: collect all video files quickly (no ffprobe)
        video_paths = []
        try:
            for file_path in source_path.rglob('*'):
                if not self.is_scanning:
                    break
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    video_paths.append(file_path)
                    
                    # Update status periodically without blocking
                    if len(video_paths) % 20 == 0:
                        self.ui_queue.put(('scan_status', f"Scanning... found {len(video_paths)} files"))
        except Exception as e:
            self.log_queue.put(('log', (f"Error scanning directory: {str(e)}", "error")))
            self.ui_queue.put(('scan_complete', 0))
            return
        
        if not self.is_scanning:
            self.ui_queue.put(('scan_complete', 0))
            return
        
        # Second pass: process files in batches with thread pool
        self.scan_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCANS)
        batch_results = []
        
        try:
            # Process files in batches to prevent UI freezing
            for i in range(0, len(video_paths), BATCH_SIZE):
                if not self.is_scanning:
                    break
                    
                batch = video_paths[i:i + BATCH_SIZE]
                futures = []
                
                # Submit batch for concurrent processing
                for file_path in batch:
                    if not self.is_scanning:
                        break
                    future = self.scan_executor.submit(self.process_video_file, file_path, source_path)
                    futures.append(future)
                
                # Collect results from this batch
                for future in as_completed(futures):
                    if not self.is_scanning:
                        break
                    try:
                        result = future.result(timeout=10)  # 10 second timeout per file
                        if result:
                            batch_results.append(result)
                            found_count += 1
                            
                            # Update UI with batch results periodically
                            if len(batch_results) % 10 == 0:
                                self.ui_queue.put(('batch_tree_update', batch_results[-10:]))
                                self.ui_queue.put(('scan_status', f"Processed {found_count} videos"))
                    except Exception as e:
                        self.log_queue.put(('log', (f"Error processing file: {str(e)}", "error")))
                        continue
                
                # Small delay between batches to prevent overwhelming the system
                time.sleep(0.01)
        
        except Exception as e:
            self.log_queue.put(('log', (f"Error in batch processing: {str(e)}", "error")))
        finally:
            if self.scan_executor:
                self.scan_executor.shutdown(wait=False)
                self.scan_executor = None
        
        # Final batch of remaining results
        if batch_results:
            remaining = batch_results[-(len(batch_results) % 10):]
            if remaining:
                self.ui_queue.put(('batch_tree_update', remaining))
        
        self.video_files = batch_results
        self.ui_queue.put(('scan_complete', found_count))
    
    def process_video_file(self, file_path, source_path):
        """Process a single video file for scanning."""
        try:
            # Get basic file info quickly
            file_size = file_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            relative_path = str(file_path.relative_to(source_path))
            
            # For performance, initially set format as unknown
            # We'll get detailed info only when needed (lazy loading)
            video_info = {'format': 'Unknown', 'compatible': False}
            
            # Only run ffprobe on smaller files during scan, cache larger ones
            if file_size < LARGE_FILE_THRESHOLD:
                video_info = self.get_video_info_cached(str(file_path))
            
            # Skip compatible videos if option is set
            if not self.include_compatible.get() and video_info['compatible']:
                return None
            
            data = {
                'path': str(file_path),
                'size': size_mb,
                'format': video_info['format'],
                'compatible': video_info['compatible'],
                'status': 'Ready',
                'selected': True,
                'progress': '0%',
                'tree_values': ("✓", relative_path, f"{size_mb:.1f}", video_info['format'], 'Ready', '0%')
            }
            
            return data
            
        except Exception as e:
            self.log_queue.put(('log', (f"Error processing {file_path}: {str(e)}", "error")))
            return None

    def get_video_info(self, file_path):
        """Get video info using ffprobe."""
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
            info = json.loads(result.stdout)
            format_name = info.get('format', {}).get('format_name', 'Unknown').split(',')[0].upper()
            codec = next((s['codec_name'] for s in info.get('streams', []) if s['codec_type'] == 'video'), '')
            compatible = format_name == 'MP4' and codec == 'h264'
            return {'format': format_name, 'compatible': compatible}
        except Exception:
            return {'format': 'Unknown', 'compatible': False}
    
    def get_video_info_cached(self, file_path):
        """Get video info with caching for performance."""
        # Check cache first
        if file_path in self.video_info_cache:
            return self.video_info_cache[file_path]
        
        # Get info and cache it
        info = self.get_video_info(file_path)
        self.video_info_cache[file_path] = info
        return info

    def cancel_scan(self):
        """Cancel scanning with cleanup."""
        self.is_scanning = False
        if self.scan_executor:
            self.scan_executor.shutdown(wait=False)
            self.scan_executor = None

    def start_conversion(self):
        """Start conversion thread."""
        if self.is_converting:
            return
        selected = [v for v in self.video_files if v.get('selected', False)]
        if not selected:
            messagebox.showwarning("Warning", "No videos selected!")
            return
        output_path = Path(self.output_folder.get())
        output_path.mkdir(parents=True, exist_ok=True)
        self.is_converting = True
        self.convert_button.config(state='disabled')
        self.cancel_convert_button.config(state='normal')
        self.conversion_thread = threading.Thread(target=self.convert_videos, args=(selected,))
        self.conversion_thread.daemon = True
        self.conversion_thread.start()

    def convert_videos(self, selected):
        """Convert videos in thread with performance optimization."""
        total = len(selected)
        for processed, video in enumerate(selected):
            if not self.is_converting:
                break
            
            # Get video info if not already cached (for large files)
            if video['format'] == 'Unknown':
                video_info = self.get_video_info_cached(video['path'])
                video['format'] = video_info['format']
                video['compatible'] = video_info['compatible']
            
            index = self.video_files.index(video)
            self.ui_queue.put(('update_tree', (index, 'Converting', '0%')))
            self.ui_queue.put(('status', f"Converting {processed+1}/{total}: {Path(video['path']).name}"))
            
            # Update progress
            progress = int((processed / total) * 100)
            self.ui_queue.put(('progress', progress))
            
            success = self.convert_single_video(video, index)
            status = 'Converted' if success else 'Failed'
            self.ui_queue.put(('update_tree', (index, status, '100%' if success else 'Failed')))
            
            if success and self.delete_originals.get():
                self.backup_and_delete(video['path'])
        
        self.ui_queue.put(('progress', 100))
        self.ui_queue.put(('conversion_done', None))

    def convert_single_video(self, video, index):
        """Convert a single video."""
        input_path = Path(video['path'])
        source_path = Path(self.source_folder.get())
        output_path = Path(self.output_folder.get())
        relative = input_path.relative_to(source_path)
        output_file = output_path / relative.with_suffix('.mp4')
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        if output_file.exists():
            self.log_message(f"Skipping {input_path.name} - already exists", "info")
            return True
        
        cmd = self.build_ffmpeg_command(str(input_path), str(output_file))
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while process.poll() is None:
                if not self.is_converting:
                    process.terminate()
                    return False
                # Small delay to prevent overwhelming the UI
                time.sleep(0.1)
            if process.returncode == 0:
                self.log_message(f"Converted {input_path.name}", "success")
                return True
            else:
                self.log_message(f"Failed {input_path.name}: {process.stderr}", "error")
                return False
        except Exception as e:
            self.log_message(f"Error converting {input_path.name}: {str(e)}", "error")
            return False

    def build_ffmpeg_command(self, input_file, output_file):
        """Build FFmpeg command."""
        cmd = ['ffmpeg', '-i', input_file, '-y']
        cmd.extend(['-c:v', 'libx264', '-c:a', 'aac', '-profile:v', 'high', '-level', '4.0', '-pix_fmt', 'yuv420p'])
        crf = QUALITY_PRESETS[self.quality_var.get()]
        cmd.extend(['-crf', crf])
        res = self.resolution_var.get()
        if res != "Original":
            cmd.extend(['-vf', f'scale={res.split("x")[0]}:{res.split("x")[1]}:force_original_aspect_ratio=decrease'])
        cmd.extend(['-ar', '44100', '-ab', '128k', '-movflags', '+faststart', output_file])
        return cmd

    def backup_and_delete(self, original_path):
        """Backup and delete original file."""
        try:
            backup_path = Path(original_path).with_suffix('.bak')
            shutil.copy(original_path, backup_path)
            os.remove(original_path)
            self.log_message(f"Deleted original {original_path} (backup created)", "info")
        except Exception as e:
            self.log_message(f"Error deleting original {original_path}: {str(e)}", "error")

    def cancel_conversion(self):
        """Cancel conversion."""
        self.is_converting = False

    def process_queues(self):
        """Process multiple queues with performance optimization."""
        current_time = time.time()
        
        # Process log queue (limit processing to prevent UI freezing)
        log_processed = 0
        try:
            while not self.log_queue.empty() and log_processed < QUEUE_PROCESS_LIMIT:
                msg_type, data = self.log_queue.get_nowait()
                if msg_type == 'log':
                    color = data[1] if isinstance(data, tuple) else "black"
                    message = data[0] if isinstance(data, tuple) else data
                    if not hasattr(self, 'log_text'):
                        continue
                    self.log_text.tag_config("success", foreground="green")
                    self.log_text.tag_config("error", foreground="red")
                    self.log_text.tag_config("info", foreground="blue")
                    self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n", color)
                    self.log_text.see(tk.END)
                log_processed += 1
        except queue.Empty:
            pass
        
        # Process UI queue (throttled updates)
        ui_processed = 0
        try:
            while not self.ui_queue.empty() and ui_processed < QUEUE_PROCESS_LIMIT:
                msg_type, data = self.ui_queue.get_nowait()
                
                if msg_type == 'progress':
                    self.progress_var.set(data)
                elif msg_type == 'status':
                    self.status_var.set(data)
                elif msg_type == 'update_tree':
                    if isinstance(data, tuple) and len(data) == 3:
                        index, status, progress = data
                        self.update_tree_item(index, status=status, progress=progress)
                elif msg_type == 'conversion_done':
                    self.is_converting = False
                    self.convert_button.config(state='normal')
                    self.cancel_convert_button.config(state='disabled')
                elif msg_type == 'clear_tree':
                    for item in self.video_tree.get_children():
                        self.video_tree.delete(item)
                    self.video_info_cache.clear()  # Clear cache when clearing tree
                elif msg_type == 'add_tree_item':
                    self.video_tree.insert('', 'end', values=data)
                elif msg_type == 'batch_tree_update':
                    # Process batch updates efficiently
                    for item_data in data:
                        if 'tree_values' in item_data:
                            self.video_tree.insert('', 'end', values=item_data['tree_values'])
                elif msg_type == 'scan_status':
                    self.scan_status.config(text=data)
                elif msg_type == 'scan_complete':
                    count = data
                    self.is_scanning = False
                    self.scan_button.config(state='normal')
                    self.cancel_scan_button.config(state='disabled')
                    self.scan_progress.stop()
                    text = f"Found {count} videos" if count > 0 else "No videos found"
                    self.scan_status.config(text=text)
                    self.video_count_label.config(text=text)
                    self.update_total_size()
                
                ui_processed += 1
        except queue.Empty:
            pass
        
        # Schedule next processing cycle with adaptive timing
        next_interval = UI_UPDATE_INTERVAL
        if ui_processed >= QUEUE_PROCESS_LIMIT or log_processed >= QUEUE_PROCESS_LIMIT:
            next_interval = max(25, UI_UPDATE_INTERVAL // 2)  # Process faster when busy
        
        self.root.after(next_interval, self.process_queues)

    def log_message(self, message, level="info"):
        """Log a message with level."""
        self.log_queue.put(('log', (message, level)))

    def on_closing(self):
        """Handle window close with proper cleanup."""
        if self.is_converting or self.is_scanning:
            if messagebox.askokcancel("Quit", "Operations in progress. Quit anyway?"):
                self.is_converting = self.is_scanning = False
                
                # Clean up thread pool
                if self.scan_executor:
                    self.scan_executor.shutdown(wait=False)
                    self.scan_executor = None
                
                # Wait for threads to finish
                if self.conversion_thread:
                    self.conversion_thread.join(timeout=1)
                if self.scanning_thread:
                    self.scanning_thread.join(timeout=1)
            else:
                return
        
        # Save settings
        self.settings.set('Paths', 'source_folder', self.source_folder.get())
        self.settings.set('Paths', 'output_folder', self.output_folder.get())
        self.settings.set('UI', 'show_logs', str(self.show_logs.get()))
        self.settings.save()
        
        # Clean up resources
        if self.scan_executor:
            self.scan_executor.shutdown(wait=False)
        
        self.root.destroy()

def main():
    # Use TkinterDnD.Tk() instead of tk.Tk()
    root = TkinterDnD.Tk()
    app = VideoConverter(root)
    
    # Bind the drop event to the root window
    root.drop_target_register(DND_FILES)
    root.dnd_bind('<<Drop>>', app.handle_drop)
    
    root.mainloop()

if __name__ == "__main__":
    main()