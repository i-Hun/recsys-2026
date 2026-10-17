// Проекции данных путеводителя для одного маршрута.
//
// Зачем: страницы слоя импортировали data/recsys-2026.json (496 КБ), -tags.json (77 КБ)
// и -zotero.json (39 КБ) статически, поэтому весь датасет уезжал в клиентские чанки
// (~700 КБ JS, из них ~482 КБ — cам корпус) и разбирался на main thread при каждой
// загрузке любой страницы путеводителя. Здесь те же данные остаются на сервере, а
// маршруту отдаётся только то, что он рендерит и на чём гидрируется.
//
// Эндпоинт отвечает плоским набором полей; страница кладёт его в payload (useAsyncData),
// поэтому SSR-разметка и гидрация видят один и тот же объект — расхождений нет.
import data from "../../data/recsys-2026.json";
import tagsData from "../../data/recsys-2026-tags.json";
import mapData from "../../data/recsys-2026-map.json";
import zoteroData from "../../data/recsys-2026-zotero.json";

type Paper = (typeof data.papers)[number];

const BASE = "/stories/recsys-2026";

// Поля, которые нужны на каждой странице раздела: по ним строятся карта тем,
// разрезы истории, облако, счётчики и переходы. Плюс аффилиации — только их id.
const CORE_KEYS = ["slug", "title", "status", "primaryTheme", "tags", "kind"] as const;

const orgIds = (p: Paper) => p.affiliations.map((a) => ({ organization: a.organization }));

function slim(papers: Paper[] = data.papers, extra: readonly string[] = []) {
  return papers.map((p) => {
    const row: Record<string, unknown> = {};
    for (const k of [...CORE_KEYS, ...extra]) row[k] = (p as Record<string, unknown>)[k];
    row.affiliations = orgIds(p);
    return row;
  });
}

const themesLite = () => data.themes.map((t) => ({ id: t.id, title: t.title, dek: t.dek, short: t.short }));
const themesShort = () => data.themes.map((t) => ({ id: t.id, title: t.title, short: t.short }));
const orgsLite = () => data.organizations.map((o) => ({ id: o.id, name: o.name, type: o.type }));
const tagsLite = () => tagsData.tags.map((t) => ({ id: t.id, label: t.label, count: t.count }));
const zotItems = () => zoteroData.items.map((it) => ({ slug: it.slug, url: it.url }));

const stats = () => ({
  ...data.stats,
  // Те же числа, что страницы считали по загруженному датасету, — но без самого датасета.
  themeInsights: data.themes.reduce((n, t) => n + t.insights.length, 0),
  zoteroLinked: zoteroData.items.length,
});

export function guideBundle(mode: string, id?: string) {
  const shared = { version: data.version, stats: stats() };

  if (mode === "catalog" || mode === "home" || mode === "organizations") {
    // Каталог рендерит карточки (сводка, DOI, теги, организации), остальное — счётчики.
    const extra = mode === "catalog" ? ["summary", "doi"] : [];
    return {
      ...shared,
      mode,
      pageTitle: mode === "catalog" ? "Каталог материалов" : mode === "organizations" ? "Организации авторов" : "Путеводитель по RecSys 2026",
      papers: slim(data.papers, extra),
      themes: mode === "catalog" ? themesShort() : themesLite(),
      organizations: mode === "organizations" ? data.organizations : orgsLite(),
      tags: mode === "catalog" ? { tags: tagsLite(), byPaper: tagsData.byPaper } : { tags: tagsLite(), byPaper: {} },
      zotero: { items: mode === "catalog" ? zotItems() : [] },
      // Карта близости (UMAP/HDBSCAN, 32 КБ) — только главной: другим маршрутам она не нужна.
      map: mode === "home" ? mapData : undefined,
    };
  }

  if (mode === "topics") {
    const topic = data.themes.find((t) => t.id === id);
    if (!topic) return null;
    return {
      ...shared,
      mode,
      pageTitle: topic.title,
      papers: slim(),
      themes: data.themes,
      organizations: orgsLite(),
      tags: { tags: tagsLite(), byPaper: {} },
      zotero: { items: [] },
    };
  }

  if (mode === "papers") {
    const paper = data.papers.find((p) => p.slug === id);
    if (!paper) return null;
    // Одна карточка целиком (включая цитаты аффилиаций и «что важно») + поле, нужное
    // для «рядом по тематике», «в тематических выводах» и переходов по теме.
    return {
      ...shared,
      mode,
      pageTitle: paper.title,
      papers: [paper, ...slim(data.papers.filter((p) => p.slug !== paper.slug))],
      themes: data.themes.map((t) => ({ id: t.id, title: t.title, short: t.short, insights: t.insights.map((i) => ({ slugs: i.slugs })) })),
      organizations: orgsLite(),
      tags: { tags: tagsLite(), byPaper: { [paper.slug]: (tagsData.byPaper as Record<string, string[]>)[paper.slug] || [] } },
      zotero: { items: zotItems().filter((it) => it.slug === paper.slug) },
    };
  }

  if (mode === "workshops") {
    // Страница воркшопов брала из основного корпуса только slug'и (для ссылки на разбор)
    // и число разборов в шапке. Сам разрез воркшопов импортируется статически.
    return {
      ...shared,
      mode,
      pageTitle: "Воркшопы, туториалы и кейноуты RecSys 2026",
      papers: data.papers.map((p) => ({ slug: p.slug })),
      themes: themesShort(),
      organizations: [],
      tags: { tags: [], byPaper: {} },
      zotero: { items: [] },
    };
  }

  return null;
}

export const GUIDE_BASE = BASE;