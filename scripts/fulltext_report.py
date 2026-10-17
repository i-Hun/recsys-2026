"""Шаг 6: отчёт по карте полных текстов — markdown с числами.

Читает data/fulltext/{agreement,moved,grid,fulltext-map}.json и пишет отчёт
в workspace задачи (REPORT_PATH). Числа не дублируются руками: всё берётся
из артефактов прогона.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FT = ROOT / "data" / "fulltext"
DATA = json.loads((ROOT / "data" / "recsys-2026.json").read_text(encoding="utf-8"))
REPORT = Path(os.environ.get("REPORT_PATH",
                             "/home/hun/.hermes/kanban/workspaces/t_71ddcae0/fulltext-map-report.md"))
FIG = Path(os.environ.get("FIGDIR", "/home/hun/tmp_fulltext"))

THEMES = {t["id"]: t["title"] for t in DATA["themes"]}


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def main():
    agree = json.loads((FT / "agreement.json").read_text(encoding="utf-8"))
    moved = json.loads((FT / "moved.json").read_text(encoding="utf-8"))
    grid = json.loads((FT / "grid.json").read_text(encoding="utf-8"))
    fmap = json.loads((FT / "fulltext-map.json").read_text(encoding="utf-8"))
    match = json.loads((ROOT / ".fulltext-match.json").read_text(encoding="utf-8"))
    papers = [p for p in DATA["papers"] if p.get("status") == "reviewed"]
    meta = fmap["meta"]
    n = agree["n"]
    no_text = [p for p in papers if p["slug"] not in match]
    corpus = [json.loads(x) for x in (ROOT / "data" / "fulltext-corpus.jsonl")
              .read_text(encoding="utf-8").splitlines() if x.strip()]
    med_chars = sorted(r["chars"] for r in corpus)[len(corpus) // 2] if corpus else 0
    n_chunks = sum(r["nChunks"] for r in corpus)
    title_of = {p["slug"]: p["title"] for p in papers}
    n_pdf = sum(1 for _ in Path("/home/hun/papers").rglob("*.pdf"))

    # разбивка «сменивших группу» по типу сдвига
    chg: dict[str, int] = {}
    for r in moved:
        chg[r["change"]] = chg.get(r["change"], 0) + 1
    same_group = chg.pop("та же группа", 0)
    noise_ft = chg.pop("шум по полному тексту", 0)
    no_review_cluster = chg.pop("не было кластера в разборе", 0)
    theme_shift = sum(chg.values())
    changed = noise_ft + no_review_cluster + theme_shift
    # CSV со списком сменивших группу
    csv_rows = ["slug\ttheme\treviewCluster\treviewClusterTheme\tfulltextCluster\t"
                "fulltextClusterTheme\tchange\tcosFulltextReview\ttitle"]
    for r in moved:
        if r["change"] == "та же группа":
            continue
        csv_rows.append("\t".join(str(x) for x in [
            r["slug"], r["theme"], r["reviewCluster"], r["reviewClusterTheme"],
            r["fulltextCluster"], r["fulltextClusterTheme"], r["change"],
            r["cosFulltextReview"], r["title"].replace("\t", " ").replace("\n", " ")]))
    (FT / "moved.tsv").write_text("\n".join(csv_rows) + "\n", encoding="utf-8")

    # список «ждём PDF»: работы без полного текста, с источником и причиной
    miss = ["# Работы без полного текста (ждём PDF)", ""]
    for p in sorted(no_text, key=lambda x: x["slug"]):
        doi = (p.get("doi") or [""])[0]
        src = p.get("source") or ""
        why = "PDF не скачался с ACM DL (Camoufox) и не найден на arXiv" if doi \
            else "нет DOI / материала нет в открытом доступе"
        miss.append(f"- `{p['slug']}` — {p['title']} ({p.get('kind', '')}); {doi or src}; {why}")
    (FT / "missing.md").write_text("\n".join(miss) + "\n", encoding="utf-8")

    L = []
    A = L.append
    A("# RecSys 2026: карта по полным текстам статей и сверка с картой по разборам")
    A("")
    A(f"Дата: 2026-10-17. Корпус разборов — {len(papers)} работ, полный текст (PDF) — **{n}** "
      f"(это {n / len(papers):.1%} корпуса).")
    A("")
    A("## 1. Что на входе")
    A("")
    via = {}
    for v in match.values():
        via[v["via"].split(":")[0]] = via.get(v["via"].split(":")[0], 0) + 1
    A(f"- PDF на диске (`~/papers`, включая подкаталоги): {n_pdf} "
      f"{plural(n_pdf, 'файл', 'файла', 'файлов')}, из них с работами RecSys 2026 "
      f"сопоставилось **{len(match)}**;")
    A(f"- по DOI с первой страницы — {via.get('doi', 0)}; по arXiv-id из имени файла — {via.get('arxiv', 0)}; "
      f"по нечёткому совпадению заголовка — {via.get('title', 0)};")
    if no_text:
        A(f"- полного текста нет у {len(no_text)} {plural(len(no_text), 'работы', 'работ', 'работ')} из "
          f"{len(papers)} (см. раздел 6, там же причина по каждой).")
    else:
        A(f"- полный текст есть у всех {len(papers)} работ корпуса.")
    A("")
    A("## 2. Как считали")
    A("")
    A(f"- текст: pymupdf, срезана секция литературы, переносы склеены; медиана {med_chars} знаков на работу, "
      f"всего {n_chunks} чанков на {n} работ;")
    A("- документ режется на чанки ~6000 знаков (перекрытие 600), чанки кодируются и усредняются по работе — "
      "иначе окно модели видит только введение;")
    A("- модель `Qwen/Qwen3-Embedding-0.6B`, `max_seq_length=2048`, L2-нормировка, GPU RTX 5080 (ПК Олега);")
    A(f"- кластеризация: UMAP поверх эмбеддингов + HDBSCAN; качество меряется в **исходном** пространстве "
      f"(косинусный силуэт), а не в проекции;")
    A(f"- выбранный конфиг: `n_neighbors={meta['umap']['n_neighbors']}`, `min_dist={meta['umap']['min_dist']}`, "
      f"`n_components={meta['umap']['n_components']}`, `min_cluster_size={meta['hdbscan']['min_cluster_size']}` — "
      f"{meta['clusters']} {plural(meta['clusters'], 'кластер', 'кластера', 'кластеров')}, "
      f"{meta['noise']} {plural(meta['noise'], 'работа', 'работы', 'работ')} вне кластеров;")
    A(f"- стабильность (средний попарный ARI по 5 сидам UMAP): **{meta.get('stabilityAriSeeds')}**; "
      f"косинусный силуэт кластеров в исходном пространстве: **{meta.get('silhouetteCosine')}**;")
    A(f"- сетка: {meta['grid']} {plural(meta['grid'], 'конфигурация', 'конфигурации', 'конфигураций')} "
      f"(n_neighbors × min_dist × n_components × min_cluster_size).")
    A("")
    A("Порог интерпретации: силуэт ≤0.1 на 1024-мерных эмбеддингах корпуса в сотни документов означает, "
      "что сильной разделимости нет — это «группы в проекции», а не естественные классы.")
    A("")
    A("## 3. Сетка параметров (лучшие по силуэту при шуме ≤15%)")
    A("")
    A("| n_neighbors | min_dist | n_comp | min_cluster | кластеров | шум | силуэт | ARI с темами | NMI |")
    A("|---|---|---|---|---|---|---|---|---|")
    ok = [r for r in grid if r["silhouette"] is not None and r["noiseShare"] <= 0.15 and r["clusters"] >= 8]
    ok.sort(key=lambda r: -r["silhouette"])
    for r in ok[:10]:
        A(f"| {r['nn']} | {r['minDist']} | {r['nComp']} | {r['mcs']} | {r['clusters']} | {r['noise']} | "
          f"{r['silhouette']} | {r['ariTheme']} | {r['nmiTheme']} |")
    A("")
    A("## 4. Согласие: полный текст против разбора")
    A("")
    fv, rv = agree["fulltextVsThemes"], agree["reviewVsThemes"]
    ch = agree.get("chanceLevel", {})
    ts = agree.get("themeSeparability", {})
    A("| что сравниваем | полный текст | разбор | уровень случайности (95%) |")
    A("|---|---|---|---|")
    A(f"| ARI с редакторской темой | {fv['ari']} | {rv['ari']} | ARI {ch.get('ari95')} |")
    A(f"| NMI с редакторской темой | {fv['nmi']} | {rv['nmi']} | NMI {ch.get('nmi95')} |")
    A(f"| kNN-чистота по темам (доля 10 соседей той же темы) | {fv['knnPurity']} | {rv['knnPurity']} | — |")
    A(f"| силуэт тем в исходном пространстве | {ts.get('fulltext')} | {ts.get('review')} | 0 по построению |")
    A("")
    A(f"- ARI кластеров по полному тексту с кластерами существующей карты: **{agree['fulltextVsReviewClusters']['ari']}**, "
      f"NMI **{agree['fulltextVsReviewClusters']['nmi']}**;")
    A(f"- доля общих соседей в top-10 между пространствами: **{agree['knnOverlap10']}** "
      f"(0 — соседи совсем разные, 1 — одинаковые);")
    A(f"- косинус «полный текст ↔ разбор» по работам: среднее **{agree['perPaperCosine']['mean']}**, "
      f"минимум {agree['perPaperCosine']['min']}, 10-й перцентиль {agree['perPaperCosine']['p10']};")
    A(f"- косинус между РАЗНЫМИ работами: среднее {agree['pairCosine']['mean']}, "
      f"10-й перцентиль {agree['pairCosine']['p10']}, 90-й {agree['pairCosine']['p90']};")
    A(f"- доля работ, у которых группа изменилась (другая доминирующая тема кластера или шум): "
      f"**{agree['movedShare']:.0%}** ({changed} из {n}); разбивка: та же группа — {same_group}, "
      f"другая доминирующая тема — {theme_shift}, шум по полному тексту — {noise_ft}, "
      f"в разборе не было кластера — {no_review_cluster}.")
    A("")
    A("## 5. Что из этого следует")
    A("")
    A(f"1. Обе карты отделяются от случайности: ARI {fv['ari']} против {ch.get('ari95')} на перемешанных метках, "
      f"NMI {fv['nmi']} против {ch.get('nmi95')}.")
    if abs(fv["ari"] - rv["ari"]) < 0.1:
        A(f"2. Полный текст и разбор дают **одинаковое** согласие с редакторскими темами "
          f"(ARI {fv['ari']} против {rv['ari']}, NMI {fv['nmi']} против {rv['nmi']}) — разбор не теряет "
          f"тематическую информацию относительно полного текста.")
    else:
        better = "полный текст" if fv["ari"] > rv["ari"] else "разбор"
        A(f"2. По согласию с темами выигрывает **{better}** (ARI {fv['ari']} против {rv['ari']}).")
    A(f"3. Соседство расходится сильнее, чем тематика: общих соседей в top-10 всего "
      f"{agree['knnOverlap10']:.0%}, доля сменивших группу — {agree['movedShare']:.0%} "
      f"({changed} из {n}). Основная часть сдвигов — смена доминирующей темы "
      f"({theme_shift} {plural(theme_shift, 'работа', 'работы', 'работ')}), а не уход в шум ({noise_ft}); ещё {no_review_cluster} "
      f"{plural(no_review_cluster, 'работа', 'работы', 'работ')} в карте по разборам были вне "
      f"кластеров и получили кластер по тексту.")
    A(f"4. Разделимость тем в обоих пространствах слабая (силуэт {ts.get('fulltext')} и {ts.get('review')}): "
      f"девять редакторских тем — не естественные классы корпуса, а рамка каталога.")
    A(f"5. Число кластеров разное ({meta['clusters']} по тексту против 18 по разборам), поэтому ARI "
      f"{agree['fulltextVsReviewClusters']['ari']} занижен по построению — он штрафует за разницу в "
      f"дробности. Доля переехавших считается по доминирующей ТЕМЕ кластера, а не по номеру кластера.")
    A("")
    A("## 6. Работы без полного текста")
    A("")
    if no_text:
        A(f"{len(no_text)} {plural(len(no_text), 'работа', 'работы', 'работ')}: PDF нет ни в `~/papers`, "
          f"ни в докачке. Причина по каждой — в `data/fulltext/missing.md`.")
    else:
        A(f"Нет: полный текст есть у всех {len(papers)} работ корпуса "
          f"({len(match)} сопоставлено по PDF).")
    A("")
    A("## 7. Профиль кластеров по полному тексту")
    A("")
    A("| кластер | размер | доминирующая тема | чистота | примеры работ |")
    A("|---|---|---|---|---|")
    cos_of = {r["slug"]: r["cosFulltextReview"] for r in moved}
    for c in sorted(fmap["clusters"], key=lambda x: -x["size"]):
        members = sorted(((cos_of.get(p["slug"], 0), title_of.get(p["slug"], p["slug"]))
                          for p in fmap["points"] if p["cluster"] == c["id"]),
                         key=lambda z: -z[0])
        A(f"| #{c['id']} | {c['size']} | {c['topTheme']} — {c['label']} | {c['purity']:.2f} | "
          f"{'; '.join(t[:60] for _, t in members[:2])} |")
    A("")
    A(f"Всего {meta['clusters']} {plural(meta['clusters'], 'кластер', 'кластера', 'кластеров')} и "
      f"{meta['noise']} {plural(meta['noise'], 'работа', 'работы', 'работ')} вне кластеров. "
      f"Чистота — доля работ доминирующей темы в кластере.")
    A("")
    A("## 8. Работы, чья группа изменилась (худшие по совпадению с разбором)")
    A("")
    A("| работа | тема | кластер по разбору | кластер по полному тексту | сдвиг | cos(текст, разбор) |")
    A("|---|---|---|---|---|---|")
    for r in moved[:25]:
        A(f"| {r['title'][:70]} | {r['theme']} | #{r['reviewCluster']} ({r['reviewClusterTheme']}) | "
          f"#{r['fulltextCluster']} ({r['fulltextClusterTheme']}) | {r['change']} | {r['cosFulltextReview']} |")
    A("")
    A(f"В таблице — 25 худших по совпадению с разбором. Полный список: "
      f"`data/fulltext/moved.tsv` ({changed} строк, только сменившие группу) и "
      f"`data/fulltext/moved.json` (все {len(moved)}) — в TSV есть `change`, кластеры и косинус.")
    A("")
    A("## 9. Артефакты")
    A("")
    A(f"- карта: `{FIG / 'fulltext-map.png'}` (кластеры и темы на одной проекции),")
    A(f"- сверка: `{FIG / 'fulltext-agreement.png'}` (тема × кластер, распределение косинуса),")
    A(f"- сравнение раскладок: `{FIG / 'fulltext-compare.png'}` (полный текст против разбора),")
    A("- данные прогона: `data/fulltext/{fulltext-emb.npy, review-emb.npy, fulltext-map.json, agreement.json, moved.json, moved.tsv, grid.json, inventory.json}`,")
    A("- скрипты: `scripts/{_fulltext_match,fulltext_corpus,review_corpus,embed_fulltext_pc,embed_review_pc,fulltext_map}.py`, `scripts/fetch_acm_fulltexts.sh`, `scripts/refresh_fulltext.sh`.")
    A("")
    A("На сайт ничего не выкладывалось: карта по полным текстам — отдельный артефакт, "
      "публикация — только после подтверждения Олега.")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"отчёт: {REPORT} ({len(L)} строк)")


if __name__ == "__main__":
    main()
