def fmt_srt_time(seconds: float) -> str:
    ms = round(max(seconds, 0) * 1000)
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    secs = ms // 1000
    ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def fmt_vtt_time(seconds: float) -> str:
    ms = round(max(seconds, 0) * 1000)
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    secs = ms // 1000
    ms %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def _clean_text(text: str) -> str:
    lines = text.strip().split("\n")
    cleaned = [line for line in lines if line.strip() != ""]
    return "\n".join(cleaned)


def _clean_text_vtt(text: str) -> str:
    return _clean_text(text).replace("-->", "->")


def to_srt(segments: list[dict]) -> str:
    cues = []
    n = 1
    for seg in segments:
        text = _clean_text(seg["text"])
        if not text:
            continue
        start = seg["start"]
        end = max(seg["end"], start)
        start_str = fmt_srt_time(start)
        end_str = fmt_srt_time(end)
        cue = f"{n}\n{start_str} --> {end_str}\n{text}\n\n"
        cues.append(cue)
        n += 1
    return "".join(cues)


def to_vtt(segments: list[dict]) -> str:
    cues = []
    for seg in segments:
        text = _clean_text_vtt(seg["text"])
        if not text:
            continue
        start = seg["start"]
        end = max(seg["end"], start)
        start_str = fmt_vtt_time(start)
        end_str = fmt_vtt_time(end)
        cue = f"{start_str} --> {end_str}\n{text}\n\n"
        cues.append(cue)
    if not cues:
        return "WEBVTT\n\n"
    return "WEBVTT\n\n" + "".join(cues)