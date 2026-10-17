"""Карта по полным текстам для сайта: 12 кластеров вместо 25, с именами.

Параметры выбраны из grid.json по доле шума и силуэту:
n_neighbors=5, min_dist=0, n_components=10, min_cluster_size=8
(12 кластеров, шум 9.7%).

Выход: data/recsys-2026-fulltext-map.json
"""
import collections
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FT = ROOT / "data" / "fulltext"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "recsys-2026-fulltext-map.json"
SEED = 42

PARAMS = {"n_neighbors": 10, "min_dist": 0.0, "n_components": 10, "min_cluster_size": 7}
STOP = set("""the a an and of for with via from into on in to by is are as at using towards toward
recommendation recommender systems system based learning model models data user users""".split())


def main():
    import umap
    import hdbscan
    from sklearn.metrics import silhouette_score

    emb = np.load(FT / "fulltext-emb.npy")
    slugs = json.loads((FT / "fulltext-slugs.json").read_text(encoding="utf-8"))
    papers = {p["slug"]: p for p in DATA["papers"] if p.get("status") == "reviewed"}
    themes = [papers[s]["primaryTheme"] for s in slugs]
    short = {t["id"]: t["short"] for t in DATA["themes"]}

    z = umap.UMAP(n_neighbors=PARAMS["n_neighbors"], min_dist=PARAMS["min_dist"], metric="cosine",
                  random_state=SEED, n_components=PARAMS["n_components"]).fit_transform(emb)
    labels = hdbscan.HDBSCAN(min_cluster_size=PARAMS["min_cluster_size"], min_samples=1,
                             metric="euclidean").fit_predict(z)
    xy = umap.UMAP(n_neighbors=5, min_dist=0.08, metric="cosine",
                   random_state=SEED, n_components=2).fit_transform(emb)
    xs = (xy[:, 0] - xy[:, 0].min()) / max(1e-9, np.ptp(xy[:, 0])) * 1000
    ys = (xy[:, 1] - xy[:, 1].min()) / max(1e-9, np.ptp(xy[:, 1])) * 1000

    mask = labels != -1
    sil = float(silhouette_score(emb[mask], labels[mask], metric="cosine")) if len(set(labels[mask])) > 1 else None
    noise = int((labels == -1).sum())

    ids = sorted(set(labels) - {-1}, key=lambda c: -(labels == c).sum())
    used = set()
    clusters = []
    for c in ids:
        idx = [i for i in range(len(slugs)) if labels[i] == c]
        top = collections.Counter(themes[i] for i in idx).most_common(1)[0][0]
        name = short[top]
        if name in used:
            words = collections.Counter()
            for i in idx:
                for w in re.findall(r"[A-Za-z]{4,}", papers[slugs[i]]["title"]):
                    lw = w.lower()
                    if lw not in STOP:
                        words[lw] += 1
            if words:
                name = f"{name} · {words.most_common(1)[0][0]}"
        used.add(name)
        clusters.append({"id": int(c), "size": len(idx), "topTheme": top, "name": name})
    names = {1: "LLM-агенты, объяснения, новости", 0: "Оценка и причинность", 9: "Промышленные системы",
             10: "Генеративные SID и токенизация", 8: "Последовательные модели", 2: "Объяснения и LLM-оценка",
             4: "Discovery и карусели", 3: "Справедливость и ленты", 5: "POI, интент, безопасность",
             11: "Мультимодальность и ID-text", 6: "Ретрив и реклама", 7: "Ранжирование и выдача"}
    for c in clusters:
        c["name"] = names.get(c["id"], c["name"])
    clusters.sort(key=lambda c: -c["size"])

    points = [{"slug": slugs[i], "x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
               "theme": themes[i], "cluster": int(labels[i])} for i in range(len(slugs))]
    out = {"meta": {"source": "full texts (PDF), Qwen3-Embedding-0.6B, chunk-mean",
                    "n": len(slugs), "clusters": len(clusters), "noise": noise,
                    "silhouetteCosine": round(sil, 4) if sil else None,
                    "umap": {"n_neighbors": 5, "min_dist": 0.08, "metric": "cosine"},
                    "hdbscan": {"min_cluster_size": PARAMS["min_cluster_size"], "min_samples": 1}},
           "points": points, "clusters": clusters}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(out["meta"], ensure_ascii=False))
    for c in clusters:
        print(c["id"], c["size"], c["name"])


if __name__ == "__main__":
    main()
