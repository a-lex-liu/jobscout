from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "jobs.db"
STORAGE_STATE_PATH = DATA_DIR / "storage_state.json"
DEBUG_HTML_DIR = DATA_DIR / "debug"

# Realistic recent Chrome on Windows.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1366, "height": 768}

DEFAULT_DELAY_RANGE = (2.0, 5.0)


@dataclass
class CrawlConfig:
    keyword: str
    city: Optional[str] = None
    max_jobs: int = 30
    max_pages: int = 5
    experience: Optional[str] = None
    salary: Optional[str] = None
    headless: bool = True
    debug_dump: bool = False
    delay_range: tuple[float, float] = field(default_factory=lambda: DEFAULT_DELAY_RANGE)
