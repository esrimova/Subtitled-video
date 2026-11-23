import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import steps  # noqa: E402

R = steps.resolve_outputs


class Resolve(unittest.TestCase):
    def test_video_only_url(self):
        r = R({"video"}, False, "url")
        self.assertEqual(r["keep"], ["video"])
        self.assertEqual(r["temporary"], [])
        self.assertEqual(r["pipeline"], ["download"])
        self.assertFalse(r["audio_only_download"])

    def test_audio_only_url_downloads_audio_only(self):
        r = R({"audio"}, False, "url")
        self.assertEqual(r["keep"], ["audio"])
        self.assertEqual(r["pipeline"], ["download", "audio"])
        self.assertTrue(r["audio_only_download"])

    def test_audio_from_file_has_no_download_step(self):
        r = R({"audio"}, False, "file")
        self.assertEqual(r["pipeline"], ["audio"])
        self.assertFalse(r["audio_only_download"])

    def test_video_from_file_needs_no_pipeline_steps(self):
        r = R({"video"}, False, "file")
        self.assertEqual(r["keep"], ["video"])
        self.assertEqual(r["pipeline"], [])

    def test_transcript_alone_uses_temporary_audio(self):
        r = R({"transcript"}, False, "url")
        self.assertEqual(r["keep"], ["transcript"])
        self.assertEqual(r["temporary"], ["audio"])
        self.assertEqual(r["pipeline"], ["download", "audio", "transcribe"])
        self.assertTrue(r["audio_only_download"])
        self.assertTrue(any("not kept" in n for n in r["notes"]))

    def test_transcript_plus_audio_keeps_audio(self):
        r = R({"transcript", "audio"}, False, "url")
        self.assertEqual(r["keep"], ["audio", "transcript"])
        self.assertEqual(r["temporary"], [])

    def test_replay_only_keeps_just_the_html(self):
        r = R({"replay"}, False, "url")
        self.assertEqual(r["keep"], ["replay"])
        self.assertEqual(r["temporary"], ["audio", "video"])
        self.assertEqual(r["pipeline"], ["download", "audio", "transcribe", "captions"])
        self.assertFalse(r["audio_only_download"])
        self.assertTrue(r["video_needed"])
        self.assertTrue(any("single HTML" in n for n in r["notes"]))

    def test_replay_plus_video_keeps_both(self):
        r = R({"replay", "video"}, False, "file")
        self.assertEqual(r["keep"], ["video", "replay"])
        self.assertEqual(r["temporary"], ["audio"])

    def test_video_needed_only_for_video_or_replay(self):
        self.assertFalse(R({"transcript"}, False, "url")["video_needed"])
        self.assertTrue(R({"video"}, False, "url")["video_needed"])

    def test_everything_in_canonical_order(self):
        r = R({"replay", "transcript", "audio", "video"}, False, "url")
        self.assertEqual(r["keep"], ["video", "audio", "transcript", "replay"])
        self.assertEqual(r["temporary"], [])

    def test_no_audio_allows_video_only(self):
        r = R({"video"}, True, "url")
        self.assertEqual(r["pipeline"], ["download"])

    def test_no_audio_refuses_audio_transcript_replay(self):
        for sel in ({"audio"}, {"transcript"}, {"replay"}, {"video", "audio"}):
            with self.assertRaises(ValueError):
                R(sel, True, "url")

    def test_empty_and_unknown_are_errors(self):
        with self.assertRaises(ValueError):
            R(set(), False, "url")
        with self.assertRaises(ValueError):
            R({"video", "gif"}, False, "url")
        with self.assertRaises(ValueError):
            R({"video"}, False, "ftp")


class Eta(unittest.TestCase):
    def test_hidden_until_enough_progress(self):
        self.assertIsNone(steps.estimate_eta(0, 10))
        self.assertIsNone(steps.estimate_eta(0.05, 10))
        self.assertIsNone(steps.estimate_eta(0.10, 4.9))

    def test_estimates(self):
        self.assertEqual(steps.estimate_eta(0.5, 30), 30)
        self.assertEqual(steps.estimate_eta(0.25, 10), 30)
        self.assertEqual(steps.estimate_eta(0.1, 5), 45)
        self.assertEqual(steps.estimate_eta(1.0, 50), 0)

    def test_fraction_above_one_is_clamped(self):
        self.assertEqual(steps.estimate_eta(1.2, 50), 0)


if __name__ == "__main__":
    unittest.main()
