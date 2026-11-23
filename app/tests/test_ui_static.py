import os
import re
import sys
import unittest

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static")
IDS = ["source", "check-btn", "checking", "error", "options", "summary", "no-audio-banner", "outputs",
       "plan-notes", "folder-name", "model-row", "model", "start-btn", "running", "stages", "bar",
       "stage-msg", "eta", "live-transcript", "cancel-btn", "done", "done-title", "done-files",
       "open-replay", "open-folder-btn", "new-btn", "stopped", "stopped-msg", "retry-btn",
       "quality-row", "quality"]


def read(name):
    with open(os.path.join(STATIC, name), encoding="utf-8") as f:
        return f.read()


class StaticUi(unittest.TestCase):
    def setUp(self):
        self.html = read("index.html")
        self.js = read("app_api.js") + "\n" + read("app_ui.js")

    def test_every_required_id_exists_exactly_once(self):
        for i in IDS:
            self.assertEqual(len(re.findall(r'\bid="%s"' % re.escape(i), self.html)), 1, i)

    def test_all_ids_in_html_are_unique(self):
        ids = re.findall(r'\bid="([^"]+)"', self.html)
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        self.assertEqual(dupes, [])

    def test_ids_the_js_reads_exist_in_html(self):
        used = set(re.findall(r'getElementById\(\s*["\']([^"\']+)["\']', self.js))
        used |= set(re.findall(r'querySelector\(\s*["\']#([\w-]+)["\']', self.js))
        used |= set(re.findall(r'\$\(\s*["\']#?([\w-]+)["\']', self.js))
        html_ids = set(re.findall(r'\bid="([^"]+)"', self.html))
        self.assertEqual(sorted(used - html_ids), [])

    def test_no_html_parsing_apis(self):
        self.assertIsNone(re.search(r"innerHTML|outerHTML|insertAdjacentHTML", self.js))

    def test_no_external_resources(self):
        self.assertNotRegex(self.html + self.js + read("style.css"), r"https?://")

    def test_scripts_load_in_order(self):
        self.assertLess(self.html.index("app_api.js"), self.html.index("app_ui.js"))

    def test_required_api_paths_are_used(self):
        for p in ("/api/check", "/api/plan", "/api/start", "/api/cancel", "/api/open-folder",
                  "/api/state", "/api/events"):
            self.assertIn(p, self.js)

    def test_quality_is_read_from_check_and_sent_on_start(self):
        self.assertIn("qualities", self.js)
        self.assertRegex(self.js, r"\bquality\b\s*[,:}]")

    def test_known_wrong_patterns_are_gone(self):
        # measured bugs from the first draft
        self.assertNotIn('=== "link"', self.js)                       # server kind is "url" or "file"
        screens = r'"(idle|checking|options|running|done|stopped)"'
        self.assertIsNone(re.search(r'setError\(\s*' + screens, self.js))    # setError(msg) takes only a message
        self.assertIsNone(re.search(r'clearError\(\s*"', self.js))           # clearError takes none
        self.assertNotIn('pipeline.includes("video")', self.js)        # pipeline holds steps, not outputs
        self.assertIn("res.keep", self.js)                             # quality row depends on plan.keep
        self.assertRegex(self.js, r'all\s*=\s*\[[^\]]*"checking"')     # "checking" is hidden on every screen change
        self.assertRegex(self.js, r'"quality-row"')

    def test_unknown_length_is_not_shown_as_zero(self):
        self.assertIn("lengthUnknown", self.js)
        self.assertRegex(self.js, r"duration\s*(>|===|!==|==|!=)")

    def test_token_header_and_query(self):
        self.assertIn("X-Token", self.js)
        self.assertIn("/api/events?t=", self.js)


if __name__ == "__main__":
    unittest.main()
