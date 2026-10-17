"""Инвентаризация PDF на диске: какие работы корпуса уже имеют полный текст.

Ищет PDF во всех каталогах, где они реально копятся (не только ~/papers), достаёт
DOI с первых двух страниц, arXiv-id из имени и текста, сверяет с корпусом разборов.
Результат — data/fulltext/inventory.json + отчёт в stdout.

Запуск: python scripts/inventory_pdfs.py
"""
import json
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "fulltext" / "inventory.json"

ROOTS = ["/home/hun/papers", "/home/hun/tmp_acm", "/home/hun/tmp_fulltext", "/home/hun/tmp_cf",
         "/home/hun/tmp_ssrn", "/home/hun/tmp_ingest", "/home/hun/tmp_pp", "/home/hun/decks"]
DOI_RE = re.compile(r"10\.1145/(3773078\.\d{7})")
ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")


def first_pages_text(path, pages=2):
    try:
        with pymupdf.open(path) as doc:
            return "\n".join(doc[i].get_text() for i in range(min(pages, doc.page_count)))
    except Exception:
        return ""


def main():
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    by_doi = {}
    by_arxiv = {}
    for p in papers:
        doi = (p.get("doi") or [""])[0].lower()
        if "10.1145/" in doi:
            by_doi[doi.split("10.1145/")[-1]] = p["slug"]
        src = str(p.get("source", "")) + " " + " ".join(p.get("doi") or [])
        m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", src) or re.search(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", src, re.I)
        if m:
            by_arxiv[m.group(1)] = p["slug"]

    found = {}
    scanned = 0
    for base in ROOTS:
        b = Path(base)
        if not b.exists():
            continue
        for f in b.rglob("*.pdf"):
            scanned += 1
            text = first_pages_text(f)
            slug = None
            m = DOI_RE.search(text)
            if m and m.group(1) in by_doi:
                slug = by_doi[m.group(1)]
            if not slug:
                for a in ARXIV_RE.findall(f.name):
                    if a in by_arxiv:
                        slug = by_arxiv[a]
                        break
            if not slug:
                for a in ARXIV_RE.findall(text[:4000]):
                    if a in by_arxiv:
                        slug = by_arxiv[a]
                        break
            if slug and slug not in found:
                found[slug] = str(f)

    report = {
        "scanned": scanned,
        "papers": len(papers),
        "withFulltext": len(found),
        "missing": sorted({p["slug"] for p in papers} - set(found)),
        "files": found,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("scanned", "papers", "withFulltext")}, ensure_ascii=False))
    print("нет полного текста:", len(report["missing"]))
    dirs = {}
    for path in found.values():
        d = str(Path(path).parent)
        dirs[d] = dirs.get(d, 0) + 1
    for d, n in sorted(dirs.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {d}")


if __name__ == "__main__":
    main()
