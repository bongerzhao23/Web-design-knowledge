#!/usr/bin/env python3.11
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Callable


ARCHIVE_ROOT = Path(os.environ.get("WEB_DESIGN_RADAR_ROOT", str(Path.home() / "Desktop" / "Web Design Radar"))).expanduser()
INSTALLED_SKILL = Path(os.environ.get(
    "WEB_DESIGN_RADAR_INSTALLED_SKILL", str(Path.home() / ".openclaw" / "workspace" / "skills" / "web-design-radar")
)).expanduser()
TOOLS = "exec,read,write,browser"


def _declarations(skill_root: Path) -> list[dict[str, object]]:
    coordinator = (skill_root / "prompts/daily-coordinator.md").read_text(encoding="utf-8")
    worker = (skill_root / "prompts/site-worker.md").read_text(encoding="utf-8")
    executable = INSTALLED_SKILL / "scripts/web-design-radar.py"
    return [
        {
            "key": "web-design-radar-coordinator", "schedule": "0 2 * * *", "timeout": 1200,
            "kind": "agent", "payload": coordinator,
        },
        {
            "key": "web-design-radar-worker-a", "schedule": "3 2-7 * * *", "timeout": 3300,
            "kind": "agent", "payload": worker + "\n\nBound slot: A\n",
        },
        {
            "key": "web-design-radar-worker-b", "schedule": "3 2-7 * * *", "timeout": 3300,
            "kind": "agent", "payload": worker + "\n\nBound slot: B\n",
        },
        {
            "key": "web-design-radar-closeout", "schedule": "30 8 * * *", "timeout": 1200,
            "kind": "command", "payload": ["python3.11", str(executable), "finalize-day", "--json"],
        },
        {
            "key": "web-design-radar-deadline", "schedule": "0 9 * * *", "timeout": 1200,
            "kind": "command", "payload": ["python3.11", str(executable), "finalize-day", "--force-deadline", "--json"],
        },
    ]


def _digest(declaration: dict[str, object]) -> str:
    body = json.dumps(declaration, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def _argv(declaration: dict[str, object]) -> list[str]:
    key = str(declaration["key"])
    argv = [
        "openclaw", "cron", "add", str(declaration["schedule"]),
        "--name", key,
        "--declaration-key", key,
        "--tz", "Asia/Shanghai",
        "--timeout-seconds", str(declaration["timeout"]),
        "--disabled", "--exact", "--no-deliver",
    ]
    if declaration["kind"] == "agent":
        argv.extend([
            "--message", str(declaration["payload"]),
            "--session", "isolated", "--tools", TOOLS,
        ])
    else:
        argv.extend([
            "--command-argv", json.dumps(declaration["payload"], separators=(",", ":")),
            "--command-env", f"WEB_DESIGN_RADAR_ROOT={ARCHIVE_ROOT}",
        ])
    argv.append("--json")
    return argv


def declare_crons(
    archive_root: Path = ARCHIVE_ROOT,
    run_command: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    skill_root: Path | None = None,
) -> dict[str, dict[str, str]]:
    archive_root = archive_root.resolve()
    skill_root = (skill_root or Path(__file__).resolve().parents[1]).resolve()
    run_command = run_command or _run
    path = archive_root / "state" / "automation.json"
    existing: dict[str, object] = {"declarations": {}}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    records = dict(existing.get("declarations", {}))
    declarations = _declarations(skill_root)

    for declaration in declarations:
        key = str(declaration["key"])
        digest = _digest(declaration)
        previous = records.get(key)
        if previous is not None and previous.get("sha256") != digest:
            raise ValueError(f"declaration conflict for {key}; inspect stored job ID before changing it")

    for declaration in declarations:
        key = str(declaration["key"])
        digest = _digest(declaration)
        if key in records:
            continue
        result = run_command(_argv(declaration))
        if result.returncode != 0:
            raise RuntimeError(f"cron declaration failed for {key}: {result.stderr.strip()}")
        payload = json.loads(result.stdout)
        job_id = _extract_id(payload)
        records[key] = {"id": job_id, "sha256": digest}

    _atomic_json(path, {"version": 1, "declarations": records})
    return records


def _extract_id(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("id", "jobId"):
            if payload.get(key):
                return str(payload[key])
        if isinstance(payload.get("job"), dict):
            return _extract_id(payload["job"])
    raise ValueError("OpenClaw cron response did not include an ID")


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, capture_output=True, check=False)


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Declare Web Design Radar cron jobs disabled")
    parser.add_argument("--archive-root", type=Path, default=ARCHIVE_ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps({"status": "ok", "declarations": declare_crons(args.archive_root)}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
