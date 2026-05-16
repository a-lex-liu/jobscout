# jobscout

Personal job scout for Zhipin (BOSS直聘). Runs locally via Playwright, stores listings in a SQLite database.

## Setup

```powershell
# 1. Create venv + install
uv venv --python 3.11           # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -e ".[dev]"      # or: pip install -e ".[dev]"

# 2. Install Chromium for Playwright
python -m playwright install chromium
```

## First run (manual login)

```powershell
jobscout --keyword "Python" --city Beijing --max-jobs 5 --debug-dump
```

The first invocation opens a visible Chromium window. Log in via QR or SMS, then press Enter in the terminal. Your session is saved to `data/storage_state.json` and reused on later runs.

## Usage

```
jobscout --keyword <kw> [--city <name>] [--max-jobs N] [--max-pages N]
         [--experience <level>] [--salary <range>]
         [--headless/--headed] [--debug-dump] [--relogin]
```

## Querying the data

```powershell
sqlite3 data\jobs.db "SELECT title, company, salary_raw FROM jobs LIMIT 10;"
sqlite3 data\jobs.db "SELECT count(*) FROM jobs;"
sqlite3 data\jobs.db "SELECT title, skills FROM jobs WHERE skills LIKE '%Python%';"
```

## Layout

- `src/jobscout/cli.py` — CLI entry
- `src/jobscout/sites/zhipin.py` — Zhipin-specific selectors and parsing
- `src/jobscout/db.py` — SQLite schema + dedup
- `data/jobs.db` — your crawled data (gitignored)

## Re-login

If a run fails with an auth error, the saved session has expired. Run with `--relogin` to clear it and log in again.
