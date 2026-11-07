"""Reuse the latest download in data-scraping/ unless it is older than MAX_AGE_DAYS (fewer requests to the servers)."""
import datetime
import re
from pathlib import Path

MAX_AGE_DAYS = 90  # about three months
FOLDER = Path(__file__).resolve().parent.parent / "data-scraping"


def latest(prefix, ext):
    """(path, date) of the newest data-scraping/<prefix>-YYYY-MM-DD.<ext> not older than MAX_AGE_DAYS, else (None, None)."""
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d{{4}}-\d\d-\d\d)\.{re.escape(ext)}$")
    found = []
    for p in FOLDER.glob(f"{prefix}-*.{ext}"):
        m = pattern.match(p.name)
        if m:
            found.append((m.group(1), p))
    if not found:
        return None, None
    day, path = max(found)
    age = (datetime.date.today() - datetime.date.fromisoformat(day)).days
    return (path, day) if age <= MAX_AGE_DAYS else (None, None)
