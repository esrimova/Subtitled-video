def _validate_quality(quality: str) -> None:
    if quality != "best" and (not quality.isdigit() or int(quality) <= 0):
        raise ValueError("Invalid quality")


def quality_options(info: dict | None) -> list[dict]:
    if not info or not info.get("formats"):
        return []
    effective_sizes = set()
    size_by_effective = {}
    for f in info["formats"]:
        h = f.get("height")
        vcodec = f.get("vcodec")
        if isinstance(h, int) and h > 0 and vcodec != "none":
            w = f.get("width")
            if isinstance(w, int) and w > 0:
                eff = min(w, h)
            else:
                eff = h
            effective_sizes.add(eff)
            size = f.get("filesize") or f.get("filesize_approx")
            if isinstance(size, int) and size > 0:
                size_by_effective[eff] = max(size_by_effective.get(eff, 0), size)
    if not effective_sizes:
        return []
    sorted_sizes = sorted(effective_sizes, reverse=True)
    tallest = sorted_sizes[0]
    options = [{"id": "best", "label": f"Best available ({tallest}p)"}]
    if len(sorted_sizes) > 1:
        for eff in sorted_sizes:
            label = f"{eff}p"
            if eff in size_by_effective:
                mb = round(size_by_effective[eff] / 1_000_000)
                label += f" (~{mb} MB)"
            options.append({"id": str(eff), "label": label})
    return options


def format_selector(quality: str, audio_only: bool) -> str:
    _validate_quality(quality)
    if audio_only:
        return "bestaudio/best"
    return "bestvideo+bestaudio/best"


def format_sort(quality: str) -> list[str]:
    _validate_quality(quality)
    if quality == "best":
        return []
    return ["res:" + quality]