#!/usr/bin/env python3
"""Compare data/*.yml with the UBB VRIP registry.

Every run downloads, untouched, into data-scraping/ (dated files, all ignored by git; the latest one under three months old is reused):
  vrip-linfati-projects-YYYY-MM-DD.json   filtered by researcher
  vrip-linfati-papers-YYYY-MM-DD.json     filtered by researcher
  vrip-linfati-mixto-YYYY-MM-DD.json      combined search by surname
  vrip-all-YYYY-MM-DD.json                the whole UBB registry, only with --all
and then merges the three own files into vrip-linfati-YYYY-MM-DD.json, which is the
data used for the comparison.

Usage:
  python3 scripts/vrip-check.py              report only (the latest download is reused if it is under three months old)
  python3 scripts/vrip-check.py --force      download everything again
  python3 scripts/vrip-check.py --all        also download the whole UBB registry (not used by the comparison)
  python3 scripts/vrip-check.py --write-ids  also add `id-ubb-vrip` to entries found in the registry

Reports registry records that are not in the CV data (new?) and id-ubb-vrip (missing = not in the registry)
that disagree with the registry. Entries that already have `id-ubb-vrip` are
matched by id; the others by title (or project code).
"""
import datetime, glob, json, os, re, sys, unicodedata, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache import latest

# Combined search by surname ("mixto"), saved for reference.
URL = "https://vrip.ubiobio.cl/searcher/server/server.php?request=mixta_clave&clave=linfati"

# The registry stores the RUT without its check digit (VRIP_RUT overrides the default).
RUT_DEFAULT = "15512884"
# Keep clave=a: an empty clave makes the server ignore the RUT filter and return
# the entire registry.
# Empty clave returns the whole registry, without researcher filters (only with --all).
ALL_URL = "https://vrip.ubiobio.cl/searcher/server/server.php?request=mixta&clave="
PROJECTS_URL = "https://vrip.ubiobio.cl/searcher/server/server.php?request=proyecto&tipo_proyecto=&periodo_inicio=&periodo_fin=&facultad=20400000&interno=&area_conocimiento=&tipo_programa=&tipo_disciplina=&clave=a&rut_investigador={rut}"
PUBLICATIONS_URL = "https://vrip.ubiobio.cl/searcher/server/server.php?request=publicacion&tip_codigo=-1&pub_ano_inicio=&pub_ano_fin=&mpu_codigo=-1&dpy_codigo=&rep_codigo=20400000&tidi_codigo=&clave=a&acp_rut={rut}"


def load_ids():
    return os.environ.get("VRIP_RUT") or RUT_DEFAULT


PUBS = tuple(Path(f).stem for f in sorted(glob.glob("data/070[1-4]-*.yml")))
PROJECTS = tuple(Path(f).stem for f in sorted(glob.glob("data/060[1-3]-*.yml")))
WRITE = "--write-ids" in sys.argv
FORCE = "--force" in sys.argv
ALL = "--all" in sys.argv


def words(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return {w for w in re.sub(r"[^a-z0-9 ]+", " ", s).split() if len(w) > 2}


def jac(a, b):
    return len(a & b) / max(1, len(a | b))


def field(b, k):
    m = re.search(r'(?m)^    %s: "?(.*?)"?$' % re.escape(k), b)
    return m.group(1) if m else None


def titles(b):
    m = re.search(r'(?m)^    title:\n      en: "(.*?)"\n      es: "(.*?)"', b)
    return [m.group(1), m.group(2)] if m else [field(b, "title") or ""]


def load(names, start):
    out = []
    for name in names:
        path = f"data/{name}.yml"
        text = open(path, encoding="utf-8").read()
        parts = re.split(r"(?m)^(  - %s:)" % start, text)
        for k in range(1, len(parts), 2):
            out.append(dict(path=path, block=parts[k] + parts[k + 1].split("\n  - ")[0] if False else parts[k] + parts[k + 1]))
    return out


def reg_id(r, id_key):
    # publications: pub_correlativo; projects: year-correlativo (the correlativo alone is not unique)
    return str(r[id_key]) if id_key == "pub_correlativo" else f"{r['pri_ano_proyecto']}-{r[id_key]}"


def match(mine, registry, id_key, score):
    """Assign each of my entries to one registry record (by id first, then best score)."""
    assigned, used = {}, set()
    ids = {reg_id(r, id_key): i for i, r in enumerate(registry)}
    for n, e in enumerate(mine):
        rid = field(e["block"], "id-ubb-vrip")
        if rid and rid != "NOK" and rid in ids:
            assigned[n] = ids[rid]
            used.add(ids[rid])
    pairs = sorted(((score(e, r), n, i) for n, e in enumerate(mine) for i, r in enumerate(registry)), reverse=True)
    for s, n, i in pairs:
        if s >= THRESHOLD[id_key] and n not in assigned and i not in used:
            assigned[n] = i
            used.add(i)
    return assigned, used


THRESHOLD = {"pub_correlativo": 0.55, "pri_correlativo": 0.5}


def missing(flag):
    """No id-ubb-vrip (or the old "NOK" mark) = not in the registry."""
    return flag in (None, "", "NOK")


def write_ids(mine, registry, assigned, id_key):
    changes = {}
    for n, i in assigned.items():
        e = mine[n]
        cur = field(e["block"], "id-ubb-vrip")
        if cur and cur != "NOK":
            continue
        rid = reg_id(registry[i], id_key)
        if cur == "NOK":
            new = e["block"].replace('id-ubb-vrip: "NOK"', 'id-ubb-vrip: "%s"' % rid, 1)
        elif re.search(r'(?m)^    ubb-VRIP: ', e["block"]):
            new = re.sub(r'(\n    ubb-VRIP: [^\n]*)', r'\1\n    id-ubb-vrip: "%s"' % rid, e["block"], count=1)
        else:
            new = e["block"].rstrip("\n") + '\n    id-ubb-vrip: "%s"\n' % rid
            if e["block"].endswith("\n\n"):
                new += "\n"
        if new != e["block"]:
            changes.setdefault(e["path"], []).append((e["block"], new))
    for path, pairs in changes.items():
        text = open(path, encoding="utf-8").read()
        for old, new in pairs:
            text = text.replace(old, new, 1)
        open(path, "w", encoding="utf-8").write(text)
    return sum(len(v) for v in changes.values())


os.makedirs("data-scraping", exist_ok=True)
RUT = load_ids()
PROJECTS_URL = PROJECTS_URL.format(rut=RUT)
PUBLICATIONS_URL = PUBLICATIONS_URL.format(rut=RUT)
download_date = datetime.date.today().isoformat()
downloaded, dates = {}, []
for name, url in (("projects", PROJECTS_URL), ("papers", PUBLICATIONS_URL), ("mixto", URL)):
    old, old_date = latest(f"vrip-linfati-{name}", "json")
    saved = f"data-scraping/vrip-linfati-{name}-{download_date}.json"
    if old and not FORCE:  # recent enough: reuse it
        saved = f"data-scraping/{old.name}"
        dates.append(old_date)
        with open(saved, "rb") as fh:
            raw = fh.read()
        status = "exists, not downloaded again"
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read()
        status = "downloaded"
        dates.append(download_date)
    payload = json.loads(raw)
    if payload.get("exito") is not True:
        raise RuntimeError(f"VRIP {name}: {payload}")
    if status == "downloaded":
        with open(saved, "wb") as fh:  # the original response, untouched
            fh.write(raw)
    result = payload["resultado"]
    count = sum(len(v) for v in result.values()) if isinstance(result, dict) else len(result)
    print(f"{saved} ({count} records, {status})")
    downloaded[name] = result


def merged(id_of, *lists):
    """Union of record lists by id; a later list only adds or refreshes fields."""
    out = {}
    for lst in lists:
        for r in lst:
            out.setdefault(id_of(r), {}).update(r)
    return list(out.values())


mixto = downloaded["mixto"]
data = {
    "proyectos": merged(lambda r: (r["pri_ano_proyecto"], r["pri_correlativo"]), downloaded["projects"], mixto["proyectos"]),
    "publicaciones": merged(lambda r: r["pub_correlativo"], downloaded["papers"], mixto["publicaciones"]),
}
saved = f"data-scraping/vrip-linfati-{max(dates)}.json"  # dated like the newest source
with open(saved, "w", encoding="utf-8") as fh:
    json.dump({"exito": True, "resultado": data}, fh, ensure_ascii=False, indent=2)
print(f"saved {saved} (combined: {len(data['proyectos'])} projects, {len(data['publicaciones'])} publications)")

if ALL:  # the whole UBB registry as well (vrip-all-YYYY-MM-DD.json); nothing below reads it
    old, _ = latest("vrip-all", "json")
    if old and not FORCE:
        print(f"data-scraping/{old.name} exists, not downloaded again")
    else:
        with urllib.request.urlopen(ALL_URL, timeout=120) as response:
            raw = response.read()
        payload = json.loads(raw)
        res = payload.get("resultado")
        if payload.get("exito") is not True or not isinstance(res, dict) or any(not isinstance(res.get(k), list) for k in ("proyectos", "publicaciones")):
            raise RuntimeError("VRIP all: unexpected response")
        saved = f"data-scraping/vrip-all-{download_date}.json"
        with open(saved, "wb") as fh:
            fh.write(raw)
        print(f"{saved} ({len(res['proyectos'])} projects, {len(res['publicaciones'])} publications, downloaded)")

print("== Publications")
vp = data["publicaciones"]
mine = load(PUBS, "key")


def pub_score(e, p):
    t, year = titles(e["block"])[0], field(e["block"], "year")
    s = max([jac(words(re.sub(r"\[.*?\]", "", t)), words(p["titulo"]))] + [jac(words(x), words(p["titulo"])) for x in re.findall(r"\[(.*?)\]", t)])
    return s + (0.15 if p["periodo"] == year else 0)


assigned, used = match(mine, vp, "pub_correlativo", pub_score)
for n, e in enumerate(mine):
    key, flag = e["block"].split("\n")[0].split(":")[1].strip(), field(e["block"], "id-ubb-vrip")
    if n in assigned and missing(flag):
        print(f"  no id-ubb-vrip but in VRIP ({vp[assigned[n]]['pub_correlativo']}): {key}")
    if n not in assigned and not missing(flag):
        print(f"  id {flag!r} but NOT in VRIP: {key}")
for i, p in enumerate(vp):
    if i not in used:
        print(f"  in VRIP, not in data: {p['pub_correlativo']} {p['periodo']} {p['tipo_publicacion']} {p['titulo'][:70]}")
if WRITE:
    print(f"  ids written: {write_ids(mine, vp, assigned, 'pub_correlativo')}")

print("== Projects")
vpr = data["proyectos"]
mine = load(PROJECTS, "start")


def proj_score(e, p):
    code = (field(e["block"], "code") or "").replace("UBioBio-", "").replace(" ", "").lower()
    internal = (field(e["block"], "ubb-code") or "").replace(" ", "").lower()
    pc = (p["codigo"] or "").replace(" ", "").lower()
    if pc and (code.endswith(pc) or pc == internal):
        return 1
    return max(jac(words(t), words(p["titulo"])) for t in titles(e["block"]))


assigned, used = match(mine, vpr, "pri_correlativo", proj_score)
for n, e in enumerate(mine):
    label, flag = field(e["block"], "code") or titles(e["block"])[0][:40], field(e["block"], "id-ubb-vrip")
    if n in assigned and missing(flag):
        print(f"  no id-ubb-vrip but in VRIP: {label}")
    if n not in assigned and not missing(flag):
        print(f"  id {flag!r} but NOT in VRIP: {label}")
for i, p in enumerate(vpr):
    if i not in used:
        print(f"  in VRIP, not in data: {p['periodo']} {p['programa'][:30]} {p['titulo'][:70]}")
if WRITE:
    print(f"  ids written: {write_ids(mine, vpr, assigned, 'pri_correlativo')}")
