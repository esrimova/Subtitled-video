# Subtitled-video

Turn any video into a searchable transcript and a captioned player, entirely on your own PC.

Paste a video link (or drop a file), and Subtitled-video downloads it, extracts the audio, transcribes the speech locally with Whisper, and builds:

- an audio file and a plain-text transcript,
- a **replay page** (`index.html`): the video on the left, the subtitles and a clickable transcript on the right.

Nothing is sent to an online service for transcription. The replay page works offline.

## The replay page

- **Layout:** the video takes 68% of the width, subtitles 28%, with a 4% gap. Everything is in percentages, so the proportions hold at any window size or resolution.
- **Fullscreen with subtitles:** use the **Fullscreen** button (not the video's own one) so the subtitles stay visible.
- **CC** toggles the subtitles, **Replay line** repeats the current line, and a speed menu goes from 0.5x to 1.5x. Click any line of the transcript to jump to it.
- **Settings:** font, text color, text size, background color, background brightness, bold and italic. They are remembered in your browser.

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
