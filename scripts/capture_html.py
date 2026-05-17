"""
Quick helper to capture rendered HTML from job site pages for selector debugging.
Saves files to tests/fixtures/ and data/debug/.

Usage:
    python scripts/capture_html.py --site zhipin
    python scripts/capture_html.py --site jobsdb
"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures"
DEBUG_DIR = ROOT / "data" / "debug"

SITES = {
    "zhipin": {
        "login_url": "https://www.zhipin.com",
        "storage_state": ROOT / "data" / "storage_state_zhipin.json",
        "search_url": (
            "https://www.zhipin.com/web/geek/jobs"
            "?query=%E8%BB%9F%E4%BB%B6%E5%B7%A5%E7%A8%8B%E5%B8%AB"
            "&city=101020100"
        ),
        "detail_url": "https://www.zhipin.com/job_detail/ed52ef5b3b612e1f0ndz3d60EFVV.html",
        "detail_id": "ed52ef5b3b612e1f0ndz3d60EFVV",
    },
    "jobsdb": {
        "login_url": "https://hk.jobsdb.com",
        "storage_state": ROOT / "data" / "storage_state_jobsdb.json",
        "search_url": "https://hk.jobsdb.com/software-engineer-jobs/in-Hong-Kong-SAR",
        "detail_url": "https://hk.jobsdb.com/job/92078211",
        "detail_id": "92078211",
    },
}


def ensure_login(pw, site: dict):
    site["storage_state"].parent.mkdir(parents=True, exist_ok=True)
    if not site["storage_state"].exists():
        print(f"No saved session. Opening browser for login at {site['login_url']} ...")
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(site["login_url"])
        input("Log in, then press Enter...")
        ctx.storage_state(path=str(site["storage_state"]))
        ctx.close()
        browser.close()
        print(f"Session saved to {site['storage_state']}")


def capture(pw, site: dict, name: str):
    browser = pw.chromium.launch(headless=False)
    ctx = browser.new_context(storage_state=str(site["storage_state"]))
    page = ctx.new_page()

    # --- Search results page ---
    print(f"\nOpening search page:\n  {site['search_url']}\n")
    page.goto(site["search_url"], wait_until="domcontentloaded")
    input("Wait until job cards are visible, then press Enter...")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURES_DIR / f"{name}_search_results.html"
    out.write_text(page.content(), encoding="utf-8")
    print(f"Saved -> {out}")

    # --- Job detail page ---
    print(f"\nOpening job detail page:\n  {site['detail_url']}\n")
    page.goto(site["detail_url"], wait_until="domcontentloaded")
    input("Wait until the job detail is fully loaded, then press Enter...")
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    out2 = DEBUG_DIR / f"{site['detail_id']}.html"
    out2.write_text(page.content(), encoding="utf-8")
    fixture = FIXTURES_DIR / f"{name}_job_detail_sample.html"
    fixture.write_text(page.content(), encoding="utf-8")
    print(f"Saved -> {out2}")
    print(f"Saved parser fixture -> {fixture}")

    ctx.close()
    browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["zhipin", "jobsdb"], default="jobsdb")
    args = parser.parse_args()

    site = SITES[args.site]
    with sync_playwright() as pw:
        ensure_login(pw, site)
        capture(pw, site, args.site)
    print("\nDone. You can now run: pytest tests/")
