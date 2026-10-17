"""Эмбеддинги текстов разборов на GPU ПК (для сверки с полными текстами).

Вход: C:/Users/hun/tmp/ft/review-corpus.jsonl (slug, text).
Выход: review-emb.npy, review-slugs.json.
Модель та же и те же настройки, что для полных текстов (кроме длины: разбор
короче, max_seq_length=1024 хватает целиком).
"""
import json
from pathlib import Path

import numpy as np

BASE = Path("C:/Users/hun/tmp/ft")
MODEL = "Qwen/Qwen3-Embedding-0.6B"


def main():
    import torch
    from sentence_transformers import SentenceTransformer

    rows = [json.loads(x) for x in (BASE / "review-corpus.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    texts = [r["text"] for r in rows]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL, device=device)
    model.max_seq_length = 1024
    emb = model.encode(texts, batch_size=16, normalize_embeddings=True,
                       show_progress_bar=False, convert_to_numpy=True)
    np.save(BASE / "review-emb.npy", emb)
    (BASE / "review-slugs.json").write_text(
        json.dumps([r["slug"] for r in rows], ensure_ascii=False), encoding="utf-8")
    print("review-emb:", emb.shape)


if __name__ == "__main__":
    main()
