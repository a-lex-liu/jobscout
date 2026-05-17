from __future__ import annotations

import sys
from pathlib import Path

import click
from playwright.sync_api import sync_playwright

from jobscout import auth, db
from jobscout.config import (
    DB_PATH,
    STORAGE_STATE_ZHIPIN,
    STORAGE_STATE_JOBSDB,
    USER_AGENT,
    VIEWPORT,
    CrawlConfig,
)
from jobscout.sites.zhipin import ZhipinCrawler
from jobscout.sites.jobsdb import JobsdbCrawler

SITE_CONFIG = {
    "zhipin": {
        "crawler_cls": ZhipinCrawler,
        "storage_state": STORAGE_STATE_ZHIPIN,
        "login_url": "https://www.zhipin.com",
    },
    "jobsdb": {
        "crawler_cls": JobsdbCrawler,
        "storage_state": STORAGE_STATE_JOBSDB,
        "login_url": "https://hk.jobsdb.com",
    },
}


@click.command()
@click.option("--keyword", required=True, help="Search keyword, e.g. 'software engineer' or 'Python'.")
@click.option("--site", default="jobsdb", show_default=True, type=click.Choice(["zhipin", "jobsdb"]), help="Job site to crawl.")
@click.option("--city", default=None, help="City/location filter. For Zhipin: city name or code. For JobsDB: location slug (default: Hong-Kong-SAR).")
@click.option("--max-jobs", default=30, show_default=True, type=int, help="Max number of new jobs to crawl.")
@click.option("--max-pages", default=5, show_default=True, type=int, help="Max search result pages to scan.")
@click.option("--experience", default=None, help="Experience filter (site-specific value).")
@click.option("--salary", default=None, help="Salary filter (site-specific value).")
@click.option("--headless/--headed", default=True, help="Run the crawl headless (login is always headed).")
@click.option("--debug-dump", is_flag=True, help="Save raw HTML of each visited detail page to data/debug/.")
@click.option("--relogin", is_flag=True, help="Discard saved session and prompt for login again.")
@click.option(
    "--db-path",
    default=str(DB_PATH),
    show_default=True,
    type=click.Path(),
    help="SQLite database path.",
)
def main(
    keyword: str,
    site: str,
    city: str | None,
    max_jobs: int,
    max_pages: int,
    experience: str | None,
    salary: str | None,
    headless: bool,
    debug_dump: bool,
    relogin: bool,
    db_path: str,
) -> None:
    """Crawl job listings into a local SQLite database."""
    site_cfg = SITE_CONFIG[site]

    config = CrawlConfig(
        keyword=keyword,
        city=city,
        max_jobs=max_jobs,
        max_pages=max_pages,
        experience=experience,
        salary=salary,
        headless=headless,
        debug_dump=debug_dump,
    )

    storage_state_path = site_cfg["storage_state"]

    if relogin:
        auth.clear_storage_state(storage_state_path)
        print("Saved session cleared.")

    conn = db.connect(Path(db_path))
    db.init_schema(conn)

    with sync_playwright() as pw:
        state_path = auth.ensure_storage_state(
            pw, storage_state_path, login_url=site_cfg["login_url"]
        )

        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                storage_state=str(state_path),
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
            )
            try:
                crawler = site_cfg["crawler_cls"](context, config)
                stats = crawler.run(conn)
            finally:
                context.close()
        finally:
            browser.close()

    total = db.count_jobs(conn)
    conn.close()
    print(f"Done: {stats}. Total jobs in db: {total}.")
    if stats.failed > 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
