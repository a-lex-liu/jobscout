from __future__ import annotations

import sys
from pathlib import Path

import click
from playwright.sync_api import sync_playwright

from jobscout import auth, db
from jobscout.config import (
    DB_PATH,
    STORAGE_STATE_PATH,
    USER_AGENT,
    VIEWPORT,
    CrawlConfig,
)
from jobscout.sites.zhipin import ZhipinCrawler


@click.command()
@click.option("--keyword", required=True, help="Search keyword, e.g. 'Python开发' or 'data engineer'.")
@click.option("--city", default=None, help="City name (e.g. Beijing / 北京) or raw Zhipin city code.")
@click.option("--max-jobs", default=30, show_default=True, type=int, help="Max number of new jobs to crawl.")
@click.option("--max-pages", default=5, show_default=True, type=int, help="Max search result pages to scan.")
@click.option("--experience", default=None, help="Raw Zhipin experience filter value (verify in URL).")
@click.option("--salary", default=None, help="Raw Zhipin salary filter value (verify in URL).")
@click.option("--headless/--headed", default=True, help="Run the actual crawl headless (login is always headed).")
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
    """Crawl Zhipin job listings into a local SQLite database."""
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

    if relogin:
        auth.clear_storage_state(STORAGE_STATE_PATH)
        print("Saved session cleared.")

    conn = db.connect(Path(db_path))
    db.init_schema(conn)

    with sync_playwright() as pw:
        state_path = auth.ensure_storage_state(pw, STORAGE_STATE_PATH)

        browser = pw.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                storage_state=str(state_path),
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
            )
            try:
                crawler = ZhipinCrawler(context, config)
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
