from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from .scoring import Candidate, score_candidate
from .urls import domain_slug


@dataclass(frozen=True)
class SiteRun:
    run_id: str
    batch_date: str
    slot: str
    canonical_url: str
    canonical_domain: str
    title: str
    source_url: str
    state: str
    current_stage: str
    staging_dir: Path
    revision_dir: Path


@dataclass(frozen=True)
class StageClaim:
    run_id: str
    batch_date: str
    slot: str
    stage: str
    lease_owner: str
    lease_expires_at: str
    deadline_at: str
    site_url: str
    source_url: str
    staging_dir: Path
    task_space_id: str | None
    browser_preference: str = "playwright-chromium"
    browser_fallback: str = "other-browser"


_STAGES = ("observing", "extracting", "assets", "documenting", "validating")
_PERMANENT_FAILURES = {"captcha", "login", "paywall", "blocked", "offline"}
_MAX_ATTEMPTS = 3


class RunStore:
    def __init__(self, connection: sqlite3.Connection, root: Path):
        self.connection = connection
        self.root = root.resolve()

    def start_batch(
        self,
        batch_date: str,
        candidates: list[Candidate],
        started_at: str,
        source_status: str = "primary",
    ) -> list[SiteRun]:
        date.fromisoformat(batch_date)
        existing = self.get_batch(batch_date)
        if existing:
            return existing
        if len(candidates) != 2:
            raise ValueError("daily batch requires exactly two candidates")
        domains = [candidate.canonical_domain for candidate in candidates]
        if len(set(domains)) != 2:
            raise ValueError("daily batch requires exactly two unique candidates")

        batch_id = f"daily:{batch_date}"
        deadline = f"{batch_date}T09:00:00+08:00"
        created: list[SiteRun] = []
        with self.connection:
            self.connection.execute(
                "INSERT INTO batches(id,batch_date,kind,status,source_status,deadline_at,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (batch_id, batch_date, "daily", "active", source_status, deadline, started_at),
            )
            for rank, (slot, candidate) in enumerate(zip(("A", "B"), candidates), start=1):
                slug = domain_slug(candidate.site_url)
                run_id = f"{batch_date}-{slot.lower()}-{slug}"
                staging_dir = self.root / "state" / "runs" / run_id / "work"
                revision_dir = self.root / _delivery_folder(started_at, candidate.title, candidate.site_url)
                staging_dir.mkdir(parents=True, exist_ok=False)
                self.connection.execute(
                    "INSERT INTO candidates(batch_id,rank,canonical_url,canonical_domain,score,raw_json) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        batch_id,
                        rank,
                        candidate.site_url,
                        candidate.canonical_domain,
                        score_candidate(candidate),
                        json.dumps(asdict(candidate), ensure_ascii=False, sort_keys=True),
                    ),
                )
                self.connection.execute(
                    "INSERT INTO site_runs(run_id,batch_id,batch_date,kind,slot,canonical_url,"
                    "canonical_domain,title,source_url,state,current_stage,staging_dir,revision_dir,"
                    "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        batch_id,
                        batch_date,
                        "daily",
                        slot,
                        candidate.site_url,
                        candidate.canonical_domain,
                        candidate.title,
                        candidate.source_url,
                        "assigned",
                        "observing",
                        str(staging_dir),
                        str(revision_dir),
                        started_at,
                        started_at,
                    ),
                )
                created.append(
                    SiteRun(
                        run_id=run_id,
                        batch_date=batch_date,
                        slot=slot,
                        canonical_url=candidate.site_url,
                        canonical_domain=candidate.canonical_domain,
                        title=candidate.title,
                        source_url=candidate.source_url,
                        state="assigned",
                        current_stage="observing",
                        staging_dir=staging_dir,
                        revision_dir=revision_dir,
                    )
                )
        return created

    def start_one_off(self, candidate: Candidate, started_at: str, rerun: bool = False) -> SiteRun:
        moment = _parse_time(started_at)
        batch_date = moment.date().isoformat()
        existing = self.connection.execute(
            "SELECT * FROM site_runs WHERE batch_date = ? AND canonical_domain = ? "
            "AND kind = 'one_off'",
            (batch_date, candidate.canonical_domain),
        ).fetchone()
        slug = domain_slug(candidate.site_url)
        suffix = ""
        if existing is not None:
            prior = self.connection.execute(
                "SELECT * FROM site_runs WHERE batch_date = ? AND canonical_domain = ? AND kind = 'one_off' "
                "ORDER BY created_at DESC LIMIT 1", (batch_date, candidate.canonical_domain)).fetchone()
            finished = prior["state"] in ("completed", "partial", "failed")
            if not (rerun and finished):
                return self._row_to_run(prior)
            count = self.connection.execute(
                "SELECT count(*) FROM site_runs WHERE batch_date = ? AND canonical_domain = ? AND kind = 'one_off'",
                (batch_date, candidate.canonical_domain)).fetchone()[0]
            suffix = f"-r{count + 1}"
        batch_id = f"one-off:{batch_date}:{slug}{suffix}"
        run_id = f"{batch_date}-m-{slug}{suffix}"
        staging_dir = self.root / "state" / "runs" / run_id / "work"
        revision_dir = self.root / _delivery_folder(started_at, candidate.title, candidate.site_url)
        deadline = (moment + timedelta(hours=12)).isoformat()
        with self.connection:
            self.connection.execute(
                "INSERT INTO batches(id,batch_date,kind,status,source_status,deadline_at,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (batch_id, batch_date, "one_off", "active", "manual", deadline, started_at),
            )
            self.connection.execute(
                "INSERT INTO candidates(batch_id,rank,canonical_url,canonical_domain,score,raw_json) "
                "VALUES (?,?,?,?,?,?)",
                (
                    batch_id,
                    1,
                    candidate.site_url,
                    candidate.canonical_domain,
                    score_candidate(candidate),
                    json.dumps(asdict(candidate), ensure_ascii=False, sort_keys=True),
                ),
            )
            staging_dir.mkdir(parents=True, exist_ok=False)
            self.connection.execute(
                "INSERT INTO site_runs(run_id,batch_id,batch_date,kind,slot,canonical_url,"
                "canonical_domain,title,source_url,state,current_stage,staging_dir,revision_dir,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id, batch_id, batch_date, "one_off", "M", candidate.site_url,
                    candidate.canonical_domain, candidate.title, candidate.source_url,
                    "assigned", "observing", str(staging_dir), str(revision_dir),
                    started_at, started_at,
                ),
            )
        return self._row_to_run(
            self.connection.execute("SELECT * FROM site_runs WHERE run_id = ?", (run_id,)).fetchone()
        )

    def claim_stage(self, slot: str, owner: str, now: str) -> StageClaim | None:
        if slot not in {"A", "B", "M"}:
            raise ValueError("slot must be A, B, or M")
        if not owner.strip():
            raise ValueError("owner is required")
        moment = _parse_time(now)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            row = self.connection.execute(
                "SELECT r.*, b.deadline_at FROM site_runs r JOIN batches b ON b.id = r.batch_id "
                "WHERE r.slot = ? AND r.state NOT IN ('completed','partial','failed','ready_to_publish') "
                "ORDER BY r.created_at DESC LIMIT 1",
                (slot,),
            ).fetchone()
            if row is None or moment >= _parse_time(row["deadline_at"]):
                self.connection.commit()
                return None

            active = self.connection.execute(
                "SELECT * FROM stage_attempts WHERE run_id = ? AND stage = ? AND state = 'claimed' "
                "ORDER BY attempt DESC LIMIT 1",
                (row["run_id"], row["current_stage"]),
            ).fetchone()
            if active is not None and moment < _parse_time(active["lease_expires_at"]):
                self.connection.commit()
                return None
            if active is not None:
                self.connection.execute(
                    "UPDATE stage_attempts SET state='failed',error_class='lease-expired',"
                    "error_message='lease expired',finished_at=? WHERE id=?",
                    (now, active["id"]),
                )

            attempts = self.connection.execute(
                "SELECT count(*) FROM stage_attempts WHERE run_id = ? AND stage = ?",
                (row["run_id"], row["current_stage"]),
            ).fetchone()[0]
            if attempts >= _MAX_ATTEMPTS:
                self.connection.execute(
                    "UPDATE site_runs SET state='partial',updated_at=? WHERE run_id=?",
                    (now, row["run_id"]),
                )
                self.connection.commit()
                return None

            attempt = attempts + 1
            expires = (moment + timedelta(minutes=55)).isoformat()
            self.connection.execute(
                "INSERT INTO stage_attempts(run_id,stage,attempt,state,lease_owner,lease_expires_at,started_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (row["run_id"], row["current_stage"], attempt, "claimed", owner, expires, now),
            )
            self.connection.execute(
                "UPDATE site_runs SET state=?,updated_at=? WHERE run_id=?",
                (row["current_stage"], now, row["run_id"]),
            )
            self.connection.commit()
            return StageClaim(
                run_id=row["run_id"], batch_date=row["batch_date"], slot=row["slot"],
                stage=row["current_stage"], lease_owner=owner, lease_expires_at=expires,
                deadline_at=row["deadline_at"], site_url=row["canonical_url"],
                source_url=row["source_url"], staging_dir=Path(row["staging_dir"]),
                task_space_id=row["task_space_id"],
            )
        except Exception:
            self.connection.rollback()
            raise

    def submit_stage(
        self,
        run_id: str,
        stage: str,
        owner: str,
        result: dict[str, Any],
        now: str,
    ) -> str:
        moment = _parse_time(now)
        with self.connection:
            run = self.connection.execute(
                "SELECT * FROM site_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            attempt = self._owned_attempt(run_id, stage, owner)
            if run is None or run["current_stage"] != stage:
                raise ValueError("stage does not match current run stage")
            if moment > _parse_time(attempt["lease_expires_at"]):
                raise ValueError("stage lease has expired")
            task_space_id = result.get("taskSpaceId")
            fallback_reason = result.get("browserFallbackReason")
            browser_used = result.get("browserUsed", "playwright-chromium")
            if browser_used not in {"playwright-chromium", "ego-lite", "openclaw-chrome", "other-browser"}:
                raise ValueError("browserUsed must be playwright-chromium, ego-lite, openclaw-chrome, or other-browser")
            if browser_used in {"openclaw-chrome", "other-browser"} and not str(fallback_reason or "").strip():
                raise ValueError("browserFallbackReason is required for non-kit browser fallback")
            if fallback_reason is not None and not str(fallback_reason).strip():
                raise ValueError("browserFallbackReason cannot be empty")
            self.connection.execute(
                "UPDATE stage_attempts SET state='completed',finished_at=?,result_json=? WHERE id=?",
                (now, json.dumps(result, ensure_ascii=False, sort_keys=True), attempt["id"]),
            )
            index = _STAGES.index(stage)
            if index == len(_STAGES) - 1:
                next_stage = stage
                next_state = "ready_to_publish"
            else:
                next_stage = _STAGES[index + 1]
                next_state = "assigned"
            self.connection.execute(
                "UPDATE site_runs SET state=?,current_stage=?,task_space_id=COALESCE(?,task_space_id),"
                "browser_fallback_reason=COALESCE(?,browser_fallback_reason),updated_at=? WHERE run_id=?",
                (next_state, next_stage, task_space_id, fallback_reason, now, run_id),
            )
        return next_state

    def fail_stage(
        self,
        run_id: str,
        stage: str,
        owner: str,
        error_class: str,
        message: str,
        now: str,
    ) -> str:
        with self.connection:
            attempt = self._owned_attempt(run_id, stage, owner)
            self.connection.execute(
                "UPDATE stage_attempts SET state='failed',error_class=?,error_message=?,finished_at=? "
                "WHERE id=?",
                (error_class, _sanitize_message(message), now, attempt["id"]),
            )
            count = self.connection.execute(
                "SELECT count(*) FROM stage_attempts WHERE run_id=? AND stage=?",
                (run_id, stage),
            ).fetchone()[0]
            state = "partial" if error_class in _PERMANENT_FAILURES or count >= _MAX_ATTEMPTS else "assigned"
            self.connection.execute(
                "UPDATE site_runs SET state=?,updated_at=? WHERE run_id=?",
                (state, now, run_id),
            )
        return state

    def status_counts(self) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT kind,count(*) AS total FROM site_runs GROUP BY kind"
        ).fetchall()
        counts = {row["kind"]: row["total"] for row in rows}
        return {"dailyRuns": counts.get("daily", 0), "oneOffRuns": counts.get("one_off", 0)}

    def _owned_attempt(self, run_id: str, stage: str, owner: str) -> sqlite3.Row:
        attempt = self.connection.execute(
            "SELECT * FROM stage_attempts WHERE run_id=? AND stage=? AND state='claimed' "
            "AND lease_owner=? ORDER BY attempt DESC LIMIT 1",
            (run_id, stage, owner),
        ).fetchone()
        if attempt is None:
            raise ValueError("no active stage lease for owner")
        return attempt

    def get_batch(self, batch_date: str) -> list[SiteRun]:
        rows = self.connection.execute(
            "SELECT * FROM site_runs WHERE batch_date = ? ORDER BY slot", (batch_date,)
        ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> SiteRun:
        row = self.connection.execute(
            "SELECT * FROM site_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown run: {run_id}")
        return self._row_to_run(row)

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> SiteRun:
        return SiteRun(
            run_id=row["run_id"],
            batch_date=row["batch_date"],
            slot=row["slot"],
            canonical_url=row["canonical_url"],
            canonical_domain=row["canonical_domain"],
            title=row["title"],
            source_url=row["source_url"],
            state=row["state"],
            current_stage=row["current_stage"],
            staging_dir=Path(row["staging_dir"]),
            revision_dir=Path(row["revision_dir"]),
        )


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset")
    return parsed


def _sanitize_message(value: str) -> str:
    cleaned = re.sub(
        r"(?i)(authorization|cookie|token|signature|password)\s*[:=]\s*[^\s,;]+",
        r"\1=REDACTED",
        value,
    )
    return cleaned[:500]


def _delivery_folder(started_at: str, title: str, site_url: str) -> str:
    moment = _parse_time(started_at)
    site_name = title.strip()
    if not site_name or re.match(r"^https?://", site_name, re.IGNORECASE):
        site_name = domain_slug(site_url)
    site_name = re.sub(r"[\\/:*?\"<>|]+", "-", site_name)
    site_name = re.sub(r"\s+", "-", site_name).strip(" .-_")
    if not site_name:
        site_name = domain_slug(site_url)
    return f"{moment:%Y-%m-%d_%H-%M}_{site_name[:80]}"
