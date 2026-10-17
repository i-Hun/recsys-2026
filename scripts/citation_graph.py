"""Сообщества по графу ссылок: вес = число общих источников (как просил Олег).

Узлы — 269 разборов. Ребро — две работы ссылаются на один и тот же источник;
вес ребра = сколько общих источников, без нормировки. Сообщества — Leiden
(RBConfiguration, weights=weight), перебор resolution и выбор по modularity.

Раскладка — графовая (ForceAtlas2 / FR), а не UMAP: карта должна показывать
структуру связей, а не текстовую близость.
"""
import collections
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
REFS = json.loads((ROOT / "data" / "recsys-2026-refs.json").read_text(encoding="utf-8"))
SEED = 42


def key_of(ref):
    if ref.get("doi"):
        return "doi:" + ref["doi"].strip().lower()
    t = "".join(ch if ch.isalnum() else " " for ch in (ref.get("title") or "").lower())
    t = " ".join(t.split())
    return "ttl:" + t[:120] if t else ""


def build():
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    slugs = [p["slug"] for p in papers]
    themes = [p["primaryTheme"] for p in papers]
    sets = []
    for p in papers:
        keys = {key_of(r) for r in REFS["papers"].get(p["slug"], [])}
        keys.discard("")
        sets.append(keys)
    n = len(sets)
    edges = {}
    for i in range(n):
        if not sets[i]:
            continue
        for j in range(i + 1, n):
            if not sets[j]:
                continue
            inter = len(sets[i] & sets[j])
            if inter >= 2:  # одна общая ссылка — ещё не связь, это шум
                edges[(i, j)] = inter
    return papers, slugs, themes, sets, edges


def main():
    import igraph as ig
    import leidenalg
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    papers, slugs, themes, sets, edges = build()
    n = len(slugs)
    print("пар с общими ссылками (>=2):", len(edges))

    g = ig.Graph(n=n, edges=list(edges.keys()), directed=False)
    g.es["weight"] = [float(w) for w in edges.values()]

    best = None
    for res in (1.2, 1.3, 1.5, 1.7):
        part = leidenalg.find_partition(
            g, leidenalg.RBConfigurationVertexPartition,
            weights="weight", resolution_parameter=res, seed=SEED, n_iterations=-1)
        sizes = collections.Counter(part.membership)
        big = {c: s for c, s in sizes.items() if s >= 5}
        cover = sum(big.values()) / n
        print(f"res={res}: comm={len(sizes)} >=5:{len(big)} cover={cover:.2f} "
              f"mod={part.modularity:.3f} sizes={sorted(big.values(), reverse=True)[:10]}")
        if 6 <= len(big) <= 10 and (best is None or part.modularity > best[0]):
            best = (part.modularity, part, res)

    mod, part, res = best
    labels = np.array(part.membership)
    raw = collections.Counter(labels.tolist())
    for c, sz in raw.items():
        if sz < 5:
            labels[labels == c] = -1
    sizes = collections.Counter(labels.tolist())
    sizes.pop(-1, None)
    print(f"\nвыбрано res={res}: сообществ {len(sizes)}, вне сообществ {int((labels == -1).sum())}, "
          f"modularity {mod:.3f}")

    # стабильность по сидам
    runs = []
    for s in (42, 7, 2026, 13, 99):
        p2 = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition,
                                      weights="weight", resolution_parameter=res, seed=s, n_iterations=-1)
        runs.append(np.array(p2.membership))
    aris = [adjusted_rand_score(runs[i], runs[j]) for i in range(len(runs)) for j in range(i + 1, len(runs))]
    print("стабильность ARI:", round(float(np.mean(aris)), 3), "±", round(float(np.std(aris)), 3))

    text_map = json.loads((ROOT / "data" / "recsys-2026-map.json").read_text(encoding="utf-8"))
    txt = [next((p["cluster"] for p in text_map["points"] if p["slug"] == s), -1) for s in slugs]
    print("NMI с темами:", round(float(normalized_mutual_info_score(themes, labels)), 3),
          "ARI с текстовыми кластерами:", round(float(adjusted_rand_score(txt, labels)), 3))

    # Графовая раскладка: ForceAtlas2 по ядру (узлы со связями), изолированные —
    # по внешнему кольцу. FR на всём графе раздувает периметр: изолированные узлы
    # отталкиваются к краю и сжимают связное ядро в точку.
    core = [i for i in range(n) if g.degree(i) > 0]
    iso = [i for i in range(n) if g.degree(i) == 0]
    sub = g.induced_subgraph(core)
    xy = np.zeros((n, 2))
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(range(len(core)))
    for e in sub.es:
        G.add_edge(e.source, e.target, weight=e["weight"])
    pos = nx.spring_layout(G, weight="weight", seed=SEED, k=1.2 / math.sqrt(len(core)), iterations=400)
    P = np.array([pos[i] for i in range(len(core))])
    P = (P - P.min(0)) / np.maximum(np.ptp(P, axis=0), 1e-9) * 0.84 + 0.08
    for k, i in enumerate(core):
        xy[i] = P[k]
    if iso:
        ang = np.linspace(0, 2 * math.pi, num=len(iso), endpoint=False)
        for k, i in enumerate(iso):
            xy[i] = [0.5 + 0.47 * math.cos(ang[k]), 0.5 + 0.47 * math.sin(ang[k])]
    xs = xy[:, 0] * 1000
    ys = (1 - xy[:, 1]) * 1000

    out = {
        "meta": {
            "method": "ребро = >=2 общих источников, вес = число общих; Leiden RBConfiguration",
            "resolution": res, "edges": len(edges), "papers": n,
            "withRefs": sum(1 for s in sets if s),
            "communities": len(sizes), "isolated": int((labels == -1).sum()),
            "modularity": round(float(mod), 3), "stabilityAri": round(float(np.mean(aris)), 3),
            "nmiThemes": round(float(normalized_mutual_info_score(themes, labels)), 3),
            "ariTextClusters": round(float(adjusted_rand_score(txt, labels)), 3),
            "layout": "spring (FR-like) по ядру со связями; изолированные — по внешнему кольцу",
        },
        "points": [{"slug": slugs[i], "x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
                    "community": int(labels[i])} for i in range(n)],
        "communities": [],
    }
    for c in sorted(sizes, key=lambda c: -sizes[c]):
        members = [i for i in range(n) if labels[i] == c]
        cnt = collections.Counter()
        for i in members:
            for k in sets[i]:
                cnt[k] += 1
        theme = collections.Counter(themes[i] for i in members).most_common(1)[0][0]
        out["communities"].append({"id": int(c), "size": int(sizes[c]), "theme": theme,
                                   "topRefs": [k.split(":", 1)[1] for k, _ in cnt.most_common(6)]})
    (ROOT / "data" / "recsys-2026-communities.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("сообщества:", [(c["id"], c["size"]) for c in out["communities"]])


if __name__ == "__main__":
    main()
