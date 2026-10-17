"""Шаг 3: текст из PDF → очищенный корпус для эмбеддингов.

- первый проход: сопоставление PDF с работами (см. _fulltext_match.py, вызывается как модуль);
- pymupdf (fitz) вместо pdftotext: лучше сохраняет порядок колонок на ACM-вёрстке;
- срезаем секцию литературы («References» / «Bibliography» в конце документа);
- убираем колонтитулы-номера страниц, склеиваем переносы;
- режем на чанки ~6000 знаков (≈1500 токенов) с перекрытием 600 — эмбеддинг
  считается по чанкам и усредняется по работе, иначе 512-токенный контекст
  модели видит только введение.

Выход: data/fulltext-corpus.jsonl (slug, file, chars, tokensApprox, nChunks, chunks[]).
Запуск: env -u PYTHONPATH ~/.venvs/agent-researcher/bin/python scripts/fulltext_corpus.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS = Path("/home/hun/papers")
MATCH = ROOT / ".fulltext-match.json"
OUT = ROOT / "data" / "fulltext-corpus.jsonl"
NOVEL = Path("/home/hun/papers/recsys26")

REF_HEADS = re.compile(
    r"^\s*(?:\d+\.?\s*)?(references|bibliography|literature cited|references and notes)\s*$",
    re.I | re.M)
BOILER = [
    r"Permission to make digital or hard copies.*?(?=\n[A-Z])",
    r"This work is licensed under a Creative Commons.*?(?=\n[A-Z])",
    r"ACM ISBN [^\n]*\n",
    r"^\s*\d{1,3}\s*$",
]


def clean(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"-\n(?=[a-z])", "", text)          # перенос внутри слова
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    for pat in BOILER:
        text = re.sub(pat, " ", text, flags=re.M | re.S)
    return text.strip()


def strip_references(text: str) -> str:
    """Срезать список литературы: последний заголовок References в хвосте."""
    tail_start = int(len(text) * 0.45)
    best = None
    for m in REF_HEADS.finditer(text):
        if m.start() > tail_start:
            best = m
    if best:
        return text[: best.start()]
    return text


def chunk(text: str, size: int = 6000, overlap: int = 600) -> list[str]:
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        if i + size >= len(text):
            break
        i += size - overlap
    return out


def main():
    import fitz

    match = json.loads(MATCH.read_text(encoding="utf-8"))
    recs, missing, errors = [], [], []
    for slug, info in sorted(match.items()):
        f = PAPERS / info["file"]
        if not f.exists():
            missing.append(slug)
            continue
        try:
            doc = fitz.open(f)
            raw = "\n".join(page.get_text("text") for page in doc)
            doc.close()
        except Exception as e:            # битый/заглушка
            errors.append({"slug": slug, "err": str(e)[:120]})
            continue
        body = strip_references(clean(raw))
        if len(body) < 3000:
            errors.append({"slug": slug, "err": f"слишком короткий текст ({len(body)} зн.)"})
            continue
        ch = chunk(body)
        recs.append({
            "slug": slug, "file": info["file"], "via": info["via"],
            "chars": len(body), "tokensApprox": round(len(body) / 3.6),
            "nChunks": len(ch), "chunks": ch,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    chars = [r["chars"] for r in recs]
    print(json.dumps({
        "corpus": len(recs),
        "chunks": sum(r["nChunks"] for r in recs),
        "medianChars": sorted(chars)[len(chars) // 2] if chars else 0,
        "minChars": min(chars) if chars else 0,
        "maxChars": max(chars) if chars else 0,
        "missingFile": missing,
        "errors": errors[:10],
        "nErrors": len(errors),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
