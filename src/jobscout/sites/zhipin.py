"""
Zhipin (BOSS直聘) site crawler.

NOTE on brittleness: Zhipin is a Vue SPA whose hashed class names rotate on
deploys. We prefer semantic anchors (href patterns, label text) over hashed
classes. When the parser breaks, run with --debug-dump, look at the saved
HTML, and adjust SELECTORS at the top of this module.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from jobscout.config import CrawlConfig, DEBUG_HTML_DIR
from jobscout.models import Job, JobListing
from jobscout.sites.base import SiteCrawler


BASE_URL = "https://www.zhipin.com"
SEARCH_PATH = "/web/geek/job"


# Common city -> Zhipin city code. The user can also pass a raw numeric code.
# 100 == "all China". Verify/extend during use.
CITY_CODES: dict[str, str] = {
    "all": "100",
    "beijing": "101010100",
    "北京": "101010100",
    "shanghai": "101020100",
    "上海": "101020100",
    "guangzhou": "101280100",
    "广州": "101280100",
    "shenzhen": "101280600",
    "深圳": "101280600",
    "hangzhou": "101210100",
    "杭州": "101210100",
    "chengdu": "101270100",
    "成都": "101270100",
    "nanjing": "101190100",
    "南京": "101190100",
}


# All site-specific selectors live here. Update in one place when Zhipin changes.
SELECTORS = {
    # List page
    "job_card_link": 'a[href*="/job_detail/"]',
    "list_loaded": 'a[href*="/job_detail/"]',  # first selector that proves results rendered

    # Detail page — verify and adjust on first run with --debug-dump
    "detail_title": [
        '.job-primary .name h1',
        '.job-banner .name',
        'h1',
    ],
    "detail_salary": [
        '.job-primary .salary',
        '.job-banner .salary',
        '.salary',
    ],
    "detail_company": [
        '.company-info .name',
        '.sider-company .name',
        '.company-name',
    ],
    "detail_tags": [
        '.job-primary .tag-list li',
        '.job-banner .tag-list li',
        '.tag-list li',
        '.job-tags span',
    ],
    "detail_description": [
        '.job-sec-text',
        '.job-detail-section .text',
        '.job-detail .text',
    ],
    "detail_location": [
        '.job-primary .location',
        '.location-address',
        '.job-location',
    ],
}


JOB_ID_RE = re.compile(r"/job_detail/([^./?#]+)\.html")
SALARY_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*([KkWw万元])", re.UNICODE)


def resolve_city_code(city: Optional[str]) -> Optional[str]:
    if not city:
        return None
    if city.isdigit():
        return city
    return CITY_CODES.get(city.strip().lower())


def build_search_url(config: CrawlConfig) -> str:
    params: dict[str, str] = {"query": config.keyword}
    city_code = resolve_city_code(config.city)
    if city_code:
        params["city"] = city_code
    if config.experience:
        params["experience"] = config.experience
    if config.salary:
        params["salary"] = config.salary
    return urljoin(BASE_URL, SEARCH_PATH) + "?" + urlencode(params)


def extract_job_id(href: str) -> Optional[str]:
    m = JOB_ID_RE.search(href)
    return m.group(1) if m else None


def parse_salary(raw: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """
    Convert a string like '20-35K·14薪' or '15-25K' to (min_thousands, max_thousands).
    Returns (None, None) if it can't be parsed.
    """
    if not raw:
        return (None, None)
    m = SALARY_RE.search(raw)
    if not m:
        return (None, None)
    lo, hi, unit = float(m.group(1)), float(m.group(2)), m.group(3)
    if unit in ("W", "w", "万"):
        # convert 万/year-ish or 万/month tokens to thousands
        return (int(lo * 10), int(hi * 10))
    return (int(lo), int(hi))


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


# Tags in Zhipin's job-primary block typically encode "city · experience · education".
# We try to pull experience/education out of the tag list by pattern.
EXPERIENCE_RE = re.compile(r"(\d+\s*-\s*\d+\s*年|应届|在校生|经验不限|\d+\s*年(?:以[上下])?)")
EDUCATION_RE = re.compile(
    r"(博士|硕士|本科|大专|高中|中专|学历不限|不限学历)"
)


def parse_job_detail_from_html(html: str, url: str, job_id: str) -> Job:
    soup = BeautifulSoup(html, "html.parser")

    title = _first_text(soup, SELECTORS["detail_title"]) or "(unknown title)"
    company = _first_text(soup, SELECTORS["detail_company"]) or "(unknown company)"
    salary_raw = _first_text(soup, SELECTORS["detail_salary"])
    salary_min, salary_max = parse_salary(salary_raw)
    description = _first_text(soup, SELECTORS["detail_description"])
    location_raw = _first_text(soup, SELECTORS["detail_location"])

    tags = _all_texts(soup, SELECTORS["detail_tags"])

    experience: Optional[str] = None
    education: Optional[str] = None
    skills: list[str] = []
    for tag in tags:
        if experience is None and EXPERIENCE_RE.search(tag):
            experience = EXPERIENCE_RE.search(tag).group(1)
            continue
        if education is None and EDUCATION_RE.search(tag):
            education = EDUCATION_RE.search(tag).group(1)
            continue
        # Anything left is treated as a skill chip.
        skills.append(tag)

    city: Optional[str] = None
    district: Optional[str] = None
    if location_raw:
        # Zhipin often shows "城市·区·街道" style locations.
        parts = [p for p in re.split(r"[·•・\s]+", location_raw) if p]
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
        experience=experience,
        education=education,
        skills=skills,
        description=description,
        posted_at=None,
    )


class ZhipinCrawler(SiteCrawler):
    def iter_job_listings(self, page: Page) -> Iterator[JobListing]:
        url = build_search_url(self.config)
        print(f"Opening search: {url}")
        page.goto(url, wait_until="domcontentloaded")

        try:
            page.wait_for_selector(SELECTORS["list_loaded"], timeout=20_000)
        except Exception:
            # The page may show a verification challenge or be empty. Surface and stop.
            print("! search results did not load — Zhipin may be showing a captcha or empty results.")
            return

        seen: set[str] = set()
        for page_index in range(self.config.max_pages):
            anchors = page.locator(SELECTORS["job_card_link"]).all()
            new_on_this_page = 0
            for a in anchors:
                href = a.get_attribute("href") or ""
                jid = extract_job_id(href)
                if not jid or jid in seen:
                    continue
                seen.add(jid)
                new_on_this_page += 1
                title_hint = (a.text_content() or "").strip() or None
                full_url = urljoin(BASE_URL, href)
                yield JobListing(job_id=jid, url=full_url, title_hint=title_hint)

            if page_index == self.config.max_pages - 1:
                break

            # Trigger pagination via scroll (Zhipin's list lazy-loads on scroll).
            prev_count = len(anchors)
            page.mouse.wheel(0, 4000)
            try:
                page.wait_for_function(
                    f"document.querySelectorAll('{SELECTORS['job_card_link']}').length > {prev_count}",
                    timeout=8_000,
                )
            except Exception:
                # No more results loaded — stop paginating.
                break

    def parse_job_detail(self, page: Page, listing: JobListing) -> Job:
        page.goto(listing.url, wait_until="domcontentloaded")
        # Wait for any plausible description selector to show up before reading content.
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
