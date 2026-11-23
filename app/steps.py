import os

CANONICAL = ["video", "audio", "transcript", "replay"]
# Biggest video that can go inside the single-file replay (AE_EMBED_LIMIT lets tests shrink it).
EMBED_LIMIT = int(os.environ.get("AE_EMBED_LIMIT") or 200 * 1024 * 1024)


def too_big_message(size_bytes: int) -> str:
    return ("This video is %d MB, over the %d MB limit for a captioned replay that is a single HTML file. "
            "Tick Save video as well to keep a separate copy that the replay plays from, or pick a lower video quality."
            % (round(size_bytes / 1_048_576), EMBED_LIMIT // 1_048_576))


def resolve_outputs(selected: set[str], no_audio: bool, kind: str) -> dict:
    if not selected:
        raise ValueError("selected is empty")
    if kind not in ("url", "file"):
        raise ValueError("kind must be 'url' or 'file'")
    for s in selected:
        if s not in CANONICAL:
            raise ValueError(f"unknown output id: {s}")

    if no_audio:
        forbidden = {"audio", "transcript", "replay"}
        if selected & forbidden:
            raise ValueError("no_audio conflicts with audio/transcript/replay")

    keep = [x for x in CANONICAL if x in selected]

    video_needed = "video" in selected or "replay" in selected

    audio_needed = "transcript" in selected or "replay" in selected
    temporary = []
    if audio_needed and "audio" not in selected:
        temporary.append("audio")
    if "replay" in selected and "video" not in selected:
        temporary.append("video")

    pipeline = []
    if kind == "url":
        pipeline.append("download")
    if audio_needed or "audio" in selected:
        pipeline.append("audio")
    if "transcript" in selected or "replay" in selected:
        pipeline.append("transcribe")
    if "replay" in selected:
        pipeline.append("captions")

    audio_only_download = kind == "url" and not video_needed

    notes = []
    if "replay" in selected and "video" not in selected:
        notes.append("The captioned replay is a single HTML file with the video inside it, so no separate video file is kept. Videos over 200 MB don't fit inside the page: tick Save video too to keep a separate copy.")
    if temporary == ["audio"]:
        notes.append("The audio is processed temporarily and not kept.")

    return {
        "keep": keep,
        "temporary": temporary,
        "pipeline": pipeline,
        "audio_only_download": audio_only_download,
        "notes": notes,
        "video_needed": video_needed,
    }


def estimate_eta(fraction: float, elapsed: float) -> int | None:
    if fraction <= 0 or fraction < 0.10 or elapsed < 5:
        return None
    fraction = min(fraction, 1.0)
    return int(round(elapsed * (1 - fraction) / fraction))