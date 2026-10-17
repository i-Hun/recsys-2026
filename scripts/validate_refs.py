"""Проверка DOI в списках литературы и подстановка названий через Crossref.

Crossref в поле reference часто отдаёт только DOI без названия. Здесь для каждого
уникального DOI делаем запрос works/{doi}: 200 → берём title/authors/year/venue,
404 → помечаем ссылку как недействительную (на сайте не рисуем ссылку).
Результат переписывает data/recsys-2026-refs.json и public/.../refs/*.json.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = json.loads((ROOT / "data" / "recsys-2026-refs.json").read_text(encoding="utf-8"))
CACHE_PATH = ROOT / "data" / ".doi-validate.json"
UA = "recsys2026-guide/1.0 (mailto:nagornyy.o@gmail.com)"


def fetch(doi):
    try:
        req = urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi),
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            m = json.load(r)["message"]
        authors = []
        for a in m.get("author") or []:
            name = " ".join(x for x in [a.get("given"), a.get("family")] if x).strip()
            if name:
                authors.append(name)
        return {"ok": True, "title": " ".join((m.get("title") or [""])[0].split()),
                "authors": authors[:6], "year": str((m.get("issued") or {}).get("date-parts", [[""]])[0][0] or ""),
                "venue": " ".join(((m.get("container-title") or [""])[0]).split())}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False}
        return {"ok": None}
    except Exception:
        return {"ok": None}


def main():
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    dois = sorted({r["doi"] for items in REFS["papers"].values() for r in items if r.get("doi")})
    todo = [d for d in dois if d not in cache]
    print("уникальных DOI:", len(dois), "проверить:", len(todo), flush=True)

    def work(d):
        res = fetch(d)
        if res.get("ok") is None:
            time.sleep(0.5)
            res = fetch(d)
        return d, res

    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (d, res) in enumerate(ex.map(work, todo), 1):
            cache[d] = res
            if i % 200 == 0:
                print(i, flush=True)
                CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    bad = sum(1 for d in dois if cache.get(d, {}).get("ok") is False)
    unknown = sum(1 for d in dois if cache.get(d, {}).get("ok") is None)
    print("недействительных DOI:", bad, "не проверились:", unknown, flush=True)

    out_dir = ROOT / "public" / "stories" / "recsys-2026" / "refs"
    filled = 0
    for slug, items in REFS["papers"].items():
        new_items = []
        for r in items:
            doi = (r.get("doi") or "").lower()
            meta = cache.get(doi) or {}
            if doi and meta.get("ok") is False:
                continue  # битый DOI — ссылку не показываем
            item = dict(r)
            if doi and meta.get("ok"):
                item["title"] = item.get("title") or meta.get("title") or ""
                item["authors"] = item.get("authors") or meta.get("authors") or []
                item["year"] = item.get("year") or meta.get("year") or ""
                item["venue"] = item.get("venue") or meta.get("venue") or ""
                filled += 1
            if not item.get("title") and not item.get("doi"):
                continue
            new_items.append(item)
        REFS["papers"][slug] = new_items
        (out_dir / f"{slug}.json").write_text(
            json.dumps({"slug": slug, "items": new_items}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")
    REFS["meta"]["refs"] = sum(len(v) for v in REFS["papers"].values())
    REFS["meta"]["badDoisRemoved"] = bad
    (ROOT / "data" / "recsys-2026-refs.json").write_text(
        json.dumps(REFS, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("заполнено названий:", filled, "итого ссылок:", REFS["meta"]["refs"])


if __name__ == "__main__":
    main()
