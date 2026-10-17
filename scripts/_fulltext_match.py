"""Шаг 1: сопоставить PDF из ~/papers с корпусом разборов RecSys 2026.

Три правила, по убыванию надёжности:
  1) DOI 10.1145/3773078.* на первой странице PDF;
  2) arXiv id в имени файла → заголовок из arXiv API → сверка с заголовком работы;
  3) нечёткое сравнение заголовка работы с первой страницей PDF (SequenceMatcher
     по нормализованным буквам), порог 0.80.

Выход: .fulltext-match.json (slug → {file, via, score}) и отчёт в stdout.
Запуск: env -u PYTHONPATH ~/.venvs/agent-researcher/bin/python scripts/_fulltext_match.py
"""
import json
import re
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
PAPERS_DIR = Path("/home/hun/papers")
CACHE = ROOT / ".firstpage-cache.json"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def first_page(f: Path) -> str:
    try:
        return subprocess.run(["pdftotext", "-f", "1", "-l", "2", str(f), "-"],
                              capture_output=True, text=True, timeout=40).stdout[:8000]
    except Exception:
        return ""


def arxiv_titles(ids: list[str]) -> dict[str, str]:
    """Заголовки arXiv по списку id (один запрос на пачку)."""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ",".join(ids[i:i + 50])
        url = f"http://export.arxiv.org/api/query?id_list={chunk}&max_results=50"
        try:
            xml = subprocess.run(["curl", "-sL", url], capture_output=True, text=True,
                                 timeout=90).stdout
        except Exception:
            continue
        for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
            m_id = re.search(r"<id>http://arxiv.org/abs/([^<]+)</id>", entry)
            m_ti = re.search(r"<title>(.*?)</title>", entry, re.S)
            if m_id and m_ti:
                key = re.sub(r"v\d+$", "", m_id.group(1).strip())
                out[key] = re.sub(r"\s+", " ", m_ti.group(1)).strip()
    return out


def main():
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    by_doi = {}
    for p in papers:
        for d in p.get("doi") or []:
            d = d.lower()
            if d.startswith("10.1145/"):
                by_doi[d.split("10.1145/")[-1]] = p["slug"]

    pdfs = sorted(PAPERS_DIR.rglob("*.pdf"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    pages = {}
    for f in pdfs:
        key = str(f)
        if key not in cache:
            cache[key] = first_page(f)
        pages[key] = cache[key]
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # --- правило 1: DOI
    match: dict[str, dict] = {}
    for f in pdfs:
        m = re.search(r"10\.1145/(3773078\.\d{7})", pages[str(f)])
        if m and m.group(1) in by_doi:
            slug = by_doi[m.group(1)]
            if slug not in match:
                match[slug] = {"file": str(f.relative_to(PAPERS_DIR)), "via": "doi", "score": 1.0}

    # --- правило 2: arXiv id из имени файла
    ids = {}
    for f in pdfs:
        m = re.search(r"(?<!\d)(\d{4}\.\d{4,5})(v\d+)?(?!\d)", f.name)
        if m:
            ids.setdefault(m.group(1), []).append(f)
    titles = arxiv_titles(sorted(ids)) if ids else {}
    by_title = {norm(p["title"]): p["slug"] for p in papers}
    slug_by_title_loose = {}
    for p in papers:
        slug_by_title_loose.setdefault(norm(p["title"])[:120], p["slug"])
    for aid, files in ids.items():
        t = titles.get(aid)
        if not t:
            continue
        cand = by_title.get(norm(t)) or slug_by_title_loose.get(norm(t)[:120])
        if cand and cand not in match:
            match[cand] = {"file": str(files[0].relative_to(PAPERS_DIR)),
                           "via": f"arxiv:{aid}", "score": 1.0}

    # --- правило 3: нечёткий заголовок по первой странице
    for p in papers:
        if p["slug"] in match:
            continue
        nt = norm(p["title"])
        best, best_f = 0.0, None
        for f in pdfs:
            body = norm(pages[str(f)])[:1500]
            if not body:
                continue
            r = SequenceMatcher(None, nt, body[:len(nt) + 60]).ratio()
            if r > best:
                best, best_f = r, f
        if best >= 0.80:
            match[p["slug"]] = {"file": str(best_f.relative_to(PAPERS_DIR)),
                                "via": "title", "score": round(best, 3)}

    (ROOT / ".fulltext-match.json").write_text(
        json.dumps(match, ensure_ascii=False, indent=0), encoding="utf-8")

    used = {v["file"] for v in match.values()}
    via = {}
    for v in match.values():
        k = v["via"].split(":")[0]
        via[k] = via.get(k, 0) + 1
    print(json.dumps({
        "papers": len(papers), "pdfs": len(pdfs),
        "matched": len(match), "byVia": via,
        "pdfsUnused": len([f for f in pdfs if str(f.relative_to(PAPERS_DIR)) not in used]),
        "papersWithoutText": len(papers) - len(match),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
