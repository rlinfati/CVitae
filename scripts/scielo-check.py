#!/usr/bin/env python3
"""Check which papers of data/0701-0704 are in SciELO (ArticleMeta public API, https://articlemeta.scielo.org).

Level 1 (journal): the entry's ISSNs (issn-print / issn-online / issn-series) against the SciELO journal list (only to choose where to look; nothing is written for it).
Level 2 (article): inside that journal, find the issue (year + volume + number), list its article PIDs and match the DOI
(or the title if the record has no DOI or a different one). Only level 2 is written.

Result per entry:
  id-scielo: "<PID>"  article found in SciELO (counts)
  id-scielo: "NOK"    journal is in SciELO, but every article of the issue was checked and this one is not there (does not count)
  (no id-scielo)      journal not in SciELO, or article level not resolved (does not count)

Usage:
  python3 scripts/scielo-check.py            report only
  python3 scripts/scielo-check.py --write    also write id-scielo into the data files
  python3 scripts/scielo-check.py --force    ignore the cache (files younger than three months are reused otherwise)

Saves, in data-scraping/ (ignored by git): scielo-journals-DATE.json, scielo-issues-ISSN-DATE.json, scielo-articles-ISSN-DATE.json.
"""
import datetime, glob, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import latest, FOLDER

API = "https://articlemeta.scielo.org/api/v1/"
FILES = sorted(glob.glob("data/070[1-4]-*.yml"))  # journal articles and conference papers (not 0705, preprints)
FORCE = "--force" in sys.argv
WRITE = "--write" in sys.argv
PAUSE = 0.5
MAX_CANDIDATES = 400  # articles fetched per paper, at most
TODAY = datetime.date.today().isoformat()
FOLDER.mkdir(exist_ok=True)


def get(path, **params):
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                raw = r.read()
            time.sleep(PAUSE)
            return json.loads(raw)
        except Exception as e:  # network or JSON
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def cached(prefix, build):
    """Latest data-scraping/<prefix>-DATE.json if fresh, else build() and save it."""
    path, _ = latest(prefix, "json")
    if path and not FORCE:
        return json.load(open(path, encoding="utf-8")), path
    data = build()
    path = FOLDER / f"{prefix}-{TODAY}.json"
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data, path


def save(prefix, data):
    json.dump(data, open(FOLDER / f"{prefix}-{TODAY}.json", "w", encoding="utf-8"), ensure_ascii=False)


# ---- level 1: journals
def load_journals():
    raw, _ = cached("scielo-journals", lambda: get("journal/"))
    index = {}  # issn -> [(collection, code, title, status)]
    for j in raw:
        issns = set(j.get("issns", [])) | {x["_"] for k in ("v400", "v935") for x in j.get(k, [])}
        info = (j["collection"], j["code"], (j.get("v100") or [{}])[0].get("_", ""), (j.get("v50") or [{}])[0].get("_", ""))
        for i in issns:
            index.setdefault(i, []).append(info)
    return index


# ---- level 2: articles
def load_ids(code, collection):
    prefix = f"scielo-ids-{code}-{collection}"
    def build():
        out, offset = [], 0
        while True:
            d = get("article/identifiers/", issn=code, collection=collection, limit=1000, offset=offset)
            out += [o["code"] for o in d["objects"]]
            offset += 1000
            if offset >= d["meta"]["total"]:
                return out
    return cached(prefix, build)[0]


def load_issues(code, collection):
    prefix = f"scielo-issues-{code}-{collection}"
    def build():
        d = get("issue/identifiers/", issn=code, collection=collection, limit=1000)
        out = {}
        for o in d["objects"]:
            out[o["code"]] = None  # volume/number are fetched when the year is needed
        return out
    return cached(prefix, build)


def issue_numbers(code, collection, issues, year):
    """Fetch volume/number of the issues of one year, once."""
    changed = False
    for ic in issues:
        if ic[9:13] == str(year) and issues[ic] is None:
            d = get("issue/", collection=collection, code=ic)
            i = d.get("issue", {}) if d else {}
            f = lambda k: (i.get(k) or [{}])[0].get("_", "")
            issues[ic] = {"volume": f("v31"), "number": f("v32")}
            changed = True
    if changed:
        save(f"scielo-issues-{code}-{collection}", issues)


def norm_doi(s):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", (s or "").strip().lower())


def words(s):
    return {w for w in re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split() if len(w) > 2}


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0


def find_article(e, code, collection):
    """-> (pid | 'NOK' | None, note)."""
    year = e.get("year")
    if not year:
        return None, "no year"
    issues, _ = load_issues(code, collection)
    issue_numbers(code, collection, issues, year)
    in_year = [ic for ic in issues if ic[9:13] == str(year)]  # issue code: ISSN (9) + year (4) + order (4)
    if not in_year:
        return "NOK", "no issue of that year in SciELO"
    vol, num = str(e.get("volume") or ""), str(e.get("number") or "")
    exact = [ic for ic in in_year if issues[ic] and (not vol or issues[ic]["volume"] == vol) and (not num or issues[ic]["number"] == num)]
    chosen, how = (exact, "issue") if exact else (in_year, "year")
    pids = [p for p in load_ids(code, collection) if any(p[1:].startswith(ic) for ic in chosen)]
    if len(pids) > MAX_CANDIDATES:
        return None, f"{len(pids)} candidates, skipped"
    arts_prefix = f"scielo-articles-{code}-{collection}"
    path, _ = latest(arts_prefix, "json")
    arts = json.load(open(path, encoding="utf-8")) if path and not FORCE else {}
    changed = False
    want_doi, want_title = norm_doi(e.get("doi")), words(e.get("title"))
    hit, by = None, ""
    for pid in pids:
        if pid not in arts:
            d = get("article/", collection=collection, code=pid)
            a = (d or {}).get("article", {})
            arts[pid] = {"doi": (a.get("v237") or [{}])[0].get("_", ""),
                         "titles": [t["_"] for t in a.get("v12", []) if t.get("_")]}
            changed = True
        a = arts[pid]
        if want_doi and norm_doi(a["doi"]) == want_doi:
            hit, by = pid, "DOI"
            break
        if any(jac(want_title, words(t)) >= 0.9 for t in a["titles"]):  # no DOI in the record, or a different one
            hit, by = pid, "title"
            break
    if changed:
        save(arts_prefix, arts)
    if hit:
        return hit, f"matched by {by} ({how})"
    if not pids:
        return None, f"no articles listed ({how})"
    return "NOK", f"not among {len(pids)} articles of the {how}"


# ---- entries
def field(b, k):
    m = re.search(r'(?m)^    %s: "?(.*?)"?$' % re.escape(k), b)
    return m.group(1) if m else None


def entry_of(b):
    t = re.search(r'(?m)^    title: "(.*?)"$', b)
    y = field(b, "year")
    return {"key": field(b, "key") or re.match(r"\s*key: (\S+)", b).group(1), "title": t.group(1) if t else "",
            "year": int(y) if y and y.isdigit() else None, "volume": field(b, "volume"), "number": field(b, "number"),
            "doi": field(b, "doi"), "issns": re.findall(r'(?m)^    issn[\w-]*: "([\dX]{4}-[\dX]{4})"', b)}


def put(block, key, value):
    block = re.sub(r'(?m)^    %s: .*\n?' % key, "", block)
    line = f'    {key}: "{value}"\n'
    for anchor in (r"(?m)^    doi: .*\n", r"(?m)(^    issn[\w-]*: .*\n)(?!    issn)"):
        m = re.search(anchor, block)
        if m:
            return block[:m.end()] + line + block[m.end():]
    return block.rstrip("\n") + "\n" + line


def main():
    journals = load_journals()
    rows, edits = [], {}
    for f in FILES:
        text = open(f, encoding="utf-8").read()
        parts = re.split(r"(?m)^(  - key:)", text)
        out = [parts[0]]
        for i in range(1, len(parts), 2):
            head, body = parts[i], parts[i + 1]
            e = entry_of("key:" + body)
            hits = [h for s in e["issns"] for h in journals.get(s, [])]
            res = None
            if hits:
                for col, code, title, status in dict.fromkeys(hits):
                    try:
                        res = find_article(e, code, col)
                    except Exception as ex:
                        res = (None, f"error: {ex}")
                    if res[0] and res[0] != "NOK":
                        break
                col, code, title, status = hits[0]
                rows.append((f.split("/")[1][:4], e["key"], f"{col} {title[:28]}", res[0] or "-", res[1]))
                if WRITE:
                    if res[0]:
                        body = put(body, "id-scielo", res[0])
            out += [head, body]
        edits[f] = "".join(out)
    w = max(len(r[1]) for r in rows) if rows else 10
    print(f"{'file':<5}{'key':<{w+1}}{'journal':<31}{'article':<26}note")
    for r in rows:
        print(f"{r[0]:<5}{r[1]:<{w+1}}{r[2]:<31}{r[3]:<26}{r[4]}")
    found = sum(1 for r in rows if r[3] not in ("-", "NOK"))
    nok = sum(1 for r in rows if r[3] == "NOK")
    print(f"\nin SciELO journals: {len(rows)}; article confirmed (id-scielo): {found}; confirmed absent (NOK): {nok}; unresolved: {len(rows) - found - nok}")
    if WRITE:
        for f, t in edits.items():
            open(f, "w", encoding="utf-8").write(t)
        print("written to data files")
    else:
        print("report only (use --write to save into the data files)")


main()
