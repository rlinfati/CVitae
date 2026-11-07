#!/usr/bin/env python3
"""Download the Google Scholar profile (all pages of articles) and write data/0101-scholar.yml (citations, h-index, i10-index).

Usage:
  python3 scripts/scholar-download.py            reuse the latest download if it is under three months old
  python3 scripts/scholar-download.py --force    download it again

Saves, in data-scraping/ (ignored by git):
  scholar-linfati-pagN-YYYY-MM-DD.html   each page of 100 articles, untouched (page 1 also has the metrics table)
  scholar-linfati-YYYY-MM-DD.json        all articles (title, authors, venue, year, citations, link)
and writes data/0101-scholar.yml, read by `{{< cv scholar >}}`. If Google answers with something that is not
the profile (captcha, changed layout) nothing is written and the previous numbers stay.
"""
import datetime
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import latest

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "data-scraping"
USER = "6bJ02OAAAAAJ"
PAGE = 100
FORCE = "--force" in sys.argv
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"


def fetch(start):
    url = f"https://scholar.google.com/citations?user={USER}&hl=en&view_op=list_works&sortby=pubdate&cstart={start}&pagesize={PAGE}"
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def rows_of(text):
    return re.findall(r'<tr class="gsc_a_tr">(.*?)</tr>', text, flags=re.S)


def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def article(row):
    m = re.search(r'<a href="([^"]*)" class="gsc_a_at">(.*?)</a>', row, flags=re.S)
    gray = re.findall(r'<div class="gs_gray">(.*?)</div>', row, flags=re.S)
    cites = re.search(r'class="gsc_a_ac[^"]*"[^>]*>(\d*)<', row)
    year = re.search(r'class="gsc_a_h gsc_a_hc gs_ibl">(\d*)<', row)
    return {
        "title": clean(m.group(2)) if m else "",
        "authors": clean(gray[0]) if gray else "",
        "venue": clean(gray[1]) if len(gray) > 1 else "",
        "year": int(year.group(1)) if year and year.group(1) else None,
        "citations": int(cites.group(1) or 0) if cites else 0,
        "url": "https://scholar.google.com" + html.unescape(m.group(1)) if m else "",
    }


first, day = latest("scholar-linfati-pag1", "html")
if first and not FORCE:
    status = "exists, not downloaded again"
    pages = []
    n = 1
    while (FOLDER / f"scholar-linfati-pag{n}-{day}.html").exists():
        pages.append(((FOLDER / f"scholar-linfati-pag{n}-{day}.html").read_bytes()))
        n += 1
else:
    status, day, pages, start = "downloaded", datetime.date.today().isoformat(), [], 0
    while True:
        raw = fetch(start)
        pages.append(raw)
        if len(rows_of(raw.decode("utf-8", errors="replace"))) < PAGE:
            break
        start += PAGE
        time.sleep(8)  # be gentle with Google

texts = [p.decode("utf-8", errors="replace") for p in pages]
# the table has six cells: citations, h-index and i10-index, each "All" and "Since <year>"
cells = re.findall(r'<td class="gsc_rsb_std">(\d+)</td>', texts[0])
if len(cells) != 6 or not rows_of(texts[0]):
    sys.exit(f"Scholar: the profile table was not found ({len(cells)} cells); the page may be a captcha or have a new layout. Nothing written.")
articles = [article(r) for t in texts for r in rows_of(t)]
if status == "downloaded":
    FOLDER.mkdir(exist_ok=True)
    for i, raw in enumerate(pages, 1):
        (FOLDER / f"scholar-linfati-pag{i}-{day}.html").write_bytes(raw)
(FOLDER / f"scholar-linfati-{day}.json").write_text(
    json.dumps({"user": USER, "date": day, "articles": articles}, ensure_ascii=False, indent=1), encoding="utf-8")
citations, h, i10 = (int(cells[i]) for i in (0, 2, 4))
(ROOT / "data" / "0101-scholar.yml").write_text(
    f'items:\n  - citations: {citations}\n    h-index: {h}\n    i10-index: {i10}\n    date: "{day}"\n    user: "{USER}"\n',
    encoding="utf-8",
)
print(f"scholar-linfati-{day}.json ({status}): {len(articles)} articles in {len(pages)} page(s); data/0101-scholar.yml: citations {citations}, h-index {h}, i10-index {i10}, as of {day}")
