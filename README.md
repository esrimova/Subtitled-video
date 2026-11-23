# Subtitled-video

Turn any video into a transcript and a captioned player, entirely on your own PC.

Give it a video link or a video file on your computer. It downloads the video (for links), extracts the audio, transcribes the speech locally with Whisper, and saves whichever of these you choose:

- the **video**,
- the **audio** (`audio.wav`),
- a timestamped **transcript** (`transcript.md`),
- a **captioned replay** (`index.html` + `captions.srt`): a web page with the video on the left, and the subtitles and a clickable transcript on the right. You can change how the subtitles look.

The speech is transcribed on your PC, not sent to an online service. The language is detected automatically. A graphics card (NVIDIA/CUDA) is used when available, otherwise the processor.

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

1. Double-click `run_web.bat`. A browser tab opens with the app. Keep the black window open while you use it: closing it stops the app. (If the tab doesn't open, copy the address shown in the black window into your browser.)
2. **Video source:** paste a video link (it must start with `http://` or `https://`, and it must be one single video, not a playlist or channel) or the full path to a video file on your PC, for example `C:\Videos\lesson.mp4`. Click **Check** (or press Enter).
3. **Check** validates the source before anything is downloaded or processed: your tools are installed, a file is readable media, a link points to a single finished video the app can reach, and what the video contains (audio, video, available resolutions) decides which options you can pick next. The details are in [What the app checks](#what-the-app-checks). If the source passes, the app shows its **title**, whether it is a **Link** or a **File**, and its **length** ("Length unknown" when the source doesn't say). If it fails, you get a plain explanation and can try another source. Checking a link can take up to a minute.
4. **Choose what to save.** You can tick more than one. **Save video** is ticked by default, and **Start** stays disabled until at least one box is ticked.

   | Option | What you get |
   | --- | --- |
   | **Save video** | The video, saved as `video.*` (usually `video.mp4` for links; a copy of your file keeps its own extension) |
   | **Save audio** | `audio.wav` |
   | **Save transcript** | `transcript.md`: the title, source, detected language, length, and every line with its time |
   | **Create captioned replay** | `index.html` and `captions.srt` (standard subtitle file). The replay needs the video, so it is kept too |

   A note under the boxes says what will be kept. If you pick only a transcript or the replay, the audio is used temporarily and then deleted. Options that don't apply are greyed out with a reason: a video with no audio track can only be saved as a video, and an audio-only file can't be saved as a video or a replay.
5. **Folder name:** type a name, for example `My lesson`, or leave it blank and the app names the folder from the video title (plus the video ID for links, and a number if that name is taken). Folders are created inside the `output` folder next to `run_web.bat`, for example `output\My lesson`. If a folder with the name you typed already exists, the app asks you to choose another one: it never overwrites anything.
6. **Video quality (resolution):** for links, when you are saving the video or the replay, a menu lets you choose the resolution. The first choice is **Best available** (it shows the tallest resolution), followed by each available resolution, such as `1080p (~250 MB)` or `720p`, with an approximate download size when the site reports it. A lower resolution downloads faster and uses less disk space. If the site offers a single quality, the menu is disabled and says so. If you save only audio or a transcript from a link, only the audio is downloaded and no quality is needed.
7. **Model size:** shown when you choose a transcript or a replay. **More accurate (medium)** is the default; **Faster (small)** finishes sooner with less accuracy. The first time you use each one, the model is downloaded.
8. Click **Start**. The app shows the steps (Downloading, Extracting audio, Transcribing, Building captions), a progress bar, an estimated time left, and the transcript as it appears. Only one video can be processed at a time. **Cancel** stops the job and leaves no half-finished folder. If you reload the page while a job is running, it reconnects to it.
9. When it finishes, you see the list of files saved. Click **Open replay** to watch the captioned video in your browser, **Open folder** to see the files in Explorer, or **New video** to start another one. If something stops the job, the app tells you why and offers **Retry**, which takes you back to the source box with your previous link or path still filled in.

### What the app checks

Everything is checked before any work starts, so you never wait on something that can't succeed.

**When you click Check**

- **Tools:** ffmpeg and ffprobe must be installed and on your PATH.
- **Local file:** the path must be a file (not a folder) that ffmpeg can read, and it must contain video or audio. Images and other non-media files are rejected. The app notes whether the file has an audio track and whether it has a video track.
- **Link:** it must start with `http://` or `https://`. Anything else that isn't an existing file is rejected. The site must answer within 60 seconds. The app also rejects:
  - a link that can't be reached (check your connection and the link),
  - a site or page the downloader doesn't support (paste the direct link to one video),
  - a playlist or channel (paste one video instead),
  - a live stream that hasn't ended,
  - a video protected by DRM,
  - a private or removed video, or one that needs you to be logged in. For those, export your browser cookies to a file named `cookies.txt` (Netscape format) in the project folder (next to `run_web.bat`) and check again.
- **No audio track:** the app warns you, and disables Save audio, Save transcript and Create captioned replay, since there is nothing to transcribe. An audio-only file can't be saved as a video or a replay.

**While you choose options**

- You must tick at least one output before **Start** is enabled.
- The app works out what each combination needs (for example, that the replay keeps the video) and tells you in the note under the boxes.

**When you click Start**

- Only one job can run at a time (a second tab or a second click is refused).
- An unrecognized model size falls back to **medium**, and an invalid video quality value is rejected.
- A **blank folder name** means automatic naming. If you type a name, characters Windows doesn't allow in folder names (such as `< > : " / \ | ? *`) are removed; if nothing is left after that, the name is rejected as not valid, and a name that already exists is rejected so nothing is ever overwritten.

**While it runs**

- If audio extraction or transcription fails, the app stops and shows the reason, then offers **Retry**.
- If your graphics card can't be used for transcription, the app switches to the processor automatically.
- **Cancel** stops the job and removes the unfinished work. Results are saved in one final step, so you never get a half-filled folder. If the result had already been saved when you cancelled, the app keeps it and tells you.
- If you close the black window, any running job is stopped.

**Privacy and security of the app itself**

- The app only listens on your own computer (127.0.0.1) and only accepts requests carrying a random access code created at each start, so other programs and websites can't drive it.

### Command-line version

`run.bat` is a simpler text-window version. It asks for a video link or file path and for a folder name (Enter for automatic), then saves the video, the audio and a transcript (when the video has audio). You can also drag a video file onto `run.bat`. The resolution menu and the captioned replay are only in the browser app (`run_web.bat`).

## Watch and customize your replay

Click **Open replay** when the job finishes, or open `index.html` from your output folder later. The page works offline. Keep `index.html` and the `video.*` file in the same folder; if you copy or share it, copy the whole folder.

- **Layout:** the video is on the left (68% of the width), the subtitles and transcript panel on the right (28%), with a 4% gap. These are percentages, so the proportions hold at any window size or screen resolution.
- **CC** shows or hides the current subtitle (on by default). The clickable transcript stays visible either way.
- **Fullscreen** takes the video and the subtitles fullscreen together, so the subtitles stay visible with CC on. Use this button rather than the video's own fullscreen button. Press **Esc** to exit.
- **Speed** plays at 0.5x, 0.75x, 1x, 1.25x or 1.5x.
- **Replay line** jumps back to the start of the current line and plays it again.
- Click any **transcript line** to jump to that moment. The line being spoken is highlighted.
- **Settings** changes how the subtitles look, immediately:
  - **Font**: system default, serif, monospace, sans-serif or comic
  - **Text color** and **text size** (12 to 48 px)
  - **Background color** and **background brightness** (20% to 200%)
  - **Bold** and **italic**
  - **Reset** restores the defaults

  Font, color, size, bold and italic apply to both the current subtitle and the transcript lines. Background color and brightness apply to the current subtitle. Changes also apply in fullscreen.

  Your choices are saved in your browser and used the next time you open a replay. If your browser blocks storage, the defaults are used. A replay opened from `output\...\index.html` on disk and one opened with **Open replay** may keep separate settings, because browsers store them per address.

## Try it with free videos

These are examples of places with free tech videos you can paste into the app. They are only suggestions, and each video has its own terms. Pick a single video, not a whole channel or playlist.

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
