import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "capture"))
import capture_lib as L  # noqa: E402


class ConsentLabelTest(unittest.TestCase):
    def test_accept_labels_in_many_languages(self):
        for label in ("ACCEPT", "Accept all cookies", "Tout accepter", "Alle akzeptieren", "Aceptar", "同意", "接受全部", "Got it!", "OK", "すべて同意"):
            self.assertTrue(L.is_accept_label(label), label)

    def test_never_clicks_login_or_subscribe(self):
        for label in ("Log in", "Sign up and accept", "Subscribe", "Accept and subscribe", "登录", "订阅", "S'abonner"):
            self.assertFalse(L.is_accept_label(label), label)

    def test_rejects_unrelated_long_text(self):
        self.assertFalse(L.is_accept_label("Book a call"))
        self.assertFalse(L.is_accept_label("accept " + "x" * 50))

    def test_consent_context(self):
        self.assertTrue(L.is_consent_context("We use audience measurement and advertising cookies"))
        self.assertTrue(L.is_consent_context("我们使用 Cookie 与隐私设置"))
        self.assertFalse(L.is_consent_context("Most brands produce content"))


class AssetHelpersTest(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(L.classify("https://x/a/scene.glb?v=2"), "model")
        self.assertEqual(L.classify("https://x/f.woff2"), "font")
        self.assertEqual(L.classify("https://x/v.mp4"), "video")
        self.assertEqual(L.classify("https://x/stream", "video/mp4"), "video")
        self.assertIsNone(L.classify("https://x/app.js", "text/javascript", "script"))

    def test_redact(self):
        self.assertEqual(L.redact("https://x/v.mp4?token=abc&w=1"), "https://x/v.mp4?token=REDACTED&w=1")

    def test_range_plan(self):
        self.assertEqual(L.range_plan(10, 100)["action"], "download")
        self.assertEqual(L.range_plan(None, 100)["action"], "stream-with-cap")
        self.assertEqual(L.range_plan(1000, 100)["action"], "metadata-only")

    def test_effective_fps(self):
        self.assertEqual(L.effective_fps(150, 6.0), 25.0)


class SectionChoiceTest(unittest.TestCase):
    def block(self, top, height, **kw):
        return {"top": top, "height": height, "width_ratio": kw.pop("w", 1.0), "semantic": kw.pop("semantic", True),
                "depth": kw.pop("depth", 1), "bg": kw.pop("bg", "white"), "selector": f"#s{top}", **kw}

    def test_orders_dedupes_nested_and_drops_containers(self):
        c = [self.block(0, 5000, depth=0), self.block(0, 900), self.block(0, 880, depth=2),
             self.block(900, 1200, bg="black"), self.block(2100, 900, bg="red")]
        out = L.choose_sections(c, 3000, 900, 6)
        self.assertEqual([s["top"] for s in out], [0, 900, 2100])
        self.assertEqual([s["order"] for s in out], [1, 2, 3])

    def test_drops_narrow_and_short_blocks(self):
        c = [self.block(0, 900), self.block(900, 100), self.block(1000, 900, w=0.5), self.block(1900, 900, bg="x")]
        self.assertEqual([s["top"] for s in L.choose_sections(c, 2800, 900, 6)], [0, 1900])

    def test_merges_short_same_background_followers(self):
        c = [self.block(0, 900, bg="black"), self.block(900, 400, bg="black"), self.block(1300, 900, bg="white")]
        out = L.choose_sections(c, 2200, 900, 6)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["height"], 1300)

    def test_negative_top_is_clipped_so_next_section_survives(self):
        c = [self.block(-900, 2700), self.block(900, 1264, bg="black")]
        out = L.choose_sections(c, 4000, 900, 6)
        self.assertEqual([(s["top"], s["height"]) for s in out], [(0, 900), (900, 1264)])

    def test_falls_back_to_viewport_slices(self):
        out = L.choose_sections([], 2700, 900, 6)
        self.assertEqual(len(out), 3)
        self.assertIsNone(out[0]["selector"])

    def test_respects_max_sections(self):
        c = [self.block(i * 900, 900, bg=str(i)) for i in range(10)]
        self.assertEqual(len(L.choose_sections(c, 9000, 900, 4)), 4)


if __name__ == "__main__":
    unittest.main()
