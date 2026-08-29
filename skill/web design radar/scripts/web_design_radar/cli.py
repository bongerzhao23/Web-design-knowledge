from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any
from zoneinfo import ZoneInfo

from .assets import AssetManifest, record_file
from .config import Settings
from .db import connect
from .migrations import migrate
from .runs import RunStore, SiteRun, StageClaim
from .scoring import Candidate, select_candidates
from .reporting import finalize_day, finalize_one_off, report_day
from .validation import validate_case


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="web-design-radar.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def command(name: str) -> argparse.ArgumentParser:
        item = subparsers.add_parser(name)
        item.add_argument("--json", action="store_true")
        return item

    command("init")
    start = command("start-batch")
    start.add_argument("--date", required=True)
    start.add_argument("--candidates", required=True)
    start.add_argument("--now")
    one_off = command("start-one-off")
    one_off.add_argument("--url", required=True)
    one_off.add_argument("--source-url", required=True)
    one_off.add_argument("--now")
    claim = command("claim-stage")
    claim.add_argument("--slot", required=True)
    claim.add_argument("--owner", required=True)
    claim.add_argument("--now")
    submit = command("submit-stage")
    submit.add_argument("--run-id", required=True)
    submit.add_argument("--stage", required=True)
    submit.add_argument("--owner", required=True)
    submit.add_argument("--result", required=True)
    submit.add_argument("--now")
    fail = command("fail-stage")
    fail.add_argument("--run-id", required=True)
    fail.add_argument("--stage", required=True)
    fail.add_argument("--owner", required=True)
    fail.add_argument("--error-class", required=True)
    fail.add_argument("--message", required=True)
    fail.add_argument("--now")
    asset = command("record-asset")
    asset.add_argument("--run-id", required=True)
    asset.add_argument("--source-url", required=True)
    asset.add_argument("--input-file", required=True)
    asset.add_argument("--local-path", required=True)
    asset.add_argument("--mime", required=True)
    asset.add_argument("--used-by", action="append", required=True)
    validate = command("validate-case")
    validate.add_argument("--revision", required=True)
    finalize = command("finalize-day")
    finalize.add_argument("--date")
    finalize.add_argument("--now")
    finalize.add_argument("--force-deadline", action="store_true")
    finalize_manual = command("finalize-one-off")
    finalize_manual.add_argument("--run-id", required=True)
    finalize_manual.add_argument("--now")
    report = command("report")
    report.add_argument("--date", required=True)
    command("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        settings = Settings.from_env()
        payload = _dispatch(args, settings)
        _emit(payload)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        _emit({"status": "error", "error": str(exc)})
        return 2


def _dispatch(args: argparse.Namespace, settings: Settings) -> dict[str, Any]:
    now = getattr(args, "now", None) or datetime.now(ZoneInfo(settings.timezone)).isoformat()
    if args.command == "validate-case":
        validation = validate_case(Path(args.revision))
        return {
            "status": "passed" if validation.passed else "failed",
            "passed": validation.passed,
            "issues": [asdict(issue) for issue in validation.issues],
        }
    if args.command == "init":
        for path in (settings.root / "sites", settings.root / "daily-reports", settings.runs_path):
            path.mkdir(parents=True, exist_ok=True)
        database = connect(settings.db_path)
        try:
            migrate(database)
        finally:
            database.close()
        return {"status": "initialized", "root": str(settings.root)}

    if not settings.db_path.exists():
        raise ValueError("archive is not initialized")
    database = connect(settings.db_path)
    try:
        migrate(database)
        store = RunStore(database, settings.root)
        if args.command == "start-batch":
            raw = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
            candidates = [_candidate_from_json(item) for item in raw["candidates"]]
            selected = select_candidates(candidates, previous_domains=set(), quota=settings.daily_quota)
            runs = store.start_batch(args.date, selected, now, str(raw.get("sourceStatus", "primary")))
            return {"status": "started", "runs": [_run_json(run) for run in runs]}
        if args.command == "start-one-off":
            candidate = Candidate(
                args.url, args.source_url, args.url, 1, 1, 1, 1, 1, tuple()
            )
            return {"status": "started", "run": _run_json(store.start_one_off(candidate, now))}
        if args.command == "claim-stage":
            claim = store.claim_stage(args.slot, args.owner, now)
            if claim is None:
                return {"status": "idle", "claim": None}
            return {"status": "claimed", "claim": _claim_json(claim)}
        if args.command == "submit-stage":
            result = json.loads(Path(args.result).read_text(encoding="utf-8"))
            state = store.submit_stage(args.run_id, args.stage, args.owner, result, now)
            return {"status": state, "runId": args.run_id}
        if args.command == "fail-stage":
            state = store.fail_stage(
                args.run_id, args.stage, args.owner, args.error_class, args.message, now
            )
            return {"status": state, "runId": args.run_id}
        if args.command == "record-asset":
            run = store.get_run(args.run_id)
            manifest = AssetManifest.load(
                run.staging_dir,
                settings.asset_max_file_bytes,
                settings.asset_max_revision_bytes,
            )
            record = record_file(
                run.staging_dir,
                args.source_url,
                args.local_path,
                Path(args.input_file),
                args.mime,
                args.used_by,
                settings.asset_max_file_bytes,
            )
            manifest.add(record)
            manifest.write()
            return {"status": "recorded", "asset": record.as_json()}
        if args.command == "finalize-day":
            batch_date = args.date or datetime.fromisoformat(now).date().isoformat()
            result = finalize_day(database, settings.root, batch_date, now, args.force_deadline)
            return {"status": "finalized", **_daily_json(result)}
        if args.command == "finalize-one-off":
            result = finalize_one_off(database, settings.root, args.run_id, now)
            return {
                "status": result.state,
                "runId": result.run_id,
                "published": result.published,
                "outputPath": str(result.output_path),
                "issues": list(result.issue_codes),
            }
        if args.command == "report":
            return {"status": "reported", **_daily_json(report_day(database, settings.root, args.date))}
        if args.command == "status":
            return {"status": "ok", **store.status_counts()}
        raise ValueError(f"unsupported command: {args.command}")
    finally:
        database.close()


def _candidate_from_json(raw: dict[str, Any]) -> Candidate:
    return Candidate(
        site_url=raw["siteUrl"], source_url=raw["sourceUrl"], title=raw["title"],
        technology=raw["technology"], industry=raw["industry"],
        popularity=raw["popularity"], novelty=raw["novelty"],
        analyzability=raw["analyzability"], tags=tuple(raw.get("tags", [])),
    )


def _run_json(run: SiteRun) -> dict[str, Any]:
    return {
        "runId": run.run_id, "batchDate": run.batch_date, "slot": run.slot,
        "siteUrl": run.canonical_url, "state": run.state,
        "stage": run.current_stage, "stagingDir": str(run.staging_dir),
        "revisionDir": str(run.revision_dir),
    }


def _claim_json(claim: StageClaim) -> dict[str, Any]:
    payload = asdict(claim)
    return {
        "runId": payload["run_id"], "batchDate": payload["batch_date"],
        "slot": payload["slot"], "stage": payload["stage"],
        "leaseOwner": payload["lease_owner"], "leaseExpiresAt": payload["lease_expires_at"],
        "deadlineAt": payload["deadline_at"], "siteUrl": payload["site_url"],
        "sourceUrl": payload["source_url"], "stagingDir": str(payload["staging_dir"]),
        "taskSpaceId": payload["task_space_id"],
        "browserPreference": payload["browser_preference"],
        "browserFallback": payload["browser_fallback"],
    }


def _emit(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _daily_json(result: Any) -> dict[str, Any]:
    return {
        "date": result.batch_date, "completed": result.completed,
        "partial": result.partial, "failed": result.failed, "active": result.active,
        "reportPath": str(result.report_path),
    }
