from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Playwright

from jobscout.config import USER_AGENT, VIEWPORT


def storage_state_present(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def clear_storage_state(path: Path) -> None:
    if path.exists():
        path.unlink()


def ensure_storage_state(
    playwright: Playwright,
    storage_state_path: Path,
    login_url: str = "https://www.zhipin.com",
) -> Path:
    """
    Return the storage_state path, creating it via a headed login flow if it doesn't exist.
    Caller passes the path into browser.new_context(storage_state=...).
    """
    if storage_state_present(storage_state_path):
        return storage_state_path

    storage_state_path.parent.mkdir(parents=True, exist_ok=True)

    print("No saved session found. Opening a browser for manual login.")
    print(f"  1. Log in at {login_url} using QR or SMS.")
    print("  2. Once you can see your logged-in homepage, return here and press Enter.")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(user_agent=USER_AGENT, viewport=VIEWPORT)
    page = context.new_page()
    page.goto(login_url)

    try:
        input("Press Enter after you have completed login... ")
    finally:
        context.storage_state(path=str(storage_state_path))
        context.close()
        browser.close()

    print(f"Session saved to {storage_state_path}")
    return storage_state_path
