import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from main import get_channel_name, get_group, match_master_channel, parse_m3u, build_playlist, Channel


class ParserTests(unittest.TestCase):
    def test_channel_name_with_attributes(self):
        extinf = '#EXTINF:-1 tvg-id="x" group-title="News",CNN Türk HD'
        self.assertEqual(get_channel_name(extinf), "CNN Türk HD")

    def test_group(self):
        self.assertEqual(get_group('#EXTINF:-1 group-title="Xeber",TRT Haber'), "Xeber")
        self.assertEqual(get_group('#EXTINF:-1,Unknown'), "unsorted")

    def test_parse_m3u(self):
        data = "#EXTM3U\n#EXTINF:-1,AzTV\nhttps://example.com/live.m3u8\n"
        result = parse_m3u(data, 0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].url, "https://example.com/live.m3u8")

    def test_arb_24_not_arb_tv(self):
        key, data = match_master_channel("ARB 24 HD")
        self.assertEqual(key, "arb 24")
        self.assertEqual(data["name"], "ARB 24")

    def test_blocked_terms(self):
        self.assertEqual(match_master_channel("beIN Sports 1")[0], "BLOCKED")

    def test_stable_playlist_structure(self):
        channel = Channel("aztv", "Azerbaycan", "AzTV", "AzTV.az",
                          "https://example.com/a.m3u8", 0, 0)
        playlist = build_playlist([channel])
        self.assertTrue(playlist.startswith("#EXTM3U\n"))
        self.assertIn('tvg-id="AzTV.az"', playlist)
        self.assertTrue(playlist.endswith("https://example.com/a.m3u8\n"))


if __name__ == "__main__":
    unittest.main()
