import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from painscout import (classify_text, is_noise_only, score_cluster,
                       deidentify, TAXONOMY, DEFAULT_CONFIG)

class TestClassifyText(unittest.TestCase):
    def test_subscription_opaque_en(self):
        cats, _ = classify_text(
            "I signed up for a free trial and they charged me for a full year. "
            "Customer service refused to refund it.")
        self.assertIn("sub_opaque", cats)

    def test_subscription_opaque_zh(self):
        cats, _ = classify_text("一打开就要求绑定免密支付，试用就扣了我198，退不了款。")
        self.assertIn("sub_opaque", cats)

    def test_plan_rigid_from_section0_quote(self):
        # Section-0 card D-3's de-identified quote must classify as plan rigidity.
        cats, _ = classify_text(
            "The only way you can edit payments or extra payments is by "
            "resetting your data entirely.")
        self.assertIn("plan_rigid", cats)

    def test_credits_expiry_zh(self):
        # Section-0 card C-2's core complaint.
        cats, sig = classify_text("按张买还限时，过期就清零，我真金白银买的，为什么不还给我")
        self.assertIn("credits_wall", cats)
        self.assertTrue(sig["payment"])

    def test_ai_aversion(self):
        cats, _ = classify_text("The new AI coach and AI voice narrations ruined it for me.")
        self.assertIn("ai_aversion", cats)
        cats_zh, _ = classify_text("换成AI配音之后完全没法听，像机器人念经。")
        self.assertIn("ai_aversion", cats_zh)

    def test_forced_flow_from_section0_quote(self):
        cats, _ = classify_text(
            "Logging on requires me to answer 1 million questions about my "
            "goals before I can even meditate.")
        self.assertIn("forced_flow", cats)

    def test_trust_export_lockin_zh(self):
        cats, _ = classify_text("数据就放在我自己手机上，导出还要开会员，吃相是真难看。")
        self.assertIn("trust_data", cats)

    def test_gen_fail_zh(self):
        cats, _ = classify_text("冲了10块钱，总说图片不符合范围，又不给我说原因。")
        self.assertIn("gen_fail", cats)

    def test_harvested_auto_deduct(self):
        # Real first-run phrasing (Headspace, 2026-11-08).
        cats, _ = classify_text(
            "A spam that auto-deducts your money as you download it, no "
            "matter you sign up for its membership or not.")
        self.assertIn("sub_opaque", cats)

    def test_harvested_credits_double_limit_zh(self):
        # Real first-run phrasing (PixCake, 2026-11-08).
        cats, _ = classify_text(
            "收费还要双重限制，限制时间限制张数，按张数购买还限定使用时间，霸王条款。")
        self.assertIn("credits_wall", cats)

    def test_harvested_ai_chatbot(self):
        cats, _ = classify_text(
            "They added the AI chat bot that they wanted you to use like a therapist.")
        self.assertIn("ai_aversion", cats)

    def test_harvested_cancelled_still_billed(self):
        cats, _ = classify_text("Cancelled, still billed — I cancelled and "
                                "just received a bill for the month.")
        self.assertIn("sub_opaque", cats)

    def test_harvested_gen_fail_95_zh(self):
        cats, _ = classify_text("为什么每次到进度95就失败？？？生成不了啊")
        self.assertIn("gen_fail", cats)

    def test_neutral_text_no_classes(self):
        cats, sig = classify_text("I love this app, it helps me relax every evening.")
        self.assertEqual(cats, set())
        self.assertFalse(sig["workaround"])

class TestSignals(unittest.TestCase):
    def test_workaround_en(self):
        _, sig = classify_text("Gave up and went back to my excel spreadsheet.")
        self.assertTrue(sig["workaround"])

    def test_workaround_zh(self):
        _, sig = classify_text("没办法，只能用备忘录凑合记每一笔。")
        self.assertTrue(sig["workaround"])

    def test_payment_language(self):
        _, sig = classify_text("I would pay for a one-time purchase, just not a subscription.")
        self.assertTrue(sig["payment"])

    def test_unresolved(self):
        _, sig = classify_text("Still can't export after the update, it never fixed anything.")
        self.assertTrue(sig["unresolved"])

class TestNoise(unittest.TestCase):
    def test_pure_price_rage_short_is_noise(self):
        text = "Too expensive!! greedy rip-off"
        cats, sig = classify_text(text)
        self.assertTrue(is_noise_only(text, cats, sig))

    def test_price_rage_with_workaround_not_noise(self):
        text = ("Too expensive and greedy — I keep my own excel spreadsheet "
                "to track everything instead, it works fine for me.")
        cats, sig = classify_text(text)
        self.assertFalse(is_noise_only(text, cats, sig))

    def test_detailed_complaint_not_noise(self):
        text = ("They charged me after the free trial converted and support "
                "refused to refund — the cancel flow is deliberately hidden "
                "three menus deep so nobody can find it in time.")
        cats, sig = classify_text(text)
        self.assertFalse(is_noise_only(text, cats, sig))

class TestScoreCluster(unittest.TestCase):
    def test_full_marks(self):
        sc = score_cluster(count=25, workaround_hits=3, payment_hits=2,
                           apps_hit=3, unresolved_hits=2, noise_hits=0)
        self.assertEqual(sc, {"freq": 2, "intensity": 2, "unmet": 2, "total": 6})

    def test_card_threshold(self):
        # freq 1 (6 hits) + intensity 1 (one workaround) + unmet 2
        # (cross-app resonance AND an unresolved marker) = 4 -> card.
        sc = score_cluster(count=6, workaround_hits=1, payment_hits=0,
                           apps_hit=2, unresolved_hits=1, noise_hits=1)
        self.assertEqual(sc["total"], 4)
        # Same cluster without the unresolved marker stays at 3 (observed).
        sc = score_cluster(count=6, workaround_hits=1, payment_hits=0,
                           apps_hit=2, unresolved_hits=0, noise_hits=1)
        self.assertEqual(sc["total"], 3)

    def test_small_cluster_scores_low(self):
        sc = score_cluster(count=2, workaround_hits=0, payment_hits=0,
                           apps_hit=1, unresolved_hits=0, noise_hits=3)
        self.assertEqual(sc["total"], 0)

    def test_unmet_needs_resonance_or_repetition(self):
        sc = score_cluster(count=12, workaround_hits=0, payment_hits=0,
                           apps_hit=1, unresolved_hits=1, noise_hits=0)
        self.assertEqual(sc["unmet"], 1)
        sc2 = score_cluster(count=12, workaround_hits=0, payment_hits=0,
                            apps_hit=1, unresolved_hits=0, noise_hits=0)
        self.assertEqual(sc2["unmet"], 0)

    def test_resonance_alone_lifts_unmet_to_one(self):
        sc = score_cluster(count=5, workaround_hits=0, payment_hits=0,
                           apps_hit=3, unresolved_hits=0, noise_hits=0)
        self.assertEqual(sc["unmet"], 1)

class TestDeidentify(unittest.TestCase):
    def test_strips_url_and_email(self):
        out = deidentify("broken, see https://example.com/x or mail me a@b.com please")
        self.assertNotIn("example.com", out)
        self.assertNotIn("a@b.com", out)

    def test_truncates(self):
        out = deidentify("x" * 500, limit=140)
        self.assertEqual(len(out), 140)

    def test_collapses_whitespace(self):
        self.assertEqual(deidentify("a\n\n  b\tc"), "a b c")

class TestSeedConfig(unittest.TestCase):
    def test_three_categories_with_apps(self):
        keys = [c["key"] for c in DEFAULT_CONFIG["categories"]]
        self.assertEqual(keys, ["meditation", "debt", "kidsdraw"])
        for c in DEFAULT_CONFIG["categories"]:
            self.assertGreaterEqual(len(c["apps"]), 2)
            for app_id, cc, _label in c["apps"]:
                self.assertTrue(app_id.isdigit(), app_id)
                self.assertIn(cc, ("us", "cn"))

    def test_taxonomy_has_eight_classes(self):
        self.assertEqual(len(TAXONOMY), 8)

if __name__ == "__main__":
    unittest.main()
