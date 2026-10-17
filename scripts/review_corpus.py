"""Тексты разборов для тех же работ, что уже есть в полном тексте.

Нужно для прямой сверки: косинус «полный текст ↔ разбор» и совпадение
k-ближайших соседей в двух пространствах. Состав документа — как в
embeddings_map.py (иначе сравнение будет нечестным): title + summary +
insight + limitation + начало «Метода».

Выход: data/fulltext/review-corpus.jsonl (slug, text).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "public" / "stories" / "recsys-2026" / "articles"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
SLUGS = json.loads((ROOT / "data" / "fulltext" / "fulltext-slugs.json").read_text(encoding="utf-8"))


def section_text(article, prefix):
    for s in article.get("sections", []):
        if s.get("title", "").startswith(prefix):
            return re.sub(r"\s+", " ", s.get("markdown", "")).strip()
    return ""


def main():
    by_slug = {p["slug"]: p for p in DATA["papers"]}
    out = []
    for slug in SLUGS:
        p = by_slug[slug]
        method = ""
        f = ART / f"{slug}.json"
        if f.exists():
            method = section_text(json.loads(f.read_text(encoding="utf-8")), "Метод")[:700]
        parts = [f"Title: {p['title']}"]
        if p.get("summary"):
            parts.append(f"Задача и подход: {p['summary']}")
        if p.get("insight"):
            parts.append(f"Результат: {p['insight']}")
        if p.get("limitation"):
            parts.append(f"Ограничение: {p['limitation']}")
        if method:
            parts.append(f"Метод: {method}")
        out.append({"slug": slug, "text": "\n".join(parts)})

    dst = ROOT / "data" / "fulltext" / "review-corpus.jsonl"
    with dst.open("w", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    lens = [len(r["text"]) for r in out]
    print(json.dumps({"docs": len(out), "medianChars": sorted(lens)[len(lens) // 2],
                      "missingArticle": [s for s in SLUGS if not (ART / f"{s}.json").exists()]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
