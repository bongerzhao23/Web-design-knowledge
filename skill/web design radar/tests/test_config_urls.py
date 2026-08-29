import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import import_package

import_package()

from web_design_radar.config import Settings
from web_design_radar.urls import canonicalize_url, domain_slug


class ConfigTest(unittest.TestCase):
    def test_environment_root_is_the_only_runtime_root(self):
        """Catches production writes that ignore WEB_DESIGN_RADAR_ROOT."""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"WEB_DESIGN_RADAR_ROOT": tmp}, clear=False
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.root, Path(tmp).resolve())
        self.assertEqual(settings.timezone, "Asia/Shanghai")
        self.assertEqual(settings.daily_quota, 2)
        self.assertEqual(
            settings.stage_order,
            ("observing", "extracting", "assets", "documenting", "validating"),
        )
        self.assertEqual(settings.deadline_hour, 9)
        self.assertEqual(settings.browser_preference, "ego-lite")
        self.assertEqual(settings.browser_fallback, "openclaw-chrome")


class UrlTest(unittest.TestCase):
    def test_canonicalization_normalizes_identity_and_drops_tracking(self):
        """Catches duplicate domains caused by scheme, www, fragments, or trackers."""
        self.assertEqual(
            canonicalize_url("HTTP://WWW.Example.COM/?utm_source=x#hero"),
            "https://example.com/",
        )

    def test_canonicalization_sorts_non_tracking_query_pairs(self):
        """Catches unstable identities when meaningful query order differs."""
        self.assertEqual(
            canonicalize_url("https://example.com/work?z=2&gclid=x&a=1"),
            "https://example.com/work?a=1&z=2",
        )

    def test_domain_slug_is_stable_for_subdomains(self):
        """Catches output-directory collisions caused by punctuation."""
        self.assertEqual(domain_slug("https://sub.example.com/work/"), "sub-example-com")

    def test_canonicalization_rejects_non_http_urls(self):
        """Catches unsafe or meaningless file and script URLs entering state."""
        for value in ("file:///tmp/page.html", "javascript:alert(1)", "example.com"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonicalize_url(value)


if __name__ == "__main__":
    unittest.main()
