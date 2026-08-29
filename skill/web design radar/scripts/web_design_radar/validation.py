from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    root: Path
    issues: list[ValidationIssue]

    @property
    def passed(self) -> bool:
        return not self.issues


_OVERALL_SUMMARY = "00-网站整体前端技术总结.md"
_REQUIRED_FILES = (_OVERALL_SUMMARY, "asset-manifest.json")
_SECTION_ANCHORS = {
    "visual-goal": ("效果目标",),
    "technology": ("前端技术结论",),
    "layer-tree": ("层级关系",),
    "layout": ("布局与样式参数",),
    "motion": ("动效与交互时间线",),
    "visual-evidence": ("视觉证据：截图与录屏",),
    "implementation": ("实现方法与组件职责",),
    "resources": ("资源清单",),
    "reproduction": ("从空项目复刻步骤",),
    "acceptance": ("验收标准",),
    "evidence": ("证据与可信度",),
}
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_SECTION_NAME = re.compile(r"^(\d+)-.+\.md$")
_CJK = re.compile(r"[\u3400-\u9fff]")
_RAW_SOURCE_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".cjs"}
_VIDEO_SUFFIXES = {".mp4", ".mov", ".webm"}


def validate_case(root: Path) -> ValidationReport:
    root = root.resolve()
    issues: list[ValidationIssue] = []
    if not root.is_dir() or root.is_symlink():
        return ValidationReport(root, [ValidationIssue("missing-case", "case root is not a real directory")])

    for relative in _REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            issues.append(ValidationIssue("missing-required-file", f"required file is missing or empty: {relative}", relative))

    overall = root / _OVERALL_SUMMARY
    if overall.is_file():
        _validate_document_depth(
            overall, root, issues, minimum_chars=1200, minimum_cjk=200,
            shallow_code="shallow-overall-summary",
        )

    sections_dir = root / "sections"
    sections = sorted(sections_dir.glob("*.md")) if sections_dir.is_dir() else []
    if not sections:
        issues.append(ValidationIssue("missing-sections", "at least one section document is required", "sections"))
    else:
        numbers: list[int] = []
        for section in sections:
            match = _SECTION_NAME.match(section.name)
            if match is None:
                issues.append(ValidationIssue("invalid-section-name", "section must use a numeric NN-name.md prefix", section.relative_to(root).as_posix()))
                continue
            numbers.append(int(match.group(1)))
            text = section.read_text(encoding="utf-8").lower()
            for code, anchors in _SECTION_ANCHORS.items():
                if not any(anchor in text for anchor in anchors):
                    issues.append(ValidationIssue(f"missing-section-{code}", f"section is missing the {code} contract anchor", section.relative_to(root).as_posix()))
            _validate_document_depth(
                section, root, issues, minimum_chars=900, minimum_cjk=120,
                shallow_code="shallow-section-document",
            )
            if "```" not in text:
                issues.append(ValidationIssue(
                    "missing-implementation-example",
                    "section must include a layer tree, pseudocode, interface, or implementation snippet",
                    section.relative_to(root).as_posix(),
                ))
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            issues.append(ValidationIssue("noncontinuous-sections", "section numbering must be continuous from 01", "sections"))

    _validate_section_index(root, sections, issues)

    _validate_json_files(root, issues)
    _validate_links(root, issues)
    _validate_assets(root, issues)
    _validate_claims(root, issues)
    _validate_screenshots(root, issues)
    _validate_no_raw_source_deliverables(root, issues)
    return ValidationReport(root, _deduplicate(issues))


def _validate_document_depth(
    path: Path,
    root: Path,
    issues: list[ValidationIssue],
    minimum_chars: int,
    minimum_cjk: int,
    shallow_code: str,
) -> None:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(root).as_posix()
    compact = re.sub(r"\s+", "", text)
    cjk_count = len(_CJK.findall(text))
    language_chars = cjk_count + len(re.findall(r"[A-Za-z]", text))
    if len(compact) < minimum_chars:
        issues.append(ValidationIssue(
            shallow_code,
            f"document is too shallow for replication: {len(compact)} < {minimum_chars} characters",
            relative,
        ))
    if cjk_count < minimum_cjk or language_chars and cjk_count / language_chars < 0.35:
        issues.append(ValidationIssue(
            "non-chinese-primary-document",
            "user-facing replication documents must be primarily written in Chinese",
            relative,
        ))


def _validate_no_raw_source_deliverables(root: Path, issues: list[ValidationIssue]) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in _RAW_SOURCE_SUFFIXES:
            issues.append(ValidationIssue(
                "raw-source-deliverable",
                "raw HTML/CSS/JavaScript belongs in temporary analysis, not the final case pack",
                path.relative_to(root).as_posix(),
            ))


def render_validation_report(report: ValidationReport) -> str:
    lines = ["# Validation Report", "", f"Status: {'PASS' if report.passed else 'FAIL'}", ""]
    if report.passed:
        lines.append("No validation issues found.")
    else:
        lines.append("## Issues")
        lines.append("")
        for issue in report.issues:
            location = f" ({issue.path})" if issue.path else ""
            lines.append(f"- `{issue.code}`{location}: {issue.message}")
    return "\n".join(lines) + "\n"


def _validate_json_files(root: Path, issues: list[ValidationIssue]) -> None:
    for path in sorted(root.rglob("*.json")):
        if path.is_symlink():
            issues.append(ValidationIssue("unsafe-symlink", "JSON file cannot be a symlink", path.relative_to(root).as_posix()))
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            issues.append(ValidationIssue("invalid-json", str(exc), path.relative_to(root).as_posix()))


def _validate_links(root: Path, issues: list[ValidationIssue]) -> None:
    for document in sorted(root.rglob("*.md")):
        text = document.read_text(encoding="utf-8")
        for raw_target in _LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative = target.split("#", 1)[0]
            if not relative:
                continue
            resolved = (document.parent / relative).resolve()
            if root != resolved and root not in resolved.parents:
                issues.append(ValidationIssue("unsafe-link", f"link escapes the case root: {target}", document.relative_to(root).as_posix()))
            elif not resolved.exists():
                issues.append(ValidationIssue("broken-link", f"local link does not exist: {target}", document.relative_to(root).as_posix()))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _validate_section_index(
    root: Path, sections: list[Path], issues: list[ValidationIssue]
) -> None:
    relative_index = "evidence/section-index.json"
    index = _load_json(root / relative_index)
    if index is None or not isinstance(index.get("sections"), list):
        issues.append(ValidationIssue(
            "missing-section-index",
            "evidence/section-index.json must enumerate every observed homepage section",
            relative_index,
        ))
        return
    expected = index["sections"]
    if len(expected) != len(sections):
        issues.append(ValidationIssue(
            "section-count-mismatch",
            f"observed {len(expected)} homepage sections but found {len(sections)} section documents",
            relative_index,
        ))
    expected_orders = list(range(1, len(expected) + 1))
    actual_orders = [item.get("order") for item in expected if isinstance(item, dict)]
    if actual_orders != expected_orders:
        issues.append(ValidationIssue(
            "invalid-section-index-order",
            "section index order must be continuous from 1 in actual homepage order",
            relative_index,
        ))
    actual_documents = {path.relative_to(root).as_posix() for path in sections}
    expected_documents: set[str] = set()
    for item in expected:
        if not isinstance(item, dict) or not isinstance(item.get("document"), str):
            issues.append(ValidationIssue(
                "invalid-section-index-entry", "each section index entry needs a document path",
                relative_index,
            ))
            continue
        document = item["document"]
        expected_documents.add(document)
        if document not in actual_documents:
            issues.append(ValidationIssue(
                "missing-section-document",
                f"observed homepage section has no matching Markdown: {document}",
                relative_index,
            ))
        else:
            _validate_section_media(root, item, issues)
    for unexpected in sorted(actual_documents - expected_documents):
        issues.append(ValidationIssue(
            "unindexed-section-document",
            f"section Markdown is not mapped to an observed homepage section: {unexpected}",
            unexpected,
        ))


def _validate_section_media(
    root: Path, item: dict[str, Any], issues: list[ValidationIssue]
) -> None:
    document_relative = str(item["document"])
    document_path = root / document_relative
    document_text = document_path.read_text(encoding="utf-8")
    screenshots = item.get("screenshots")
    if not isinstance(screenshots, list):
        screenshots = []
    if len(screenshots) < 4:
        issues.append(ValidationIssue(
            "insufficient-section-screenshots",
            f"each section needs at least 4 meaningful screenshots; found {len(screenshots)}",
            document_relative,
        ))

    viewports: set[str] = set()
    states: set[str] = set()
    screenshot_hashes: dict[str, str] = {}
    for capture in screenshots:
        if not isinstance(capture, dict):
            issues.append(ValidationIssue(
                "invalid-section-screenshot-entry",
                "screenshot entries require path, viewport, state, and trigger",
                document_relative,
            ))
            continue
        relative = capture.get("path")
        viewport = str(capture.get("viewport") or "").lower().replace("×", "x")
        state = str(capture.get("state") or "").strip()
        trigger = str(capture.get("trigger") or "").strip()
        viewports.add(viewport)
        if state:
            states.add(state)
        if not isinstance(relative, str) or not state or not trigger:
            issues.append(ValidationIssue(
                "invalid-section-screenshot-entry",
                "screenshot entries require path, viewport, state, and trigger",
                document_relative,
            ))
            continue
        capture_path = _safe_case_file(root, relative)
        if capture_path is None or not _valid_image_signature(capture_path):
            issues.append(ValidationIssue(
                "missing-section-screenshot",
                f"declared screenshot is missing or invalid: {relative}",
                relative,
            ))
        else:
            digest = hashlib.sha256(capture_path.read_bytes()).hexdigest()
            first = screenshot_hashes.get(digest)
            if first is not None:
                issues.append(ValidationIssue(
                    "duplicate-section-screenshot-content",
                    f"screenshot bytes duplicate another declared state: {first}",
                    relative,
                ))
            else:
                screenshot_hashes[digest] = relative
        if relative not in document_text:
            issues.append(ValidationIssue(
                "unreferenced-section-media",
                "declared screenshot must be embedded and explained in its Section Markdown",
                relative,
            ))

    if "1440x900" not in viewports:
        issues.append(ValidationIssue(
            "missing-section-desktop-screenshot",
            "each section needs a 1440x900 desktop capture",
            document_relative,
        ))
    if "390x844" not in viewports:
        issues.append(ValidationIssue(
            "missing-section-mobile-screenshot",
            "each section needs a 390x844 mobile capture",
            document_relative,
        ))
    if len(states) < min(3, len(screenshots)):
        issues.append(ValidationIssue(
            "insufficient-section-visual-states",
            "screenshots must represent distinct start, interaction/scroll, end, or mobile states",
            document_relative,
        ))

    motion_required = item.get("motionCaptureRequired") is True
    video = item.get("video")
    if motion_required and not isinstance(video, dict):
        issues.append(ValidationIssue(
            "missing-section-video",
            "animated or interactive sections require a short interaction recording",
            document_relative,
        ))
        return
    if not motion_required and not isinstance(video, dict):
        reason = str(item.get("videoOmissionReason") or "").strip()
        if len(reason) < 8:
            issues.append(ValidationIssue(
                "missing-video-omission-reason",
                "a static section without video needs a concrete Chinese omission reason",
                document_relative,
            ))
        return
    if not isinstance(video, dict):
        return
    relative = video.get("path")
    duration = video.get("durationSeconds")
    method = str(video.get("captureMethod") or "").strip()
    interaction = str(video.get("interaction") or "").strip()
    if not isinstance(relative, str) or not method or not interaction:
        issues.append(ValidationIssue(
            "invalid-section-video-entry",
            "video requires path, durationSeconds, captureMethod, and interaction",
            document_relative,
        ))
        return
    video_path = _safe_case_file(root, relative)
    invalid_container = (
        video_path is None
        or video_path.suffix.lower() not in _VIDEO_SUFFIXES
        or not _valid_video_signature(video_path)
    )
    if invalid_container:
        issues.append(ValidationIssue(
            "missing-section-video",
            f"declared interaction recording is missing or invalid: {relative}",
            relative,
        ))
    if not isinstance(duration, (int, float)) or not 6 <= duration <= 12:
        issues.append(ValidationIssue(
            "invalid-section-video-duration",
            "interaction recording must declare a focused 6-12 second duration",
            relative,
        ))
    if not invalid_container and video_path is not None:
        actual_duration, probe_error = _probe_video(video_path)
        if probe_error is not None:
            issues.append(ValidationIssue(
                "invalid-section-video-stream",
                f"ffprobe could not confirm a decodable video stream: {probe_error}",
                relative,
            ))
        elif actual_duration is not None:
            if not 6 <= actual_duration <= 12:
                issues.append(ValidationIssue(
                    "invalid-section-video-duration",
                    f"ffprobe duration must be 6-12 seconds; got {actual_duration:.3f}",
                    relative,
                ))
            if isinstance(duration, (int, float)) and abs(actual_duration - duration) > 0.75:
                issues.append(ValidationIssue(
                    "section-video-duration-mismatch",
                    f"declared duration {duration} does not match ffprobe duration {actual_duration:.3f}",
                    relative,
                ))
    if relative not in document_text:
        issues.append(ValidationIssue(
            "unreferenced-section-media",
            "declared recording must be linked and explained in its Section Markdown",
            relative,
        ))


def _safe_case_file(root: Path, relative: str) -> Path | None:
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file() or path.is_symlink():
        return None
    return path


def _validate_assets(root: Path, issues: list[ValidationIssue]) -> None:
    manifest = _load_json(root / "asset-manifest.json")
    if manifest is None:
        return
    for record in manifest.get("assets", []):
        if not isinstance(record, dict) or record.get("status") != "downloaded":
            continue
        relative = record.get("localPath")
        if not isinstance(relative, str):
            issues.append(ValidationIssue("missing-asset", "downloaded asset has no localPath", "asset-manifest.json"))
            continue
        path = (root / relative).resolve()
        if root not in path.parents or not path.is_file() or path.is_symlink():
            issues.append(ValidationIssue("missing-asset", f"downloaded asset is missing: {relative}", "asset-manifest.json"))
            continue
        body = path.read_bytes()
        if record.get("bytes") != len(body):
            issues.append(ValidationIssue("asset-size-mismatch", f"asset size does not match: {relative}", "asset-manifest.json"))
        if record.get("sha256") != hashlib.sha256(body).hexdigest():
            issues.append(ValidationIssue("asset-hash-mismatch", f"asset hash does not match: {relative}", "asset-manifest.json"))


def _validate_claims(root: Path, issues: list[ValidationIssue]) -> None:
    claims = _load_json(root / "evidence" / "claims.json")
    if claims is None:
        issues.append(ValidationIssue("missing-claims", "evidence/claims.json is required", "evidence/claims.json"))
        return
    for claim in claims.get("claims", []):
        if not isinstance(claim, dict):
            continue
        confidence = claim.get("confidence")
        if confidence not in {"observed", "source-confirmed", "inferred", "unknown"}:
            issues.append(ValidationIssue("invalid-confidence", f"unsupported evidence confidence: {confidence}", "evidence/claims.json"))
        evidence_ids = claim.get("evidenceIds")
        if confidence == "observed" and (not isinstance(evidence_ids, list) or not evidence_ids):
            issues.append(ValidationIssue("unsupported-observed-claim", f"observed claim lacks evidence: {claim.get('id', 'unknown')}", "evidence/claims.json"))
            continue
        for evidence_id in evidence_ids or []:
            if not (root / "evidence" / f"{evidence_id}.json").is_file():
                issues.append(ValidationIssue("missing-evidence", f"claim references missing evidence: {evidence_id}", "evidence/claims.json"))


def _validate_screenshots(root: Path, issues: list[ValidationIssue]) -> None:
    screenshots = root / "screenshots"
    desktop = sorted(screenshots.rglob("*desktop*")) if screenshots.is_dir() else []
    mobile = sorted(screenshots.rglob("*mobile*")) if screenshots.is_dir() else []
    if not desktop:
        issues.append(ValidationIssue("missing-desktop-screenshot", "a desktop screenshot is required", "screenshots"))
    if not mobile:
        issues.append(ValidationIssue("missing-mobile-screenshot", "a mobile screenshot is required", "screenshots"))
    for path in desktop + mobile:
        if not _valid_image_signature(path):
            issues.append(ValidationIssue("invalid-screenshot", "screenshot has an unsupported or empty image signature", path.relative_to(root).as_posix()))


def _valid_image_signature(path: Path) -> bool:
    try:
        header = path.read_bytes()[:16]
    except OSError:
        return False
    return (
        header.startswith(b"\x89PNG\r\n\x1a\n")
        or header.startswith(b"\xff\xd8\xff")
        or len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    )


def _valid_video_signature(path: Path) -> bool:
    try:
        header = path.read_bytes()[:32]
    except OSError:
        return False
    return (
        len(header) >= 12 and header[4:8] == b"ftyp"
        or header.startswith(b"\x1a\x45\xdf\xa3")
    )


def _probe_video(path: Path) -> tuple[float | None, str | None]:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_type,width,height:format=duration",
                "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return None, "ffprobe is unavailable"
    except subprocess.TimeoutExpired:
        return None, "ffprobe timed out"
    if result.returncode != 0:
        return None, (result.stderr.strip() or "ffprobe returned a non-zero status")[:300]
    try:
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        duration = float(payload["format"]["duration"])
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None, "missing video stream dimensions or duration"
    if stream.get("codec_type") != "video" or width <= 0 or height <= 0 or duration <= 0:
        return None, "invalid video stream dimensions or duration"
    return duration, None


def _deduplicate(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return list(dict.fromkeys(issues))
