"""Списки литературы для разборов RecSys 2026 через Crossref.

Для каждой работы берём её DOI, запрашиваем api.crossref.org/works/<doi> и складываем
reference[] (DOI, название, авторы, год, журнал). Crossref — единственный открытый
источник, где ACM депонирует полные списки ссылок; OpenAlex для этих работ отдаёт 0,
Semantic Scholar закрыт 403.

Выход: data/recsys-2026-refs.json
Запуск: python scripts/fetch_references.py
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "recsys-2026-refs.json"
UA = "recsys2026-guide/1.0 (mailto:nagornyy.o@gmail.com)"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(1.5 * (i + 1))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def clean(ref):
    if isinstance(ref, str):
        return {"doi": "", "title": " ".join(ref.split())[:400], "authors": [], "year": "", "venue": ""}
    doi = (ref.get("DOI") or "").lower().strip()
    title = (ref.get("article-title") or ref.get("volume-title") or ref.get("unstructured") or "").strip()
    authors = []
    for a in ref.get("author") or []:
        if isinstance(a, str):
            if a.strip():
                authors.append(a.strip())
            continue
        name = " ".join(x for x in [a.get("given"), a.get("family")] if x).strip()
        if name:
            authors.append(name)
    year = ref.get("year") or ""
    journal = ref.get("journal-title") or ""
    return {
        "doi": doi,
        "title": " ".join(title.split())[:400],
        "authors": authors[:6],
        "year": str(year),
        "venue": " ".join(str(journal).split())[:160],
    }


def main():
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    cache_path = ROOT / "data" / ".crossref-cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    out = {}
    missing = []
    for i, p in enumerate(papers, 1):
        doi = (p.get("doi") or [""])[0].lower()
        if not doi:
            missing.append(p["slug"])
            continue
        if doi in cache:
            msg = cache[doi]
        else:
            data = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))
            msg = data["message"] if data else None
            cache[doi] = msg
            if i % 20 == 0:
                cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        refs = [clean(r) for r in ((msg or {}).get("reference") or [])]
        refs = [r for r in refs if r["doi"] or r["title"]]
        out[p["slug"]] = refs
        print(f"{i:3d}/{len(papers)} {p['slug'][:40]:42s} refs={len(refs)}", flush=True)
        time.sleep(0.1)

    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    payload = {"papers": out, "meta": {
        "source": "Crossref REST API, поле reference",
        "papers": len(papers),
        "withRefs": sum(1 for v in out.values() if v),
        "refs": sum(len(v) for v in out.values()),
        "noDoi": len(missing),
    }}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(payload["meta"], ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
