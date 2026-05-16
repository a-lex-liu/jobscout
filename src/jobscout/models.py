from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    url: str
    crawled_at: str
    city: Optional[str] = None
    district: Optional[str] = None
    salary_raw: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    experience: Optional[str] = None
    education: Optional[str] = None
    skills: list[str] = field(default_factory=list)
    description: Optional[str] = None
    posted_at: Optional[str] = None

    def to_db_row(self) -> tuple:
        return (
            self.job_id,
            self.title,
            self.company,
            self.city,
            self.district,
            self.salary_raw,
            self.salary_min,
            self.salary_max,
            self.experience,
            self.education,
            json.dumps(self.skills, ensure_ascii=False),
            self.description,
            self.url,
            self.posted_at,
            self.crawled_at,
        )


@dataclass
class JobListing:
    job_id: str
    url: str
    title_hint: Optional[str] = None
