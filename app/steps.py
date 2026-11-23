CANONICAL = ["video", "audio", "transcript", "replay"]


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

    keep_set = set(selected)
    if "replay" in keep_set:
        keep_set.add("video")

    keep = [x for x in CANONICAL if x in keep_set]

    audio_needed = "transcript" in keep_set or "replay" in keep_set
    if audio_needed and "audio" not in keep_set:
        temporary = ["audio"]
    else:
        temporary = []

    pipeline = []
    if kind == "url":
        pipeline.append("download")
    if audio_needed or "audio" in keep_set:
        pipeline.append("audio")
    if "transcript" in keep_set or "replay" in keep_set:
        pipeline.append("transcribe")
    if "replay" in keep_set:
        pipeline.append("captions")

    audio_only_download = kind == "url" and "video" not in keep_set

    notes = []
    if "replay" in selected and "video" not in selected:
        notes.append("Captioned replay keeps video.mp4 so the page can play it.")
    if temporary == ["audio"]:
        notes.append("The audio is processed temporarily and not kept.")

    return {
        "keep": keep,
        "temporary": temporary,
        "pipeline": pipeline,
        "audio_only_download": audio_only_download,
        "notes": notes,
    }


def estimate_eta(fraction: float, elapsed: float) -> int | None:
    if fraction <= 0 or fraction < 0.10 or elapsed < 5:
        return None
    fraction = min(fraction, 1.0)
    return int(round(elapsed * (1 - fraction) / fraction))