"""Раскладка графа по сообществам: каждое сообщество — отдельный «остров».

Внутри острова — spring по подграфу; центры островов — по кругу, радиус зависит
от размера. Так связи внутри сообщества видны, а не слипаются в одно пятно.
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "data" / "recsys-2026-communities.json").read_text(encoding="utf-8"))
REFS = json.loads((ROOT / "data" / "recsys-2026-refs.json").read_text(encoding="utf-8"))
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
SEED = 42


def key_of(r):
    if r.get("doi"):
        return "doi:" + r["doi"].strip().lower()
    t = "".join(ch if ch.isalnum() else " " for ch in (r.get("title") or "").lower())
    return "ttl:" + " ".join(t.split())[:120]


papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
slug_to_refs = {p["slug"]: {key_of(r) for r in REFS["papers"].get(p["slug"], [])} - {""} for p in papers}

points = C["points"]
idx = {p["slug"]: i for i, p in enumerate(points)}
comms = {c["id"]: [] for c in C["communities"]}
noise = []
for p in points:
    (comms[p["community"]] if p["community"] in comms else noise).append(idx[p["slug"]])

edges = [(i, j, w) for i, j, w in C["edges"]]
import networkx as nx

xy = np.zeros((len(points), 2))
ids = sorted(comms, key=lambda c: -len(comms[c]))
n_big = len(ids)
for k, cid in enumerate(ids):
    members = comms[cid]
    sub = nx.Graph()
    sub.add_nodes_from(members)
    for i, j, w in edges:
        if i in members and j in members:
            sub.add_edge(i, j, weight=float(w) ** 0.7)
    pos = nx.spring_layout(sub, weight="weight", seed=SEED, k=0.45, iterations=600)
    P = np.array([pos[m] for m in members])
    P -= P.mean(0)
    span = max(np.ptp(P[:, 0]), np.ptp(P[:, 1]), 1e-9)
    P /= span
    P *= 0.30 * math.sqrt(len(members) / max(len(m) for m in comms.values()))
    # центры островов по кругу
    ang = 2 * math.pi * k / max(1, n_big) - math.pi / 2
    center = np.array([0.5 + 0.30 * math.cos(ang), 0.5 + 0.30 * math.sin(ang)])
    P += center
    xy[members] = P

if noise:
    ang = np.linspace(0, 2 * math.pi, num=len(noise), endpoint=False)
    for k, i in enumerate(noise):
        xy[i] = [0.5 + 0.48 * math.cos(ang[k]), 0.5 + 0.48 * math.sin(ang[k])]

xy = np.clip(xy, 0, 1)
for k, p in enumerate(points):
    p["x"] = round(float(xy[k, 0] * 1000), 1)
    p["y"] = round(float((1 - xy[k, 1]) * 1000), 1)
C["meta"]["layout"] = "острова сообществ: spring внутри, центры по кругу; изолированные по внешнему кольцу"
(ROOT / "data" / "recsys-2026-communities.json").write_text(
    json.dumps(C, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("ok", {c["id"]: c["size"] for c in C["communities"]})
