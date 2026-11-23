"""Integration tests: start the real server and drive it over HTTP.
Job tests need AE_TEST_CLIP (a short clip with speech). They run on the CPU so they never compete for the GPU."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLIP = os.environ.get("AE_TEST_CLIP")


def tasklist_pids(name):
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + name, "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return {int(m.group(1)) for m in re.finditer(r'"[^"]+","(\d+)"', out)}


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ae_srv_"))
        cls.out = cls.tmp / "output"
        env = dict(os.environ, AUDIOEXT_OUT=str(cls.out), CUDA_VISIBLE_DEVICES="-1", PYTHONIOENCODING="utf-8")
        cls.proc = subprocess.Popen([sys.executable, "-I", "-X", "utf8", str(ROOT / "app" / "server.py"),
                                     "--no-browser"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", env=env)
        line = ""
        t0 = time.time()
        while time.time() - t0 < 20:
            line = cls.proc.stdout.readline()
            m = re.search(r"http://127\.0\.0\.1:(\d+)/\?t=(\S+)", line)
            if m:
                cls.port, cls.token = int(m.group(1)), m.group(2)
                break
        else:
            raise RuntimeError("server did not start")
        cls.base = "http://127.0.0.1:%d" % cls.port
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=2",
                        str(cls.tmp / "silent.mp4")], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()

    def call(self, path, body=None, token=True, headers=None):
        h = {"Content-Type": "application/json"}
        if token:
            h["X-Token"] = self.token
        h.update(headers or {})
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def events(self, until=("done", "error", "cancelled"), timeout=240):
        req = urllib.request.Request(self.base + "/api/events?t=" + self.token)
        out, t0 = [], time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if line.startswith("data: "):
                    ev = json.loads(line[6:])
                    out.append(ev)
                    if ev["type"] in until:
                        return out
                if time.time() - t0 > timeout:
                    break
        return out


class Security(ServerCase):
    def test_page_loads_without_token_but_api_needs_it(self):
        with urllib.request.urlopen(self.base + "/?t=" + self.token) as r:
            self.assertEqual(r.status, 200)
            self.assertIn("t=" + self.token, r.headers.get("Set-Cookie", ""))
        self.assertEqual(self.call("/api/state", token=False)[0], 403)
        self.assertEqual(self.call("/api/check", {"source": "x"}, token=False)[0], 403)

    def test_wrong_host_header_is_refused(self):
        self.assertEqual(self.call("/api/state", headers={"Host": "evil.example:80"})[0], 403)

    def test_path_traversal_is_refused(self):
        req = urllib.request.Request(self.base + "/files/..%2F..%2Fapp%2Fserver.py",
                                     headers={"X-Token": self.token})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 404)

    def test_static_traversal_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + "/..%2Fserver.py")


class CheckAndPlan(ServerCase):
    def test_silent_video_disables_audio_outputs(self):
        code, r = self.call("/api/check", {"source": str(self.tmp / "silent.mp4")})
        self.assertTrue(r["ok"])
        self.assertTrue(r["no_audio"])
        avail = {o["id"]: o["available"] for o in r["outputs"]}
        self.assertEqual(avail, {"video": True, "audio": False, "transcript": False, "replay": False})

    def test_bad_input_gives_a_reason(self):
        code, r = self.call("/api/check", {"source": "hello world"})
        self.assertFalse(r["ok"])
        self.assertIn("web link", r["reason"])

    def test_plan_endpoint_matches_steps(self):
        code, r = self.call("/api/plan", {"outputs": ["replay"], "no_audio": False, "kind": "url"})
        self.assertEqual(r["keep"], ["replay"])
        code, r = self.call("/api/plan", {"outputs": ["audio"], "no_audio": True, "kind": "url"})
        self.assertFalse(r["ok"])

    def test_start_refuses_impossible_combo(self):
        src = str(self.tmp / "silent.mp4")
        self.call("/api/check", {"source": src})
        code, r = self.call("/api/start", {"source": src, "outputs": ["transcript"], "quality": "best"})
        self.assertFalse(r["ok"])


@unittest.skipUnless(CLIP and os.path.exists(CLIP), "set AE_TEST_CLIP to a short clip with speech")
class Jobs(ServerCase):
    def test_full_job_creates_only_requested_files_and_serves_them(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["transcript", "replay"],
                                           "folder_name": "mi prueba", "model": "small", "quality": "best"})
        self.assertTrue(r["ok"], r)
        evs = self.events()
        self.assertEqual(evs[-1]["type"], "done", evs[-3:])
        stages = [e["stage"] for e in evs if e["type"] == "stage"]
        self.assertIn("download" if False else "audio", stages)
        self.assertIn("transcribe", stages)
        folder = self.out / "mi prueba"
        # the output matches the selection: transcript + replay = transcript.md + ONE html (video inside it)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(["transcript.md", "index.html"]))
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".staging")], [])
        html = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="video-data"', html)
        self.assertNotIn("captions.srt", html)
        seg_json = re.search(r'id="segments">(.*?)</script>', html, re.S).group(1)
        self.assertGreater(len(json.loads(seg_json)), 0)
        # the embedded video is exactly the source clip
        import base64
        payload = re.search(r'id="video-data" data-mime="[^"]*">([A-Za-z0-9+/=]*)</script>', html).group(1)
        self.assertEqual(base64.b64decode(payload), Path(CLIP).read_bytes())
        # served with Range support
        req = urllib.request.Request(self.base + "/files/mi%20prueba/index.html",
                                     headers={"X-Token": self.token, "Range": "bytes=0-99"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 206)
            self.assertEqual(len(resp.read()), 100)
        # same name again is refused
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video"], "folder_name": "mi prueba"})
        self.assertFalse(r["ok"])
        self.assertIn("already exists", r["reason"])

    def test_video_only_from_file_is_a_plain_copy(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video"], "folder_name": "solo video"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.events()[-1]["type"], "done")
        self.assertEqual([p.name for p in (self.out / "solo video").iterdir()], ["video.mp4"])

    def test_two_jobs_back_to_back_do_not_leak_into_each_other(self):
        # regression: the first run's relay thread used to write an error into the second run
        for name in ("seguido uno", "seguido dos", "seguido tres"):
            self.call("/api/check", {"source": CLIP})
            code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video"], "folder_name": name})
            self.assertTrue(r["ok"], r)
            evs = self.events()
            self.assertEqual(evs[-1]["type"], "done", evs)
            self.assertEqual([e for e in evs if e["type"] == "error"], [])
        time.sleep(1.5)  # let the previous relay threads finish
        self.assertEqual(self.call("/api/state")[1]["state"], "done")
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".staging")], [])

    def test_only_one_of_two_simultaneous_starts_is_accepted(self):
        import threading
        long_clip = self.tmp / "long2.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "14", "-i", CLIP, "-c", "copy",
                        str(long_clip)], check=True)
        self.call("/api/check", {"source": str(long_clip)})
        results, gate = [], threading.Barrier(2)

        def go(name):
            gate.wait()
            results.append(self.call("/api/start", {"source": str(long_clip), "outputs": ["transcript"],
                                                    "folder_name": name, "model": "small"})[1])

        ts_ = [threading.Thread(target=go, args=(n,)) for n in ("pestana a", "pestana b")]
        [t.start() for t in ts_]
        [t.join() for t in ts_]
        self.assertEqual(sorted(r["ok"] for r in results), [False, True], results)
        loser = next(r for r in results if not r["ok"])
        self.assertIn("already running", loser["reason"])
        self.call("/api/cancel", {})
        self.events()
        time.sleep(1)
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".staging")], [])

    def test_cancel_kills_the_tree_and_leaves_nothing(self):
        long_clip = self.tmp / "long.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "14", "-i", CLIP, "-c", "copy",
                        str(long_clip)], check=True)
        before = tasklist_pids("ffmpeg.exe")
        self.call("/api/check", {"source": str(long_clip)})
        code, r = self.call("/api/start", {"source": str(long_clip), "outputs": ["transcript"],
                                           "folder_name": "cancelame", "model": "small"})
        self.assertTrue(r["ok"], r)
        self.events(until=("stage",))
        time.sleep(2)
        code, r = self.call("/api/cancel", {})
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.events()[-1]["type"], "cancelled")
        self.assertEqual(self.call("/api/state")[1]["state"], "stopped")
        time.sleep(1)
        self.assertFalse((self.out / "cancelame").exists())
        self.assertEqual([p.name for p in self.out.iterdir() if p.name.startswith(".staging")], [])
        self.assertEqual(tasklist_pids("ffmpeg.exe") - before, set())
        # and a new job can start right after
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video"], "folder_name": "despues"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.events()[-1]["type"], "done")

    def test_replay_plus_video_keeps_both_files(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video", "replay"],
                                           "folder_name": "con video", "model": "small", "quality": "best"})
        self.assertTrue(r["ok"], r)
        evs = self.events()
        self.assertEqual(evs[-1]["type"], "done", evs[-3:])
        folder = self.out / "con video"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(["video.mp4", "index.html"]))
        html = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="video-data"', html)
        # the page does not depend on the saved video: it has no src pointing at it
        self.assertNotIn('src="video.mp4"', html)


class CancelAfterPublish(unittest.TestCase):
    """No HTTP: drive server.cancel_job() with a fake run whose result folder is already published."""

    def test_cancel_after_publication_keeps_the_result_and_says_so(self):
        sys.path.insert(0, str(ROOT / "app"))
        sys.path.insert(0, str(ROOT))
        import server
        tmp = Path(tempfile.mkdtemp(prefix="ae_cap_"))
        final = tmp / "ya publicado"
        final.mkdir()
        (final / "video.mp4").write_bytes(b"x")
        (final / "index.html").write_text("<html></html>")
        staging = tmp / ".staging-x"
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        job = server.Job()
        job.state, job.proc, job.staging, job.final_dir = "running", proc, staging, final
        old, server.JOB = server.JOB, job
        try:
            res = server.cancel_job()
        finally:
            server.JOB = old
        self.assertFalse(res["ok"])
        self.assertIn("Too late", res["reason"])
        self.assertEqual(job.state, "done")
        self.assertEqual(job.events[-1]["type"], "done")
        self.assertEqual(job.events[-1]["files"], ["index.html", "video.mp4"])
        self.assertTrue(job.events[-1]["replay_url"].endswith("/index.html"))
        self.assertTrue((final / "video.mp4").exists())
        self.assertIsNotNone(proc.poll())  # the worker was killed


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(CLIP and os.path.exists(CLIP), "set AE_TEST_CLIP to a short clip with speech")
class SmallEmbedLimit(ServerCase):
    """The server and its worker both run with a tiny embed limit, so any clip is 'too big'."""

    @classmethod
    def setUpClass(cls):
        cls._old = os.environ.get("AE_EMBED_LIMIT")
        os.environ["AE_EMBED_LIMIT"] = "1000"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls._old is None:
            os.environ.pop("AE_EMBED_LIMIT", None)
        else:
            os.environ["AE_EMBED_LIMIT"] = cls._old

    def test_replay_only_over_the_limit_stops_before_any_slow_work_and_saves_nothing(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["replay"], "folder_name": "grande",
                                           "model": "small", "quality": "best"})
        self.assertTrue(r["ok"], r)
        evs = self.events()
        self.assertEqual(evs[-1]["type"], "error", evs[-3:])
        self.assertIn("limit", evs[-1]["message"])
        self.assertIn("untick", evs[-1]["message"])
        self.assertNotIn("transcribe", [e.get("stage") for e in evs if e["type"] == "stage"])
        self.assertFalse((self.out / "grande").exists())
        for _ in range(50):  # the server removes the temporary folder just after reporting the error
            if not list(self.out.iterdir()):
                break
            time.sleep(0.1)
        self.assertEqual([p.name for p in self.out.iterdir()], [])

    def test_replay_plus_video_over_the_limit_also_stops_and_saves_nothing(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video", "replay"], "folder_name": "grande3",
                                           "model": "small", "quality": "best"})
        self.assertTrue(r["ok"], r)
        evs = self.events()
        self.assertEqual(evs[-1]["type"], "error", evs[-3:])
        self.assertIn("limit", evs[-1]["message"])
        self.assertFalse((self.out / "grande3").exists())

    def test_video_alone_has_no_size_limit(self):
        self.call("/api/check", {"source": CLIP})
        code, r = self.call("/api/start", {"source": CLIP, "outputs": ["video"], "folder_name": "solo video",
                                           "model": "small", "quality": "best"})
        self.assertTrue(r["ok"], r)
        evs = self.events()
        self.assertEqual(evs[-1]["type"], "done", evs[-3:])
        self.assertEqual([p.name for p in (self.out / "solo video").iterdir()], ["video.mp4"])
