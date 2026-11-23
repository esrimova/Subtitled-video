"""Small shared helpers for the web app (no network, no threads)."""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path


def ts(x):
    x = int(x)
    return "%d:%02d:%02d" % (x // 3600, x % 3600 // 60, x % 60) if x >= 3600 else "%02d:%02d" % (x // 60, x % 60)


def unique_dir(base: Path) -> Path:
    """base, or 'base (2)', 'base (3)'... so an existing result is never overwritten."""
    if not base.exists():
        return base
    n = 2
    while (base.parent / ("%s (%d)" % (base.name, n))).exists():
        n += 1
    return base.parent / ("%s (%d)" % (base.name, n))


def probe_streams(path: Path) -> set:
    """Set of stream kinds ('video', 'audio') ffprobe finds in a local file."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json",
                          str(path)], capture_output=True, text=True)
    try:
        return {s.get("codec_type") for s in json.loads(out.stdout or "{}").get("streams", [])}
    except ValueError:
        return set()


def kill_tree(pid: int) -> None:
    """Kill a process and every child it started (ffmpeg, yt-dlp, ...)."""
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)


def rmtree_retry(path: Path, tries: int = 10) -> bool:
    """Remove a folder; Windows may hold files for a moment after a kill."""
    for _ in range(tries):
        try:
            shutil.rmtree(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            time.sleep(0.3)
    return not Path(path).exists()


def render_transcript_md(title, source, language, duration, model, device, segments) -> str:
    lines = ["# %s\n" % title, "- Source: %s" % source,
             "- Language: %s" % language,
             "- Duration: %s | model: %s on %s\n" % (ts(duration), model, device), "## Transcript\n"]
    for s in segments:
        lines.append("**[%s]** %s\n" % (ts(s["start"]), re.sub(r"\s+", " ", s["text"]).strip()))
    return "\n".join(lines)
