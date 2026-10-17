"""Шаг 5: кластеризация по ПОЛНЫМ текстам и сверка с картой по разборам.

Читает data/fulltext/{fulltext-emb,fulltext-slugs,review-emb,review-slugs}.*,
гоняет сетку UMAP × HDBSCAN, меряет качество в ИСХОДНОМ пространстве
(косинусный silhouette, доля шума), стабильность по сидам — и считает согласие
с редакторскими темами и с кластерами карты по разборам.

Выход:
  data/fulltext/fulltext-map.json   — точки, кластеры, метрики
  data/fulltext/agreement.json      — числа согласия
  data/fulltext/moved.json          — работы, сменившие группу
  ~/tmp_fulltext/fulltext-map.png, fulltext-agreement.png

Запуск: env -u PYTHONPATH ~/.venvs/agent-researcher/bin/python scripts/fulltext_map.py
"""
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FT = ROOT / "data" / "fulltext"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
REVIEW_MAP = json.loads((ROOT / "data" / "recsys-2026-map.json").read_text(encoding="utf-8"))
SEED = 42
FIGDIR = Path(os.environ.get("FIGDIR", "/home/hun/tmp_fulltext"))


def cosine_silhouette(emb, labels):
    from sklearn.metrics import silhouette_score
    mask = labels != -1
    if len(set(labels[mask])) < 2 or mask.sum() < 3:
        return None
    return float(silhouette_score(emb[mask], labels[mask], metric="cosine"))


def knn(sim, k):
    s = sim.copy()
    np.fill_diagonal(s, -2)
    return np.argsort(-s, axis=1)[:, :k]


def chance_level(themes, labels, n_perm: int = 200, seed: int = 0):
    """ARI/NMI при случайной подмене тем: ниже этого значения согласие не значимо."""
    from sklearn.metrics import adjusted_rand_score as ari
    from sklearn.metrics import normalized_mutual_info_score as nmi
    rng = np.random.default_rng(seed)
    a, m = [], []
    for _ in range(n_perm):
        perm = rng.permutation(themes)
        a.append(ari(perm, labels))
        m.append(nmi(perm, labels))
    return {"ari95": round(float(np.percentile(a, 95)), 3),
            "nmi95": round(float(np.percentile(m, 95)), 3),
            "nPerm": n_perm}


def silhouette_or_none(emb, labels):
    from sklearn.metrics import silhouette_score
    try:
        return round(float(silhouette_score(emb, labels, metric="cosine")), 4)
    except Exception:
        return None


def main():
    import hdbscan
    import umap
    from sklearn.metrics import adjusted_rand_score as ari
    from sklearn.metrics import normalized_mutual_info_score as nmi
    from sklearn.metrics.pairwise import cosine_similarity

    ft_emb = np.load(FT / "fulltext-emb.npy")
    slugs = json.loads((FT / "fulltext-slugs.json").read_text(encoding="utf-8"))
    rv_emb = np.load(FT / "review-emb.npy")
    rv_slugs = json.loads((FT / "review-slugs.json").read_text(encoding="utf-8"))
    assert slugs == rv_slugs, "порядок работ в двух корпусах разошёлся"
    n = len(slugs)
    by_slug = {p["slug"]: p for p in DATA["papers"]}
    themes = [by_slug[s]["primaryTheme"] for s in slugs]
    theme_title = {t["id"]: t["title"] for t in DATA["themes"]}

    # кластеры карты по разборам на том же подмножестве работ
    rev_cluster = {p["slug"]: p["cluster"] for p in REVIEW_MAP["points"]}
    rev_labels = np.array([rev_cluster.get(s, -9) for s in slugs])
    rev_themes = {p["slug"]: p["theme"] for p in REVIEW_MAP["points"]}

    # ---------- сетка UMAP × HDBSCAN ----------
    mcs_grid = sorted({max(3, int(round(n * f))) for f in (0.02, 0.03, 0.05)})
    rows = []
    for nn in (5, 10, 15, 30):
        for md in (0.0, 0.1, 0.25):
            for nc in (5, 10):
                z = umap.UMAP(n_neighbors=min(nn, n - 2), min_dist=md, metric="cosine",
                              random_state=SEED, n_components=nc).fit_transform(ft_emb)
                for mcs in mcs_grid:
                    labels = hdbscan.HDBSCAN(min_cluster_size=mcs, min_samples=1,
                                             metric="euclidean").fit_predict(z)
                    sil = cosine_silhouette(ft_emb, labels)
                    k = len(set(labels) - {-1})
                    rows.append({"nn": nn, "minDist": md, "nComp": nc, "mcs": mcs,
                                 "clusters": k, "noise": int((labels == -1).sum()),
                                 "noiseShare": round(float((labels == -1).mean()), 3),
                                 "silhouette": None if sil is None else round(sil, 4),
                                 "ariTheme": round(float(ari(themes, labels)), 3),
                                 "nmiTheme": round(float(nmi(themes, labels)), 3)})
    # выбор: непустой силуэт, шум ≤ 40%, кластеров ≥ 6; берём максимум силуэта,
    # при равенстве — меньше шума
    ok = [r for r in rows if r["silhouette"] is not None and r["noiseShare"] <= 0.15
          and r["clusters"] >= 8]
    ok.sort(key=lambda r: (-r["silhouette"], r["noiseShare"]))
    if not ok:                      # запасной путь: ослабить требования, но не падать
        ok = sorted([r for r in rows if r["silhouette"] is not None],
                    key=lambda r: (-r["silhouette"], r["noiseShare"])) or rows[:1]
    best = ok[0]

    # Стабильность по сидам UMAP для шортлиста: при силуэте ≤0.1 выбор конфига
    # по силуэту — это шум (скилл embedding-cluster-map, п.6), поэтому берём
    # три лучших по силуэту конфига и решаем по стабильности.
    shortlist = ok[:3]

    def stability_of(cfg):
        labs = []
        for seed in (42, 1, 7, 2024, 99):
            z = umap.UMAP(n_neighbors=cfg["nn"], min_dist=cfg["minDist"], metric="cosine",
                          random_state=seed, n_components=cfg["nComp"]).fit_transform(ft_emb)
            labs.append(hdbscan.HDBSCAN(min_cluster_size=cfg["mcs"], min_samples=1,
                                        metric="euclidean").fit_predict(z))
        pair = []
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                pair.append(float(ari(labs[i], labs[j])))
        return round(float(np.mean(pair)), 3) if pair else None

    for cfg in shortlist:
        cfg["stability"] = stability_of(cfg)
    floor = 0.8 * max(c["silhouette"] for c in shortlist)
    eligible = [c for c in shortlist if c["silhouette"] >= floor and c["stability"] is not None]
    best = max(eligible or shortlist, key=lambda c: c["stability"])
    stability = best["stability"]

    # ---------- финальная модель: 10D-кластеры, 2D — только для картинки ----------
    z10 = umap.UMAP(n_neighbors=best["nn"], min_dist=best["minDist"], metric="cosine",
                    random_state=SEED, n_components=best["nComp"]).fit_transform(ft_emb)
    labels = hdbscan.HDBSCAN(min_cluster_size=best["mcs"], min_samples=1,
                             metric="euclidean").fit_predict(z10)
    xy = umap.UMAP(n_neighbors=best["nn"], min_dist=0.08, metric="cosine",
                   random_state=SEED, n_components=2).fit_transform(ft_emb)

    sim_ft = cosine_similarity(ft_emb)
    sim_rv = cosine_similarity(rv_emb)
    # согласие «кто рядом»: доля общих соседей в top-10
    nn_ft, nn_rv = knn(sim_ft, 10), knn(sim_rv, 10)
    overlap10 = float(np.mean([len(set(nn_ft[i]) & set(nn_rv[i])) / 10 for i in range(n)]))
    pair_cos = np.clip((sim_ft * sim_rv), -1, 1)
    tril = pair_cos[np.tril_indices(n, -1)]

    # kNN-чистота по темам (тот же смысл, что meanPurity в карте по разборам)
    def purity(sim):
        nbh = knn(sim, 10)
        return float(np.mean([np.mean([themes[j] == themes[i] for j in nbh[i]]) for i in range(n)]))

    # ---------- кластеры: состав, имена ----------
    def scale(v):
        lo, hi = float(v.min()), float(v.max())
        return (v - lo) / (hi - lo) * 1000 if hi > lo else np.zeros_like(v)

    xs, ys = scale(xy[:, 0]), scale(xy[:, 1])
    points = []
    clusters = []
    for c in sorted(int(x) for x in set(labels) - {-1}):
        idx = [i for i in range(n) if labels[i] == c]
        counts = {}
        for i in idx:
            counts[themes[i]] = counts.get(themes[i], 0) + 1
        top = max(counts, key=counts.get)
        clusters.append({"id": c, "size": len(idx), "topTheme": top,
                         "label": theme_title[top],
                         "mix": {k: int(v) for k, v in counts.items()},
                         "purity": round(counts[top] / len(idx), 2)})
    clusters.sort(key=lambda c: -c["size"])
    top_of = {c["id"]: c["topTheme"] for c in clusters}

    moved = []
    for i, s in enumerate(slugs):
        p = by_slug[s]
        rc = int(rev_labels[i])
        rev_top = None
        for c in REVIEW_MAP["clusters"]:
            if c["id"] == rc:
                rev_top = c["topTheme"]
        ft_top = top_of.get(int(labels[i]))
        if labels[i] == -1:
            state = "шум по полному тексту"
        elif rev_top is None:
            state = "не было кластера в разборе"
        elif ft_top != rev_top:
            state = f"{rev_top} → {ft_top}"
        else:
            state = "та же группа"
        moved.append({"slug": s, "title": p["title"], "theme": p["primaryTheme"],
                      "reviewCluster": rc, "reviewClusterTheme": rev_top,
                      "fulltextCluster": int(labels[i]), "fulltextClusterTheme": ft_top,
                      "change": state,
                      "cosFulltextReview": round(float(np.dot(ft_emb[i], rv_emb[i])), 3)})
    moved.sort(key=lambda r: r["cosFulltextReview"])

    agree = {
        "n": n,
        "chunks": None,
        "fulltextVsThemes": {"ari": round(float(ari(themes, labels)), 3),
                             "nmi": round(float(nmi(themes, labels)), 3),
                             "knnPurity": round(purity(sim_ft), 3)},
        "reviewVsThemes": {"ari": round(float(ari(themes, rev_labels)), 3),
                           "nmi": round(float(nmi(themes, rev_labels)), 3),
                           "knnPurity": round(purity(sim_rv), 3),
                           "ariMap": REVIEW_MAP["meta"]["ariHdbscan"],
                           "nmiMap": REVIEW_MAP["meta"]["nmiHdbscan"]},
        "chanceLevel": chance_level(themes, labels),
        "themeSeparability": {
            "fulltext": silhouette_or_none(ft_emb, themes),
            "review": silhouette_or_none(rv_emb, themes),
        },
        "fulltextVsReviewClusters": {"ari": round(float(ari(rev_labels, labels)), 3),
                                     "nmi": round(float(nmi(rev_labels, labels)), 3)},
        "knnOverlap10": round(overlap10, 3),
        "pairCosine": {"mean": round(float(tril.mean()), 3),
                       "p10": round(float(np.percentile(tril, 10)), 3),
                       "p50": round(float(np.percentile(tril, 50)), 3),
                       "p90": round(float(np.percentile(tril, 90)), 3)},
        "perPaperCosine": {"mean": round(float(np.mean([np.dot(ft_emb[i], rv_emb[i]) for i in range(n)])), 3),
                           "min": round(float(np.min([np.dot(ft_emb[i], rv_emb[i]) for i in range(n)])), 3),
                           "p10": round(float(np.percentile([np.dot(ft_emb[i], rv_emb[i]) for i in range(n)], 10)), 3)},
        "movedShare": round(float(np.mean([r["change"] not in ("та же группа",) for r in moved])), 3),
        "noiseShare": round(float((labels == -1).mean()), 3),
    }

    out = {
        "meta": {"source": "full texts (PDF), Qwen3-Embedding-0.6B, chunk-mean",
                 "n": n, "seed": SEED,
                 "umap": {"n_neighbors": best["nn"], "min_dist": best["minDist"],
                          "n_components": best["nComp"], "metric": "cosine"},
                 "hdbscan": {"min_cluster_size": best["mcs"], "min_samples": 1},
                 "clusters": len(clusters), "noise": int((labels == -1).sum()),
                 "silhouetteCosine": best["silhouette"],
                 "stabilityAriSeeds": stability,
                 "grid": len(rows)},
        "points": [{"slug": slugs[i], "x": round(float(xs[i]), 1), "y": round(float(ys[i]), 1),
                    "theme": themes[i], "cluster": int(labels[i])} for i in range(n)],
        "clusters": clusters,
    }
    (FT / "fulltext-map.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (FT / "agreement.json").write_text(json.dumps(agree, ensure_ascii=False, indent=1), encoding="utf-8")
    (FT / "moved.json").write_text(json.dumps(moved, ensure_ascii=False, indent=1), encoding="utf-8")
    (FT / "grid.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({"chosen": best, "stability": stability, "agree": agree},
                     ensure_ascii=False, indent=1))

    # ---------- картинки ----------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGDIR.mkdir(parents=True, exist_ok=True)
    palette = plt.get_cmap("tab20")
    ids = sorted(set(int(x) for x in labels) - {-1})

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    for ax, mode in zip(axes, ("cluster", "theme")):
        if mode == "cluster":
            for k, c in enumerate(ids):
                m = labels == c
                ax.scatter(xs[m], ys[m], s=26, color=palette(k % 20),
                           label=f"#{c} {top_of[c]} (n={int(m.sum())})", alpha=.85)
            m = labels == -1
            if m.any():
                ax.scatter(xs[m], ys[m], s=20, color="#bdbdbd", label=f"шум (n={int(m.sum())})")
            ax.set_title(f"Полные тексты: кластеры HDBSCAN (n={n}), "
                         f"silhouette={best['silhouette']}, шум={int((labels == -1).sum())}")
            ax.legend(fontsize=7, loc="best", framealpha=.85)
        else:
            tid = sorted(set(themes))
            for k, t in enumerate(tid):
                m = np.array([x == t for x in themes])
                ax.scatter(xs[m], ys[m], s=26, color=palette(k % 20), label=f"{t} (n={int(m.sum())})", alpha=.85)
            ax.set_title("Полные тексты: редакторские темы на той же проекции")
            ax.legend(fontsize=8, loc="best", framealpha=.85)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#dddddd")
    fig.tight_layout()
    fig.savefig(FIGDIR / "fulltext-map.png", dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.4))
    # heatmap тема × кластер
    ax = axes[0]
    tid = sorted(set(themes))
    mat = np.zeros((len(tid), len(ids)))
    for j, c in enumerate(ids):
        for i, t in enumerate(tid):
            mat[i, j] = sum(1 for k in range(n) if labels[k] == c and themes[k] == t)
    im = ax.imshow(mat, aspect="auto", cmap="YlGnBu")
    ax.set_yticks(range(len(tid))); ax.set_yticklabels(tid, fontsize=8)
    ax.set_xticks(range(len(ids))); ax.set_xticklabels([f"#{c}" for c in ids], fontsize=8)
    ax.set_title("Тема (строки) × кластер по полному тексту (столбцы)")
    fig.colorbar(im, ax=ax, fraction=.03)
    # распределение косинуса «полный текст ↔ разбор»
    ax = axes[1]
    per = [float(np.dot(ft_emb[i], rv_emb[i])) for i in range(n)]
    ax.hist(per, bins=20, color="#4c78a8", alpha=.85)
    ax.axvline(float(np.mean(per)), color="#e45756", lw=1.4,
               label=f"среднее {np.mean(per):.3f}")
    ax.set_title("Косинус между эмбеддингом полного текста и разбора (по работам)")
    ax.set_xlabel("cos"); ax.set_ylabel("работ"); ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fulltext-agreement.png", dpi=140)
    plt.close(fig)

    # сверка «полный текст против разбора» на одной и той же проекции-раскладке
    xy_rv = umap.UMAP(n_neighbors=best["nn"], min_dist=0.08, metric="cosine",
                      random_state=SEED, n_components=2).fit_transform(rv_emb)
    xs2, ys2 = scale(xy_rv[:, 0]), scale(xy_rv[:, 1])
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    tid = sorted(set(themes))
    for ax, (px, py, title) in zip(axes, [
            (xs, ys, f"Полные тексты (PDF): {n} работ, kNN-чистота {purity(sim_ft):.2f}"),
            (xs2, ys2, f"Разборы тех же работ: kNN-чистота {purity(sim_rv):.2f}")]):
        for k, t in enumerate(tid):
            m = np.array([x == t for x in themes])
            ax.scatter(px[m], py[m], s=26, color=palette(k % 20), label=f"{t} (n={int(m.sum())})", alpha=.85)
        ax.set_title(title, fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#dddddd")
    axes[0].legend(fontsize=8, loc="best", framealpha=.85)
    fig.suptitle(f"Одна и та же раскладка (UMAP {best['nn']}/{best['minDist']}, cos): "
                 f"cos по работам {agree['perPaperCosine']['mean']}, общих соседей@10 {agree['knnOverlap10']}",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fulltext-compare.png", dpi=140)
    plt.close(fig)
    print("картинки:", FIGDIR / "fulltext-map.png", FIGDIR / "fulltext-agreement.png",
          FIGDIR / "fulltext-compare.png")


if __name__ == "__main__":
    main()
