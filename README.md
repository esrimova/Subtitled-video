# Subtitled-video

Turn any video into a searchable transcript and a captioned player, entirely on your own PC.

Paste a video link (or drop a file), and Subtitled-video downloads it, extracts the audio, transcribes the speech locally with Whisper, and builds:

- an audio file and a plain-text transcript,
- a **replay page** (`index.html`): the video on the left, the subtitles and a clickable transcript on the right, with settings for how the subtitles look.

You choose which of these to keep.

Nothing is sent to an online service for transcription. The replay page works offline.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer, on your PATH
- ffmpeg and ffprobe, on your PATH
- Internet access for the first run (to install packages and download the speech model) and to download videos from links
- About 5 GB of free disk space

The Python packages `yt-dlp` and `faster-whisper` are installed automatically the first time you run `run_web.bat`.

## Two ways to install

**Option 1 - manual**

1. Install [Python](https://www.python.org/downloads/) (tick "Add python.exe to PATH").
2. Install ffmpeg, for example: `winget install -e --id Gyan.FFmpeg`, then open a new terminal.
3. Download or clone this repository.
4. Double-click `run_web.bat`. A browser tab opens with the app.

**Option 2 - with an AI agent**

This repository includes a setup skill: [`skills/setup-subtitled-video/SKILL.md`](skills/setup-subtitled-video/SKILL.md). Give it to your coding agent and ask it to set up Subtitled-video. The agent checks what is installed on your PC, tells you what is missing, and asks whether you want it to install those things for you or guide you step by step. If the agent has no permission to run commands, it will ask you to grant it, or give you the commands to run yourself.

## How to use the app

1. Double-click `run_web.bat`. A browser tab opens with the app (keep the black window open while you use it; closing it stops the app).
2. **Paste a video link** (for example a YouTube URL) **or a file path** into the box, then click **Check**. The app looks at the video and shows its title and length.
3. **Choose what you want to save** with the checkboxes:
   - **Save video** - the video file (`video.mp4`).
   - **Save audio** - the audio of the video (`audio.wav`).
   - **Save transcript** - a timestamped text transcript (`transcript.md`).
   - **Create captioned replay** - the replay page (`index.html`) plus subtitles (`captions.srt`). It keeps the video, since the page plays it.

   A note under the checkboxes tells you what will be kept. If the video has no audio, only the video option is available.
4. **Folder name:** type the name of the folder where your files will go, or leave it blank and the app names the folder from the video title (plus the video ID when there is one, and a number if that name is already taken). Folders are created inside the `output` folder next to `run_web.bat` (for example `output\My lecture`). If that name already exists, the app asks you to choose another, so nothing is overwritten.
5. Optional: if you chose a transcript or a replay, pick the **model size**: *Faster (small)* or *More accurate (medium)*. For links, you can also pick the **video quality**.
6. Click **Start**. The app shows each stage, a progress bar, an estimated time and the transcript as it is written. **Cancel** stops it.
7. When it finishes, click **Open replay** to watch it in your browser, **Open folder** to see the files, or **New video** to start again.

The first run is slower: it downloads the speech model (and installs the Python packages).

## The replay page

Open `index.html` from the folder you created (or use **Open replay**). It works offline. To watch it later, open `index.html` from the output folder and keep `video.mp4` in that same folder; if you copy or share it, copy the whole folder.

- **Layout:** the video is on the left (68% of the width), the subtitles and the transcript on the right (28%), with a 4% gap. The proportions are percentages, so they hold at any window size or resolution.
- **Controls:**
  - **CC** shows or hides the subtitles.
  - **Speed** goes from 0.5x to 1.5x.
  - **Replay line** repeats the current subtitle line.
  - **Fullscreen** makes the whole player fullscreen. Use this button, not the video's own one, so the subtitles stay visible.
  - Click any line of the transcript to jump to that moment.
- **Subtitle settings:** click **Settings** to change the subtitles live:
  - **Font** (system default, serif, monospace, sans-serif, comic)
  - **Text color** and **text size** (12 to 48 px)
  - **Background color** and **background brightness** (20% to 200%)
  - **Bold** and **italic**
  - **Reset** returns to the defaults.

  Your choices are saved in your browser and applied the next time you open any replay page. They also apply in fullscreen.

## Try it with free videos

These are examples of places with free tech videos you can paste into the app. They are only suggestions, and each video has its own terms.

- [freeCodeCamp on YouTube](https://www.youtube.com/@freecodecamp) - long programming courses
- [MIT OpenCourseWare](https://ocw.mit.edu/) - free university lectures, including computer science

## Run the tests

```
python -I -m unittest discover -s app/tests
```

The browser check for the replay page needs Node.js 22+ and Chrome:

```
node app/tests/replay_e2e.js <path-to-a-generated-index.html> <path-to-chrome.exe> <empty-profile-folder>
```

## License

MIT - see [LICENSE](LICENSE).
