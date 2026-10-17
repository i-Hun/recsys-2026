"""Названия общих источников для сообществ: DOI → название через Crossref.

Дополняет data/recsys-2026-communities.json полем refsTitles у каждого сообщества
(топ-5 общих ссылок с человекочитаемыми названиями) и name — доминирующая тема.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "recsys-2026-communities.json"
CACHE = ROOT / "data" / ".crossref-refcache.json"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
UA = "recsys2026-guide/1.0 (mailto:nagornyy.o@gmail.com)"


def title_for(doi, cache):
    if doi in cache:
        return cache[doi]
    try:
        req = urllib.request.Request("https://api.crossref.org/works/" + urllib.parse.quote(doi),
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            msg = json.load(r)["message"]
        t = " ".join((msg.get("title") or [""])[0].split())
    except Exception:
        t = ""
    cache[doi] = t
    time.sleep(0.12)
    return t


def main():
    data = json.loads(OUT.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    points = data["points"]
    clusters = json.loads((ROOT / "data" / "recsys-2026-map.json").read_text(encoding="utf-8"))["points"]
    theme_of = {p["slug"]: p["theme"] for p in clusters}
    theme_title = {t["id"]: t["short"] for t in DATA["themes"]}

    for c in data["communities"]:
        members = [p["slug"] for p in points if p["community"] == c["id"]]
        themes = {}
        for s in members:
            t = theme_of.get(s, "?")
            themes[t] = themes.get(t, 0) + 1
        top = max(themes, key=themes.get) if themes else "?"
        c["theme"] = top
        c["name"] = theme_title.get(top, top)
        if c["size"] < 5:
            c["refsTitles"] = []
            continue
        titles = []
        for ref in c["topRefs"][:5]:
            if ref.startswith("10."):
                t = title_for(ref, cache)
                titles.append({"doi": ref, "title": t or ref})
            else:
                titles.append({"doi": "", "title": ref[:160]})
        c["refsTitles"] = titles
        print(c["id"], c["size"], c["name"], "|", (titles[0]["title"][:70] if titles else "—"))

    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
