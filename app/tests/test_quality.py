import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import quality  # noqa: E402


def F(height, size=None, vcodec="avc1", width=None, **extra):
    d = {"height": height, "vcodec": vcodec}
    if width is not None:
        d["width"] = width
    if size is not None:
        d["filesize"] = size
    d.update(extra)
    return d


class Options(unittest.TestCase):
    def test_lists_heights_descending_with_best_first_and_dedupes(self):
        info = {"formats": [F(360), F(720), F(1080), F(720)]}
        opts = quality.quality_options(info)
        self.assertEqual([o["id"] for o in opts], ["best", "1080", "720", "360"])
        self.assertEqual(opts[0]["label"], "Best available (1080p)")
        self.assertEqual(opts[2]["label"], "720p")

    def test_size_is_added_when_known(self):
        info = {"formats": [F(720, 12_000_000), F(360)]}
        labels = {o["id"]: o["label"] for o in quality.quality_options(info)}
        self.assertEqual(labels["720"], "720p (~12 MB)")
        self.assertEqual(labels["360"], "360p")

    def test_approximate_size_field_is_used_too(self):
        info = {"formats": [F(720, None, filesize_approx=24_000_000), F(360)]}
        labels = {o["id"]: o["label"] for o in quality.quality_options(info)}
        self.assertEqual(labels["720"], "720p (~24 MB)")

    def test_single_quality_returns_only_best(self):
        opts = quality.quality_options({"formats": [F(720)]})
        self.assertEqual(opts, [{"id": "best", "label": "Best available (720p)"}])

    def test_portrait_video_is_labelled_by_its_short_side(self):
        info = {"formats": [F(1920, width=1080), F(1280, width=720), F(640, width=360)]}
        opts = quality.quality_options(info)
        self.assertEqual([o["id"] for o in opts], ["best", "1080", "720", "360"])
        self.assertEqual(opts[0]["label"], "Best available (1080p)")

    def test_landscape_video_keeps_its_height(self):
        info = {"formats": [F(720, width=1280), F(360, width=640)]}
        self.assertEqual([o["id"] for o in quality.quality_options(info)], ["best", "720", "360"])

    def test_audio_only_or_missing_info_returns_empty(self):
        self.assertEqual(quality.quality_options({"formats": [{"height": None, "vcodec": "none"}]}), [])
        self.assertEqual(quality.quality_options({"formats": [F(480, vcodec="none")]}), [])
        self.assertEqual(quality.quality_options({}), [])
        self.assertEqual(quality.quality_options(None), [])


class Selector(unittest.TestCase):
    def test_best(self):
        self.assertEqual(quality.format_selector("best", False), "bestvideo+bestaudio/best")

    def test_a_chosen_height_does_not_change_the_selector(self):
        self.assertEqual(quality.format_selector("720", False), "bestvideo+bestaudio/best")

    def test_audio_only_ignores_height(self):
        self.assertEqual(quality.format_selector("best", True), "bestaudio/best")
        self.assertEqual(quality.format_selector("720", True), "bestaudio/best")

    def test_bad_values_are_errors(self):
        for bad in ("abc", "0", "-5", "", "720; rm", "1080p"):
            with self.assertRaises(ValueError):
                quality.format_selector(bad, False)


class Sort(unittest.TestCase):
    def test_best_has_no_sort(self):
        self.assertEqual(quality.format_sort("best"), [])

    def test_height_sorts_by_resolution_limit(self):
        self.assertEqual(quality.format_sort("720"), ["res:720"])

    def test_bad_values_are_errors(self):
        for bad in ("abc", "0", "-5", "", "720; rm", "1080p"):
            with self.assertRaises(ValueError):
                quality.format_sort(bad)


if __name__ == "__main__":
    unittest.main()

