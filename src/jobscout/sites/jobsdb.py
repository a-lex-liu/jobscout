"""
JobsDB Hong Kong crawler (hk.jobsdb.com).

NOTE: Selectors marked 'verify' need to be confirmed against captured HTML.
Run: python scripts/capture_html.py --site jobsdb
Then paste the HTML here to validate and fix any selectors.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Iterator, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from jobscout.config import CrawlConfig, DEBUG_HTML_DIR
from jobscout.models import Job, JobListing
from jobscout.sites.base import SiteCrawler


BASE_URL = "https://hk.jobsdb.com"

# All site-specific selectors in one place — update here when JobsDB changes.
SELECTORS = {
    # Search results page
    "job_card_link": 'a[href*="/job/"]',
    "list_loaded": 'a[href*="/job/"]',
    "next_page": 'a[aria-label="Next"]',      # verify

    # Job detail page — verify against captured HTML
    "detail_title": [
        'h1[data-automation="job-detail-title"]',
        'h1',
    ],
    "detail_company": [
        'span[data-automation="advertiser-name"]',
        '[data-automation="job-detail-company"]',
        '.company-name',
    ],
    "detail_salary": [
        '[data-automation="job-detail-salary"]',
        '[data-automation="salary"]',
        '.salary',
    ],
    "detail_location": [
        '[data-automation="job-detail-location"]',
        '[data-automation="location"]',
    ],
    "detail_tags": [
        '[data-automation="job-detail-classifications"] a',
        '[data-automation="job-detail-work-type"]',
        '.tag',
    ],
    "detail_description": [
        '[data-automation="jobAdDetails"]',
        '[data-automation="job-detail-description"]',
        '.job-details',
    ],
    "detail_posted_at": [
        '[data-automation="job-detail-date"]',
    ],
}

JOB_ID_RE = re.compile(r"/job/(\d+)")
SALARY_RE = re.compile(r"HK\$\s*([\d,]+)\s*[-–]\s*([\d,]+)", re.IGNORECASE)


def slugify(text: str) -> str:
    """Convert 'software engineer' -> 'software-engineer'."""
    return re.sub(r"\s+", "-", text.strip().lower())


def build_search_url(config: CrawlConfig, page_num: int = 1) -> str:
    """
    JobsDB uses SEO-friendly slug URLs:
      https://hk.jobsdb.com/{keyword}-jobs/in-{location}?page=2
    Default location: Hong-Kong-SAR
    """
    location = slugify(config.city) if config.city else "Hong-Kong-SAR"
    keyword_slug = slugify(config.keyword)
    url = f"{BASE_URL}/{keyword_slug}-jobs/in-{location}"
    if page_num > 1:
        url += f"?page={page_num}"
    return url


def extract_job_id(href: str) -> Optional[str]:
    m = JOB_ID_RE.search(href)
    return m.group(1) if m else None


def parse_salary(raw: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """
    Parse 'HK$20,000 - HK$30,000' into (20, 30) thousands.
    Returns (None, None) if unparseable.
    """
    if not raw:
        return (None, None)
    m = SALARY_RE.search(raw)
    if not m:
        return (None, None)
    lo = int(m.group(1).replace(",", "")) // 1000
    hi = int(m.group(2).replace(",", "")) // 1000
    return (lo, hi)


def _first_text(soup: BeautifulSoup, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return None


def _all_texts(soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    for sel in selectors:
        els = soup.select(sel)
        if els:
            texts = [e.get_text(strip=True) for e in els]
            texts = [t for t in texts if t]
            if texts:
                return texts
    return []


def parse_job_detail_from_html(html: str, url: str, job_id: str) -> Job:
    soup = BeautifulSoup(html, "html.parser")

    title = _first_text(soup, SELECTORS["detail_title"]) or "(unknown title)"
    company = _first_text(soup, SELECTORS["detail_company"]) or "(unknown company)"
    salary_raw = _first_text(soup, SELECTORS["detail_salary"])
    salary_min, salary_max = parse_salary(salary_raw)
    description = _first_text(soup, SELECTORS["detail_description"])
    location_raw = _first_text(soup, SELECTORS["detail_location"])
    posted_at = _first_text(soup, SELECTORS["detail_posted_at"])

    tags = _all_texts(soup, SELECTORS["detail_tags"])

    city: Optional[str] = None
    district: Optional[str] = None
    if location_raw:
        parts = [p.strip() for p in location_raw.split(",") if p.strip()]
        if parts:
            city = parts[0]
        if len(parts) > 1:
            district = parts[1]

    return Job(
        job_id=job_id,
        title=title,
        company=company,
        url=url,
        crawled_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        city=city,
        district=district,
        salary_raw=salary_raw,
        salary_min=salary_min,
        salary_max=salary_max,
        experience=None,    # JobsDB embeds experience in description; parse later if needed
        education=None,
        skills=tags,
        description=description,
        posted_at=posted_at,
    )


class JobsdbCrawler(SiteCrawler):
    def iter_job_listings(self, page: Page) -> Iterator[JobListing]:
        seen: set[str] = set()

        for page_num in range(1, self.config.max_pages + 1):
            url = build_search_url(self.config, page_num)
            print(f"Opening search page {page_num}: {url}")
            page.goto(url, wait_until="domcontentloaded")

            try:
                page.wait_for_selector(SELECTORS["list_loaded"], timeout=20_000)
            except Exception:
                print("! search results did not load.")
                return

            anchors = page.locator(SELECTORS["job_card_link"]).all()
            new_on_page = 0
            for a in anchors:
                href = a.get_attribute("href") or ""
                jid = extract_job_id(href)
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                new_on_page += 1
                title_hint = (a.text_content() or "").strip() or None
                full_url = urljoin(BASE_URL, href)
                yield JobListing(job_id=jid, url=full_url, title_hint=title_hint)

            if new_on_page == 0:
                # No new jobs on this page — end of results.
                break

    def parse_job_detail(self, page: Page, listing: JobListing) -> Job:
        page.goto(listing.url, wait_until="domcontentloaded")

        for sel in SELECTORS["detail_description"]:
            try:
                page.wait_for_selector(sel, timeout=8_000)
                break
            except Exception:
                continue

        html = page.content()

        if self.config.debug_dump:
            DEBUG_HTML_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_HTML_DIR / f"{listing.job_id}.html").write_text(html, encoding="utf-8")

        return parse_job_detail_from_html(html, listing.url, listing.job_id)
