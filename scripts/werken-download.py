#!/usr/bin/env python3
"""Download the UBB library catalog (WERKEN) records for an author, page by page.

Usage:
  python3 scripts/werken-download.py            reuse the latest pages if they are under three months old
  python3 scripts/werken-download.py --force    download everything again

Saves, in data-scraping/ (ignored by git):
  werken-linfati-pagN-YYYY-MM-DD.html   each result page, untouched (declared ISO-8859-1, really cp1252)
  werken-linfati-YYYY-MM-DD.json        all records parsed (id, title, author, year, call number, format)
"""
import datetime, html, json, os, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import latest

AUTHOR = "Linfati Medina, Rodrigo Carlos Eugenio"
BASE = "http://buscadorwerken.ubiobio.cl/php/busqueda_detalle.php"
FORCE = "--force" in sys.argv
PAUSE = 1.0  # seconds between requests
_, _last = latest("werken-linfati-pag1", "html")
TODAY = _last if _last and not FORCE else datetime.date.today().isoformat()  # date of the pages used

RECORD = re.compile(
    r"<img src='[^']*' [^>]*alt='(?P<kind>[^']*)'>.*?"
    r"<a HREF='existencias\.php\?numero=(?P<id>\d+)'>(?P<title>.*?)</a>.*?"
    r"<font class='autor'>(?P<author>.*?)</font>"
    r"(?:<font class='publicacion'>\s*\[(?P<year>[^\]]*)\]</font>)?.*?"
    r"(?:<font class='dewey'>(?P<call>.*?)</font>)?</font></td></tr>",
    re.S,
)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def page_path(n):
    return f"data-scraping/werken-linfati-pag{n}-{TODAY}.html"


def get_page(n):
    path = page_path(n)
    if os.path.exists(path) and not FORCE:
        with open(path, "rb") as fh:
            return fh.read(), "exists, not downloaded again"
    url = BASE + "?" + urllib.parse.urlencode({"texto": AUTHOR, "tipo_busqueda": "autor", "pag": n}, quote_via=urllib.parse.quote)
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
    with open(path, "wb") as fh:
        fh.write(raw)
    time.sleep(PAUSE)
    return raw, "downloaded"


os.makedirs("data-scraping", exist_ok=True)
records, total, n = [], None, 1
while True:
    raw, status = get_page(n)
    text = raw.decode("cp1252", errors="replace")  # served as ISO-8859-1 but uses cp1252 characters such as the curly apostrophe
    if total is None:
        m = re.search(r"(\d+) aciertos", text)
        total = int(m.group(1)) if m else 0
    found = [m.groupdict() for m in RECORD.finditer(text)]
    print(f"page {n}: {len(found)} records ({status})")
    if not found:
        os.remove(page_path(n)) if status == "downloaded" else None  # empty page after the last one
        break
    for r in found:
        records.append(dict(id=r["id"], kind=clean(r["kind"]), title=clean(r["title"]), author=clean(r["author"]),
                            year=clean(r["year"]), call_number=clean(r["call"]), page=n))
    n += 1
    if len(records) >= total:
        break

out = f"data-scraping/werken-linfati-{TODAY}.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump({"author": AUTHOR, "hits": total, "records": records}, fh, ensure_ascii=False, indent=2)
print(f"saved {out}: {len(records)} records of {total} hits")
if len(records) != total:
    print("WARNING: the number of parsed records differs from the number of hits")
