from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from .assets import publish_revision
from .validation import render_validation_report, validate_case


@dataclass(frozen=True)
class DailyResult:
    batch_date: str
    completed: int
    partial: int
    failed: int
    active: int
    report_path: Path


@dataclass(frozen=True)
class OneOffResult:
    run_id: str
    state: str
    published: bool
    output_path: Path
    issue_codes: tuple[str, ...] = tuple()


_TERMINAL = {"completed", "partial", "failed"}


def finalize_one_off(
    connection: sqlite3.Connection,
    root: Path,
    run_id: str,
    now: str,
) -> OneOffResult:
    row = connection.execute(
        "SELECT * FROM site_runs WHERE run_id=? AND kind='one_off'", (run_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown one-off run: {run_id}")
    revision = Path(row["revision_dir"])
    if row["state"] == "completed":
        if not revision.is_dir():
            raise ValueError("completed one-off revision is missing")
        return OneOffResult(run_id, "completed", True, revision)
    if row["state"] != "ready_to_publish":
        raise ValueError("one-off run must be ready_to_publish before finalization")

    staging = Path(row["staging_dir"])
    validation = validate_case(staging)
    (staging / "validation-report.md").write_text(
        render_validation_report(validation), encoding="utf-8"
    )
    if not validation.passed:
        with connection:
            connection.execute(
                "UPDATE site_runs SET state='assigned',current_stage='validating',updated_at=? "
                "WHERE run_id=? AND kind='one_off'",
                (now, run_id),
            )
        return OneOffResult(
            run_id, "assigned", False, staging,
            tuple(issue.code for issue in validation.issues),
        )

    metadata = {
        "runId": row["run_id"],
        "kind": "one_off",
        "batchDate": row["batch_date"],
        "siteUrl": row["canonical_url"],
        "sourceUrl": row["source_url"],
        "browserFallbackReason": row["browser_fallback_reason"],
    }
    publish_revision(staging, revision, metadata)
    with connection:
        connection.execute(
            "UPDATE site_runs SET state='completed',updated_at=? WHERE run_id=? AND kind='one_off'",
            (now, run_id),
        )
    return OneOffResult(run_id, "completed", True, revision)


def finalize_day(
    connection: sqlite3.Connection,
    root: Path,
    batch_date: str,
    now: str,
    force_deadline: bool = False,
) -> DailyResult:
    root = root.resolve()
    rows = connection.execute(
        "SELECT * FROM site_runs WHERE batch_date=? AND kind='daily' ORDER BY slot", (batch_date,)
    ).fetchall()

    for row in rows:
        if row["state"] != "ready_to_publish":
            continue
        staging = Path(row["staging_dir"])
        validation = validate_case(staging)
        (staging / "validation-report.md").write_text(render_validation_report(validation), encoding="utf-8")
        if not validation.passed:
            with connection:
                connection.execute(
                    "UPDATE site_runs SET state='partial',updated_at=? WHERE run_id=?",
                    (now, row["run_id"]),
                )
            continue
        metadata = {
            "runId": row["run_id"],
            "batchDate": row["batch_date"],
            "siteUrl": row["canonical_url"],
            "sourceUrl": row["source_url"],
            "browserFallbackReason": row["browser_fallback_reason"],
        }
        publish_revision(staging, Path(row["revision_dir"]), metadata)
        with connection:
            connection.execute(
                "UPDATE site_runs SET state='completed',updated_at=? WHERE run_id=?",
                (now, row["run_id"]),
            )

    if force_deadline:
        with connection:
            connection.execute(
                "UPDATE site_runs SET state='partial',updated_at=? "
                "WHERE batch_date=? AND kind='daily' AND state NOT IN ('completed','partial','failed')",
                (now, batch_date),
            )

    current = connection.execute(
        "SELECT r.*, b.source_status FROM site_runs r JOIN batches b ON b.id=r.batch_id "
        "WHERE r.batch_date=? AND r.kind='daily' ORDER BY r.slot",
        (batch_date,),
    ).fetchall()
    report_path = root / "daily-reports" / f"{batch_date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_report(batch_date, current), encoding="utf-8")
    counts = {state: sum(row["state"] == state for row in current) for state in _TERMINAL}
    active = sum(row["state"] not in _TERMINAL for row in current)
    return DailyResult(
        batch_date=batch_date,
        completed=counts["completed"],
        partial=counts["partial"],
        failed=counts["failed"],
        active=active,
        report_path=report_path,
    )


def report_day(connection: sqlite3.Connection, root: Path, batch_date: str) -> DailyResult:
    return finalize_day(connection, root, batch_date, f"{batch_date}T00:00:00+08:00", False)


def _render_report(batch_date: str, rows: list[sqlite3.Row]) -> str:
    completed = sum(row["state"] == "completed" for row in rows)
    total = len(rows)
    source_status = rows[0]["source_status"] if rows else "missing"
    lines = [
        f"# Web Design Radar — {batch_date}",
        "",
        f"Summary: {completed}/{total} completed",
        f"Candidate source: {source_status}",
        "",
    ]
    for row in rows:
        revision = Path(row["revision_dir"])
        staging = Path(row["staging_dir"])
        case_root = revision if revision.is_dir() else staging
        asset_count, asset_bytes, unknown_licenses, failed_assets = _asset_stats(case_root)
        validation = validate_case(case_root) if case_root.is_dir() else None
        missing_stages = _missing_stages(row["current_stage"], row["state"])
        lines.extend([
            f"## Slot {row['slot']}: {row['title']}",
            "",
            f"- Official site: {row['canonical_url']}",
            f"- Awwwards source: {row['source_url']}",
            f"- Status: {row['state']}",
            f"- Output: {row['revision_dir'] if row['state'] == 'completed' else row['staging_dir']}",
            f"- Assets: {asset_count} files, {asset_bytes} bytes, {unknown_licenses} license unknown, {failed_assets} unavailable",
            f"- Validation: {'PASS' if validation and validation.passed else 'INCOMPLETE'}",
            f"- Validation issues: {', '.join(issue.code for issue in validation.issues) if validation and validation.issues else 'none'}",
            f"- Missing stages: {', '.join(missing_stages) if missing_stages else 'none'}",
            f"- Browser evidence: {'Fallback browser — ' + row['browser_fallback_reason'] if row['browser_fallback_reason'] else 'kit Playwright Chromium; see case evidence'}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _asset_stats(root: Path) -> tuple[int, int, int, int]:
    path = root / "asset-manifest.json"
    try:
        assets = json.loads(path.read_text(encoding="utf-8")).get("assets", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return 0, 0, 0, 0
    downloaded = [item for item in assets if item.get("status") == "downloaded"]
    unavailable = [item for item in assets if item.get("status") != "downloaded"]
    return (
        len(downloaded),
        sum(int(item.get("bytes") or 0) for item in downloaded),
        sum(item.get("license", "unknown") == "unknown" for item in assets),
        len(unavailable),
    )


def _missing_stages(current: str, state: str) -> list[str]:
    stages = ["observing", "extracting", "assets", "documenting", "validating"]
    if state == "completed":
        return []
    try:
        return stages[stages.index(current) + (1 if state != current else 0):]
    except ValueError:
        return stages
