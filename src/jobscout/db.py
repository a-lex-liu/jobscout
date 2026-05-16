from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

from jobscout.models import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    company       TEXT NOT NULL,
    city          TEXT,
    district      TEXT,
    salary_raw    TEXT,
    salary_min    INTEGER,
    salary_max    INTEGER,
    experience    TEXT,
    education     TEXT,
    skills        TEXT NOT NULL DEFAULT '[]',
    description   TEXT,
    url           TEXT NOT NULL,
    posted_at     TEXT,
    crawled_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_crawled_at ON jobs(crawled_at);
CREATE INDEX IF NOT EXISTS idx_jobs_city       ON jobs(city);
CREATE INDEX IF NOT EXISTS idx_jobs_company    ON jobs(company);
"""

INSERT_SQL = """
INSERT OR IGNORE INTO jobs (
    job_id, title, company, city, district,
    salary_raw, salary_min, salary_max, experience, education,
    skills, description, url, posted_at, crawled_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def connect(db_path: Union[str, Path]) -> sqlite3.Connection:
    if isinstance(db_path, Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def job_exists(conn: sqlite3.Connection, job_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM jobs WHERE job_id = ? LIMIT 1", (job_id,))
    return cur.fetchone() is not None


def insert_job(conn: sqlite3.Connection, job: Job) -> bool:
    """Insert a job. Returns True if a new row was inserted, False if it already existed."""
    cur = conn.execute(INSERT_SQL, job.to_db_row())
    conn.commit()
    return cur.rowcount > 0


def count_jobs(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM jobs")
    return cur.fetchone()[0]
