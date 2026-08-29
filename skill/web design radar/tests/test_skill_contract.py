import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillContractTest(unittest.TestCase):
    def text(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_entrypoint_routes_the_two_modes_and_four_contracts(self):
        skill = self.text("SKILL.md")
        self.assertRegex(skill, r"(?m)^name: web-design-radar$")
        self.assertIn("section-by-section", skill)
        self.assertIn("1:1 复刻", skill)
        self.assertIn("awwwards-crawler", skill)
        self.assertIn("one-off", skill)
        self.assertIn("daily batch", skill)
        for name in ("evidence-contract.md", "section-contract.md", "asset-policy.md", "browser-acceptance.md"):
            self.assertIn(name, skill)

    def test_coordinator_has_bounded_source_and_selection_contract(self):
        prompt = self.text("prompts/daily-coordinator.md")
        for term in ("quota=2", "Awwwards", "agent-reach", "OpenCLI", "sourceStatus", "public pages", "candidate-list.schema.json"):
            self.assertIn(term, prompt)

    def test_worker_prefers_ego_and_has_exact_lifecycle_boundaries(self):
        worker = self.text("prompts/site-worker.md")
        for term in (
            "ego-browser", "taskSpaceId", "completeTaskSpace(id, { keep: false })",
            "browserFallbackReason", "claim-stage", "submit-stage", "fail-stage",
            "09:00", "stagingDir", "desktop", "mobile", "public", "IDLE|OK|PARTIAL",
        ):
            self.assertIn(term, worker)
        self.assertLess(worker.index("ego-browser"), worker.index("OpenClaw/Chrome"))

    def test_templates_and_references_have_no_scaffold_placeholders(self):
        files = list((ROOT / "references").glob("*.md")) + list((ROOT / "templates").glob("*.md"))
        self.assertEqual(len(files), 7)
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        self.assertNotRegex(combined, r"\[TODO|TODO:")
        self.assertIn("source-confirmed", combined)
        self.assertIn("reduced-motion", combined)
        self.assertIn("license", combined)

    def test_user_facing_documents_are_chinese_first_and_md_first(self):
        skill = self.text("SKILL.md")
        worker = self.text("prompts/site-worker.md")
        contract = self.text("references/section-contract.md")
        combined = "\n".join((skill, worker, contract))
        for term in (
            "00-网站整体前端技术总结.md", "中文为主", "一个 Section 对应一个 Markdown",
            "HTML", "CSS", "JavaScript", "不属于最终交付",
        ):
            self.assertIn(term, combined)

    def test_per_section_media_contract_has_recording_fallback_and_markdown_mapping(self):
        browser = self.text("references/browser-acceptance.md")
        worker = self.text("prompts/site-worker.md")
        section = self.text("templates/section.md")
        combined = "\n".join((browser, worker, section))
        for term in (
            "at least four", "motionCaptureRequired", "videoOmissionReason",
            "Page.captureScreenshot", "ffmpeg -framerate", "ego-lite-frame-sequence",
            "视觉证据：截图与录屏", "Screenshot or recording failure alone does not authorize Chrome fallback",
        ):
            self.assertIn(term, combined)


if __name__ == "__main__":
    unittest.main()
