import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from support import import_package

import_package()

from web_design_radar.assets import AssetManifest, publish_revision, record_download


class AssetManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "work"
        self.root.mkdir()

    def test_downloaded_asset_has_hash_mapping_and_redacted_public_url(self):
        """Catches unverifiable assets and leaked signed query values."""
        body = b"glTF-binary"
        record = record_download(
            staging_root=self.root,
            source_url="https://cdn.example/scene.glb?token=secret&variant=hero",
            relative_path="assets/models/scene.glb",
            body=body,
            mime_type="model/gltf-binary",
            used_by=["03-hero"],
        )

        self.assertEqual(record.type, "model")
        self.assertEqual(
            record.original_url,
            "https://cdn.example/scene.glb?token=REDACTED&variant=hero",
        )
        self.assertEqual(record.status, "downloaded")
        self.assertEqual(record.sha256, hashlib.sha256(body).hexdigest())
        self.assertEqual((self.root / record.local_path).read_bytes(), body)

    def test_over_limit_asset_is_metadata_only(self):
        """Catches unbounded model or video downloads."""
        manifest = AssetManifest(self.root, max_file_bytes=10, max_revision_bytes=20)
        record = manifest.plan(
            source_url="https://cdn.example/movie.mp4",
            content_length=11,
            mime_type="video/mp4",
            used_by=["03-hero"],
        )
        self.assertEqual(record.status, "metadata-only")
        self.assertEqual(record.reason, "file-size-limit")
        self.assertIsNone(record.local_path)

    def test_path_traversal_and_absolute_paths_fail_before_write(self):
        """Catches target resources escaping the run staging directory."""
        outside = self.root.parent / "outside.glb"
        for path in ("../outside.glb", str(outside)):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    record_download(
                        self.root,
                        "https://cdn.example/scene.glb",
                        path,
                        b"body",
                        "model/gltf-binary",
                        ["03-hero"],
                    )
        self.assertFalse(outside.exists())

    def test_symlink_parent_is_rejected(self):
        """Catches asset writes redirected through a staging symlink."""
        outside = self.root.parent / "outside"
        outside.mkdir()
        (self.root / "assets").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            record_download(
                self.root,
                "https://cdn.example/scene.glb",
                "assets/scene.glb",
                b"body",
                "model/gltf-binary",
                ["03-hero"],
            )
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_write_is_machine_readable_and_stable(self):
        """Catches nondeterministic manifests that break idempotent publication."""
        manifest = AssetManifest(self.root)
        manifest.add(
            record_download(
                self.root,
                "https://cdn.example/scene.glb",
                "assets/models/scene.glb",
                b"body",
                "model/gltf-binary",
                ["03-hero"],
            )
        )
        first = manifest.write()
        first_bytes = first.read_bytes()
        second = manifest.write()
        self.assertEqual(first_bytes, second.read_bytes())
        self.assertEqual(json.loads(first_bytes)["assets"][0]["usedBy"], ["03-hero"])


class AtomicPublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.final = self.root / "sites" / "example-com" / "revisions" / "2026-08-29"

    def staging(self, name, content=b"overview"):
        staging = self.root / "state" / "runs" / name / "revision"
        staging.mkdir(parents=True)
        (staging / "overview.md").write_bytes(content)
        return staging

    def test_publish_moves_complete_revision_and_writes_manifest_last(self):
        """Catches partially visible case packs."""
        staging = self.staging("run-a")
        result = publish_revision(staging, self.final, {"runId": "run-a"})
        self.assertEqual(result, self.final)
        self.assertFalse(staging.exists())
        manifest = json.loads((self.final / "run-manifest.json").read_text())
        self.assertEqual(manifest["files"]["overview.md"], hashlib.sha256(b"overview").hexdigest())

    def test_same_content_is_idempotent_but_different_content_never_overwrites(self):
        """Catches revision retries clobbering previously published evidence."""
        publish_revision(self.staging("run-a"), self.final, {"runId": "run-a"})
        duplicate = self.staging("run-b")
        self.assertEqual(
            publish_revision(duplicate, self.final, {"runId": "run-a"}),
            self.final,
        )
        self.assertTrue(duplicate.exists())

        different = self.staging("run-c", b"different")
        with self.assertRaises(FileExistsError):
            publish_revision(different, self.final, {"runId": "run-a"})
        self.assertEqual((self.final / "overview.md").read_bytes(), b"overview")


if __name__ == "__main__":
    unittest.main()
