import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ffmpeg
import os
import re
from typing import List
from dataclasses import dataclass
import subprocess
import threading
import time
from queue import Queue

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        messagebox.showerror(
            "FFmpeg Not Found",
            "FFmpeg is required but not found on your system.\n\n"
            "Please install FFmpeg:\n"
            "1. Download from https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip\n"
            "2. Extract the zip file\n"
            "3. Copy all .exe files from the bin folder to C:\\Windows\\System32\n"
            "4. Restart this application"
        )
        return False

def check_nvidia_gpu():
    try:
        # Check if NVIDIA GPU is available through ffmpeg
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        return 'h264_nvenc' in result.stdout
    except:
        return False

@dataclass
class TimeSegment:
    start: str  # Format: "MM:SS"
    end: str    # Format: "MM:SS"

class VideoProcessor:
    def __init__(self):
        self.top_video = None
        self.bottom_video = None
        self.audio_file = None
        self.output_dir = None
        self.processing_thread = None
        self.progress_queue = Queue()
        self.status_queue = Queue()
        self.has_nvidia = check_nvidia_gpu()
        
    def convert_timestamp(self, timestamp: str) -> float:
        """Convert MM:SS format to seconds"""
        parts = timestamp.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid timestamp format: {timestamp}. Use MM:SS format.")
        try:
            minutes = int(parts[0])
            seconds = int(parts[1])
            if seconds >= 60:
                raise ValueError(f"Seconds must be less than 60 in timestamp: {timestamp}")
            return minutes * 60 + seconds
        except ValueError as e:
            raise ValueError(f"Invalid timestamp format: {timestamp}. Use MM:SS format with numbers only.") from e
    
    def process_videos(self, segments: List[TimeSegment], progress_callback=None):
        if not check_ffmpeg():
            return

        if not all([self.top_video, self.bottom_video, self.output_dir]):
            raise ValueError("Missing input files or output directory")
            
        # Check if input files are mp4
        if not self.top_video.endswith('.mp4') or not self.bottom_video.endswith('.mp4'):
            raise ValueError("Input files must be mp4")
            
        # Check audio file if provided
        if self.audio_file and not self.audio_file.lower().endswith(('.mp3', '.wav', '.m4a', '.aac')):
            raise ValueError("Audio file must be mp3, wav, m4a, or aac format")
            
        self.status_queue.put("Analyzing videos...")
        
        # Get video dimensions for both videos
        probe_top = ffmpeg.probe(self.top_video)
        probe_bottom = ffmpeg.probe(self.bottom_video)
        width_top = int(probe_top['streams'][0]['width'])
        height_top = int(probe_top['streams'][0]['height'])
        width_bottom = int(probe_bottom['streams'][0]['width'])
        height_bottom = int(probe_bottom['streams'][0]['height'])
        
        # Calculate dimensions for 9:16 final output
        target_height = min(height_top, height_bottom)
        segment_height = target_height // 2
        segment_width = int(segment_height * 9 / 8)
        
        # Create combined video
        temp_output = os.path.join(self.output_dir, "temp_combined.mp4").replace('\\', '/')
        
        try:
            self.status_queue.put("Combining videos...")

            # Build the ffmpeg command with hardware acceleration if available
            video_encoder = 'h264_nvenc' if self.has_nvidia else 'libx264'
            encoder_preset = 'p1' if self.has_nvidia else 'ultrafast'
            
            # Base command for video
            command = [
                'ffmpeg',
                '-hwaccel', 'auto',  # Enable hardware acceleration
                '-i', self.top_video.replace('\\', '/'),
                '-i', self.bottom_video.replace('\\', '/')
            ]
            
            # Add audio input if specified
            if self.audio_file:
                command.extend(['-i', self.audio_file.replace('\\', '/')])
            
            # Add video filter complex
            command.extend([
                '-filter_complex',
                f'[0:v]crop={segment_width}:{segment_height}:(in_w-{segment_width})/2:(in_h-{segment_height})/2[top];'
                f'[1:v]crop={segment_width}:{segment_height}:(in_w-{segment_width})/2:(in_h-{segment_height})/2[bottom];'
                '[top][bottom]vstack[v]'
            ])
            
            # Add mapping
            command.extend(['-map', '[v]'])
            
            # Add audio mapping based on presence of audio file
            if self.audio_file:
                command.extend(['-map', '2:a'])  # Use external audio
            else:
                command.extend(['-map', '0:a'])  # Use top video audio
            
            # Add encoding parameters
            command.extend([
                '-c:v', video_encoder,
                '-preset', encoder_preset,
                '-c:a', 'aac',  # Use AAC audio codec
                '-y',
                temp_output
            ])
            
            # Start the process
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Monitor progress during combining phase
            start_time = time.time()
            progress = 0
            while process.poll() is None and progress < 98:
                time.sleep(0.1)  # Small delay for smooth progress
                progress += 0.1  # Increment by 0.1%
                self.progress_queue.put(progress)
            
            # Wait for process to complete
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg Error:\n{stderr.decode()}")
            
            self.progress_queue.put(30)  # Progress after combination
            
            # Process segments sequentially
            def process_segment(segment, index, total):
                try:
                    self.status_queue.put(f"Processing segment {index}/{total}...")
                    
                    start_seconds = self.convert_timestamp(segment.start)
                    end_seconds = self.convert_timestamp(segment.end)
                    duration = end_seconds - start_seconds
                    
                    if duration <= 0:
                        raise ValueError(f"Invalid segment duration: {segment.start}-{segment.end}")
                    
                    output_file = os.path.join(
                        self.output_dir, 
                        f'segment_{segment.start.replace(":", ".")}-{segment.end.replace(":", ".")}.mp4'
                    ).replace('\\', '/')
                    
                    # Enhanced segment extraction with proper encoding settings
                    segment_command = [
                        'ffmpeg',
                        '-hwaccel', 'auto',
                        '-ss', str(start_seconds),
                        '-i', temp_output,
                        '-t', str(duration),
                        '-c:v', video_encoder,
                        '-preset', encoder_preset,
                        '-c:a', 'aac',
                        '-avoid_negative_ts', '1',
                        '-async', '1',
                        '-vsync', 'cfr',  # Use constant frame rate
                        '-max_muxing_queue_size', '1024',  # Increase muxing queue size
                        '-y',
                        output_file
                    ]
                    
                    process = subprocess.run(segment_command, capture_output=True, text=True)
                    if process.returncode != 0:
                        raise RuntimeError(f"FFmpeg Error during segmentation:\n{process.stderr}")
                    
                    # Simulate gradual progress for this segment
                    progress_start = 30 + ((index - 1) / total * 70)
                    progress_end = 30 + (index / total * 70)
                    progress_step = (progress_end - progress_start) / 10
                    
                    for i in range(10):
                        time.sleep(0.1)  # Small delay for smoother progress
                        self.progress_queue.put(progress_start + (i * progress_step))
                    
                    self.progress_queue.put(progress_end)
                        
                except Exception as e:
                    raise RuntimeError(f"Error processing segment {segment.start}-{segment.end}: {str(e)}")
            
            # Process segments sequentially to avoid timing issues
            total_segments = len(segments)
            for i, segment in enumerate(segments, 1):
                process_segment(segment, i, total_segments)
                    
        except Exception as e:
            raise RuntimeError(f"Video processing failed: {str(e)}")
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_output):
                    os.remove(temp_output)
            except Exception as e:
                print(f"Warning: Could not remove temporary file {temp_output}: {str(e)}")

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Video Shorts Creator")
        self.processor = VideoProcessor()
        self.configure_theme()
        self.setup_ui()
        
    def configure_theme(self):
        # Configure dark theme
        self.configure(bg='#2b2b2b')
        style = ttk.Style()
        style.configure('TProgressbar', background='#007acc')
        
    def setup_ui(self):
        # Configure dark theme colors
        bg_color = '#2b2b2b'
        fg_color = '#ffffff'
        button_bg = '#007acc'
        
        # GPU status
        gpu_status = "NVIDIA GPU Acceleration Available" if self.processor.has_nvidia else "CPU Mode (No NVIDIA GPU)"
        tk.Label(self, text=gpu_status, bg=bg_color, fg='#00ff00' if self.processor.has_nvidia else '#ff9900').pack(pady=5)
        
        # File selection
        tk.Label(self, text="Top Video:", bg=bg_color, fg=fg_color).pack(pady=5)
        self.top_video_btn = tk.Button(
            self, text="Select Top Video",
            command=lambda: self.select_file('top'),
            bg=button_bg, fg=fg_color
        )
        self.top_video_btn.pack()
        
        tk.Label(self, text="Bottom Video:", bg=bg_color, fg=fg_color).pack(pady=5)
        self.bottom_video_btn = tk.Button(
            self, text="Select Bottom Video",
            command=lambda: self.select_file('bottom'),
            bg=button_bg, fg=fg_color
        )
        self.bottom_video_btn.pack()
        
        # Audio file selection (optional)
        tk.Label(self, text="Audio File (Optional):", bg=bg_color, fg=fg_color).pack(pady=5)
        self.audio_btn = tk.Button(
            self, text="Select Audio File",
            command=self.select_audio,
            bg=button_bg, fg=fg_color
        )
        self.audio_btn.pack()
        
        tk.Label(self, text="Output Directory:", bg=bg_color, fg=fg_color).pack(pady=5)
        self.output_dir_btn = tk.Button(
            self, text="Select Output Directory",
            command=self.select_output_dir,
            bg=button_bg, fg=fg_color
        )
        self.output_dir_btn.pack()
        
        # Timestamps input
        tk.Label(self, text="Enter timestamps (MM:SS-MM:SS, one per line):", bg=bg_color, fg=fg_color).pack(pady=5)
        self.timestamps_text = tk.Text(self, height=10, width=40, bg='#3c3c3c', fg=fg_color, insertbackground=fg_color)
        self.timestamps_text.pack(pady=5)
        
        # Set default timestamps (first 90 seconds in 30-second windows)
        default_timestamps = "00:00-00:30\n00:30-01:00\n01:00-01:30"
        self.timestamps_text.insert("1.0", default_timestamps)
        
        # Example timestamp
        tk.Label(self, text="Example: 00:30-01:00", bg=bg_color, fg=fg_color).pack()
        
        # Status label
        self.status_label = tk.Label(self, text="Ready", bg=bg_color, fg=fg_color)
        self.status_label.pack(pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self, orient="horizontal",
            length=300, mode="determinate"
        )
        self.progress.pack(pady=10)
        
        # Process button
        self.process_btn = tk.Button(
            self, text="Process Videos",
            command=self.process_videos,
            bg=button_bg, fg=fg_color
        )
        self.process_btn.pack(pady=10)
        
    def select_file(self, target: str):
        filename = filedialog.askopenfilename(
            filetypes=[("mp4 files", "*.mp4")]
        )
        if filename:
            if target == 'top':
                self.processor.top_video = filename
                self.top_video_btn.config(text="Top Video Selected ")
            else:
                self.processor.bottom_video = filename
                self.bottom_video_btn.config(text="Bottom Video Selected ")
    
    def select_audio(self):
        filename = filedialog.askopenfilename(
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.m4a *.aac"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("M4A files", "*.m4a"),
                ("AAC files", "*.aac")
            ]
        )
        if filename:
            self.processor.audio_file = filename
            self.audio_btn.config(text="Audio File Selected ")
                
    def select_output_dir(self):
        dirname = filedialog.askdirectory()
        if dirname:
            self.processor.output_dir = dirname
            self.output_dir_btn.config(text="Output Directory Selected ")
            
    def parse_timestamps(self) -> List[TimeSegment]:
        timestamps = []
        pattern = re.compile(r'(\d{2}:\d{2})-(\d{2}:\d{2})')
        
        for line in self.timestamps_text.get("1.0", tk.END).split('\n'):
            line = line.strip()
            if not line:
                continue
                
            match = pattern.match(line)
            if not match:
                raise ValueError(f"Invalid timestamp format: {line}\nUse MM:SS-MM:SS format (e.g., 00:30-01:00)")
                
            start = match.group(1)
            end = match.group(2)
            
            # Validate timestamps
            self.processor.convert_timestamp(start)
            self.processor.convert_timestamp(end)
            
            timestamps.append(TimeSegment(start, end))
            
        if not timestamps:
            raise ValueError("No timestamps provided")
            
        return timestamps
        
    def update_progress(self, value):
        self.progress['value'] = value
        self.update_idletasks()
        
    def check_queues(self):
        # Check progress queue
        while not self.processor.progress_queue.empty():
            progress = self.processor.progress_queue.get()
            self.update_progress(progress)
            
        # Check status queue
        while not self.processor.status_queue.empty():
            status = self.processor.status_queue.get()
            self.status_label.config(text=status)
            
        self.after(100, self.check_queues)
        
    def process_videos(self):
        try:
            timestamps = self.parse_timestamps()
            self.process_btn.config(state=tk.DISABLED)
            self.progress['value'] = 0
            self.status_label.config(text="Starting...")
            
            # Start queue checker
            self.check_queues()
            
            # Start processing in a separate thread
            def process_thread():
                try:
                    self.processor.process_videos(timestamps, self.update_progress)
                    self.after(0, lambda: self.status_label.config(text="Complete!"))
                    self.after(0, lambda: messagebox.showinfo("Success", "Video processing complete!"))
                except Exception as e:
                    self.after(0, lambda: self.status_label.config(text="Error!"))
                    self.after(0, lambda: messagebox.showerror("Error", str(e)))
                finally:
                    self.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            
            threading.Thread(target=process_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.process_btn.config(state=tk.NORMAL)
            self.progress['value'] = 0
            self.status_label.config(text="Error!")

if __name__ == "__main__":
    app = Application()
    # Check for ffmpeg before showing the window
    if check_ffmpeg():
        app.mainloop()
