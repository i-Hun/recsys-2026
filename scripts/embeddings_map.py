"""Кладёт на карту 269 разборов RecSys 2026 по эмбеддингам.

Текст работы: title + summary + insight + limitation (+ начало «Метода»).
Тема и теги в текст НЕ попадают — иначе кластеризация просто перескажет разметку.

Выход: data/recsys-2026-map.json — 2D-координаты UMAP, кластеры HDBSCAN,
согласие с редакторской темой и метрики качества кластеризации.

Запуск: source ~/.venvs/agent-researcher/bin/activate && python scripts/embeddings_map.py
"""
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "public" / "stories" / "recsys-2026" / "articles"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))

MODEL = "Qwen/Qwen3-Embedding-0.6B"
SEED = 42
NN2D = int(os.environ.get("NN2D", 15))
NN10 = int(os.environ.get("NN10", 10))
MCS = int(os.environ.get("MCS", 6))
MS = int(os.environ.get("MS", 2))


def section_text(article, title_prefix):
    for s in article.get("sections", []):
        if s.get("title", "").startswith(title_prefix):
            return re.sub(r"\s+", " ", s.get("markdown", "")).strip()
    return ""


def build_documents():
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    docs, kept = [], []
    for p in papers:
        f = ART / f"{p['slug']}.json"
        method = ""
        if f.exists():
            art = json.loads(f.read_text(encoding="utf-8"))
            method = section_text(art, "Метод")[:700]
        parts = [f"Title: {p['title']}"]
        if p.get("summary"):
            parts.append(f"Задача и подход: {p['summary']}")
        if p.get("insight"):
            parts.append(f"Результат: {p['insight']}")
        if p.get("limitation"):
            parts.append(f"Ограничение: {p['limitation']}")
        if method:
            parts.append(f"Метод: {method}")
        docs.append("\n".join(parts))
        kept.append(p)
    return kept, docs


def main():
    from sentence_transformers import SentenceTransformer
    import umap
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, silhouette_score
    from sklearn.metrics.pairwise import cosine_similarity

    papers, docs = build_documents()
    slugs = [p["slug"] for p in papers]
    themes = [p["primaryTheme"] for p in papers]
    n = len(papers)
    print(f"документов: {n}", flush=True)

    import hashlib
    import tempfile

    import torch

    key = hashlib.sha1(("\n\n".join(docs)).encode("utf-8")).hexdigest()[:16]
    cache = Path(tempfile.gettempdir()) / f"recsys26-emb-{key}.npy"
    if cache.exists():
        emb = np.load(cache)
        print("эмбеддинги из кэша:", emb.shape, flush=True)
    else:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print("device:", device, flush=True)
        model = SentenceTransformer(MODEL, device=device)
        model.max_seq_length = 512
        emb = model.encode(docs, batch_size=16, normalize_embeddings=True,
                           show_progress_bar=True, convert_to_numpy=True)
        np.save(cache, emb)
    print("эмбеддинги:", emb.shape, flush=True)

    # 10D — для кластеризации (стандартная связка UMAP+HDBSCAN)
    z10 = umap.UMAP(n_neighbors=NN10, min_dist=0.0, metric="cosine",
                    random_state=SEED, n_components=10).fit_transform(emb)
    # 2D — только для графика; проецируем САМО z10, иначе карта и кластеры живут
    # в разных пространствах и кластер выглядит размазанным по всему облаку
    xy = umap.UMAP(n_neighbors=NN2D, min_dist=0.08, metric="cosine",
                   random_state=SEED, n_components=2).fit_transform(emb)

    import hdbscan
    # Кластеризуем в той же 2D-проекции, что видит читатель: иначе границы кластеров
    # на карте не совпадают с тем, что нашёл алгоритм в 10-мерном пространстве.
    labels = hdbscan.HDBSCAN(min_cluster_size=MCS, min_samples=MS,
                             metric="euclidean").fit_predict(z10)
    print("HDBSCAN кластеров:", len(set(labels) - {-1}), "шум:", int((labels == -1).sum()), flush=True)

    km = KMeans(n_clusters=len(DATA["themes"]), n_init=50, random_state=SEED).fit_predict(z10)

    sim = cosine_similarity(emb)
    np.fill_diagonal(sim, -1)
    purity = []
    for i in range(n):
        nb = np.argsort(-sim[i])[:10]
        purity.append(float(np.mean([themes[j] == themes[i] for j in nb])))

    # 2D-координаты в 0..1000 для SVG
    def scale(v):
        lo, hi = float(v.min()), float(v.max())
        return (v - lo) / (hi - lo) * 1000 if hi > lo else np.zeros_like(v)

    xs, ys = scale(xy[:, 0]), scale(xy[:, 1])
    points = [{
        "slug": slugs[i], "x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
        "theme": themes[i], "cluster": int(labels[i]),
        "purity": round(purity[i], 2),
    } for i in range(n)]

    theme_title = {t["id"]: t["title"] for t in DATA["themes"]}
    clusters = []
    for c in sorted(int(x) for x in set(labels) - {-1}):
        idx = [i for i in range(n) if labels[i] == c]
        counts = {}
        for i in idx:
            counts[themes[i]] = counts.get(themes[i], 0) + 1
        top = max(counts, key=counts.get)
        clusters.append({"id": int(c), "size": len(idx), "topTheme": top,
                         "label": theme_title[top], "mix": {k: int(v) for k, v in counts.items()}})
    clusters.sort(key=lambda c: -c["size"])
    # человекочитаемые названия кластеров: порядок по размеру, ключ "mcs-ms"
    names_file = ROOT / "scripts" / "recsys26-cluster-names.json"
    names = json.loads(names_file.read_text(encoding="utf-8")).get(f"{MCS}-{MS}", []) if names_file.exists() else []
    for i, c in enumerate(clusters):
        c["name"] = names[i] if i < len(names) else c["label"]

    meta = {
        "model": MODEL, "n": n, "seed": SEED,
        "umap2d": {"from": "embedding", "n_neighbors": NN2D, "min_dist": 0.08, "metric": "cosine"},
        "hdbscan": {"min_cluster_size": MCS, "min_samples": MS, "space": "umap10d"},
        "clusters": len(clusters), "noise": int((labels == -1).sum()),
        "ariHdbscan": round(float(adjusted_rand_score(themes, labels)), 3),
        "nmiHdbscan": round(float(normalized_mutual_info_score(themes, labels)), 3),
        "ariKmeans9": round(float(adjusted_rand_score(themes, km)), 3),
        "nmiKmeans9": round(float(normalized_mutual_info_score(themes, km)), 3),
        "silhouette2d": round(float(silhouette_score(xy, themes, metric="euclidean")), 3),
        "meanPurity": round(float(np.mean(purity)), 3),
    }
    out = {"meta": meta, "points": points, "clusters": clusters}
    (ROOT / "data" / "recsys-2026-map.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    print("записано data/recsys-2026-map.json")


if __name__ == "__main__":
    main()
