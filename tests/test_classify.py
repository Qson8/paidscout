import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paidscout import classify_offline, is_big, fmt_delta, free_earners, window_trend, DEFAULT_CONFIG

POS = DEFAULT_CONFIG["offline_positive"]
NEG = DEFAULT_CONFIG["offline_negative"]
BIG = DEFAULT_CONFIG["big_companies"]

class TestClassifyOffline(unittest.TestCase):
    def test_pure_offline(self):
        self.assertEqual(classify_offline(
            "Play completely offline. No wifi needed, single player, no ads.", POS, NEG), "offline")

    def test_offline_chinese(self):
        self.assertEqual(classify_offline("无需联网，单机游戏，本地存档。", POS, NEG), "offline")

    def test_online_leaning(self):
        self.assertEqual(classify_offline(
            "Online multiplayer battles. Requires internet. Live streaming events.", POS, NEG), "online-leaning")

    def test_unknown(self):
        self.assertEqual(classify_offline("A nice app for everyone.", POS, NEG), "unknown")

    def test_big_company(self):
        self.assertTrue(is_big("Mojang AB", BIG))
        self.assertTrue(is_big("Shenzhen Tencent Tianyou Technology Ltd", BIG))
        self.assertTrue(is_big("X.D. Network Inc.", BIG))
        self.assertTrue(is_big("East2west Network Tech. Co. Ltd.", BIG))
        self.assertTrue(is_big("Bandai Namco Entertainment Inc.", BIG))
        self.assertFalse(is_big("Seungyun Kim", BIG))
        self.assertFalse(is_big("", BIG))

class TestFmtDelta(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(fmt_delta(123), "+123")

    def test_negative_is_annotated_not_broken(self):
        out = fmt_delta(-123)
        self.assertNotIn("+-", out)
        self.assertIn("version reset", out)

    def test_none(self):
        self.assertEqual(fmt_delta(None), "—")

class TestFreeEarners(unittest.TestCase):
    def setUp(self):
        self.meta = {
            "1": {"price": 0, "trackName": "Free Earner", "sellerName": "Indie Dev",
                  "averageUserRating": 4.5, "userRatingCount": 1200,
                  "primaryGenreName": "Utilities", "description": "offline tool"},
            "2": {"price": 2.99, "trackName": "Paid App", "sellerName": "Someone",
                  "averageUserRating": 4.0, "userRatingCount": 50,
                  "primaryGenreName": "Games", "description": ""},
            "3": {"price": 0, "trackName": "Free NoFreeChart", "sellerName": "Duo",
                  "averageUserRating": 4.2, "userRatingCount": 88,
                  "primaryGenreName": "Education", "description": ""},
        }
        self.grossing = {"1": 5, "2": 3, "3": 9, "4": 1}
        self.free = {"1": 12}

    def test_only_free_price_kept(self):
        out = free_earners(self.grossing, self.free, self.meta)
        self.assertEqual([r["app_id"] for r in out], ["1", "3"])

    def test_sorted_by_grossing_rank(self):
        out = free_earners(self.grossing, self.free, self.meta)
        self.assertEqual([r["grank"] for r in out], [5, 9])

    def test_free_chart_rank_annotated(self):
        out = free_earners(self.grossing, self.free, self.meta)
        self.assertEqual(out[0]["frank"], 12)
        self.assertIsNone(out[1]["frank"])

    def test_missing_meta_skipped(self):
        out = free_earners(self.grossing, self.free, self.meta)
        self.assertNotIn("4", [r["app_id"] for r in out])

class TestWindowTrend(unittest.TestCase):
    def test_too_thin(self):
        self.assertIsNone(window_trend([]))
        self.assertIsNone(window_trend([("2026-11-07", 100)]))
        self.assertIsNone(window_trend([("2026-11-07", 100), ("2026-11-06", 99)]))

    def test_short_history_uses_real_span(self):
        rows = [("2026-11-07", 160), ("2026-11-02", 100)]
        v, span = window_trend(rows)
        self.assertEqual(span, 5)
        self.assertAlmostEqual(v, 12.0)

    def test_30d_window_preferred_over_7d(self):
        rows = [("2026-11-07", 1000), ("2026-10-31", 940), ("2026-10-08", 400), ("2026-10-01", 380)]
        v, span = window_trend(rows)
        self.assertEqual(span, 30)
        self.assertAlmostEqual(v, 20.0)

    def test_7d_when_only_10_days(self):
        rows = [("2026-11-07", 500), ("2026-10-31", 430), ("2026-10-28", 400)]
        v, span = window_trend(rows)
        self.assertEqual(span, 7)
        self.assertAlmostEqual(v, 10.0)

if __name__ == "__main__":
    unittest.main()
