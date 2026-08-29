import json
import os
import subprocess
import sys
import tempfile
import unittest
import sqlite3
from pathlib import Path

from test_validation_reporting import write_case


SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL / "scripts" / "web-design-radar.py"
FIXTURE = SKILL / "tests" / "fixtures" / "candidates.json"


def run_cli(*arguments, root):
    environment = os.environ.copy()
    environment["WEB_DESIGN_RADAR_ROOT"] = str(root)
    return subprocess.run(
        [sys.executable, str(CLI), *arguments],
        text=True,
        capture_output=True,
        env=environment,
        cwd=SKILL.parents[1],
    )


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def init(self):
        result = run_cli("init", "--json", root=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "initialized")

    def test_init_and_daily_claim_are_single_json_objects(self):
        """Catches cron parsing failures caused by logs mixed into stdout."""
        self.init()
        started = run_cli(
            "start-batch",
            "--date", "2026-08-29",
            "--candidates", str(FIXTURE),
            "--now", "2026-08-29T02:00:00+08:00",
            "--json",
            root=self.root,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(len(json.loads(started.stdout)["runs"]), 2)
        self.assertEqual(started.stdout.count("\n"), 1)

        claimed = run_cli(
            "claim-stage",
            "--slot", "A",
            "--owner", "worker-a",
            "--now", "2026-08-29T02:03:00+08:00",
            "--json",
            root=self.root,
        )
        payload = json.loads(claimed.stdout)
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        self.assertEqual(payload["claim"]["stage"], "observing")
        self.assertEqual(payload["claim"]["browserPreference"], "ego-lite")

    def test_late_claim_is_successful_idle(self):
        """Catches deadline enforcement being treated as a cron error."""
        self.init()
        run_cli(
            "start-batch", "--date", "2026-08-29", "--candidates", str(FIXTURE),
            "--now", "2026-08-29T02:00:00+08:00", "--json", root=self.root,
        )
        result = run_cli(
            "claim-stage", "--slot", "B", "--owner", "late",
            "--now", "2026-08-29T09:00:00+08:00", "--json", root=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "idle", "claim": None})

    def test_one_off_is_separate_from_daily_quota_and_idempotent(self):
        """Catches manual URL analysis consuming or duplicating daily slots."""
        self.init()
        arguments = (
            "start-one-off", "--url", "https://manual.example",
            "--source-url", "https://www.awwwards.com/sites/manual",
            "--now", "2026-08-30T10:00:00+08:00", "--json",
        )
        first = json.loads(run_cli(*arguments, root=self.root).stdout)
        second = json.loads(run_cli(*arguments, root=self.root).stdout)
        self.assertEqual(first["run"]["runId"], second["run"]["runId"])
        self.assertEqual(first["run"]["slot"], "M")
        status = json.loads(run_cli("status", "--json", root=self.root).stdout)
        self.assertEqual(status["dailyRuns"], 0)
        self.assertEqual(status["oneOffRuns"], 1)

    def test_contract_error_is_one_json_object_and_exit_two(self):
        """Catches tracebacks leaking into machine-readable cron output."""
        self.init()
        result = run_cli("claim-stage", "--slot", "Z", "--owner", "x", "--json", root=self.root)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "error")
        self.assertEqual(result.stdout.count("\n"), 1)
        self.assertEqual(result.stderr, "")

    def test_record_asset_imports_public_file_into_claimed_run_manifest(self):
        """Catches worker assets being left outside the durable case pack."""
        self.init()
        started = json.loads(run_cli(
            "start-batch", "--date", "2026-08-29", "--candidates", str(FIXTURE),
            "--now", "2026-08-29T02:00:00+08:00", "--json", root=self.root,
        ).stdout)
        run_id = started["runs"][0]["runId"]
        downloaded = self.root / "download.glb"
        downloaded.write_bytes(b"glTF")

        result = run_cli(
            "record-asset", "--run-id", run_id,
            "--source-url", "https://cdn.example/scene.glb?token=secret",
            "--input-file", str(downloaded),
            "--local-path", "assets/models/scene.glb",
            "--mime", "model/gltf-binary", "--used-by", "03-hero", "--json",
            root=self.root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["asset"]["type"], "model")
        self.assertIn("token=REDACTED", payload["asset"]["originalUrl"])
        staging = Path(started["runs"][0]["stagingDir"])
        self.assertEqual((staging / "assets/models/scene.glb").read_bytes(), b"glTF")
        manifest = json.loads((staging / "asset-manifest.json").read_text())
        self.assertEqual(len(manifest["assets"]), 1)

    def test_finalize_one_off_command_publishes_only_the_requested_manual_run(self):
        """Catches a CLI that can create one-off runs but cannot publish them."""
        self.init()
        started = json.loads(run_cli(
            "start-one-off", "--url", "https://manual.example",
            "--source-url", "https://manual.example",
            "--now", "2026-08-30T10:00:00+08:00", "--json", root=self.root,
        ).stdout)["run"]
        write_case(Path(started["stagingDir"]))
        database = sqlite3.connect(self.root / "state/radar.sqlite3")
        database.execute(
            "UPDATE site_runs SET state='ready_to_publish',current_stage='validating' WHERE run_id=?",
            (started["runId"],),
        )
        database.commit()
        database.close()

        result = run_cli(
            "finalize-one-off", "--run-id", started["runId"],
            "--now", "2026-08-30T10:30:00+08:00", "--json", root=self.root,
        )
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["published"])
        self.assertTrue(Path(payload["outputPath"]).is_dir())


if __name__ == "__main__":
    unittest.main()
