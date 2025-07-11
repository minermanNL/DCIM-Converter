#!/usr/bin/env python3
"""
Video Converter for iPhone Compatibility
Converts video files in DCIM folder to iPhone-compatible formats

Open Source Video Converter
Version: 2.2.0 (Performance Overhauled)
License: MIT
GitHub: https://github.com/minermanNL/DCIM-Converter
Author: Ivan van der Schuit
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
import gc
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
from collections import deque
import traceback
import psutil
import signal
from contextlib import contextmanager
import logging

# Set DPI awareness for better high-DPI display
from ctypes import windll
try:
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

# Application constants
APP_NAME = "Video Converter for iPhone"
APP_VERSION = "2.2.0"
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

# Performance constants (optimized for stability)
MAX_CONCURRENT_SCANS = max(1, min(2, multiprocessing.cpu_count() // 2))  # Conservative limit
BATCH_SIZE = 25  # Reduced for better memory management
UI_UPDATE_INTERVAL = 100  # Slightly slower for stability
QUEUE_PROCESS_LIMIT = 5  # Reduced to prevent UI freezing
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB threshold (reduced)
MAX_QUEUE_SIZE = 500  # Increased to handle bulk operations
MAX_CACHE_SIZE = 200  # Limit cache size to prevent memory leaks
FFMPEG_TIMEOUT = 300  # 5 minutes timeout for ffmpeg operations
SCAN_TIMEOUT = 30  # 30 seconds timeout for file scanning
MEMORY_LIMIT_MB = 500  # Memory usage limit in MB

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_converter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ResourceManager:
    """Manages system resources and prevents memory leaks."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = self.process.memory_info().rss / (1024 * 1024)
        self.peak_memory = self.start_memory
        self.resource_warnings = []
        
    def check_memory_usage(self):
        """Check current memory usage and warn if excessive."""
        try:
            current_memory = self.process.memory_info().rss / (1024 * 1024)
            self.peak_memory = max(self.peak_memory, current_memory)
            
            if current_memory > MEMORY_LIMIT_MB:
                warning = f"High memory usage: {current_memory:.1f}MB (limit: {MEMORY_LIMIT_MB}MB)"
                logger.warning(warning)
                self.resource_warnings.append(warning)
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking memory: {e}")
            return True
    
    def get_stats(self):
        """Get resource usage statistics."""
        try:
            current_memory = self.process.memory_info().rss / (1024 * 1024)
            cpu_percent = self.process.cpu_percent()
            return {
                'current_memory': current_memory,
                'peak_memory': self.peak_memory,
                'start_memory': self.start_memory,
                'cpu_percent': cpu_percent,
                'warnings': self.resource_warnings.copy()
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'error': str(e)}
    
    def force_garbage_collection(self):
        """Force garbage collection to free memory."""
        try:
            collected = gc.collect()
            logger.info(f"Garbage collection freed {collected} objects")
            return collected
        except Exception as e:
            logger.error(f"Error in garbage collection: {e}")
            return 0

class SafeQueue:
    """Thread-safe queue with size limits to prevent memory leaks."""
    
    def __init__(self, maxsize=MAX_QUEUE_SIZE):
        self.queue = queue.Queue(maxsize=maxsize)
        self.dropped_items = 0
        self.lock = threading.Lock()
    
    def put(self, item, block=False):
        """Put item in queue, drop if full to prevent blocking."""
        try:
            self.queue.put(item, block=block, timeout=0.1)
            return True
        except queue.Full:
            with self.lock:
                self.dropped_items += 1
            if self.dropped_items % 10 == 0:
                logger.warning(f"Queue full, dropped {self.dropped_items} items")
            return False
    
    def get(self, block=True, timeout=None):
        """Get item from queue."""
        return self.queue.get(block=block, timeout=timeout)
    
    def empty(self):
        """Check if queue is empty."""
        return self.queue.empty()
    
    def qsize(self):
        """Get queue size."""
        return self.queue.qsize()
    
    def clear(self):
        """Clear all items from queue."""
        try:
            while not self.queue.empty():
                self.queue.get_nowait()
        except queue.Empty:
            pass

class LRUCache:
    """LRU Cache with size limit to prevent memory leaks."""
    
    def __init__(self, maxsize=MAX_CACHE_SIZE):
        self.maxsize = maxsize
        self.cache = {}
        self.access_order = deque()
        self.lock = threading.Lock()
    
    def get(self, key):
        """Get item from cache."""
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.access_order.remove(key)
                self.access_order.append(key)
                return self.cache[key]
            return None
    
    def put(self, key, value):
        """Put item in cache."""
        with self.lock:
            if key in self.cache:
                # Update existing
                self.access_order.remove(key)
                self.access_order.append(key)
                self.cache[key] = value
            else:
                # Add new
                if len(self.cache) >= self.maxsize:
                    # Remove least recently used
                    oldest = self.access_order.popleft()
                    del self.cache[oldest]
                
                self.cache[key] = value
                self.access_order.append(key)
    
    def clear(self):
        """Clear cache."""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
    
    def size(self):
        """Get cache size."""
        with self.lock:
            return len(self.cache)

class SettingsManager:
    """Manages application settings using INI file."""
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config_file = Path.home() / '.video_converter_settings.ini'
        self.load()

    def load(self):
        """Load settings from file."""
        try:
            if self.config_file.exists():
                self.config.read(self.config_file)
        except Exception as e:
            logger.error(f"Error loading settings: {e}")

    def save(self):
        """Save settings to file."""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get(self, section, key, default=None):
        """Get a setting value."""
        try:
            return self.config.get(section, key, fallback=default)
        except Exception:
            return default

    def set(self, section, key, value):
        """Set a setting value."""
        try:
            if section not in self.config:
                self.config[section] = {}
            self.config[section][key] = str(value)
        except Exception as e:
            logger.error(f"Error setting config: {e}")

@contextmanager
def safe_thread_pool(max_workers=None):
    """Context manager for safe thread pool usage."""
    executor = None
    try:
        executor = ThreadPoolExecutor(max_workers=max_workers)
        yield executor
    except Exception as e:
        logger.error(f"Thread pool error: {e}")
        raise
    finally:
        if executor:
            try:
                # Python 3.9+ supports timeout parameter
                import sys
                if sys.version_info >= (3, 9):
                    executor.shutdown(wait=True, timeout=10)
                else:
                    executor.shutdown(wait=True)
            except Exception as e:
                logger.error(f"Error shutting down thread pool: {e}")

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Resource management
        self.resource_manager = ResourceManager()
        
        # Settings manager
        self.settings = SettingsManager()
        
        # Safe queues for thread communication
        self.log_queue = SafeQueue(maxsize=MAX_QUEUE_SIZE)
        self.ui_queue = SafeQueue(maxsize=MAX_QUEUE_SIZE)
        self.scan_queue = SafeQueue(maxsize=MAX_QUEUE_SIZE)
        
        # LRU cache for video info
        self.video_info_cache = LRUCache(maxsize=MAX_CACHE_SIZE)
        
        # Variables with proper defaults
        self.source_folder = tk.StringVar(value=self.settings.get('Paths', 'source_folder', ''))
        self.output_folder = tk.StringVar(value=self.settings.get('Paths', 'output_folder', ''))
        self.quality_var = tk.StringVar(value=self.settings.get('Conversion', 'quality', 'medium'))
        self.resolution_var = tk.StringVar(value=self.settings.get('Conversion', 'resolution', '1920x1080'))
        self.delete_originals = tk.BooleanVar(value=self.settings.get('Conversion', 'delete_originals', 'False') == 'True')
        self.include_compatible = tk.BooleanVar(value=self.settings.get('Scanning', 'include_compatible', 'False') == 'True')
        self.show_logs = tk.BooleanVar(value=self.settings.get('UI', 'show_logs', 'False') == 'True')
        
        # Default paths if not set
        if not self.source_folder.get():
            self.source_folder.set(os.path.join(os.path.expanduser("~"), "OneDrive", "Pictures", "DCIM"))
        if not self.output_folder.get():
            self.output_folder.set(os.path.join(os.path.expanduser("~"), "Desktop", "Converted_Videos"))
        
        # State variables with proper initialization
        self.video_files = []
        self.is_converting = False
        self.is_scanning = False
        self.conversion_thread = None
        self.scanning_thread = None
        self.shutdown_event = threading.Event()
        
        # Thread pool references for proper cleanup
        self.scan_executor = None
        self.convert_executor = None
        
        # UI update throttling
        self.last_ui_update = 0
        self.pending_tree_updates = deque(maxlen=100)  # Limit pending updates
        
        # Performance monitoring
        self.scan_start_time = None
        self.conversion_start_time = None
        
        # Conversion watchdog to prevent deadlocks
        self.last_conversion_activity = None
        self.conversion_watchdog_thread = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.setup_ui()
        self.check_ffmpeg()
        
        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start queue processing with error handling
        self.start_queue_processing()
        
        # Start resource monitoring
        self.start_resource_monitoring()
        
        logger.info(f"Application started - {APP_NAME} v{APP_VERSION}")

    def signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown_event.set()
        self.on_closing()

    def start_queue_processing(self):
        """Start queue processing with error handling."""
        try:
            self.process_queues()
        except Exception as e:
            logger.error(f"Error starting queue processing: {e}")
            # Retry after delay
            self.root.after(1000, self.start_queue_processing)

    def start_resource_monitoring(self):
        """Start resource monitoring."""
        try:
            self.monitor_resources()
        except Exception as e:
            logger.error(f"Error starting resource monitoring: {e}")

    def monitor_resources(self):
        """Monitor system resources periodically."""
        try:
            if not self.resource_manager.check_memory_usage():
                # High memory usage - force garbage collection
                self.resource_manager.force_garbage_collection()
                
                # Clear caches if memory is still high
                if not self.resource_manager.check_memory_usage():
                    self.video_info_cache.clear()
                    self.log_queue.clear()
                    logger.warning("Cleared caches due to high memory usage")
            
            # Schedule next check
            if not self.shutdown_event.is_set():
                self.root.after(10000, self.monitor_resources)  # Check every 10 seconds
                
        except Exception as e:
            logger.error(f"Error in resource monitoring: {e}")
            # Continue monitoring despite errors
            if not self.shutdown_event.is_set():
                self.root.after(10000, self.monitor_resources)

    def setup_ui(self):
        """Setup the user interface with error handling."""
        try:
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
            
            # Grid weights
            main_frame.rowconfigure(4, weight=1)
            
            logger.info("UI setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error setting up UI: {e}")
            messagebox.showerror("UI Error", f"Failed to setup UI: {str(e)}")

    def setup_styles(self):
        """Setup custom styles with error handling."""
        try:
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except:
                logger.warning("Could not set clam theme, using default")
            
            style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), background="#4CAF50", foreground="white")
            style.configure("Small.TButton", font=("Segoe UI", 9))
        except Exception as e:
            logger.error(f"Error setting up styles: {e}")

    def create_folder_selection(self, parent):
        """Create source and output folder selection UI."""
        try:
            ttk.Label(parent, text="Source Folder:").grid(row=1, column=0, sticky=tk.W, pady=5)
            ttk.Entry(parent, textvariable=self.source_folder, width=50).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
            ttk.Button(parent, text="Browse", command=self.browse_source).grid(row=1, column=2, pady=5)
            
            ttk.Label(parent, text="Output Folder:").grid(row=2, column=0, sticky=tk.W, pady=5)
            ttk.Entry(parent, textvariable=self.output_folder, width=50).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
            ttk.Button(parent, text="Browse", command=self.browse_output).grid(row=2, column=2, pady=5)
        except Exception as e:
            logger.error(f"Error creating folder selection: {e}")

    def create_scan_controls(self, parent):
        """Create scan controls UI."""
        try:
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
        except Exception as e:
            logger.error(f"Error creating scan controls: {e}")

    def create_video_list(self, parent):
        """Create video list treeview UI."""
        try:
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
        except Exception as e:
            logger.error(f"Error creating video list: {e}")

    def create_conversion_options(self, parent):
        """Create conversion options UI."""
        try:
            options_frame = ttk.LabelFrame(parent, text="Conversion Options", padding="10")
            options_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
            
            ttk.Label(options_frame, text="Quality:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
            quality_combo = ttk.Combobox(options_frame, textvariable=self.quality_var, values=list(QUALITY_PRESETS.keys()), state="readonly", width=15)
            quality_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
            
            ttk.Label(options_frame, text="Max Resolution:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
            resolution_combo = ttk.Combobox(options_frame, textvariable=self.resolution_var, values=RESOLUTION_OPTIONS, state="readonly", width=15)
            resolution_combo.grid(row=0, column=3, sticky=tk.W)
        except Exception as e:
            logger.error(f"Error creating conversion options: {e}")

    def create_convert_controls(self, parent):
        """Create convert controls UI."""
        try:
            convert_frame = ttk.Frame(parent)
            convert_frame.grid(row=6, column=0, columnspan=3, pady=20)
            
            self.convert_button = ttk.Button(convert_frame, text="🎬 Convert Selected Videos", command=self.start_conversion, style="Accent.TButton")
            self.convert_button.grid(row=0, column=0, padx=(0, 10))
            
            self.cancel_convert_button = ttk.Button(convert_frame, text="Cancel", command=self.cancel_conversion, state='disabled')
            self.cancel_convert_button.grid(row=0, column=1, padx=(0, 10))
            
            ttk.Checkbutton(convert_frame, text="Show Logs", variable=self.show_logs, command=self.toggle_logs).grid(row=0, column=2, padx=(20, 0))
        except Exception as e:
            logger.error(f"Error creating convert controls: {e}")

    def create_logs_frame(self, parent):
        """Create logs frame UI."""
        try:
            self.logs_frame = ttk.LabelFrame(parent, text="Conversion Log", padding="10")
            self.logs_frame.columnconfigure(0, weight=1)
            self.logs_frame.rowconfigure(0, weight=1)
            
            self.log_text = scrolledtext.ScrolledText(self.logs_frame, height=6, width=80)
            self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            clear_btn = ttk.Button(self.logs_frame, text="Clear Logs", command=self.clear_logs)
            clear_btn.grid(row=1, column=0, sticky=tk.E, pady=5)
            
            export_btn = ttk.Button(self.logs_frame, text="Export Logs", command=self.export_logs)
            export_btn.grid(row=1, column=0, sticky=tk.W, pady=5)
        except Exception as e:
            logger.error(f"Error creating logs frame: {e}")

    def clear_logs(self):
        """Clear logs with error handling."""
        try:
            if hasattr(self, 'log_text'):
                self.log_text.delete(1.0, tk.END)
            self.log_queue.clear()
            logger.info("Logs cleared")
        except Exception as e:
            logger.error(f"Error clearing logs: {e}")

    def toggle_logs(self):
        """Toggle logs visibility."""
        try:
            if self.show_logs.get():
                self.logs_frame.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
                self.root.geometry("900x850")
                self.logs_frame.master.rowconfigure(9, weight=1)
            else:
                self.logs_frame.grid_remove()
                self.root.geometry("900x700")
                self.logs_frame.master.rowconfigure(9, weight=0)
        except Exception as e:
            logger.error(f"Error toggling logs: {e}")

    def sort_tree(self, column):
        """Sort treeview by column with error handling."""
        try:
            items = [(self.video_tree.set(k, column), k) for k in self.video_tree.get_children('')]
            items.sort(key=lambda t: float(t[0]) if column == 'Size' and t[0].replace('.', '').isdigit() else str(t[0]))
            for index, (val, k) in enumerate(items):
                self.video_tree.move(k, '', index)
        except Exception as e:
            logger.error(f"Error sorting tree: {e}")

    def handle_drop(self, event):
        """Handle drag-and-drop for folders."""
        try:
            path = event.data
            if Path(path).is_dir():
                self.source_folder.set(path)
                messagebox.showinfo("Drop", f"Source folder set to: {path}")
                logger.info(f"Source folder set via drag-drop: {path}")
        except Exception as e:
            logger.error(f"Error handling drop: {e}")
            messagebox.showerror("Drop Error", f"Failed to set folder: {str(e)}")

    def show_settings(self):
        """Show settings dialog."""
        try:
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
                try:
                    self.settings.set('Conversion', 'quality', self.quality_var.get())
                    self.settings.set('Conversion', 'resolution', self.resolution_var.get())
                    self.settings.set('Conversion', 'delete_originals', str(self.delete_originals.get()))
                    self.settings.set('Scanning', 'include_compatible', str(self.include_compatible.get()))
                    self.settings.save()
                    window.destroy()
                    logger.info("Settings saved successfully")
                except Exception as e:
                    logger.error(f"Error saving settings: {e}")
                    messagebox.showerror("Settings Error", f"Failed to save settings: {str(e)}")
            
            ttk.Button(frame, text="Save", command=save).grid(row=5, column=0, pady=20)
            ttk.Button(frame, text="Cancel", command=window.destroy).grid(row=5, column=1, pady=20)
            
            frame.columnconfigure(1, weight=1)
        except Exception as e:
            logger.error(f"Error showing settings: {e}")
            messagebox.showerror("Settings Error", f"Failed to open settings: {str(e)}")

    def show_performance(self):
        """Show performance monitoring dialog."""
        try:
            window = tk.Toplevel(self.root)
            window.title("Performance Monitor")
            window.geometry("600x500")
            window.transient(self.root)
            window.grab_set()
            
            frame = ttk.Frame(window, padding="20")
            frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            ttk.Label(frame, text="Performance Statistics", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))
            
            # Performance stats
            stats_text = scrolledtext.ScrolledText(frame, height=20, width=70)
            stats_text.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Get performance info
            stats = self.get_performance_stats()
            stats_text.insert(tk.END, stats)
            stats_text.config(state='disabled')
            
            def refresh_stats():
                try:
                    stats_text.config(state='normal')
                    stats_text.delete(1.0, tk.END)
                    stats_text.insert(tk.END, self.get_performance_stats())
                    stats_text.config(state='disabled')
                except Exception as e:
                    logger.error(f"Error refreshing stats: {e}")
            
            def force_gc():
                try:
                    collected = self.resource_manager.force_garbage_collection()
                    messagebox.showinfo("Garbage Collection", f"Freed {collected} objects")
                    refresh_stats()
                except Exception as e:
                    logger.error(f"Error in forced GC: {e}")
                    messagebox.showerror("GC Error", f"Failed to run garbage collection: {str(e)}")
            
            def clear_caches():
                try:
                    self.video_info_cache.clear()
                    self.log_queue.clear()
                    self.ui_queue.clear()
                    messagebox.showinfo("Cache Cleared", "All caches cleared successfully")
                    refresh_stats()
                except Exception as e:
                    logger.error(f"Error clearing caches: {e}")
                    messagebox.showerror("Cache Error", f"Failed to clear caches: {str(e)}")
            
            button_frame = ttk.Frame(frame)
            button_frame.grid(row=2, column=0, columnspan=2, pady=10)
            
            ttk.Button(button_frame, text="Refresh", command=refresh_stats).grid(row=0, column=0, padx=5)
            ttk.Button(button_frame, text="Force GC", command=force_gc).grid(row=0, column=1, padx=5)
            ttk.Button(button_frame, text="Clear Caches", command=clear_caches).grid(row=0, column=2, padx=5)
            ttk.Button(button_frame, text="Close", command=window.destroy).grid(row=0, column=3, padx=5)
            
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(1, weight=1)
        except Exception as e:
            logger.error(f"Error showing performance dialog: {e}")
            messagebox.showerror("Performance Error", f"Failed to open performance monitor: {str(e)}")
    
    def get_performance_stats(self):
        """Get current performance statistics."""
        try:
            stats = []
            stats.append("=== PERFORMANCE STATISTICS ===\n")
            stats.append(f"Application Version: {APP_VERSION}\n")
            stats.append(f"Max Concurrent Scans: {MAX_CONCURRENT_SCANS}\n")
            stats.append(f"Batch Size: {BATCH_SIZE}\n")
            stats.append(f"UI Update Interval: {UI_UPDATE_INTERVAL}ms\n")
            stats.append(f"Queue Process Limit: {QUEUE_PROCESS_LIMIT}\n")
            stats.append(f"Large File Threshold: {LARGE_FILE_THRESHOLD / (1024*1024):.1f}MB\n")
            stats.append(f"Memory Limit: {MEMORY_LIMIT_MB}MB\n")
            stats.append(f"Max Cache Size: {MAX_CACHE_SIZE}\n\n")
            
            stats.append("=== CURRENT STATE ===\n")
            stats.append(f"Total Videos Found: {len(self.video_files)}\n")
            stats.append(f"Selected Videos: {sum(1 for v in self.video_files if v.get('selected', False))}\n")
            stats.append(f"Video Info Cache Size: {self.video_info_cache.size()}\n")
            stats.append(f"Is Scanning: {self.is_scanning}\n")
            stats.append(f"Is Converting: {self.is_converting}\n")
            stats.append(f"Scan Executor Active: {self.scan_executor is not None}\n")
            stats.append(f"Convert Executor Active: {self.convert_executor is not None}\n\n")
            
            stats.append("=== QUEUE STATUS ===\n")
            stats.append(f"Log Queue Size: {self.log_queue.qsize()}\n")
            stats.append(f"UI Queue Size: {self.ui_queue.qsize()}\n")
            stats.append(f"Scan Queue Size: {self.scan_queue.qsize()}\n")
            stats.append(f"Log Queue Dropped: {self.log_queue.dropped_items}\n")
            stats.append(f"UI Queue Dropped: {self.ui_queue.dropped_items}\n\n")
            
            stats.append("=== RESOURCE USAGE ===\n")
            resource_stats = self.resource_manager.get_stats()
            if 'error' not in resource_stats:
                stats.append(f"Current Memory: {resource_stats['current_memory']:.1f}MB\n")
                stats.append(f"Peak Memory: {resource_stats['peak_memory']:.1f}MB\n")
                stats.append(f"Start Memory: {resource_stats['start_memory']:.1f}MB\n")
                stats.append(f"Memory Growth: {resource_stats['current_memory'] - resource_stats['start_memory']:.1f}MB\n")
                stats.append(f"CPU Usage: {resource_stats['cpu_percent']:.1f}%\n")
                
                if resource_stats['warnings']:
                    stats.append("\n=== RESOURCE WARNINGS ===\n")
                    for warning in resource_stats['warnings'][-5:]:  # Show last 5 warnings
                        stats.append(f"⚠️ {warning}\n")
            else:
                stats.append(f"Resource monitoring error: {resource_stats['error']}\n")
            
            stats.append("\n=== SYSTEM INFO ===\n")
            stats.append(f"CPU Count: {multiprocessing.cpu_count()}\n")
            stats.append(f"Python Version: {sys.version}\n")
            stats.append(f"Platform: {sys.platform}\n")
            
            return "".join(stats)
        except Exception as e:
            logger.error(f"Error getting performance stats: {e}")
            return f"Error generating performance stats: {str(e)}"

    def show_about(self):
        """Show about dialog."""
        try:
            window = tk.Toplevel(self.root)
            window.title("About")
            window.geometry("450x350")
            window.transient(self.root)
            window.grab_set()
            
            frame = ttk.Frame(window, padding="20")
            frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold")).grid(row=0, column=0, pady=(0, 10))
            ttk.Label(frame, text=f"Version: {APP_VERSION} (Performance Overhauled)").grid(row=1, column=0, pady=2)
            ttk.Label(frame, text=f"License: {APP_LICENSE}").grid(row=2, column=0, pady=2)
            
            desc = "Free tool to convert videos to iPhone formats. Supports batch processing, folder structure preservation, and more. Now with enhanced performance and memory management."
            ttk.Label(frame, text=desc, wraplength=400, justify=tk.LEFT).grid(row=3, column=0, pady=20)
            
            ttk.Button(frame, text="🌐 GitHub", command=lambda: webbrowser.open(APP_GITHUB)).grid(row=4, column=0)
        except Exception as e:
            logger.error(f"Error showing about dialog: {e}")

    def export_logs(self):
        """Export logs to file."""
        try:
            file = filedialog.asksaveasfilename(
                defaultextension=".txt", 
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if file:
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("Export", "Logs exported successfully.")
                logger.info(f"Logs exported to: {file}")
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            messagebox.showerror("Export Error", f"Failed to export logs: {str(e)}")

    def select_all_videos(self):
        """Select all videos with batch UI updates."""
        try:
            # Update data first
            for video in self.video_files:
                video['selected'] = True
            
            # Batch update UI
            self.batch_update_tree_selection("✓")
            self.update_total_size()
            logger.info("All videos selected")
        except Exception as e:
            logger.error(f"Error selecting all videos: {e}")

    def select_no_videos(self):
        """Deselect all videos with batch UI updates."""
        try:
            # Update data first
            for video in self.video_files:
                video['selected'] = False
            
            # Batch update UI
            self.batch_update_tree_selection("")
            self.update_total_size()
            logger.info("All videos deselected")
        except Exception as e:
            logger.error(f"Error deselecting videos: {e}")
    
    def batch_update_tree_selection(self, select_value):
        """Efficiently update all tree items selection."""
        try:
            children = self.video_tree.get_children()
            for item in children:
                values = list(self.video_tree.item(item, 'values'))
                if values:
                    values[0] = select_value
                    self.video_tree.item(item, values=values)
        except Exception as e:
            logger.error(f"Error in batch tree update: {e}")

    def toggle_video_selection(self, event):
        """Toggle video selection."""
        try:
            selection = self.video_tree.selection()
            if not selection:
                return
            
            item = selection[0]
            index = self.video_tree.index(item)
            
            if index < len(self.video_files):
                self.video_files[index]['selected'] = not self.video_files[index].get('selected', False)
                select = "✓" if self.video_files[index]['selected'] else ""
                self.update_tree_item(index, select=select)
                self.update_total_size()
        except Exception as e:
            logger.error(f"Error toggling video selection: {e}")

    def update_tree_item(self, index, select=None, status=None, progress=None):
        """Update a treeview item with error handling."""
        try:
            children = self.video_tree.get_children()
            if index < len(children):
                item = children[index]
                values = list(self.video_tree.item(item, 'values'))
                if values:
                    if select is not None:
                        values[0] = select
                    if status is not None:
                        values[4] = status
                    if progress is not None:
                        values[5] = progress
                    self.video_tree.item(item, values=values)
        except Exception as e:
            logger.error(f"Error updating tree item: {e}")

    def update_total_size(self):
        """Update total selected size label."""
        try:
            total_size = sum(v['size'] for v in self.video_files if v.get('selected', False))
            self.total_size_label.config(text=f"Total Selected Size: {total_size:.1f} MB")
        except Exception as e:
            logger.error(f"Error updating total size: {e}")

    def check_ffmpeg(self):
        """Check if FFmpeg is installed."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                text=True, 
                check=True, 
                timeout=10
            )
            version = result.stdout.splitlines()[0]
            self.log_message(f"FFmpeg found: {version}", "success")
            logger.info(f"FFmpeg check passed: {version}")
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg check timed out")
            messagebox.showerror("FFmpeg Error", "FFmpeg check timed out. Please ensure FFmpeg is properly installed.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"FFmpeg check failed: {e}")
            messagebox.showerror("FFmpeg Required", 
                               "FFmpeg not found. Download from https://ffmpeg.org/download.html and add to PATH.")
            sys.exit(1)

    def browse_source(self):
        """Browse for source folder."""
        try:
            folder = filedialog.askdirectory(initialdir=self.source_folder.get())
            if folder:
                self.source_folder.set(folder)
                logger.info(f"Source folder selected: {folder}")
        except Exception as e:
            logger.error(f"Error browsing source folder: {e}")
            messagebox.showerror("Browse Error", f"Failed to browse folder: {str(e)}")

    def browse_output(self):
        """Browse for output folder."""
        try:
            folder = filedialog.askdirectory(initialdir=self.output_folder.get())
            if folder:
                self.output_folder.set(folder)
                logger.info(f"Output folder selected: {folder}")
        except Exception as e:
            logger.error(f"Error browsing output folder: {e}")
            messagebox.showerror("Browse Error", f"Failed to browse folder: {str(e)}")

    def scan_videos(self):
        """Start scanning thread with proper error handling."""
        try:
            if self.is_scanning:
                return
            
            source_path = Path(self.source_folder.get())
            if not source_path.exists():
                messagebox.showerror("Error", "Source folder does not exist!")
                return
            
            if not source_path.is_dir():
                messagebox.showerror("Error", "Source path is not a directory!")
                return
            
            self.is_scanning = True
            self.scan_button.config(state='disabled')
            self.cancel_scan_button.config(state='normal')
            self.scan_progress.start()
            self.scan_status.config(text="Scanning...")
            self.scan_start_time = time.time()
            
            # Clear previous results
            self.video_files.clear()
            self.video_info_cache.clear()
            
            self.scanning_thread = threading.Thread(target=self.scan_videos_thread, daemon=True)
            self.scanning_thread.start()
            
            logger.info(f"Started scanning: {source_path}")
            
        except Exception as e:
            logger.error(f"Error starting scan: {e}")
            self.is_scanning = False
            self.scan_button.config(state='normal')
            self.cancel_scan_button.config(state='disabled')
            self.scan_progress.stop()
            messagebox.showerror("Scan Error", f"Failed to start scan: {str(e)}")

    def scan_videos_thread(self):
        """Scan for videos in thread with comprehensive error handling."""
        try:
            self.ui_queue.put(('clear_tree', None))
            self.video_files = []
            source_path = Path(self.source_folder.get())
            found_count = 0
            
            # First pass: collect all video files quickly (no ffprobe)
            video_paths = []
            try:
                for file_path in source_path.rglob('*'):
                    if not self.is_scanning or self.shutdown_event.is_set():
                        break
                    
                    if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                        video_paths.append(file_path)
                        
                        # Update status periodically without blocking
                        if len(video_paths) % 20 == 0:
                            self.ui_queue.put(('scan_status', f"Scanning... found {len(video_paths)} files"))
                        
                        # Check memory usage periodically
                        if len(video_paths) % 100 == 0:
                            if not self.resource_manager.check_memory_usage():
                                logger.warning("High memory usage during scan, continuing with caution")
                
            except Exception as e:
                logger.error(f"Error scanning directory: {e}")
                self.log_queue.put(('log', (f"Error scanning directory: {str(e)}", "error")))
                self.ui_queue.put(('scan_complete', 0))
                return
            
            if not self.is_scanning or self.shutdown_event.is_set():
                self.ui_queue.put(('scan_complete', 0))
                return
            
            logger.info(f"Found {len(video_paths)} video files to process")
            
            # Second pass: process files in batches with thread pool
            batch_results = []
            
            try:
                with safe_thread_pool(max_workers=MAX_CONCURRENT_SCANS) as self.scan_executor:
                    # Process files in batches to prevent UI freezing
                    for i in range(0, len(video_paths), BATCH_SIZE):
                        if not self.is_scanning or self.shutdown_event.is_set():
                            break
                        
                        batch = video_paths[i:i + BATCH_SIZE]
                        futures = []
                        
                        # Submit batch for concurrent processing
                        for file_path in batch:
                            if not self.is_scanning or self.shutdown_event.is_set():
                                break
                            future = self.scan_executor.submit(self.process_video_file, file_path, source_path)
                            futures.append(future)
                        
                        # Collect results from this batch with timeout
                        for future in as_completed(futures, timeout=SCAN_TIMEOUT):
                            if not self.is_scanning or self.shutdown_event.is_set():
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
                                logger.error(f"Error processing file: {e}")
                                self.log_queue.put(('log', (f"Error processing file: {str(e)}", "error")))
                                continue
                        
                        # Small delay between batches to prevent overwhelming the system
                        time.sleep(0.05)
                        
                        # Force garbage collection periodically
                        if i % (BATCH_SIZE * 5) == 0:
                            self.resource_manager.force_garbage_collection()
            
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                self.log_queue.put(('log', (f"Error in batch processing: {str(e)}", "error")))
            finally:
                self.scan_executor = None
            
            # Final batch of remaining results
            if batch_results:
                remaining = batch_results[-(len(batch_results) % 10):]
                if remaining:
                    self.ui_queue.put(('batch_tree_update', remaining))
            
            self.video_files = batch_results
            scan_time = time.time() - self.scan_start_time if self.scan_start_time else 0
            logger.info(f"Scan completed: {found_count} videos found in {scan_time:.1f} seconds")
            
        except Exception as e:
            logger.error(f"Critical error in scan thread: {e}")
            logger.error(traceback.format_exc())
            self.log_queue.put(('log', (f"Critical scan error: {str(e)}", "error")))
            found_count = 0
        finally:
            self.ui_queue.put(('scan_complete', found_count))
    
    def process_video_file(self, file_path, source_path):
        """Process a single video file for scanning with comprehensive error handling."""
        try:
            # Check if we should continue
            if not self.is_scanning or self.shutdown_event.is_set():
                return None
            
            # Get basic file info quickly
            file_stat = file_path.stat()
            file_size = file_stat.st_size
            size_mb = file_size / (1024 * 1024)
            relative_path = str(file_path.relative_to(source_path))
            
            # Skip very large files to prevent memory issues
            if size_mb > 2000:  # 2GB limit
                logger.warning(f"Skipping very large file: {relative_path} ({size_mb:.1f}MB)")
                return None
            
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
            logger.error(f"Error processing {file_path}: {e}")
            self.log_queue.put(('log', (f"Error processing {file_path}: {str(e)}", "error")))
            return None

    def get_video_info(self, file_path):
        """Get video info using ffprobe with timeout and error handling."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json', 
                '-show_format', '-show_streams', file_path
            ]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True, 
                timeout=30
            )
            
            info = json.loads(result.stdout)
            format_name = info.get('format', {}).get('format_name', 'Unknown').split(',')[0].upper()
            
            # Get video codec from streams
            codec = 'Unknown'
            for stream in info.get('streams', []):
                if stream.get('codec_type') == 'video':
                    codec = stream.get('codec_name', 'Unknown')
                    break
            
            compatible = format_name == 'MP4' and codec.lower() == 'h264'
            
            return {
                'format': format_name,
                'compatible': compatible,
                'codec': codec
            }
            
        except subprocess.TimeoutExpired:
            logger.warning(f"ffprobe timeout for {file_path}")
            return {'format': 'Timeout', 'compatible': False, 'codec': 'Unknown'}
        except json.JSONDecodeError:
            logger.warning(f"ffprobe JSON decode error for {file_path}")
            return {'format': 'Error', 'compatible': False, 'codec': 'Unknown'}
        except Exception as e:
            logger.warning(f"ffprobe error for {file_path}: {e}")
            return {'format': 'Error', 'compatible': False, 'codec': 'Unknown'}
    
    def get_video_info_cached(self, file_path):
        """Get video info with caching for performance."""
        try:
            # Check cache first
            cached_info = self.video_info_cache.get(file_path)
            if cached_info is not None:
                return cached_info
            
            # Get info and cache it
            info = self.get_video_info(file_path)
            self.video_info_cache.put(file_path, info)
            return info
            
        except Exception as e:
            logger.error(f"Error getting cached video info: {e}")
            return {'format': 'Error', 'compatible': False, 'codec': 'Unknown'}

    def cancel_scan(self):
        """Cancel scanning with proper cleanup."""
        try:
            logger.info("Cancelling scan...")
            self.is_scanning = False
            
            # Cancel thread pool if active
            if self.scan_executor:
                try:
                    self.scan_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down scan executor: {e}")
                finally:
                    self.scan_executor = None
            
            # Wait for thread to finish
            if self.scanning_thread and self.scanning_thread.is_alive():
                self.scanning_thread.join(timeout=5)
            
            # Reset UI state
            self.scan_button.config(state='normal')
            self.cancel_scan_button.config(state='disabled')
            self.scan_progress.stop()
            self.scan_status.config(text="Scan cancelled")
            
            logger.info("Scan cancelled successfully")
            
        except Exception as e:
            logger.error(f"Error cancelling scan: {e}")

    def start_conversion(self):
        """Start conversion thread with proper error handling."""
        try:
            if self.is_converting:
                return
            
            selected = [v for v in self.video_files if v.get('selected', False)]
            if not selected:
                messagebox.showwarning("Warning", "No videos selected!")
                return
            
            output_path = Path(self.output_folder.get())
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creating output directory: {e}")
                messagebox.showerror("Error", f"Failed to create output directory: {str(e)}")
                return
            
            self.is_converting = True
            self.convert_button.config(state='disabled')
            self.cancel_convert_button.config(state='normal')
            self.conversion_start_time = time.time()
            
            self.conversion_thread = threading.Thread(
                target=self.convert_videos, 
                args=(selected,), 
                daemon=True
            )
            self.conversion_thread.start()
            
            # Start conversion watchdog
            self.last_conversion_activity = time.time()
            self.conversion_watchdog_thread = threading.Thread(
                target=self.conversion_watchdog, 
                daemon=True
            )
            self.conversion_watchdog_thread.start()
            
            logger.info(f"Started conversion of {len(selected)} videos")
            
        except Exception as e:
            logger.error(f"Error starting conversion: {e}")
            self.is_converting = False
            self.convert_button.config(state='normal')
            self.cancel_convert_button.config(state='disabled')
            messagebox.showerror("Conversion Error", f"Failed to start conversion: {str(e)}")

    def convert_videos(self, selected):
        """Convert videos in thread with comprehensive error handling."""
        try:
            total = len(selected)
            successful = 0
            failed = 0
            skipped = 0
            
            logger.info(f"Starting bulk conversion of {total} videos")
            
            for processed, video in enumerate(selected):
                if not self.is_converting or self.shutdown_event.is_set():
                    logger.info(f"Conversion cancelled at video {processed+1}/{total}")
                    break
                
                try:
                    # Get video info if not already cached (for large files)
                    if video['format'] == 'Unknown':
                        video_info = self.get_video_info_cached(video['path'])
                        video['format'] = video_info['format']
                        video['compatible'] = video_info['compatible']
                    
                    index = self.video_files.index(video)
                    filename = Path(video['path']).name
                    
                    # Update UI with current status
                    self.ui_queue.put(('update_tree', (index, 'Converting', '0%')))
                    status_msg = f"Converting {processed+1}/{total}: {filename}"
                    self.ui_queue.put(('status', status_msg))
                    
                    # Update progress bar
                    progress = int((processed / total) * 100)
                    self.ui_queue.put(('progress', progress))
                    
                    logger.info(f"Processing video {processed+1}/{total}: {filename}")
                    
                    # Update activity timestamp
                    self.last_conversion_activity = time.time()
                    
                    # Check if file already exists (skip)
                    input_path = Path(video['path'])
                    source_path = Path(self.source_folder.get())
                    output_path = Path(self.output_folder.get())
                    
                    try:
                        relative = input_path.relative_to(source_path)
                    except ValueError:
                        relative = input_path.name
                    
                    output_file = output_path / Path(relative).with_suffix('.mp4')
                    
                    if output_file.exists():
                        skipped += 1
                        self.ui_queue.put(('update_tree', (index, 'Skipped', 'Exists')))
                        logger.info(f"Skipped existing file: {filename}")
                        continue
                    
                    # Perform conversion
                    conversion_start = time.time()
                    success = self.convert_single_video(video, index)
                    conversion_time = time.time() - conversion_start
                    
                    if success:
                        successful += 1
                        status = 'Converted'
                        progress_text = '100%'
                        
                        # Delete original if requested
                        if self.delete_originals.get():
                            self.backup_and_delete(video['path'])
                        
                        logger.info(f"Successfully converted {filename} in {conversion_time:.1f}s")
                    else:
                        failed += 1
                        status = 'Failed'
                        progress_text = 'Failed'
                        logger.error(f"Failed to convert {filename}")
                    
                    self.ui_queue.put(('update_tree', (index, status, progress_text)))
                    
                    # Check memory usage periodically
                    if processed % 5 == 0:
                        if not self.resource_manager.check_memory_usage():
                            logger.warning("High memory usage during conversion")
                            self.resource_manager.force_garbage_collection()
                    
                    # Log progress summary every 10 videos
                    if (processed + 1) % 10 == 0:
                        elapsed = time.time() - self.conversion_start_time if self.conversion_start_time else 0
                        logger.info(f"Progress: {processed+1}/{total} videos processed in {elapsed:.1f}s (Success: {successful}, Failed: {failed}, Skipped: {skipped})")
                    
                except Exception as e:
                    logger.error(f"Error converting video {video.get('path', 'unknown')}: {e}")
                    failed += 1
                    try:
                        index = self.video_files.index(video)
                        self.ui_queue.put(('update_tree', (index, 'Error', 'Error')))
                    except:
                        pass
            
            conversion_time = time.time() - self.conversion_start_time if self.conversion_start_time else 0
            logger.info(f"Conversion completed: {successful} successful, {failed} failed, {skipped} skipped in {conversion_time:.1f} seconds")
            
            self.ui_queue.put(('progress', 100))
            self.ui_queue.put(('conversion_done', {'successful': successful, 'failed': failed, 'skipped': skipped}))
            
        except Exception as e:
            logger.error(f"Critical error in conversion thread: {e}")
            logger.error(traceback.format_exc())
            self.ui_queue.put(('conversion_done', {'successful': 0, 'failed': total, 'skipped': 0}))

    def convert_single_video(self, video, index):
        """Convert a single video with comprehensive error handling."""
        try:
            input_path = Path(video['path'])
            source_path = Path(self.source_folder.get())
            output_path = Path(self.output_folder.get())
            
            # Log conversion start
            logger.info(f"Starting conversion of {input_path.name}")
            
            # Calculate relative path and output file
            try:
                relative = input_path.relative_to(source_path)
            except ValueError:
                # If input is not relative to source, use just the filename
                relative = input_path.name
            
            output_file = output_path / Path(relative).with_suffix('.mp4')
            
            # Create output directory
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if output file already exists
            if output_file.exists():
                self.log_message(f"Skipping {input_path.name} - already exists", "info")
                logger.info(f"Skipped existing file: {input_path.name}")
                return True
            
            # Build and execute FFmpeg command
            cmd = self.build_ffmpeg_command(str(input_path), str(output_file))
            
            try:
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,  # Combine stderr with stdout
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                # Monitor process with timeout and progress updates
                start_time = time.time()
                last_progress_time = start_time
                output_lines = []
                
                while process.poll() is None:
                    if not self.is_converting or self.shutdown_event.is_set():
                        logger.info(f"Terminating conversion of {input_path.name} due to cancellation")
                        try:
                            process.terminate()
                            process.wait(timeout=10)
                        except:
                            try:
                                process.kill()
                            except:
                                pass
                        return False
                    
                    # Check for timeout
                    current_time = time.time()
                    if current_time - start_time > FFMPEG_TIMEOUT:
                        logger.error(f"FFmpeg timeout for {input_path.name} after {FFMPEG_TIMEOUT} seconds")
                        try:
                            process.terminate()
                            process.wait(timeout=10)
                        except:
                            try:
                                process.kill()
                            except:
                                pass
                        self.log_message(f"Timeout converting {input_path.name}", "error")
                        return False
                    
                    # Log progress every 30 seconds
                    if current_time - last_progress_time > 30:
                        elapsed = current_time - start_time
                        logger.info(f"Converting {input_path.name} - {elapsed:.1f}s elapsed")
                        last_progress_time = current_time
                        
                        # Update activity timestamp
                        if hasattr(self, 'last_conversion_activity'):
                            self.last_conversion_activity = current_time
                    
                    # Read any available output
                    try:
                        if process.stdout:
                            line = process.stdout.readline()
                            if line:
                                output_lines.append(line.strip())
                                # Keep only last 10 lines to prevent memory issues
                                if len(output_lines) > 10:
                                    output_lines.pop(0)
                    except:
                        pass
                    
                    # Small delay to prevent busy waiting
                    time.sleep(0.5)
                
                # Get any remaining output
                try:
                    if process.stdout:
                        remaining_output = process.stdout.read()
                        if remaining_output:
                            output_lines.extend(remaining_output.strip().split('\n'))
                except:
                    pass
                
                elapsed_time = time.time() - start_time
                
                if process.returncode == 0:
                    self.log_message(f"Converted {input_path.name} in {elapsed_time:.1f}s", "success")
                    logger.info(f"Successfully converted {input_path.name} in {elapsed_time:.1f}s")
                    return True
                else:
                    error_output = '\n'.join(output_lines[-3:]) if output_lines else "Unknown error"
                    self.log_message(f"Failed {input_path.name}: {error_output[:200]}", "error")
                    logger.error(f"Failed to convert {input_path.name} (exit code {process.returncode}): {error_output[:200]}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error running FFmpeg for {input_path.name}: {e}")
                self.log_message(f"Error converting {input_path.name}: {str(e)}", "error")
                return False
                
        except Exception as e:
            logger.error(f"Error in convert_single_video: {e}")
            self.log_message(f"Error converting {video.get('path', 'unknown')}: {str(e)}", "error")
            return False

    def build_ffmpeg_command(self, input_file, output_file):
        """Build FFmpeg command with error handling."""
        try:
            cmd = ['ffmpeg', '-i', input_file, '-y']
            
            # Video codec settings
            cmd.extend([
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-profile:v', 'high',
                '-level', '4.0',
                '-pix_fmt', 'yuv420p'
            ])
            
            # Quality settings
            crf = QUALITY_PRESETS.get(self.quality_var.get(), '23')
            cmd.extend(['-crf', crf])
            
            # Resolution settings
            res = self.resolution_var.get()
            if res != "Original" and 'x' in res:
                try:
                    width, height = res.split('x')
                    cmd.extend(['-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease'])
                except ValueError:
                    logger.warning(f"Invalid resolution format: {res}")
            
            # Audio settings
            cmd.extend(['-ar', '44100', '-ab', '128k'])
            
            # Optimization for streaming
            cmd.extend(['-movflags', '+faststart'])
            
            # Output file
            cmd.append(output_file)
            
            return cmd
            
        except Exception as e:
            logger.error(f"Error building FFmpeg command: {e}")
            # Return basic command as fallback
            return ['ffmpeg', '-i', input_file, '-y', '-c:v', 'libx264', '-c:a', 'aac', output_file]

    def backup_and_delete(self, original_path):
        """Backup and delete original file with error handling."""
        try:
            original = Path(original_path)
            backup_path = original.with_suffix(original.suffix + '.bak')
            
            # Create backup
            shutil.copy2(original_path, backup_path)
            
            # Delete original
            os.remove(original_path)
            
            self.log_message(f"Deleted original {original.name} (backup created)", "info")
            logger.info(f"Deleted original with backup: {original_path}")
            
        except Exception as e:
            logger.error(f"Error backing up and deleting {original_path}: {e}")
            self.log_message(f"Error deleting original {original_path}: {str(e)}", "error")

    def conversion_watchdog(self):
        """Monitor conversion progress and detect deadlocks."""
        try:
            while self.is_converting and not self.shutdown_event.is_set():
                time.sleep(60)  # Check every minute
                
                if self.last_conversion_activity:
                    idle_time = time.time() - self.last_conversion_activity
                    
                    # If no activity for 10 minutes, consider it stuck
                    if idle_time > 600:  # 10 minutes
                        logger.error(f"Conversion appears stuck (no activity for {idle_time:.1f} seconds)")
                        self.log_message("Conversion appears stuck - automatically cancelling", "error")
                        
                        # Force cancel the conversion
                        self.is_converting = False
                        
                        # Update UI
                        self.ui_queue.put(('status', 'Conversion cancelled - appeared stuck'))
                        self.ui_queue.put(('conversion_done', {'successful': 0, 'failed': 0, 'skipped': 0}))
                        
                        break
                        
        except Exception as e:
            logger.error(f"Error in conversion watchdog: {e}")

    def cancel_conversion(self):
        """Cancel conversion with proper cleanup."""
        try:
            logger.info("Cancelling conversion...")
            self.is_converting = False
            
            # Cancel thread pool if active
            if self.convert_executor:
                try:
                    self.convert_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down convert executor: {e}")
                finally:
                    self.convert_executor = None
            
            # Wait for thread to finish
            if self.conversion_thread and self.conversion_thread.is_alive():
                self.conversion_thread.join(timeout=5)
            
            # Reset UI state
            self.convert_button.config(state='normal')
            self.cancel_convert_button.config(state='disabled')
            
            logger.info("Conversion cancelled successfully")
            
        except Exception as e:
            logger.error(f"Error cancelling conversion: {e}")

    def process_queues(self):
        """Process multiple queues with comprehensive error handling."""
        try:
            if self.shutdown_event.is_set():
                return
            
            current_time = time.time()
            
            # Process log queue (limit processing to prevent UI freezing)
            log_processed = 0
            try:
                while not self.log_queue.empty() and log_processed < QUEUE_PROCESS_LIMIT:
                    msg_type, data = self.log_queue.get(block=False, timeout=0.1)
                    if msg_type == 'log':
                        self.process_log_message(data)
                    log_processed += 1
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error processing log queue: {e}")
            
            # Process UI queue (throttled updates)
            ui_processed = 0
            try:
                while not self.ui_queue.empty() and ui_processed < QUEUE_PROCESS_LIMIT:
                    msg_type, data = self.ui_queue.get(block=False, timeout=0.1)
                    self.process_ui_message(msg_type, data)
                    ui_processed += 1
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error processing UI queue: {e}")
            
            # Schedule next processing cycle with adaptive timing
            next_interval = UI_UPDATE_INTERVAL
            if ui_processed >= QUEUE_PROCESS_LIMIT or log_processed >= QUEUE_PROCESS_LIMIT:
                next_interval = max(50, UI_UPDATE_INTERVAL // 2)  # Process faster when busy
            
            if not self.shutdown_event.is_set():
                self.root.after(next_interval, self.process_queues)
                
        except Exception as e:
            logger.error(f"Critical error in process_queues: {e}")
            # Try to continue processing despite errors
            if not self.shutdown_event.is_set():
                self.root.after(1000, self.process_queues)

    def process_log_message(self, data):
        """Process a single log message."""
        try:
            if not hasattr(self, 'log_text'):
                return
            
            color = data[1] if isinstance(data, tuple) else "black"
            message = data[0] if isinstance(data, tuple) else data
            
            # Configure tags if not already done
            if not hasattr(self, 'log_tags_configured'):
                self.log_text.tag_config("success", foreground="green")
                self.log_text.tag_config("error", foreground="red")
                self.log_text.tag_config("info", foreground="blue")
                self.log_text.tag_config("warning", foreground="orange")
                self.log_tags_configured = True
            
            # Add timestamp and message
            timestamp = datetime.datetime.now().strftime('%H:%M:%S')
            log_entry = f"{timestamp} - {message}\n"
            
            self.log_text.insert(tk.END, log_entry, color)
            self.log_text.see(tk.END)
            
            # Limit log text size to prevent memory issues
            if self.log_text.get('1.0', tk.END).count('\n') > 1000:
                # Remove first 100 lines
                self.log_text.delete('1.0', '101.0')
                
        except Exception as e:
            logger.error(f"Error processing log message: {e}")

    def process_ui_message(self, msg_type, data):
        """Process a single UI message."""
        try:
            if msg_type == 'progress':
                self.progress_var.set(data)
            elif msg_type == 'status':
                self.status_var.set(data)
            elif msg_type == 'update_tree':
                if isinstance(data, tuple) and len(data) == 3:
                    index, status, progress = data
                    self.update_tree_item(index, status=status, progress=progress)
            elif msg_type == 'conversion_done':
                self.handle_conversion_done(data)
            elif msg_type == 'clear_tree':
                self.clear_tree()
            elif msg_type == 'add_tree_item':
                self.video_tree.insert('', 'end', values=data)
            elif msg_type == 'batch_tree_update':
                self.handle_batch_tree_update(data)
            elif msg_type == 'scan_status':
                self.scan_status.config(text=data)
            elif msg_type == 'scan_complete':
                self.handle_scan_complete(data)
        except Exception as e:
            logger.error(f"Error processing UI message {msg_type}: {e}")

    def handle_conversion_done(self, data):
        """Handle conversion completion."""
        try:
            self.is_converting = False
            self.convert_button.config(state='normal')
            self.cancel_convert_button.config(state='disabled')
            
            if isinstance(data, dict):
                successful = data.get('successful', 0)
                failed = data.get('failed', 0)
                skipped = data.get('skipped', 0)
                
                status_parts = []
                if successful > 0:
                    status_parts.append(f"{successful} successful")
                if failed > 0:
                    status_parts.append(f"{failed} failed")
                if skipped > 0:
                    status_parts.append(f"{skipped} skipped")
                
                status_text = "Conversion complete: " + ", ".join(status_parts)
                self.status_var.set(status_text)
                
                # Show appropriate message dialog
                if failed > 0:
                    message = f"Conversion finished:\n• {successful} successful\n• {failed} failed\n• {skipped} skipped\n\nCheck logs for failure details."
                    messagebox.showwarning("Conversion Complete", message)
                elif successful > 0:
                    message = f"Conversion successful:\n• {successful} converted\n• {skipped} skipped (already exist)"
                    messagebox.showinfo("Conversion Complete", message)
                else:
                    messagebox.showinfo("Conversion Complete", "All files were skipped (already exist)")
            else:
                self.status_var.set("Conversion complete")
                
        except Exception as e:
            logger.error(f"Error handling conversion done: {e}")

    def clear_tree(self):
        """Clear the tree view."""
        try:
            for item in self.video_tree.get_children():
                self.video_tree.delete(item)
            self.video_info_cache.clear()
        except Exception as e:
            logger.error(f"Error clearing tree: {e}")

    def handle_batch_tree_update(self, data):
        """Handle batch tree updates efficiently."""
        try:
            for item_data in data:
                if 'tree_values' in item_data:
                    self.video_tree.insert('', 'end', values=item_data['tree_values'])
        except Exception as e:
            logger.error(f"Error in batch tree update: {e}")

    def handle_scan_complete(self, count):
        """Handle scan completion."""
        try:
            self.is_scanning = False
            self.scan_button.config(state='normal')
            self.cancel_scan_button.config(state='disabled')
            self.scan_progress.stop()
            
            text = f"Found {count} videos" if count > 0 else "No videos found"
            self.scan_status.config(text=text)
            self.video_count_label.config(text=text)
            self.update_total_size()
            
            if count > 0:
                self.status_var.set(f"Scan complete: {count} videos found")
            else:
                self.status_var.set("No videos found")
                
        except Exception as e:
            logger.error(f"Error handling scan complete: {e}")

    def log_message(self, message, level="info"):
        """Log a message with level."""
        try:
            self.log_queue.put(('log', (message, level)))
        except Exception as e:
            logger.error(f"Error queuing log message: {e}")

    def on_closing(self):
        """Handle window close with comprehensive cleanup."""
        try:
            # Check if operations are in progress
            if self.is_converting or self.is_scanning:
                if messagebox.askokcancel("Quit", "Operations in progress. Quit anyway?"):
                    logger.info("User confirmed quit during operations")
                else:
                    return
            
            logger.info("Starting application shutdown...")
            
            # Set shutdown event
            self.shutdown_event.set()
            
            # Cancel operations
            self.is_converting = False
            self.is_scanning = False
            
            # Clean up thread pools
            if self.scan_executor:
                try:
                    self.scan_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down scan executor: {e}")
                finally:
                    self.scan_executor = None
            
            if self.convert_executor:
                try:
                    self.convert_executor.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"Error shutting down convert executor: {e}")
                finally:
                    self.convert_executor = None
            
            # Wait for threads to finish with timeout
            threads_to_join = []
            if self.conversion_thread and self.conversion_thread.is_alive():
                threads_to_join.append(('conversion', self.conversion_thread))
            if self.scanning_thread and self.scanning_thread.is_alive():
                threads_to_join.append(('scanning', self.scanning_thread))
            
            for thread_name, thread in threads_to_join:
                try:
                    thread.join(timeout=5)
                    if thread.is_alive():
                        logger.warning(f"{thread_name} thread did not finish in time")
                except Exception as e:
                    logger.error(f"Error joining {thread_name} thread: {e}")
            
            # Save settings
            try:
                self.settings.set('Paths', 'source_folder', self.source_folder.get())
                self.settings.set('Paths', 'output_folder', self.output_folder.get())
                self.settings.set('UI', 'show_logs', str(self.show_logs.get()))
                self.settings.save()
                logger.info("Settings saved successfully")
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
            
            # Clear caches and queues
            try:
                self.video_info_cache.clear()
                self.log_queue.clear()
                self.ui_queue.clear()
                self.scan_queue.clear()
            except Exception as e:
                logger.error(f"Error clearing caches: {e}")
            
            # Force garbage collection
            try:
                collected = self.resource_manager.force_garbage_collection()
                logger.info(f"Final garbage collection freed {collected} objects")
            except Exception as e:
                logger.error(f"Error in final garbage collection: {e}")
            
            # Log final resource stats
            try:
                stats = self.resource_manager.get_stats()
                if 'error' not in stats:
                    logger.info(f"Final memory usage: {stats['current_memory']:.1f}MB (peak: {stats['peak_memory']:.1f}MB)")
            except Exception as e:
                logger.error(f"Error getting final stats: {e}")
            
            logger.info("Application shutdown complete")
            
            # Destroy the window
            self.root.destroy()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            logger.error(traceback.format_exc())
            # Force destroy even if there are errors
            try:
                self.root.destroy()
            except:
                pass

def main():
    """Main application entry point with error handling."""
    try:
        # Use TkinterDnD.Tk() instead of tk.Tk()
        root = TkinterDnD.Tk()
        
        # Set up global exception handler
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            messagebox.showerror("Unexpected Error", 
                               f"An unexpected error occurred:\n{exc_type.__name__}: {exc_value}")
        
        sys.excepthook = handle_exception
        
        # Create application
        app = VideoConverter(root)
        
        # Bind the drop event to the root window
        root.drop_target_register(DND_FILES)
        root.dnd_bind('<<Drop>>', app.handle_drop)
        
        logger.info("Starting main application loop")
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        logger.error(traceback.format_exc())
        messagebox.showerror("Critical Error", f"Failed to start application: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()