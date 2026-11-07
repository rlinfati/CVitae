#!/usr/bin/env python3
"""Download the works of the ORCID record (public API, no key) into data-scraping/.

Usage:
  python3 scripts/orcid-download.py            reuse the latest download if it is under three months old
  python3 scripts/orcid-download.py --force    download it again

Saves, in data-scraping/ (ignored by git):
  orcid-works-YYYY-MM-DD.json          list of works grouped by external id (put-codes, titles, DOI, EID, WOS)
  orcid-works-full-YYYY-MM-DD-N.json   each work in full (authors, citation), 100 put-codes per request
Only reads and reports; it does not touch data/.
"""
import datetime
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import latest

ROOT = Path(__file__).resolve().parent.parent
ORCID = "0000-0002-7659-383X"
API = f"https://pub.orcid.org/v3.0/{ORCID}"
FORCE = "--force" in sys.argv


def get(url):
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


path, day = latest("orcid-works", "json")
if path and not FORCE:
    groups = json.loads(path.read_text(encoding="utf-8"))["group"]
    print(f"{path.relative_to(ROOT)} exists, not downloaded again: {len(groups)} groups")
    sys.exit(0)

day = datetime.date.today().isoformat()
works = get(f"{API}/works")
if "group" not in works:
    sys.exit("ORCID: no 'group' in the answer; nothing written.")
folder = ROOT / "data-scraping"
folder.mkdir(exist_ok=True)
(folder / f"orcid-works-{day}.json").write_text(json.dumps(works, ensure_ascii=False), encoding="utf-8")
codes = [str(s["put-code"]) for g in works["group"] for s in g["work-summary"]]
for n, i in enumerate(range(0, len(codes), 100), 1):
    bulk = get(f"{API}/works/{','.join(codes[i:i + 100])}")
    (folder / f"orcid-works-full-{day}-{n}.json").write_text(json.dumps(bulk, ensure_ascii=False), encoding="utf-8")
print(f"data-scraping/orcid-works-{day}.json: {len(works['group'])} groups, {len(codes)} works, {(len(codes) + 99) // 100} full file(s)")
