import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import subtitles  # noqa: E402

SEGS = [{"start": 0, "end": 2.5, "text": " Hola "}, {"start": 2.5, "end": 4, "text": "Adiós"}]


class TimeFormats(unittest.TestCase):
    def test_srt_time(self):
        self.assertEqual(subtitles.fmt_srt_time(0), "00:00:00,000")
        self.assertEqual(subtitles.fmt_srt_time(3661.5), "01:01:01,500")

    def test_vtt_time(self):
        self.assertEqual(subtitles.fmt_vtt_time(3661.5), "01:01:01.500")

    def test_rounding_carries_into_seconds(self):
        self.assertEqual(subtitles.fmt_srt_time(1.9996), "00:00:02,000")

    def test_negative_is_clamped_to_zero(self):
        self.assertEqual(subtitles.fmt_srt_time(-3), "00:00:00,000")


class Srt(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            subtitles.to_srt(SEGS),
            "1\n00:00:00,000 --> 00:00:02,500\nHola\n\n2\n00:00:02,500 --> 00:00:04,000\nAdiós\n\n")

    def test_empty(self):
        self.assertEqual(subtitles.to_srt([]), "")

    def test_blank_line_inside_cue_is_collapsed(self):
        out = subtitles.to_srt([{"start": 0, "end": 1, "text": "a\n\nb"}])
        self.assertEqual(out, "1\n00:00:00,000 --> 00:00:01,000\na\nb\n\n")

    def test_empty_text_is_skipped_and_numbering_has_no_gap(self):
        segs = [{"start": 0, "end": 1, "text": "uno"}, {"start": 1, "end": 2, "text": "   "},
                {"start": 2, "end": 3, "text": "tres"}]
        out = subtitles.to_srt(segs)
        self.assertIn("2\n00:00:02,000 --> 00:00:03,000\ntres", out)
        self.assertNotIn("\n3\n", "\n" + out)

    def test_end_before_start_is_clamped_to_start(self):
        out = subtitles.to_srt([{"start": 5, "end": 3, "text": "x"}])
        self.assertIn("00:00:05,000 --> 00:00:05,000", out)


class Vtt(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            subtitles.to_vtt(SEGS),
            "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nHola\n\n00:00:02.500 --> 00:00:04.000\nAdiós\n\n")

    def test_empty(self):
        self.assertEqual(subtitles.to_vtt([]), "WEBVTT\n\n")

    def test_arrow_in_text_cannot_break_cue(self):
        out = subtitles.to_vtt([{"start": 0, "end": 1, "text": "a --> b"}])
        body = out.split("\n", 3)[3]  # after "WEBVTT", blank, timing line
        self.assertNotIn("-->", body)


if __name__ == "__main__":
    unittest.main()
