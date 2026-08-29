import tempfile
import unittest
from pathlib import Path

from support import import_package

import_package()

from web_design_radar.db import connect
from web_design_radar.migrations import migrate
from web_design_radar.runs import RunStore
from web_design_radar.scoring import Candidate


class RunStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.db = connect(self.root / "state" / "radar.sqlite3")
        self.addCleanup(self.db.close)
        migrate(self.db)
        self.store = RunStore(self.db, self.root)

    @staticmethod
    def candidates():
        return [
            Candidate("https://a.example", "https://awwwards.com/a", "A", 1, 1, 1, 1, 1, ("webgl",)),
            Candidate("https://b.example", "https://awwwards.com/b", "B", .9, .9, .9, .9, .9, ("gsap",)),
        ]

    def test_repeat_start_returns_same_two_slot_bound_runs(self):
        """Catches cron retries that create more than two site runs."""
        first = self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        second = self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:10:00+08:00"
        )

        self.assertEqual([run.run_id for run in first], [run.run_id for run in second])
        self.assertEqual([run.slot for run in first], ["A", "B"])
        self.assertEqual(len(self.store.get_batch("2026-08-29")), 2)

    def test_batch_rejects_any_count_other_than_two(self):
        """Catches partial candidate input silently reducing daily output."""
        with self.assertRaisesRegex(ValueError, "exactly two"):
            self.store.start_batch(
                "2026-08-29", self.candidates()[:1], "2026-08-29T02:00:00+08:00"
            )
        self.assertEqual(self.store.get_batch("2026-08-29"), [])

    def test_batch_rejects_duplicate_canonical_domains_atomically(self):
        """Catches domain aliases bypassing the two-unique-site invariant."""
        duplicates = [
            self.candidates()[0],
            Candidate("https://www.a.example/work", "https://awwwards.com/a2", "A2", 1, 1, 1, 1, 1, ("gsap",)),
        ]
        with self.assertRaisesRegex(ValueError, "unique"):
            self.store.start_batch(
                "2026-08-29", duplicates, "2026-08-29T02:00:00+08:00"
            )
        self.assertEqual(self.store.get_batch("2026-08-29"), [])

    def test_new_runs_have_private_stage_directories_and_observing_state(self):
        """Catches workers writing directly into final revision directories."""
        runs = self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        for run in runs:
            self.assertEqual(run.state, "assigned")
            self.assertEqual(run.current_stage, "observing")
            self.assertEqual(run.staging_dir, self.root / "state" / "runs" / run.run_id / "work")
            self.assertTrue(run.staging_dir.is_dir())

    def test_delivery_folder_uses_date_time_and_site_name(self):
        """Catches opaque sites/<slug>/revisions/<date> output paths."""
        runs = self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )

        self.assertEqual(runs[0].revision_dir, self.root / "2026-08-29_02-00_A")
        self.assertEqual(runs[1].revision_dir, self.root / "2026-08-29_02-00_B")

    def test_one_off_delivery_folder_uses_timestamp_and_domain_name(self):
        """Catches a one-off result losing its capture time or recognizable site name."""
        run = self.store.start_one_off(
            Candidate(
                "https://www.noth.in/", "https://www.noth.in/", "https://www.noth.in/",
                1, 1, 1, 1, 1, tuple(),
            ),
            "2026-08-28T03:17:00+08:00",
        )

        self.assertEqual(run.revision_dir, self.root / "2026-08-28_03-17_noth-in")

    def test_slots_claim_distinct_runs_and_unexpired_lease_blocks_duplicate(self):
        """Catches concurrent workers sharing a site or duplicate stage ownership."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        claim_a = self.store.claim_stage("A", "worker-a", "2026-08-29T02:03:00+08:00")
        claim_b = self.store.claim_stage("B", "worker-b", "2026-08-29T02:03:00+08:00")

        self.assertEqual((claim_a.slot, claim_a.stage), ("A", "observing"))
        self.assertEqual((claim_b.slot, claim_b.stage), ("B", "observing"))
        self.assertNotEqual(claim_a.run_id, claim_b.run_id)
        self.assertIsNone(
            self.store.claim_stage("A", "other", "2026-08-29T02:04:00+08:00")
        )

    def test_successful_submission_advances_one_stage_without_skipping(self):
        """Catches workers jumping directly from observation to documentation."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        claim = self.store.claim_stage("A", "worker-a", "2026-08-29T02:03:00+08:00")
        self.store.submit_stage(
            claim.run_id,
            "observing",
            "worker-a",
            {"status": "ok", "taskSpaceId": "42"},
            "2026-08-29T02:20:00+08:00",
        )

        next_claim = self.store.claim_stage(
            "A", "worker-a2", "2026-08-29T03:03:00+08:00"
        )
        self.assertEqual(next_claim.stage, "extracting")
        self.assertEqual(next_claim.task_space_id, "42")

    def test_chrome_fallback_requires_a_persisted_reason(self):
        """Catches silent replacement of ego-lite with Chrome."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        claim = self.store.claim_stage("A", "worker-a", "2026-08-29T02:03:00+08:00")
        with self.assertRaisesRegex(ValueError, "browserFallbackReason"):
            self.store.submit_stage(
                claim.run_id,
                claim.stage,
                "worker-a",
                {"status": "ok", "browserUsed": "openclaw-chrome"},
                "2026-08-29T02:20:00+08:00",
            )

    def test_claim_at_deadline_is_idle(self):
        """Catches browser acquisition continuing at or after 09:00."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        self.assertIsNone(
            self.store.claim_stage("B", "late", "2026-08-29T09:00:00+08:00")
        )

    def test_third_retryable_failure_marks_run_partial(self):
        """Catches an unbounded failing browser loop."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        for attempt, hour in enumerate((2, 3, 4), start=1):
            owner = f"worker-{attempt}"
            claim = self.store.claim_stage(
                "A", owner, f"2026-08-29T{hour:02d}:03:00+08:00"
            )
            result = self.store.fail_stage(
                claim.run_id,
                claim.stage,
                owner,
                "network",
                "temporary timeout",
                f"2026-08-29T{hour:02d}:10:00+08:00",
            )
        self.assertEqual(result, "partial")
        self.assertEqual(self.store.get_batch("2026-08-29")[0].state, "partial")

    def test_permanent_access_failure_does_not_retry(self):
        """Catches attempts to push through CAPTCHA or access controls."""
        self.store.start_batch(
            "2026-08-29", self.candidates(), "2026-08-29T02:00:00+08:00"
        )
        claim = self.store.claim_stage("A", "worker", "2026-08-29T02:03:00+08:00")
        result = self.store.fail_stage(
            claim.run_id,
            claim.stage,
            "worker",
            "captcha",
            "challenge shown",
            "2026-08-29T02:10:00+08:00",
        )
        self.assertEqual(result, "partial")
        self.assertIsNone(
            self.store.claim_stage("A", "other", "2026-08-29T03:03:00+08:00")
        )


if __name__ == "__main__":
    unittest.main()
