"""Сообщества работ по общим ссылкам (Leiden) + карта для сайта.

Граф: две работы связаны, если ссылаются на одни и те же источники.
Вес ребра — косинус по бинарным векторам ссылок (общие / sqrt(n_i * n_j)),
это устойчивее к работам с длинной библиографией, чем сырое число общих ссылок.
Сообщества — Leiden (RBConfiguration), несколько сидов, выбор по modularity.

Выход:
  data/recsys-2026-communities.json — сообщества, размеры, метрики, координаты 2D
"""
import collections
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
REFS = json.loads((ROOT / "data" / "recsys-2026-refs.json").read_text(encoding="utf-8"))
OUT = ROOT / "data" / "recsys-2026-communities.json"
SEED = 42


def key_of(ref):
    if ref.get("doi"):
        return "doi:" + ref["doi"].strip().lower()
    t = (ref.get("title") or "").strip().lower()
    t = "".join(ch if ch.isalnum() else " " for ch in t)
    t = " ".join(t.split())
    return "ttl:" + t[:120] if t else ""


def main():
    import igraph as ig
    import leidenalg
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    slugs = [p["slug"] for p in papers]
    themes = [p["primaryTheme"] for p in papers]

    sets = []
    for p in papers:
        refs = REFS["papers"].get(p["slug"], [])
        keys = {key_of(r) for r in refs}
        keys.discard("")
        sets.append(keys)

    n = len(papers)
    print("работ со ссылками:", sum(1 for s in sets if s), "медиана ссылок:",
          sorted(len(s) for s in sets)[n // 2])

    # косинус по бинарным векторам
    weights = {}
    for i in range(n):
        if not sets[i]:
            continue
        for j in range(i + 1, n):
            if not sets[j]:
                continue
            inter = len(sets[i] & sets[j])
            if inter < 2:
                continue
            w = inter / math.sqrt(len(sets[i]) * len(sets[j]))
            if w >= 0.08:
                weights[(i, j)] = w
    print("рёбер в проекции:", len(weights))

    g = ig.Graph(n=n, edges=list(weights.keys()), directed=False)
    g.es["weight"] = list(weights.values())
    g.vs["slug"] = slugs

    best = None
    for seed in (42, 7, 2026, 13, 99):
        part = leidenalg.find_partition(
            g, leidenalg.RBConfigurationVertexPartition,
            weights="weight", resolution_parameter=1.0, seed=seed, n_iterations=-1)
        mod = part.modularity
        if best is None or mod > best[0]:
            best = (mod, part, seed)
    mod, part, seed = best
    labels = np.array(part.membership)
    # сообщества меньше 5 работ не показываем отдельно: это пары и одиночки,
    # они уходят в «вне сообществ» и рисуются серым
    raw_sizes = collections.Counter(labels.tolist())
    small = {c for c, sz in raw_sizes.items() if sz < 5}
    for c in small:
        labels[labels == c] = -1
    sizes = collections.Counter(labels.tolist())
    sizes.pop(-1, None)
    print("modularity:", round(mod, 3), "сообществ:", len(sizes), "сид:", seed)
    print("размеры:", sorted(sizes.values(), reverse=True))

    # стабильность: ARI между сидами
    runs = []
    for s in (42, 7, 2026, 13, 99):
        p2 = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition,
                                      weights="weight", resolution_parameter=1.0, seed=s, n_iterations=-1)
        runs.append(np.array(p2.membership))
    aris = [adjusted_rand_score(runs[i], runs[j]) for i in range(len(runs)) for j in range(i + 1, len(runs))]
    print("стабильность ARI:", round(float(np.mean(aris)), 3), "±", round(float(np.std(aris)), 3))

    text_map = json.loads((ROOT / "data" / "recsys-2026-map.json").read_text(encoding="utf-8"))
    text_cluster = {p["slug"]: p["cluster"] for p in text_map["points"]}
    txt = [text_cluster.get(s, -1) for s in slugs]

    print("ARI с темами:", round(adjusted_rand_score(themes, labels), 3),
          "NMI:", round(normalized_mutual_info_score(themes, labels), 3))
    print("ARI с текстовыми кластерами:", round(adjusted_rand_score(txt, labels), 3))

    # 2D для карты: UMAP по разреженной матрице ссылок
    import umap
    from scipy.sparse import csr_matrix

    vocab = sorted({k for s in sets for k in s})
    idx = {k: i for i, k in enumerate(vocab)}
    rows, cols = [], []
    for r, s in enumerate(sets):
        for k in s:
            rows.append(r)
            cols.append(idx[k])
    x = csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, len(vocab)))
    xy = umap.UMAP(n_neighbors=10, min_dist=0.1, metric="cosine", random_state=SEED,
                   n_components=2).fit_transform(x)
    xs = (xy[:, 0] - xy[:, 0].min()) / max(1e-9, np.ptp(xy[:, 0])) * 1000
    ys = (xy[:, 1] - xy[:, 1].min()) / max(1e-9, np.ptp(xy[:, 1])) * 1000

    points = [{"slug": slugs[i], "x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
               "community": int(labels[i]), "refs": len(sets[i])} for i in range(n)]

    # общие источники сообщества — для названий
    comm_words = {}
    for c in sizes:
        members = [i for i in range(n) if labels[i] == c]
        cnt = collections.Counter()
        for i in members:
            for k in sets[i]:
                cnt[k] += 1
        comm_words[int(c)] = [k.split(":", 1)[1] for k, _ in cnt.most_common(6)]

    meta = {
        "method": "Leiden RBConfiguration, weight = |S_i∩S_j|/sqrt(|S_i||S_j|), порог 0.08, ≥2 общих ссылок",
        "papers": n, "withRefs": sum(1 for s in sets if s), "edges": len(weights),
        "modularity": round(float(mod), 3), "communities": len(sizes),
        "stabilityAri": round(float(np.mean(aris)), 3),
        "ariThemes": round(float(adjusted_rand_score(themes, labels)), 3),
        "nmiThemes": round(float(normalized_mutual_info_score(themes, labels)), 3),
        "ariTextClusters": round(float(adjusted_rand_score(txt, labels)), 3),
        "seed": seed,
    }
    out = {"meta": meta, "points": points,
           "communities": [{"id": int(c), "size": int(sz), "topRefs": comm_words[int(c)]}
                           for c, sz in sizes.most_common()]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))
    for c in out["communities"][:10]:
        print(c["id"], c["size"], c["topRefs"][:4])


if __name__ == "__main__":
    main()
