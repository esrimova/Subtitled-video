"""Audio extractor: video link or file -> folder with video, audio and timestamped transcript.

Usage: python extract.py <url-or-file> [--model small|medium] [--no-open]
No AI assistant is involved: yt-dlp downloads, ffmpeg extracts audio, faster-whisper
transcribes locally.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

def _add_nvidia_dlls():
    """pip's nvidia-cublas/cudnn packages put DLLs under site-packages\\nvidia\\*\\bin;
    Windows won't find them unless those folders are on the DLL search path."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("nvidia")
        roots = list(spec.submodule_search_locations) if spec else []
    except Exception:
        roots = []
    for root in roots:
        for b in Path(root).glob("*/bin"):
            os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(str(b))
            except (OSError, AttributeError):
                pass


_add_nvidia_dlls()

HERE = Path(__file__).resolve().parent
OUT_ROOT = HERE / "output"
COOKIES = HERE / "cookies.txt"  # optional: Netscape-format export from Chrome


def slug(text, limit=60):
    text = re.sub(r"[^\w\- ]+", "", text, flags=re.UNICODE).strip()
    return re.sub(r"\s+", "_", text)[:limit] or "video"


def custom_folder(name):
    """Folder chosen by the user: keep spaces and accents, strip only characters Windows forbids."""
    if not name:
        return None
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f﻿]', "", name).strip().rstrip(".")
    return OUT_ROOT / clean if clean else None


def ts(x):
    return "%02d:%02d" % (int(x // 60), int(x % 60)) if x < 3600 else "%d:%02d:%02d" % (
        int(x // 3600), int(x % 3600 // 60), int(x % 60))


CHECK_DEADLINE = 60  # seconds the whole link check may take


def to_seconds(value):
    """Duration as float seconds; 0 when the source doesn't say ('N/A', None, junk)."""
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return 0.0


class InputRejected(Exception):
    """The input can't be processed; the reason was already shown to the user."""


def fail(msg):
    """Stop right away with a plain explanation, so the user never waits on a doomed run."""
    print("\n" + "=" * 60)
    print("CANNOT PROCESS THIS: " + msg)
    print("=" * 60)
    raise InputRejected(msg)


def ydl_opts():
    opts = {"quiet": True, "no_warnings": True, "noprogress": True,
            "socket_timeout": 20, "retries": 2}  # a silent site fails in seconds, not minutes
    if COOKIES.exists():
        opts["cookiefile"] = str(COOKIES)
    return opts


def preflight(source):
    """First thing we do: decide whether this input can be processed at all.
    Returns a dict: kind, target, title, duration, info, no_audio (flagged, not rejected)."""
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fail("%s is not installed or not on PATH, so audio can't be extracted." % tool)

    path = Path(source.strip('"'))
    if path.exists():
        if not path.is_file():
            fail("That path is a folder, not a video file.")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_type:format=duration,format_name", "-of", "json", str(path)],
            capture_output=True, text=True)
        try:
            data = json.loads(probe.stdout or "{}")
        except ValueError:
            data = {}
        if probe.returncode != 0 or "format" not in data:
            fail("This file isn't a media file ffmpeg can read: %s" % path.name)
        kinds = {s.get("codec_type") for s in data.get("streams", [])}
        fmt = data["format"].get("format_name", "")
        if "image2" in fmt or fmt.endswith("_pipe") or "video" not in kinds and "audio" not in kinds:
            fail("This is an image or has no video/audio, not a video: %s" % path.name)
        return {"kind": "file", "target": path, "title": path.stem, "info": None,
                "duration": to_seconds(data["format"].get("duration")),
                "no_audio": "audio" not in kinds}

    if not re.match(r"https?://", source.strip(), re.I):
        fail("That isn't a web link (it must start with http:// or https://) "
             "and no file exists at that path:\n  %s" % source)

    import yt_dlp
    box = {}

    def probe_link():
        try:
            with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
                box["info"] = ydl.extract_info(source.strip(), download=False)
        except Exception as err:
            box["err"] = err

    # Hard deadline for the whole check, whatever the individual network timeouts add up to.
    worker = threading.Thread(target=probe_link, daemon=True)
    worker.start()
    worker.join(CHECK_DEADLINE)
    if worker.is_alive():
        fail("The site didn't answer within %d seconds. Check your connection or try again later."
             % CHECK_DEADLINE)
    try:
        if "err" in box:
            raise box["err"]
        info = box["info"]
    except InputRejected:
        raise
    except Exception as e:
        text = re.sub(r"\x1b\[[0-9;]*m", "", str(e))
        low = text.lower()
        if any(k in low for k in ("getaddrinfo", "failed to resolve", "timed out",
                                  "connection", "network is unreachable")):
            fail("Couldn't reach the site. Check your internet connection and the link, then try again.")
        if "unsupported url" in low:
            fail("yt-dlp doesn't support this site or page. Try the direct link to a single video.")
        if any(k in low for k in ("login", "cookies", "empty media response", "private",
                                  "sign in", "not available")):
            fail("The site wouldn't give the video without a login (or it's private/removed).\n"
                 "  Fix: export your browser cookies to a cookies.txt in the project folder.\n"
                 "  Details: " + text.splitlines()[0][:200])
        if "drm" in low:
            fail("This video is DRM-protected and can't be downloaded.")
        fail("Couldn't read this link: " + text.splitlines()[0][:300])
    if info.get("_type") == "playlist" or info.get("entries"):
        fail("This link is a playlist/profile, not a single video. Paste the link to one video.")
    if info.get("is_live"):
        fail("This is a live stream that hasn't ended; there's no finished video to transcribe.")
    formats = info.get("formats") or []
    # No audio only when every format explicitly says so (None means unknown, so assume audio).
    return {"kind": "url", "target": source.strip(), "info": info,
            "title": info.get("title") or info.get("id") or "video",
            "duration": to_seconds(info.get("duration")),
            "no_audio": bool(formats) and all(f.get("acodec") == "none" for f in formats)}


def download(url, folder=None, info=None):
    import yt_dlp

    opts = ydl_opts()
    if info is None:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    title = info.get("title") or info.get("id") or "video"
    folder = folder or OUT_ROOT / (slug(title) + "_" + str(info.get("id", "")))
    folder.mkdir(parents=True, exist_ok=True)
    opts.update({"outtmpl": str(folder / "video.%(ext)s"), "merge_output_format": "mp4"})
    for old in folder.glob("video.*"):  # stale files from an earlier or failed run
        old.unlink()
    print("Downloading: %s" % title)
    with yt_dlp.YoutubeDL(opts) as ydl:
        done = ydl.extract_info(url, download=True)
    video = Path(done["requested_downloads"][0]["filepath"])
    return folder, video, title


def local(path, folder=None):
    src = Path(path.strip('"')).resolve()
    # Hash of the full path keeps two different "clip.mp4" files in separate folders.
    key = hashlib.md5(str(src).lower().encode("utf-8")).hexdigest()[:8]
    folder = folder or OUT_ROOT / (slug(src.stem) + "_" + key)
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / ("video" + src.suffix)
    if not video.exists() or video.stat().st_size != src.stat().st_size:
        shutil.copy2(src, video)
    return folder, video, src.stem


def extract_audio(video, folder):
    wav = folder / "audio.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1",
                    "-ar", "16000", str(wav)], check=True)
    return wav


def transcribe(wav, model_name):
    import numpy as np
    from faster_whisper import WhisperModel

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "f32le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)

    def run(device, ctype):
        model = WhisperModel(model_name, device=device, compute_type=ctype)
        segs, info = model.transcribe(audio, vad_filter=True)
        return list(segs), info

    try:
        segs, info = run("cuda", "int8_float16")
        device = "cuda"
    except Exception as e:  # missing CUDA libs etc.
        print("GPU not available (%s); using CPU." % str(e)[:80])
        segs, info = run("cpu", "int8")
        device = "cpu"
    return segs, info, device


def has_audio(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                          "stream=codec_type", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    return "audio" in out.stdout


def confirm(question):
    """Yes/no prompt; anything but y/yes/s/si (or end of input) means no."""
    return input(question).strip().lower() in ("y", "yes", "s", "si", "sí")


def reserve_folder(name):
    """Create the user's chosen folder; refuse if the name is taken. Returns Path or None (auto)."""
    wanted = custom_folder(name)
    if not wanted:
        return None
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    wanted.mkdir(exist_ok=False)  # atomic: raises FileExistsError if already there
    return wanted


def ask_folder():
    """Prompt until the user gives a free name, or presses Enter for automatic naming."""
    while True:
        name = input("Folder name (press Enter for automatic): ")
        try:
            return reserve_folder(name)
        except FileExistsError:
            print('A folder named "%s" already exists. Please choose another name.' % name.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--name", default=None,
                    help="output folder name (default: ask; empty string = automatic)")
    a = ap.parse_args()

    try:
        asked = not a.source
        while True:
            if not a.source:
                a.source = input("Paste the video link (or a video file path) and press Enter: ").strip()
            if not a.source:
                return
            print("Checking video...")
            try:
                a.check = preflight(a.source)
                if a.check["no_audio"]:
                    print("\n*** WARNING: this video has NO AUDIO track, so there is nothing to transcribe. ***")
                    if not confirm("Save the video anyway (without a transcript)? [y/N]: "):
                        raise InputRejected("declined")
                break
            except InputRejected:
                if not asked:  # source came from the command line / drag-and-drop
                    sys.exit(2)
                print("Try another link or file.\n")
                a.source = None
        c = a.check
        if c["no_audio"]:
            print("OK: %s. Only the video will be saved.\n" % c["title"])
        elif c["duration"] > 0:
            print("OK: %s (%s). Roughly %s of processing expected.\n" % (
                c["title"], ts(c["duration"]), ts(max(c["duration"], 10))))
        else:
            print("OK: %s (duration unknown). Processing time can't be estimated.\n" % c["title"])
        if a.name is None:
            chosen = ask_folder()
        else:
            try:
                chosen = reserve_folder(a.name)
            except FileExistsError:
                print('A folder named "%s" already exists. Choose another name.' % a.name)
                sys.exit(3)
    except EOFError:
        print("\nCancelled (no input).")
        sys.exit(130)

    try:
        process(a, chosen)
    except BaseException:
        # Free the reserved name if the run left nothing behind, so the user can retry it.
        if chosen and chosen.is_dir() and not any(chosen.iterdir()):
            chosen.rmdir()
        raise


def process(a, chosen):
    t0 = time.time()
    c = a.check
    if c["kind"] == "file":
        folder, video, title = local(a.source, chosen)
    else:
        folder, video, title = download(c["target"], chosen, c["info"])
    if not c["no_audio"] and not has_audio(video):
        # The site didn't say, but the saved file has no audio track.
        print("\n*** WARNING: the downloaded file has NO AUDIO track. ***")
        if not confirm("Keep the video anyway (without a transcript)? [y/N]: "):
            video.unlink(missing_ok=True)
            if not any(folder.iterdir()):
                folder.rmdir()
            print("Nothing saved.")
            sys.exit(2)
        c["no_audio"] = True
    if c["no_audio"]:
        print("\nDone (video only, nothing to transcribe): %s" % folder)
        if not a.no_open:
            os.startfile(folder)
        return
    print("Extracting audio...")
    wav = extract_audio(video, folder)
    print("Transcribing (%s model)..." % a.model)
    segs, info, device = transcribe(wav, a.model)

    lines = ["# %s\n" % title,
             "- Source: %s" % a.source,
             "- Language: %s (%.0f%%)" % (info.language, info.language_probability * 100),
             "- Duration: %s | model: %s on %s | processed in %.0fs\n" % (
                 ts(info.duration), a.model, device, time.time() - t0),
             "## Transcript\n"]
    for s in segs:
        lines.append("**[%s]** %s\n" % (ts(s.start), s.text.strip()))
    folder.mkdir(parents=True, exist_ok=True)  # survive the folder being removed mid-run
    (folder / "transcript.md").write_text("\n".join(lines), encoding="utf-8")

    print("\nDone: %s" % folder)
    if not a.no_open:
        os.startfile(folder)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("\nERROR: %s" % e)
        sys.exit(1)
