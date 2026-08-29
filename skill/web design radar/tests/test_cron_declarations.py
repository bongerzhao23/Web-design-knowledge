import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "declare-crons.py"
SPEC = importlib.util.spec_from_file_location("declare_crons", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CronDeclarationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []

    def runner(self, argv):
        self.calls.append(argv)
        key = argv[argv.index("--declaration-key") + 1]
        return subprocess.CompletedProcess(argv, 0, json.dumps({"id": "job-" + key}), "")

    def test_declares_five_disabled_bounded_jobs(self):
        result = MODULE.declare_crons(self.root, self.runner, skill_root=SCRIPT.parents[1])
        self.assertEqual(len(self.calls), 5)
        expected = {
            "web-design-radar-coordinator": ("0 2 * * *", "1200"),
            "web-design-radar-worker-a": ("3 2-7 * * *", "3300"),
            "web-design-radar-worker-b": ("3 2-7 * * *", "3300"),
            "web-design-radar-closeout": ("30 8 * * *", "1200"),
            "web-design-radar-deadline": ("0 9 * * *", "1200"),
        }
        for call in self.calls:
            key = call[call.index("--declaration-key") + 1]
            self.assertEqual(call[:3], ["openclaw", "cron", "add"])
            self.assertEqual(call[3], expected[key][0])
            for flag in ("--disabled", "--exact", "--no-deliver"):
                self.assertIn(flag, call)
            self.assertEqual(call[call.index("--tz") + 1], "Asia/Shanghai")
            self.assertEqual(call[call.index("--timeout-seconds") + 1], expected[key][1])
            if "worker" in key or "coordinator" in key:
                self.assertEqual(call[call.index("--session") + 1], "isolated")
                self.assertIn("--message", call)
            else:
                self.assertIn("--command-argv", call)
                self.assertIn("--command-env", call)
        saved = json.loads((self.root / "state/automation.json").read_text())
        self.assertEqual(set(saved["declarations"]), set(expected))
        self.assertEqual(set(result), set(expected))

    def test_conflicting_existing_declaration_is_rejected_without_calls(self):
        state = self.root / "state"
        state.mkdir()
        (state / "automation.json").write_text(json.dumps({
            "declarations": {"web-design-radar-coordinator": {"id": "old", "sha256": "wrong"}}
        }))
        with self.assertRaisesRegex(ValueError, "declaration conflict"):
            MODULE.declare_crons(self.root, self.runner, skill_root=SCRIPT.parents[1])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
