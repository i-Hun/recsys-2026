"""Эмбеддинги полных текстов на GPU ПК Олега (RTX 5080).

Вход: C:/Users/hun/tmp/ft/fulltext-corpus.jsonl (по строке на работу, поле chunks).
Выход: C:/Users/hun/tmp/ft/fulltext-emb.npy (N x 1024, L2-нормированные, усреднённые
по чанкам) и fulltext-slugs.json — порядок строк.

Модель Qwen/Qwen3-Embedding-0.6B, max_seq_length=2048: чанк ~1500 токенов
помещается целиком, поэтому «полный текст» действительно участвует, а не только
первые 512 токенов.
"""
import json
import sys
from pathlib import Path

import numpy as np

BASE = Path("C:/Users/hun/tmp/ft")
MODEL = "Qwen/Qwen3-Embedding-0.6B"
MAXLEN = 2048
BATCH = 8


def main():
    import torch
    from sentence_transformers import SentenceTransformer

    rows = [json.loads(line) for line in (BASE / "fulltext-corpus.jsonl")
            .read_text(encoding="utf-8").splitlines() if line.strip()]
    texts, owner = [], []
    for i, r in enumerate(rows):
        for ch in r["chunks"]:
            texts.append(ch)
            owner.append(i)
    print(f"papers={len(rows)} chunks={len(texts)}", flush=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", device, flush=True)
    model = SentenceTransformer(MODEL, device=device)
    model.max_seq_length = MAXLEN
    emb_chunks = model.encode(texts, batch_size=BATCH, normalize_embeddings=True,
                              show_progress_bar=True, convert_to_numpy=True)
    print("chunk-emb:", emb_chunks.shape, flush=True)

    owner = np.array(owner)
    dim = emb_chunks.shape[1]
    out = np.zeros((len(rows), dim), dtype=np.float32)
    for i in range(len(rows)):
        v = emb_chunks[owner == i].mean(axis=0)
        n = np.linalg.norm(v)
        out[i] = v / n if n > 0 else v

    np.save(BASE / "fulltext-emb.npy", out)
    (BASE / "fulltext-slugs.json").write_text(
        json.dumps([r["slug"] for r in rows], ensure_ascii=False), encoding="utf-8")
    print("paper-emb:", out.shape, "saved", flush=True)


if __name__ == "__main__":
    sys.exit(main())
