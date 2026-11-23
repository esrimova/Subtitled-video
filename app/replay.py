import base64
import html
import json
import mimetypes
from pathlib import Path
from replay_css import CSS
from replay_js import JS
from replay_icon import ICON_PNG_B64


def render_replay(title: str, video_file: str, segments: list[dict], embed_mime: str | None = None) -> str:
    escaped_title = html.escape(title)
    escaped_video = html.escape(video_file, quote=True)
    segments_json = json.dumps(segments, ensure_ascii=False).replace("<", "\\u003c")

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang=\"en\">")
    parts.append("<head>")
    parts.append("<meta charset=\"utf-8\">")
    parts.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
    parts.append("<link rel=\"icon\" type=\"image/png\" href=\"data:image/png;base64," + ICON_PNG_B64 + "\">")
    parts.append("<title>" + escaped_title + "</title>")
    parts.append("<style>" + CSS + "</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<div class=\"container\">")
    parts.append("<h1>" + escaped_title + "</h1>")
    parts.append("<div id=\"player\">")
    parts.append("<div id=\"stage\">")
    if embed_mime is not None:
        parts.append("<video id=\"video\" controls preload=\"metadata\"></video>")
    else:
        parts.append("<video id=\"video\" controls preload=\"metadata\" src=\"" + escaped_video + "\"></video>")
    parts.append("</div>")
    parts.append("<div id=\"side\">")
    parts.append("<div id=\"controls\">")
    parts.append("<button id=\"cc-toggle\" type=\"button\" aria-pressed=\"true\">CC</button>")
    parts.append("<select id=\"speed\">")
    parts.append("<option value=\"0.5\">0.5x</option>")
    parts.append("<option value=\"0.75\">0.75x</option>")
    parts.append("<option value=\"1\" selected>1x</option>")
    parts.append("<option value=\"1.25\">1.25x</option>")
    parts.append("<option value=\"1.5\">1.5x</option>")
    parts.append("</select>")
    parts.append("<button id=\"replay-line\" type=\"button\">Replay line</button>")
    parts.append("<button id=\"settings-toggle\" type=\"button\">Settings</button>")
    parts.append("</div>")
    parts.append("<div id=\"settings-panel\" hidden>")
    parts.append("<label for=\"set-font\">Font</label>")
    parts.append("<select id=\"set-font\">")
    parts.append("<option value=\"system-ui\">System default</option>")
    parts.append("<option value=\"Georgia, serif\">Serif</option>")
    parts.append("<option value=\"Consolas, monospace\">Monospace</option>")
    parts.append("<option value=\"Arial, sans-serif\">Sans-serif</option>")
    parts.append("<option value=\"Comic Sans MS, cursive\">Comic</option>")
    parts.append("</select>")
    parts.append("<label for=\"set-color\">Text color</label>")
    parts.append("<input id=\"set-color\" type=\"color\" value=\"#ffffff\">")
    parts.append("<label for=\"set-size\">Text size (px)</label>")
    parts.append("<input id=\"set-size\" type=\"range\" min=\"12\" max=\"48\" value=\"20\">")
    parts.append("<label for=\"set-bg\">Background color</label>")
    parts.append("<input id=\"set-bg\" type=\"color\" value=\"#101418\">")
    parts.append("<label for=\"set-brightness\">Background brightness (%)</label>")
    parts.append("<input id=\"set-brightness\" type=\"range\" min=\"20\" max=\"200\" value=\"100\">")
    parts.append("<label for=\"set-bold\">Bold</label>")
    parts.append("<input id=\"set-bold\" type=\"checkbox\">")
    parts.append("<label for=\"set-italic\">Italic</label>")
    parts.append("<input id=\"set-italic\" type=\"checkbox\">")
    parts.append("<button id=\"set-reset\" type=\"button\">Reset</button>")
    parts.append("</div>")
    parts.append("<div id=\"transcript\"></div>")
    parts.append("</div>")
    parts.append("</div>")
    parts.append("<script type=\"application/json\" id=\"segments\">" + segments_json + "</script>")
    if embed_mime is not None:
        escaped_mime = html.escape(embed_mime, quote=True)
        parts.append("<script type=\"text/plain\" id=\"video-data\" data-mime=\"" + escaped_mime + "\">@@VIDEO_DATA@@</script>")
    parts.append("<script>" + JS + "</script>")
    parts.append("</div>")
    parts.append("</body>")
    parts.append("</html>")
    return "".join(parts)


def write_replay(dest: Path, title: str, video_path: Path, segments: list[dict], embed: bool, video_name: str = "") -> None:
    if not embed:
        dest.write_text(render_replay(title, video_name, segments), encoding="utf-8")
        return

    mime = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
    html_content = render_replay(title, "", segments, embed_mime=mime)
    before, after = html_content.split("@@VIDEO_DATA@@", 1)

    chunk_size = 3 * 1024 * 1024  # multiple of 3 so base64 chunks concatenate correctly
    with dest.open("wb") as out:
        out.write(before.encode("utf-8"))
        with video_path.open("rb") as vf:
            while True:
                chunk = vf.read(chunk_size)
                if not chunk:
                    break
                out.write(base64.b64encode(chunk))
        out.write(after.encode("utf-8"))