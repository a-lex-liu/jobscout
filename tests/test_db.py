from __future__ import annotations

import datetime as _dt

from jobscout import db
from jobscout.models import Job


def _make_job(job_id: str = "abc123") -> Job:
    return Job(
        job_id=job_id,
        title="Python Engineer",
        company="ACME Corp",
        url=f"https://www.zhipin.com/job_detail/{job_id}.html",
        crawled_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        city="北京",
        district="海淀区",
        salary_raw="20-35K·14薪",
        salary_min=20,
        salary_max=35,
        experience="3-5年",
        education="本科",
        skills=["Python", "Django", "PostgreSQL"],
        description="A nice job.",
    )


def test_init_and_insert_roundtrip(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_schema(conn)

    job = _make_job()
    assert db.job_exists(conn, job.job_id) is False

    inserted = db.insert_job(conn, job)
    assert inserted is True
    assert db.job_exists(conn, job.job_id) is True
    assert db.count_jobs(conn) == 1


def test_insert_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_schema(conn)

    job = _make_job()
    assert db.insert_job(conn, job) is True
    assert db.insert_job(conn, job) is False  # second insert skipped
    assert db.count_jobs(conn) == 1


def test_init_schema_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_schema(conn)
    db.init_schema(conn)
    assert db.count_jobs(conn) == 0


def test_skills_stored_as_json(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    db.init_schema(conn)
    db.insert_job(conn, _make_job())
    row = conn.execute("SELECT skills FROM jobs WHERE job_id = 'abc123'").fetchone()
    assert row[0] == '["Python", "Django", "PostgreSQL"]'
