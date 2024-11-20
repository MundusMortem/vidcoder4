# Vidcoder4 Installation and Operation Guide

*Note: If you wishe to use the .exe version, it could be flagged as a virus. However, you can ignore the python installation requirements.
*FFmpeg must still be installed according to the provided instructions.

## Table of Contents

* [Overview](#overview)
* [Installation](#installation)
  * [Python Installation](#python-installation)
  * [FFmpeg Installation](#ffmpeg-installation)
  * [Python Dependencies](#python-dependencies)
* [Operation](#operation)
  * [Input Requirements](#input-requirements)
  * [Using the Application](#using-the-application)
  * [GPU Acceleration](#gpu-acceleration)
* [Troubleshooting](#troubleshooting)

## Overview

Vidcoder4 is a video processing tool that allows you to:
- Combine two videos vertically (stacked)
- Add optional background audio
- Create multiple video segments based on timestamps
- Utilize GPU acceleration (if NVIDIA GPU is available)

## Installation

### Python Installation

1. Download Python 3.x from [python.org](https://www.python.org/downloads/)
2. During installation, ensure you check "Add Python to PATH"
3. Verify installation by opening Command Prompt and typing:
   ```
   python --version
   ```

### FFmpeg Installation

1. Download FFmpeg from [https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip](https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip)
2. Extract the zip file
3. Copy all .exe files from the bin folder to C:\Windows\System32
4. Verify installation by opening Command Prompt and typing:
   ```
   ffmpeg -version
   ```

### Python Dependencies

Install required Python packages by opening Command Prompt and running:
```
pip install ffmpeg-python
```
Note: tkinter comes pre-installed with Python.

## Operation

### Input Requirements

- **Video Files:**
  - Must be MP4 format
  - Both top and bottom videos should have similar dimensions
  - Videos should be in landscape orientation for best results

- **Audio Files (Optional):**
  - Supported formats: MP3, WAV, M4A, or AAC
  - Will replace original video audio if provided

### Using the Application

1. Launch the application by running:
   ```
   python vidcoder4.py
   ```

2. The main window will show:
   - GPU acceleration status (if available)
   - File selection buttons
   - Timestamp input area

3. Select Input Files:
   - Click "Select Top Video" to choose the upper video
   - Click "Select Bottom Video" to choose the lower video
   - Optionally, click "Select Audio File" to add background audio
   - Choose an output directory for the processed videos

4. Enter Timestamps:
   - Use MM:SS-MM:SS format (e.g., 00:30-01:00)
   - One timestamp range per line
   - Default timestamps are provided (00:00-00:30, 00:30-01:00, 01:00-01:30)
   - Each timestamp creates a separate output video segment

5. Click "Process Videos" to start processing
   - Progress bar will show completion status
   - Status updates appear below the progress bar
   - Wait for "Complete!" message

### GPU Acceleration

- The application automatically detects NVIDIA GPU availability
- If an NVIDIA GPU is present, hardware acceleration will be used
- GPU status is displayed at the top of the application window
- CPU mode is used automatically if no NVIDIA GPU is detected

## Troubleshooting

Common issues and solutions:

1. **"FFmpeg Not Found" Error:**
   - Ensure FFmpeg is properly installed in C:\Windows\System32
   - Restart the application after installing FFmpeg
   - Verify FFmpeg installation in Command Prompt

2. **"Invalid timestamp format" Error:**
   - Ensure timestamps are in MM:SS-MM:SS format
   - Minutes and seconds must be two digits (e.g., 01:05)
   - Seconds must be less than 60

3. **"Video processing failed" Error:**
   - Verify input videos are valid MP4 files
   - Ensure sufficient disk space in output directory
   - Check if input videos are corrupted

4. **Performance Issues:**
   - Close other resource-intensive applications
   - Use GPU acceleration if available
   - Process shorter video segments if experiencing memory issues

5. **Audio Sync Issues:**
   - Ensure input videos have consistent frame rates
   - Try processing without external audio first
   - Verify audio file is in a supported format
