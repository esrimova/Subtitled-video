---
name: setup-subtitled-video
description: Check which prerequisites for Subtitled-video are installed on this Windows PC, report what is missing, and (with the user's consent) install it or guide the user through it. Use when the user wants to install, set up or troubleshoot Subtitled-video.
---

# Set up Subtitled-video (Windows)

Goal: make sure this computer can run Subtitled-video, without installing anything the user has not approved.

## Rules
- Windows only. Work from the repository folder.
- Do NOT run `run_web.bat` or `run.bat` while checking: they install packages automatically on first start.
- Check first, report, ask, and only then install.

## Step 1 - Check (read-only)
Run each command separately so you can say exactly which one fails:

1. `python --version` (need 3.10 or newer)
2. `python -I -c "import yt_dlp"`
3. `python -I -c "import faster_whisper"`
4. `ffmpeg -version`
5. `ffprobe -version`
6. Free disk space on the drive of the repository: about 5 GB is comfortable (speech models are downloaded on first use).

If you cannot run commands (no permission or no shell), do not guess. Offer the user two options:
- grant you permission to run these read-only checks, or
- run the commands above themselves in PowerShell and paste the output back.

## Step 2 - Report
List what is installed (with versions) and what is missing.

## Step 3 - Ask
If nothing is missing, skip to step 5. Otherwise, if you have permission to install, ask the user to choose:
- **Install for me**: you install the missing pieces, or
- **Guide me**: you explain each step and wait for the user to do it.

Install nothing before the user answers.

## Step 4 - Install the missing pieces
- Python: `winget install -e --id Python.Python.3.12` (or download from python.org and tick "Add python.exe to PATH"). Open a new terminal afterwards.
- yt-dlp and faster-whisper: `python -m pip install yt-dlp faster-whisper`
- ffmpeg and ffprobe: `winget install -e --id Gyan.FFmpeg` (open a new terminal afterwards so PATH updates).

## Step 5 - Re-check and finish
Repeat step 1. When everything passes, tell the user to start the app with `run_web.bat` (double-click it or run it from the repository folder). A browser tab opens automatically.
