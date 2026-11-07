import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from paidscout import classify_offline, is_big, DEFAULT_CONFIG

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
        self.assertFalse(is_big("Seungyun Kim", BIG))
        self.assertFalse(is_big("", BIG))

if __name__ == "__main__":
    unittest.main()
