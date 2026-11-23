"""Local web app server (stdlib only). Bound to 127.0.0.1; every API call needs the per-run token.

python -I -X utf8 app/server.py [--no-browser]
"""
import contextlib
import io
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import core  # noqa: E402
import extract  # noqa: E402
import quality  # noqa: E402
import steps  # noqa: E402

STATIC = HERE / "static"
OUT_ROOT = Path(os.environ.get("AUDIOEXT_OUT") or extract.OUT_ROOT)  # tests point this at a temp folder
extract.OUT_ROOT = OUT_ROOT  # extract.custom_folder reads this module attribute
LABELS = {"video": "Save video", "audio": "Save audio", "transcript": "Save transcript",
          "replay": "Create captioned replay"}
TOKEN = secrets.token_urlsafe(16)
PORT = 0
STDOUT_LOCK = threading.Lock()


class Job:
    def __init__(self):
        self.cond = threading.Condition()
        self.reset()

    def reset(self):
        self.state, self.events, self.proc, self.staging = "idle", [], None, None
        self.pipeline, self.final_dir, self.cancelling = [], None, False

    def add(self, ev):
        with self.cond:
            self.events.append(ev)
            self.cond.notify_all()


JOB = Job()
CHECKS = {}  # source -> preflight result (so Start does not re-check over the network)


def check_source(source):
    """Run extract.preflight quietly. Returns (result_dict, None) or (None, reason)."""
    with STDOUT_LOCK, contextlib.redirect_stdout(io.StringIO()):
        try:
            res = extract.preflight(source)
        except extract.InputRejected as e:
            return None, str(e)
        except Exception as e:
            return None, "Could not check this input: %s" % str(e)[:200]
    if res["kind"] == "file":
        kinds = core.probe_streams(res["target"])
        res["has_video"] = "video" in kinds
    else:
        res["has_video"] = True
    CHECKS[source] = res
    return res, None


def describe(res):
    no_audio = res["no_audio"]
    outs = []
    for oid in ("video", "audio", "transcript", "replay"):
        ok, note = True, ""
        if oid in ("audio", "transcript", "replay") and no_audio:
            ok, note = False, "This video has no audio track."
        if oid in ("video", "replay") and not res["has_video"]:
            ok, note = False, "This file has no video."
        outs.append({"id": oid, "label": LABELS[oid], "available": ok, "note": note})
    quals = quality.quality_options(res.get("info")) if res["kind"] == "url" else []
    return {"ok": True, "title": res["title"], "duration": res["duration"], "kind": res["kind"],
            "no_audio": no_audio, "outputs": outs, "qualities": quals}


START_GUARD = threading.Lock()
STARTING = False


def start_job(body):
    """Reserve the single job slot BEFORE doing the slow checks, so two tabs cannot both start a job."""
    global STARTING
    with START_GUARD:
        if STARTING or JOB.state == "running":
            return {"ok": False, "reason": "A job is already running."}
        STARTING = True
    try:
        return _start_job(body)
    finally:
        with START_GUARD:
            STARTING = False


def _start_job(body):
    global JOB
    source = (body.get("source") or "").strip()
    outputs = set(body.get("outputs") or [])
    model = body.get("model") if body.get("model") in ("small", "medium") else "medium"
    with JOB.cond:
        if JOB.state == "running":
            return {"ok": False, "reason": "A job is already running."}
    res = CHECKS.get(source)
    if res is None:
        res, reason = check_source(source)
        if res is None:
            return {"ok": False, "reason": reason}
    try:
        plan = steps.resolve_outputs(outputs, res["no_audio"], res["kind"])
        qual = str(body.get("quality") or "best")
        quality.format_selector(qual, False)  # validates the value
    except ValueError as e:
        return {"ok": False, "reason": str(e)}
    name = (body.get("folder_name") or "").strip()
    if name:
        final = extract.custom_folder(name)
        if final is None:
            return {"ok": False, "reason": "That folder name is not valid."}
        if final.exists():
            return {"ok": False, "reason": 'A folder named "%s" already exists. Choose another name.' % final.name}
    else:
        base = res["info"].get("id") if res.get("info") else None
        final = core.unique_dir(OUT_ROOT / (extract.slug(res["title"]) + ("_" + str(base) if base else "")))
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    jid = uuid.uuid4().hex[:8]
    staging = OUT_ROOT / (".staging-" + jid)
    staging.mkdir(parents=True)
    spec = {"source": source, "kind": res["kind"], "target": str(res["target"]), "title": res["title"],
            "duration": res["duration"], "plan": plan, "model": model, "quality": qual,
            "staging": str(staging), "final_dir": str(final), "parent_pid": os.getpid()}
    (staging / "job.json").write_text(json.dumps(spec), encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-I", "-X", "utf8", str(HERE / "worker.py"), str(staging / "job.json")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace")
    job = Job()  # every run gets its own state, so a finishing run can never touch the next one
    job.state, job.proc, job.staging, job.pipeline, job.final_dir = "running", proc, staging, plan["pipeline"], final
    JOB = job
    threading.Thread(target=pump, args=(job, proc, staging), daemon=True).start()
    return {"ok": True}


def pump(job, proc, staging):
    """Relay one worker's events; decide that run's final state when it exits."""
    for line in proc.stdout:
        at = line.find("@@EVT ")  # tolerate other tools' partial output glued in front
        if at >= 0:
            try:
                ev = json.loads(line[at + 6:])
            except ValueError:
                continue
            with job.cond:
                if job.cancelling:
                    continue
            job.add(ev)
            if ev.get("type") in ("done", "error"):
                with job.cond:
                    job.state = "done" if ev["type"] == "done" else "stopped"
        else:
            print("[worker]", line.rstrip(), flush=True)
    code = proc.wait()
    with job.cond:
        finished = job.state != "running"
        cancelling = job.cancelling
    if not finished and not cancelling:
        job.add({"type": "error", "message": "The job stopped unexpectedly (exit code %s)." % code})
        with job.cond:
            job.state = "stopped"
    if job.state != "done":
        core.rmtree_retry(staging)  # failed: leave nothing behind (a finished job already removed it)


def cancel_job():
    job = JOB
    with job.cond:
        if job.state != "running" or job.cancelling:
            return {"ok": False, "reason": "Nothing is running."}
        job.cancelling, proc, staging = True, job.proc, job.staging
    core.kill_tree(proc.pid)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        pass
    final = Path(job.final_dir) if job.final_dir else None
    if final and final.is_dir():
        # The worker had already published its result (one atomic rename): keep it, and say so.
        files = sorted(p.name for p in final.iterdir())
        with job.cond:
            job.state = "done"
        job.add({"type": "done", "folder": str(final), "files": files,
                 "replay_url": ("/files/%s/index.html" % quote(final.name)) if "index.html" in files else ""})
        return {"ok": False, "reason": "Too late to cancel: the result had already been saved."}
    core.rmtree_retry(staging)
    with job.cond:
        job.state = "stopped"
    job.add({"type": "cancelled"})
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AudioExtractor"

    def log_message(self, *a):
        pass

    # ---- plumbing
    def host_ok(self):
        return self.headers.get("Host", "") in ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT)

    def token_ok(self, query):
        cookie = self.headers.get("Cookie", "")
        return (self.headers.get("X-Token") == TOKEN or query.get("t", [""])[0] == TOKEN
                or ("t=" + TOKEN) in cookie.replace(" ", "").split(";"))

    def send_json(self, obj, code=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 1_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return None

    def gate(self, query, need_token=True):
        if not self.host_ok():
            self.send_json({"ok": False, "reason": "Bad host."}, 403)
            return False
        if need_token and not self.token_ok(query):
            self.send_json({"ok": False, "reason": "Bad token."}, 403)
            return False
        return True

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/api/events":
            if self.gate(q):
                self.sse()
        elif u.path == "/api/state":
            if self.gate(q):
                with JOB.cond:
                    self.send_json({"ok": True, "state": JOB.state, "plan_pipeline": JOB.pipeline})
        elif u.path.startswith("/files/"):
            if self.gate(q):
                self.serve_file(OUT_ROOT, unquote(u.path[len("/files/"):]))
        elif u.path in ("/", "/index.html"):
            if self.gate(q, need_token=False):
                self.serve_static("index.html", cookie=q.get("t", [""])[0] == TOKEN)
        else:
            if self.gate(q, need_token=False):
                self.serve_static(u.path.lstrip("/"))

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self.gate(q):
            return
        body = self.read_body()
        if body is None:
            return self.send_json({"ok": False, "reason": "Bad request."}, 400)
        if u.path == "/api/check":
            res, reason = check_source((body.get("source") or "").strip())
            self.send_json(describe(res) if res else {"ok": False, "reason": reason})
        elif u.path == "/api/plan":
            try:
                p = steps.resolve_outputs(set(body.get("outputs") or []), bool(body.get("no_audio")),
                                          body.get("kind", ""))
                self.send_json(dict(p, ok=True))
            except ValueError as e:
                self.send_json({"ok": False, "reason": str(e)})
        elif u.path == "/api/start":
            self.send_json(start_job(body))
        elif u.path == "/api/cancel":
            self.send_json(cancel_job())
        elif u.path == "/api/open-folder":
            with JOB.cond:
                folder = JOB.final_dir
            if folder and Path(folder).is_dir():
                os.startfile(folder)
                self.send_json({"ok": True})
            else:
                self.send_json({"ok": False, "reason": "No finished folder to open."})
        else:
            self.send_json({"ok": False, "reason": "Unknown endpoint."}, 404)

    # ---- static and files
    def serve_static(self, rel, cookie=False):
        path = (STATIC / rel).resolve()
        if STATIC.resolve() not in path.parents or not path.is_file():
            return self.send_json({"ok": False, "reason": "Not found."}, 404)
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(path.name)[0] or "text/plain") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", "t=%s; Path=/; HttpOnly; SameSite=Strict" % TOKEN)
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, root, rel):
        path = (root / rel).resolve()
        if root.resolve() not in path.parents or not path.is_file() or path.name.startswith("."):
            return self.send_json({"ok": False, "reason": "Not found."}, 404)
        size = path.stat().st_size
        start, end, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
            else:
                start = max(size - int(m.group(2)), 0)
            if start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            end, code = min(end, size - 1), 206
        self.send_response(code)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionError, OSError):
            pass

    def sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            i = int(self.headers.get("Last-Event-ID") or 0)
        except ValueError:
            i = 0
        job = JOB  # stream this run only; the page opens a new stream when a new run starts
        try:
            while True:
                with job.cond:
                    if i >= len(job.events):
                        job.cond.wait(timeout=15)
                    batch = job.events[i:]
                if not batch:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                for ev in batch:
                    i += 1
                    self.wfile.write(("id: %d\ndata: %s\n\n" % (i, json.dumps(ev, ensure_ascii=False))).encode("utf-8"))
                self.wfile.flush()
        except (ConnectionError, OSError):
            return


def main():
    global PORT
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    srv.daemon_threads = True
    PORT = srv.server_address[1]
    url = "http://127.0.0.1:%d/?t=%s" % (PORT, TOKEN)
    print("Audio extractor is running. Keep this window open while you use it.", flush=True)
    print("If the browser does not open, paste this address into it:\n  " + url, flush=True)
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with JOB.cond:
            proc = JOB.proc if JOB.state == "running" else None
        if proc:
            core.kill_tree(proc.pid)


if __name__ == "__main__":
    main()
