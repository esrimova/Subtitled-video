import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import replay  # noqa: E402
import replay_css  # noqa: E402

SEGS = [{"start": 0.0, "end": 2.5, "text": "Hola, ¿qué tal?"},
        {"start": 2.5, "end": 5.0, "text": "I said \"hello\" & goodbye"}]
EVIL = [{"start": 0.0, "end": 1.0, "text": "</script><script>alert(1)</script><b>x</b> 😀"}]


def segments_in(html):
    m = re.search(r'<script type="application/json" id="segments">(.*?)</script>', html, re.S)
    assert m, "embedded segments block not found"
    return json.loads(m.group(1))


class Replay(unittest.TestCase):
    def test_is_a_full_document_with_video(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<video", html)
        self.assertIn('src="video.mp4"', html)

    def test_required_controls_exist(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        for ident in ("player", "stage", "side", "current-caption", "cc-toggle", "transcript", "speed", "replay-line"):
            self.assertIn('id="%s"' % ident, html)

    def test_segments_round_trip(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertEqual(segments_in(html), SEGS)

    def test_script_breakout_is_impossible(self):
        benign = replay.render_replay("Demo", "video.mp4", SEGS)
        evil = replay.render_replay("Demo", "video.mp4", EVIL)
        self.assertEqual(evil.count("</script>"), benign.count("</script>"))
        self.assertEqual(segments_in(evil), EVIL)

    def test_title_and_filename_are_escaped(self):
        html = replay.render_replay("My <b>Title</b>", 'my "clip".mp4', SEGS)
        self.assertIn("&lt;b&gt;Title&lt;/b&gt;", html)
        self.assertNotIn("<b>Title</b>", html)
        self.assertIn('src="my &quot;clip&quot;.mp4"', html)

    def test_works_offline_and_never_uses_innerhtml(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("innerHTML", html)
        self.assertIn("textContent", html)
        self.assertNotIn("<track", html)

    def test_play_rejections_are_handled(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertEqual(html.count(".play()"), html.count(".play().catch("))
        self.assertGreaterEqual(html.count(".play().catch("), 2)

    def test_empty_segments_still_renders(self):
        html = replay.render_replay("Demo", "video.mp4", [])
        self.assertEqual(segments_in(html), [])

    def test_layout_uses_percentages(self):
        css = replay_css.CSS
        self.assertIn("grid-template-columns: 68% 28%", css)
        self.assertIn("column-gap: 4%", css)
        self.assertNotIn("max-width: 960px", css)

    def test_native_fullscreen_disabled(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertIn('controlsList="nofullscreen"', html)

    def test_custom_fullscreen_targets_player(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertIn('id="fs-toggle"', html)
        self.assertIn("requestFullscreen", html)
        self.assertIn('getElementById("player")', html)

    def test_settings_controls_exist(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        for ident in ("set-font", "set-color", "set-size", "set-bg", "set-brightness", "set-bold", "set-italic", "set-reset", "settings-toggle", "settings-panel"):
            self.assertIn('id="%s"' % ident, html)

    def test_settings_persisted_safely(self):
        html = replay.render_replay("Demo", "video.mp4", SEGS)
        self.assertIn("subtitled-video.settings", html)
        self.assertIn("localStorage", html)
        self.assertIn("try", html)

    def test_css_uses_variables(self):
        css = replay_css.CSS
        for var in ("--sub-font", "--sub-color", "--sub-size", "--sub-bg", "--sub-brightness", "--sub-weight", "--sub-style"):
            self.assertIn(var, css)


if __name__ == "__main__":
    unittest.main()
