from __future__ import annotations

import random
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from playwright.sync_api import BrowserContext, Page

from jobscout import db
from jobscout.config import CrawlConfig
from jobscout.models import Job, JobListing


@dataclass
class CrawlStats:
    new: int = 0
    skipped: int = 0
    failed: int = 0

    def __str__(self) -> str:
        return f"{self.new} new, {self.skipped} skipped, {self.failed} failed"


class SiteCrawler(ABC):
    def __init__(self, context: BrowserContext, config: CrawlConfig) -> None:
        self.context = context
        self.config = config

    @abstractmethod
    def iter_job_listings(self, page: Page) -> Iterator[JobListing]:
        """Yield JobListing entries from the search results, respecting max_pages/max_jobs."""

    @abstractmethod
    def parse_job_detail(self, page: Page, listing: JobListing) -> Job:
        """Navigate to listing.url and return a populated Job."""

    def run(self, conn: sqlite3.Connection) -> CrawlStats:
        stats = CrawlStats()
        list_page = self.context.new_page()

        try:
            queued: list[JobListing] = []
            for listing in self.iter_job_listings(list_page):
                if db.job_exists(conn, listing.job_id):
                    stats.skipped += 1
                    continue
                queued.append(listing)
                if len(queued) >= self.config.max_jobs:
                    break
        finally:
            list_page.close()

        if not queued:
            return stats

        detail_page = self.context.new_page()
        try:
            for listing in queued:
                lo, hi = self.config.delay_range
                time.sleep(random.uniform(lo, hi))
                try:
                    job = self.parse_job_detail(detail_page, listing)
                except Exception as exc:
                    stats.failed += 1
                    print(f"  ! failed to parse {listing.url}: {exc}")
                    continue
                inserted = db.insert_job(conn, job)
                if inserted:
                    stats.new += 1
                    print(f"  + {job.title} @ {job.company}")
                else:
                    stats.skipped += 1
        finally:
            detail_page.close()

        return stats
