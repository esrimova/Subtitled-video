"""One job, in its own process. Prints '@@EVT {json}' lines; the server relays them to the page.

Usage: python -I -X utf8 worker.py job.json
The server kills this whole process tree on Cancel, so nothing here needs signal handling.
"""
import ctypes
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import extract  # noqa: E402  (adds the NVIDIA DLL folders to the search path as a side effect)
import core  # noqa: E402
import quality  # noqa: E402
import replay  # noqa: E402
import steps  # noqa: E402
import subtitles  # noqa: E402



def emit(**ev):
    # leading newline: other libraries may leave a partial line (e.g. a progress bar) on stdout
    print("\n@@EVT " + json.dumps(ev, ensure_ascii=False), flush=True)


def stage(name, percent, message, eta=None):
    emit(type="stage", stage=name, percent=round(percent, 1), message=message, eta_seconds=eta)


def watch_parent(ppid):
    """If the server dies (window closed), do not leave ffmpeg/whisper running."""
    def alive():
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, ppid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE

    def loop():
        while True:
            time.sleep(2)
            if not alive():
                core.kill_tree(os.getpid())

    threading.Thread(target=loop, daemon=True).start()


def download(job, stg):
    import yt_dlp
    audio_only = job["plan"]["audio_only_download"]
    fmt = quality.format_selector(job.get("quality", "best"), audio_only)
    streams = 2 if "+" in fmt else 1
    state = {"idx": -1, "file": None, "last": 0.0, "t0": time.time()}

    def hook(d):
        if d.get("status") != "downloading":
            return
        if d.get("filename") != state["file"]:
            state["file"], state["idx"] = d.get("filename"), state["idx"] + 1
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        part = (d.get("downloaded_bytes") or 0) / total if total else 0
        frac = min((state["idx"] + part) / streams, 1.0)
        now = time.time()
        if now - state["last"] < 0.4:
            return
        state["last"] = now
        stage("download", frac * 100, "Downloading…", steps.estimate_eta(frac, now - state["t0"]))

    opts = extract.ydl_opts()
    opts.update({"format": fmt, "outtmpl": str(stg / "download.%(ext)s"), "merge_output_format": "mp4",
                 "progress_hooks": [hook]})
    if not audio_only:
        opts["format_sort"] = quality.format_sort(job.get("quality", "best"))  # e.g. ["res:720"]
    stage("download", 0, "Starting download…")
    with yt_dlp.YoutubeDL(opts) as ydl:
        done = ydl.extract_info(job["target"], download=True)
    stage("download", 100, "Download finished")
    return Path(done["requested_downloads"][0]["filepath"])


def make_audio(media, stg, duration):
    wav = stg / "audio.wav"
    stage("audio", 0, "Extracting audio…")
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(media), "-vn", "-ac", "1",
                             "-ar", "16000", "-progress", "pipe:1", str(wav)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    t0 = time.time()
    for line in proc.stdout:
        if line.startswith("out_time_ms=") and duration > 0:
            try:
                frac = min(int(line.split("=")[1]) / 1e6 / duration, 1.0)
            except ValueError:
                continue
            stage("audio", frac * 100, "Extracting audio…", steps.estimate_eta(frac, time.time() - t0))
    err = proc.stderr.read()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg could not extract the audio: " + err.strip()[-300:])
    stage("audio", 100, "Audio ready")
    return wav


def transcribe(wav, model_name, duration):
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(wav), "-f", "f32le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    total = duration or len(audio) / 16000

    def run(device, ctype):
        stage("transcribe", 0, "Loading speech model (%s)…" % device)
        model = WhisperModel(model_name, device=device, compute_type=ctype)
        segs_iter, info = model.transcribe(audio, vad_filter=True)
        t0, out = time.time(), []
        stage("transcribe", 0, "Transcribing…")
        for s in segs_iter:
            seg = {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
            out.append(seg)
            emit(type="segment", **seg)
            frac = min(seg["end"] / total, 1.0) if total else 0
            stage("transcribe", frac * 100, "Transcribing…", steps.estimate_eta(frac, time.time() - t0))
        return out, info, device

    try:
        return run("cuda", "int8_float16")
    except Exception as e:  # missing CUDA libraries, out of memory...
        if "cuda" not in str(e).lower() and "cublas" not in str(e).lower() and "cudnn" not in str(e).lower():
            raise
        return run("cpu", "int8")


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    watch_parent(job["parent_pid"])
    stg = Path(job["staging"])
    stg.mkdir(parents=True, exist_ok=True)
    plan, keep, pipe = job["plan"], job["plan"]["keep"], job["plan"]["pipeline"]
    media = Path(job["target"]) if job["kind"] == "file" else download(job, stg)
    duration = job.get("duration") or 0

    if "replay" in keep and "video" not in keep and media.stat().st_size > steps.EMBED_LIMIT:
        raise RuntimeError(steps.too_big_message(media.stat().st_size))  # before any slow work

    wav = make_audio(media, stg, duration) if "audio" in pipe else None
    segments, info, device, lang = [], None, "", ""
    if "transcribe" in pipe:
        segments, info, device = transcribe(wav, job["model"], duration)
        lang = "%s (%.0f%%)" % (info.language, info.language_probability * 100)
        duration = duration or info.duration

    files = []
    notice = ""
    video_dest = None
    if "video" in keep:
        video_dest = stg / ("video" + media.suffix)
        if job["kind"] == "file":
            shutil.copy2(media, video_dest)
        else:
            media.replace(video_dest)
        files.append(video_dest.name)
    if "audio" in keep:
        files.append(wav.name)
    if "transcript" in keep:
        (stg / "transcript.md").write_text(core.render_transcript_md(
            job["title"], job["source"], lang, duration, job["model"], device, segments), encoding="utf-8")
        files.append("transcript.md")
    if "replay" in keep:
        stage("captions", 0, "Building captions…")
        embed = (video_dest if video_dest else media).stat().st_size <= steps.EMBED_LIMIT
        video_name = video_dest.name if "video" in keep else ""
        if "video" in keep and not embed:
            notice = "The video is over %d MB, so the replay plays from the saved video file. Keep both files together." % (steps.EMBED_LIMIT // 1_048_576)
        # When embed=True and "video" not in keep, video_name stays "" and we read from media
        read_from = video_dest if video_dest else media
        replay.write_replay(stg / "index.html", job["title"], read_from, segments, embed, video_name)
        files.append("index.html")
        stage("captions", 100, "Captions ready")

    # Publish with ONE rename so the result is either completely there or not there at all
    # (a Cancel landing mid-way can never leave a half-filled folder).
    for entry in list(stg.iterdir()):
        if entry.name not in files:
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()  # temporary audio, job.json, ...
    final = Path(job["final_dir"])
    os.rename(stg, final)  # fails if the folder already exists, so nothing is ever overwritten or merged
    emit(type="done", folder=str(final), files=files,
         replay_url=("/files/%s/index.html" % quote(final.name)) if "replay" in keep else "",
         notice=notice)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        emit(type="error", message=str(e)[:500])
        sys.exit(1)
