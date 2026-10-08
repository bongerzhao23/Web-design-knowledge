from __future__ import annotations

import sqlite3


_INITIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    batch_date TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('daily', 'one_off')),
    status TEXT NOT NULL,
    source_status TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS one_daily_batch_per_date
ON batches(batch_date) WHERE kind = 'daily';

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    canonical_url TEXT NOT NULL,
    canonical_domain TEXT NOT NULL,
    score REAL NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE(batch_id, canonical_domain),
    UNIQUE(batch_id, rank)
);

CREATE TABLE IF NOT EXISTS site_runs (
    run_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    batch_date TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('daily', 'one_off')),
    slot TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    canonical_domain TEXT NOT NULL,
    title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    state TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    staging_dir TEXT NOT NULL,
    revision_dir TEXT NOT NULL,
    task_space_id TEXT,
    browser_fallback_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_daily_run_domain
ON site_runs(batch_date, canonical_domain) WHERE kind = 'daily';

CREATE UNIQUE INDEX IF NOT EXISTS unique_daily_run_slot
ON site_runs(batch_date, slot) WHERE kind = 'daily';

CREATE UNIQUE INDEX IF NOT EXISTS unique_one_off_revision
ON site_runs(batch_date, canonical_domain) WHERE kind = 'one_off';

CREATE TABLE IF NOT EXISTS stage_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES site_runs(run_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    state TEXT NOT NULL,
    lease_owner TEXT,
    lease_expires_at TEXT,
    error_class TEXT,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    result_json TEXT,
    UNIQUE(run_id, stage, attempt)
);
"""


def migrate(connection: sqlite3.Connection) -> None:
    with connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
        )
        present = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 1"
        ).fetchone()
        if present is None:
            connection.executescript(_INITIAL_SCHEMA)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")
        if connection.execute("SELECT 1 FROM schema_migrations WHERE version = 2").fetchone() is None:
            # v2: allow explicit one-off reruns (run_id carries a -rN suffix); single active run is enforced in RunStore.
            connection.execute("DROP INDEX IF EXISTS unique_one_off_revision")
            connection.execute("INSERT INTO schema_migrations(version) VALUES (2)")
