<script setup>
/* Представление путеводителя. Данные приходят готовой проекцией с /api/guide:
   страница (../[...path].vue) запрашивает её для своего маршрута и держит в payload,
   поэтому в клиентский бандл датасет не попадает. */
import wsMeta from "../../data/recsys-2026-workshops-meta.json"; // counter only; the cut itself is imported by workshops.vue
import { renderReview as render } from "../../utils/recsys-markdown.js";
import "../../assets/styles/design-tokens.css";
import "../../assets/styles/recsys-2026.css";
const props = defineProps({ bundle: { type: Object, required: true } });
const route = useRoute();
const router = useRouter();
const base = "/stories/recsys-2026";
const parts = computed(() => {
  const v = route.params.path;
  return Array.isArray(v) ? v : (v || "").split("/").filter(Boolean);
});
const mode = computed(() => parts.value[0] || "home");
const id = computed(() => parts.value[1]);
const viewKey = computed(() => mode.value + "/" + (id.value || ""));
const { papers, themes, stats, organizations, tags: tagIndex, zotero: zot, map: mapBundle, communities: commBundle, fulltext: ftBundle } = props.bundle;
// Карта близости приходит только в проекции главной; на других маршрутах — пустая заглушка,
// чтобы setup не падал (секция #map рендерится лишь на главной).
const mapData = mapBundle || { points: [], clusters: [], meta: {} };
const communitiesData = commBundle || { points: [], communities: [], meta: {} };
const fulltextData = ftBundle || { points: [], clusters: [], meta: {} };
const data = { version: props.bundle.version };
const byOrg = Object.fromEntries(organizations.map((o) => [o.id, o]));
const orgTypes = { company: "Компания", university: "Университет", research: "Исследовательская организация", other: "Другая организация" };
const orgTypesPlural = { company: "Компании", university: "Университеты", research: "Исследовательские центры", other: "Другие" };
const unknownReasonLabels = {
  source_unavailable: "Источник для проверки аффилиаций недоступен",
  author_block_missing: "Блок авторов и аффилиаций не найден в доступном источнике",
  extraction_unverified: "Извлечение аффилиаций ещё не проверено",
  no_institution_declared: "В блоке авторов указан независимый исследователь, без организации",
};
const orgCounts = Object.fromEntries(organizations.map((o) => [o.id, 0]));
for (const p of papers) for (const a of p.affiliations) orgCounts[a.organization]++;
const orgCount = (oid) => orgCounts[oid] || 0;
const sortedOrgs = [...organizations].sort((a, b) => orgCount(b.id) - orgCount(a.id) || a.name.localeCompare(b.name));
const orgLinks = papers.reduce((n, p) => n + p.affiliations.length, 0);
const reviewed = papers.filter((p) => p.status === "reviewed");
const bySlug = Object.assign(Object.create(null), Object.fromEntries(papers.map((p) => [p.slug, p])));
const byTheme = Object.assign(Object.create(null), Object.fromEntries(themes.map((t) => [t.id, t])));
const indexOf = Object.fromEntries(papers.map((p, i) => [p.slug, i + 1]));
// Zotero: only verified item keys resolved against the public Zotero library.
const zotBySlug = Object.fromEntries(zot.items.map((z) => [z.slug, z]));
const zotLinked = stats.zoteroLinked;
/* ---------- review tags: one link semantics everywhere — /catalog?tag=<id> ---------- */
const byTag = Object.assign(Object.create(null), Object.fromEntries(tagIndex.tags.map((t) => [t.id, t])));
const tagsOf = (slug) => tagIndex.byPaper?.[slug] || [];
const tagLabel = (tid) => byTag[tid]?.label || tid;
const paper = computed(() => (mode.value === "papers" ? bySlug[id.value] : null));
const topic = computed(() => (mode.value === "topics" ? byTheme[id.value] : null));
const pageTitle = computed(
  () =>
    paper.value?.title ||
    topic.value?.title ||
    (mode.value === "organizations" ? "Организации авторов" : mode.value === "catalog" ? "Каталог материалов" : "Путеводитель по RecSys 2026"),
);
useHead(() => ({
  title: pageTitle.value,
  htmlAttrs: { lang: "ru" },
  meta: [
    { name: "description", content: "Разборы работ RecSys 2026: метод, числа из статьи и границы применимости." },
    { property: "og:title", content: pageTitle.value },
    { property: "og:description", content: "Путеводитель по исследованиям рекомендательных систем: методы, проверяемые результаты и ограничения." },
    { property: "og:image", content: "https://nagornyy.me/stories/recsys-2026/og.jpg" },
    { property: "og:image:width", content: "1200" },
    { property: "og:image:height", content: "630" },
    { property: "og:type", content: "article" },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:image", content: "https://nagornyy.me/stories/recsys-2026/og.jpg" },
  ],
  // Theme before first paint: ?scheme= (screenshots) > saved choice > auto. "theme" in the query is the catalog filter.
  script: [
    {
      key: "rs-theme",
      tagPosition: "head",
      innerHTML:
        "(function(){var r=document.documentElement,t;try{t=new URLSearchParams(location.search).get('scheme')||localStorage.getItem('rs-theme')}catch(e){}r.dataset.theme=t==='light'||t==='dark'?t:'auto'})()",
    },
  ],
}));
/* ---------- theme: auto -> light -> dark, data-theme on <html> (design tokens) ---------- */
const THEMES = ["auto", "light", "dark"];
const THEME_LABEL = { auto: "как в системе", light: "светлая", dark: "тёмная" };
const themePref = ref("auto");
function cycleTheme() {
  const t = THEMES[(THEMES.indexOf(themePref.value) + 1) % THEMES.length];
  themePref.value = t;
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem("rs-theme", t);
  } catch (e) {}
}

/* ---------- обсуждение vpvd: ветка под страницей раздела (встраивание, контракт vpvd) ----------
   Кадр заводит ветку по адресу страницы, а не по домену хозяина: значит адрес канонический и без
   query. Фильтры каталога (?q=, ?theme=, ?org=, ?zotero=, ?type=) — тот же материал, и ветка у
   него должна быть одна; origin берём из домена сайта (он же в canonical и og:image), а путь — из
   маршрута: маршрут реактивен, и при переходе между разборами загрузчик переставляет кадр на
   ветку новой страницы (он следит за data-url контейнера). */
const SITE_ORIGIN = "https://nagornyy.me";
const embedUrl = computed(() => SITE_ORIGIN + route.path);
/* Загрузчик ставим сами, а не разметкой сниппета: Vue убирает <script> из DOM при гидратации
   (проверено на собранной странице: в отданном HTML тег есть, в живом DOM его уже нет), поэтому
   разметка сработала бы только на первом заходе, а клиентский переход внутри раздела — а их
   большинство, раздел листают из каталога — остался бы без виджета. Адрес загрузчика постоянный,
   поэтому повторная постановка дешева (кэш), а его собственный сторож не даёт подняться дважды. */
function ensureVpvdLoader() {
  if (typeof window === "undefined" || window.vpvd) return;
  if (document.querySelector("script[data-vpvd-loader]")) return;
  const tag = document.createElement("script");
  tag.src = "https://vpvd.io/embed.js";
  tag.async = true;
  tag.referrerPolicy = "no-referrer";
  tag.setAttribute("data-vpvd-loader", "1");
  document.head.appendChild(tag);
}
/* Дальше — сам загрузчик: он следит за добавленными узлами, но при клиентском переходе контейнер
   появляется уже после его старта, поэтому просим пересобрать кадры (документированный ключ vpvd
   для динамики). Именно refresh, а не mount(): mount принимает конкретный контейнер, а после
   перехода адрес у того же узла уже другой — нужен обход всех. Чужого кода это не поднимает:
   window.vpvd появляется только от vpvd. */
function mountVpvd() {
  const loader = window.vpvd;
  if (!loader) return;
  if (typeof loader.refresh === "function") loader.refresh();
  else if (typeof loader.mount === "function") loader.mount(document.querySelector("[data-vpvd-thread]"));
}
onMounted(() => {
  ensureVpvdLoader();
  mountVpvd();
});
watch(embedUrl, () =>
  nextTick(() => {
    ensureVpvdLoader();
    mountVpvd();
  }),
);

/* ---------- catalog filters: every state lives in the URL ---------- */
const query = computed(() => String(route.query.q || ""));
const theme = computed(() => String(route.query.theme || ""));
const second = computed(() => String(route.query.also || ""));
const org = computed(() => String(route.query.org || ""));
const tag = computed(() => String(route.query.tag || ""));
const status = computed(() => String(route.query.status || "reviewed"));
const inZotero = computed(() => route.query.zotero === "1");
function catalogQuery(patch) {
  const q = { ...(mode.value === "catalog" ? route.query : {}), ...patch };
  for (const k of Object.keys(q)) if (!q[k]) delete q[k];
  return q;
}
// Typing replaces the entry (no history spam); discrete choices push, so Back undoes them.
function setFilter(key, value, push = false) {
  router[push ? "push" : "replace"]({ path: base + "/catalog", query: catalogQuery({ [key]: value }) });
}
const tagTo = (t) => ({ path: base + "/catalog", query: catalogQuery({ theme: theme.value === t && mode.value === "catalog" ? "" : t }) });
// Ссылки внутри строк каталога — обычные <a href>. Видимый результат тот же, но при
// гидратации 269 строк каталога не создаётся ~800 компонентов NuxtLink (у каждого свой setup
// и route-вычисления): замер показал, что именно они держали TBT каталога. SPA-переход
// возвращает один делегированный обработчик на <ol> (listClick ниже).
const hrefCache = new Map();
function linkHref(to) {
  const key = to.path + "?" + JSON.stringify(to.query || {});
  let v = hrefCache.get(key);
  if (v === undefined) {
    v = router.resolve(to).href;
    hrefCache.set(key, v);
  }
  return v;
}
// review tag link: from the catalog it toggles the tag on top of the current filters; elsewhere it opens a clean filter
const reviewTagTo = (t) => ({ path: base + "/catalog", query: catalogQuery({ tag: tag.value === t && mode.value === "catalog" ? "" : t }) });
const filtered = computed(() =>
  papers.filter(
    (p) =>
      (!query.value ||
        (p.title + " " + (p.summary || "") + " " + p.doi.join(" ")).toLocaleLowerCase("ru").includes(query.value.toLocaleLowerCase("ru"))) &&
      (!theme.value || p.tags?.includes(theme.value)) &&
      (!second.value || p.tags?.includes(second.value)) &&
      (!tag.value || tagsOf(p.slug).includes(tag.value)) &&
      (!org.value || (org.value === "unknown" ? !p.affiliations.length : p.affiliations.some((a) => a.organization === org.value))) &&
      (!inZotero.value || zotBySlug[p.slug]) &&
      (status.value === "all" || p.status === status.value),
  ),
);
const activeFilters = computed(() => {
  const f = [];
  if (query.value) f.push({ key: "q", label: "«" + query.value + "»" });
  if (theme.value) f.push({ key: "theme", label: byTheme[theme.value]?.title || theme.value });
  if (second.value) f.push({ key: "also", label: "∩ " + (byTheme[second.value]?.title || second.value) });
  if (tag.value) f.push({ key: "tag", label: "#" + tagLabel(tag.value) });
  if (org.value) f.push({ key: "org", label: org.value === "unknown" ? "Без подтверждённой организации" : byOrg[org.value]?.name || org.value });
  if (inZotero.value) f.push({ key: "zotero", label: "Есть в Zotero" });
  return f;
});
const lastCatalog = useState("rs-last-catalog", () => null);
watch(
  () => route.fullPath,
  () => {
    if (mode.value === "catalog") lastCatalog.value = { ...route.query };
  },
  { immediate: true },
);
const backToCatalog = computed(() => ({ path: base + "/catalog", query: lastCatalog.value || {} }));

/* ---------- View Transitions: catalog <-> article share the work's title ----------
   The title of the work being opened/closed carries view-transition-name "rs-title" in both
   states. Unsupported browsers and prefers-reduced-motion skip it: navigation is instant. */
const vtSlug = useState("rs-vt-slug", () => null);
const vtOn = useState("rs-vt-on", () => false);
const kindOf = (path) => (path.startsWith(base + "/catalog") ? "catalog" : path.startsWith(base + "/papers/") ? "papers" : "");
// The page component is re-created per path, so the guard and the "new view is ready" hook are
// installed once per app (not per instance) and finish on Nuxt's page:finish.
if (import.meta.client) {
  const nuxtApp = useNuxtApp();
  if (!nuxtApp._rsViewTransition) {
    nuxtApp._rsViewTransition = { done: null };
    const st = nuxtApp._rsViewTransition;
    const finish = () => (st.done?.(), (st.done = null));
    nuxtApp.hook("page:finish", finish);
    nuxtApp.hook("vue:error", finish);
    router.beforeResolve((to, from) => {
      const pair = kindOf(from.path) + ">" + kindOf(to.path);
      if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      if (pair !== "catalog>papers" && pair !== "papers>catalog") return;
      vtSlug.value = (pair === "catalog>papers" ? to : from).path.split("/").pop();
      return nextTick().then(
        () =>
          new Promise((resolve) => {
            const t = document.startViewTransition(() => {
              vtOn.value = true;
              resolve();
              return new Promise((r) => {
                st.done = r;
                setTimeout(finish, 2000); // never leave the page frozen
              });
            });
            t.finished.finally(() => (vtOn.value = false));
          }),
      );
    });
  }
}
// Атрибуты заголовка строки для view-transitions: либо style с именем перехода, либо
// ничего. Пустой :style рендерился как style="" на каждой строке каталога — 269 раз.
const vtAttrs = (slug) => (vtSlug.value === slug ? { style: { viewTransitionName: "rs-title" } } : {});

const kinds = {
  conference_record: "Публикация конференции",
  doctoral_symposium: "Докторантский симпозиум",
  workshop_paper: "Воркшоп",
  challenge_report: "Отчёт челленджа",
  tutorial_materials: "Материалы tutorial",
  tutorial_proposal: "Аннотация tutorial",
};
const plural = (n, one, few, many) => (n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);
const short = (id) => byTheme[id].short; // explicit self-explanatory label from data (t.short), never a truncated title
const themeIdx = Object.fromEntries(themes.map((t, i) => [t.id, i]));
/* ---------- theme statistics ---------- */
const count = (t, primary = false) => reviewed.filter((p) => (primary ? p.primaryTheme === t : p.tags.includes(t))).length;
const intersect = (a, b) => reviewed.filter((p) => p.tags.includes(a) && p.tags.includes(b)).length;
const topicPapers = computed(() => reviewed.filter((p) => p.tags.includes(topic.value?.id)));
const chartMode = ref("primary");
const maxCount = computed(() => Math.max(...themes.map((t) => count(t.id, chartMode.value === "primary"))));
// Theme map: every reviewed work is one cell, stacked in the column of its primary theme.
const tmap = themes.map((t, col) => {
  const cells = reviewed.filter((p) => p.primaryTheme === t.id);
  return { t, col, n: cells.length, all: count(t.id), cells };
});
// Hover/focus on a cell names the work; arrows move between cells (roving tabindex: one stop per row).
const tip = ref(null);
function tmapPoint(e) {
  const a = e.target.closest?.(".rs-cell");
  // slug берём из href: он и так в разметке, отдельный data-slug дублировал его 269 раз.
  tip.value = a ? bySlug[(a.getAttribute("href") || "").split("/").pop()] : null;
}
function tmapKey(e) {
  const a = e.target.closest?.(".rs-cell");
  if (!a) return;
  let r = +a.dataset.row, c = +a.dataset.k;
  const moves = { ArrowRight: [0, 1], ArrowLeft: [0, -1], ArrowDown: [1, 0], ArrowUp: [-1, 0] };
  if (e.key === "Home") c = 0;
  else if (e.key === "End") c = 1e9;
  else if (moves[e.key]) (r += moves[e.key][0]), (c += moves[e.key][1]);
  else return;
  r = Math.max(0, Math.min(tmap.length - 1, r));
  c = Math.max(0, Math.min(tmap[r].cells.length - 1, c));
  const next = document.querySelector(`.rs-cell[data-row="${r}"][data-k="${c}"]`);
  if (next) e.preventDefault(), next.focus();
}

/* ---------- карта близости: текст, темы, сообщества по литературе ---------- */
const MAP = { w: 1000, h: 1000 };
const mapClusters = mapData.clusters;
const mapMode = ref("refs"); // refs | fulltext | clusters | themes
const mapSel = ref("");
const mapTip = ref(null);
// координаты всегда из текстовой проекции: сообщества по литературе показываем
// на той же карте, чтобы видеть, где они лежат в смысловом пространстве
const communityOf = Object.fromEntries((communitiesData.points || []).map((p) => [p.slug, p.community]));
const mapPoints = computed(() => {
  if (mapMode.value === "refs") return communitiesData.points;
  if (mapMode.value === "fulltext") return fulltextData.points;
  return mapData.points.map((p) => ({ ...p, community: communityOf[p.slug] ?? -1 }));
});
const mapGroups = computed(() => {
  if (mapMode.value === "refs") {
    return communitiesData.communities
      .filter((c) => c.size >= 5)
      .map((c, i) => ({ key: "k" + c.id, id: c.id, no: i + 1, label: c.name, n: c.size, theme: c.theme }));
  }
  if (mapMode.value === "fulltext") {
    return fulltextData.clusters.map((c, i) => ({ key: "f" + c.id, id: c.id, no: i + 1, label: c.name || short(c.topTheme), n: c.size, theme: c.topTheme }));
  }
  return mapMode.value === "clusters"
    ? mapClusters.map((c, i) => ({ key: "c" + c.id, id: c.id, no: i + 1, label: c.name, n: c.size, theme: c.topTheme }))
    : themes.map((t, i) => ({ key: "t" + t.id, id: t.id, no: i + 1, label: short(t.id), n: count(t.id, true), theme: t.id }));
});
const mapKeyOf = (p) => {
  if (mapMode.value === "refs") return p.community < 0 ? "noise" : "k" + p.community;
  if (mapMode.value === "fulltext") return p.cluster < 0 ? "noise" : "f" + p.cluster;
  return mapMode.value === "clusters" ? (p.cluster < 0 ? "noise" : "c" + p.cluster) : "t" + p.theme;
};
const mapIsNoise = (p) => mapKeyOf(p) === "noise";
const mapFill = (p) => {
  if (!mapSel.value) return mapIsNoise(p) ? "var(--rule)" : "var(--accent)";
  return mapKeyOf(p) === mapSel.value ? "var(--accent)" : "var(--rule)";
};
const mapOpacity = (p) => (!mapSel.value ? (mapIsNoise(p) ? 0.4 : 0.8) : mapKeyOf(p) === mapSel.value ? 1 : 0.16);
// Рёбра графа общих ссылок: толщина ∝ числу общих источников.
// Без выбранного сообщества рисуем только сильные связи (>=4 общих), иначе экран — клубок.
const mapEdges = computed(() => {
  if (mapMode.value !== "refs" || !communitiesData.edges) return [];
  const pts = communitiesData.points;
  const sel = mapSel.value;
  return communitiesData.edges
    // показываем только связи внутри сообщества: межгрупповые рёбра превращают карту в паутину
    .filter(([i, j, w]) => pts[i].community === pts[j].community
      && (sel ? "k" + pts[i].community === sel : w >= 4))
    .map(([i, j, w]) => ({
      key: i + "-" + j,
      x1: pts[i].x, y1: pts[i].y, x2: pts[j].x, y2: pts[j].y,
      sw: Math.min(3.6, 0.4 + w * 0.22),
      op: sel ? 0.6 : Math.min(0.5, 0.08 + w * 0.03),
    }));
});
const mapSelected = computed(() => mapGroups.value.find((g) => g.key === mapSel.value) || null);
const mapSelectedPapers = computed(() =>
  !mapSel.value ? [] : mapPoints.value.filter((p) => mapKeyOf(p) === mapSel.value).map((p) => bySlug[p.slug]).filter(Boolean),
);
const mapCaption = computed(() => {
  if (mapMode.value === "fulltext") {
    const m = fulltextData.meta;
    return `${m.clusters} кластеров · ${m.n} разборов · эмбеддинги по полным текстам статей · HDBSCAN, вне кластеров — ${m.noise}`;
  }
  if (mapMode.value === "refs") {
    const m = communitiesData.meta;
    return `${m.communities} сообществ · ${m.papers} разборов · ${m.withRefs} со списком литературы · Leiden, modularity ${m.modularity} · ${m.edges} связей`;
  }
  return `${mapData.meta.clusters} кластеров · ${mapData.meta.n} разборов · HDBSCAN в 10-мерной проекции UMAP, вне кластеров — ${mapData.meta.noise}`;
});
// Номера групп на карте: подпись у центроида, без оболочек — полигон врал бы о границах.
const mapCenters = computed(() => {
  const groups = new Map();
  for (const p of mapPoints.value) {
    const k = mapKeyOf(p);
    if (k === "noise") continue;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(p);
  }
  const out = [];
  for (const [key, pts] of groups) {
    out.push({
      key,
      n: pts.length,
      cx: pts.reduce((sum, p) => sum + p.x, 0) / pts.length,
      cy: pts.reduce((sum, p) => sum + p.y, 0) / pts.length,
      no: mapGroups.value.find((g) => g.key === key)?.no,
    });
  }
  return mapSel.value ? out.filter((s) => s.key === mapSel.value) : out.filter((s) => s.n >= 10);
});
function mapPick(e) {
  const a = e.target.closest?.(".rs-mdot");
  mapTip.value = a ? bySlug[a.dataset.slug] : null;
}
function mapToggle(key) {
  mapSel.value = mapSel.value === key ? "" : key;
}
watch(mapMode, () => (mapSel.value = ""));

const kindOrder = Object.entries(
  reviewed.reduce((m, p) => ((m[p.kind] = (m[p.kind] || 0) + 1), m), {}),
).sort((a, b) => b[1] - a[1]).map(([k]) => k);
const topOrgs = sortedOrgs.slice(0, 10);
const topOrgOf = (p) => topOrgs.find((o) => p.affiliations.some((a) => a.organization === o.id));
const inTopOrgs = reviewed.filter((p) => topOrgOf(p)).length;
const FIG = { w: 760, h: 440, x0: 236, d: 8, wrap: 24 };
// break a label on word boundaries into lines of <= FIG.wrap chars; nothing is ever shortened
function wrapLabel(label) {
  const lines = [];
  for (const w of label.split(" ")) {
    const last = lines[lines.length - 1];
    if (last !== undefined && (last + " " + w).length <= FIG.wrap) lines[lines.length - 1] = last + " " + w;
    else lines.push(w);
  }
  return lines;
}
function arrange(groups) {
  const rowH = FIG.h / groups.length;
  const per = Math.max(1, Math.floor((rowH - 10) / FIG.d));
  const pos = {}, labels = [];
  groups.forEach((g, gi) => {
    const top = gi * rowH + (rowH - per * FIG.d) / 2 + FIG.d / 2;
    g.items.forEach((p, j) => (pos[p.slug] = [FIG.x0 + Math.floor(j / per) * FIG.d, top + (j % per) * FIG.d]));
    // n — число, которое видит читатель (для организаций это все её работы), items — что рисуем точками
    labels.push({ key: g.key, label: g.label, lines: wrapLabel(g.label), n: g.n ?? g.items.length, y: gi * rowH + rowH / 2 });
  });
  return { pos, labels };
}
const arrangements = [
  arrange(themes.map((t) => ({ key: t.id, label: short(t.id), items: reviewed.filter((p) => p.primaryTheme === t.id) }))),
  arrange([
    // порядок и числа — как на странице организаций (все работы), точки — работы, отнесённые к этой
    // организации (работа с двумя организациями из десятки рисуется один раз, у самой частой)
    ...topOrgs.map((o) => ({
      key: o.id,
      label: o.name.replace(/,? Inc\.$/, ""),
      n: orgCount(o.id),
      items: reviewed.filter((p) => topOrgOf(p) === o),
    })),
    { key: "rest", label: "Остальные организации", items: reviewed.filter((p) => !topOrgOf(p)) },
  ]),
  arrange(kindOrder.map((k) => ({ key: k, label: kinds[k], items: reviewed.filter((p) => p.kind === k) }))),
];
const fills = [
  (p) => "var(--t" + themeIdx[p.primaryTheme] + ")",
  (p) => (topOrgOf(p) ? "var(--ink)" : "var(--rule)"),
  (p) => (p.kind === kindOrder[0] ? "var(--ink)" : "var(--muted)"),
];
const dots = reviewed.map((p, i) => ({ slug: p.slug, i, pos: arrangements.map((a) => a.pos[p.slug]), fill: fills.map((f) => f(p)) }));
// Координаты точки в разметке: два знака после запятой вместо полной точности double
// (translate(236px,256.88888888888886px) — это 269 значений по три разреза).
const px = (v) => Math.round(v * 100) / 100;
const steps = [
  {
    title: "Основная тема",
    text: `У каждой из ${reviewed.length} работ одна основная тема — она и задаёт цвет точки. Крупнейшая тема — «${short(tmap.reduce((a, b) => (b.n > a.n ? b : a)).t.id)}»: ${Math.max(...tmap.map((a) => a.n))} работ. Вторичные темы на этот разрез не влияют: они видны на странице работы и в каталоге.`,
  },
  {
    title: "Организации авторов",
    text: `У ${inTopOrgs} из ${reviewed.length} работ есть хотя бы один автор из десяти самых частых организаций; остальные ${reviewed.length - inTopOrgs} распределены по длинному хвосту из ${organizations.length} организаций. Число у названия — все работы организации. Точка — работа, отнесённая к самой частой из её организаций внутри десятки, поэтому точек в строке может быть меньше.`,
  },
  {
    title: "Тип материала",
    text: `Разбор полного текста есть у всех ${reviewed.length} работ, запись в Zotero — у ${zotLinked}. ${reviewed.filter((p) => p.kind === kindOrder[0]).length} — ${kinds[kindOrder[0]].toLowerCase()}; остальное — докторантский симпозиум, воркшоп-доклады, tutorial и отчёт челленджа.`,
  },
];
const step = ref(0);
let stepObserver;
function observeSteps() {
  stepObserver?.disconnect();
  if (typeof IntersectionObserver === "undefined") return;
  stepObserver = new IntersectionObserver(
    (entries) => {
      for (const e of entries) if (e.isIntersecting) step.value = +e.target.dataset.step;
    },
    { rootMargin: "-48% 0px -48% 0px" },
  );
  document.querySelectorAll(".rs-step").forEach((s) => stepObserver.observe(s));
}
const chosenPair = ref(null);
const pairPapers = computed(() => (chosenPair.value ? reviewed.filter((p) => chosenPair.value.every((t) => p.tags.includes(t))) : []));

/* ---------- tag cloud: size is a sqrt scale of the number of works ---------- */
const cloudMode = ref("tags");
function scale(items, min, max) {
  const lo = Math.sqrt(Math.min(...items.map((i) => i.n)));
  const hi = Math.sqrt(Math.max(...items.map((i) => i.n)));
  return items.map((i) => ({ ...i, size: (min + ((Math.sqrt(i.n) - lo) / Math.max(1e-9, hi - lo)) * (max - min)).toFixed(2) + "rem" }));
}
// Tags with 2+ works; single-use tags stay in the index and still work as a catalog filter.
// DOM order = tab order = descending number of works (ties alphabetical).
const tagCloud = scale(
  tagIndex.tags
    .filter((t) => t.count >= 2)
    .map((t) => ({ key: t.id, label: t.label, n: t.count, to: { path: base + "/catalog", query: { tag: t.id } } }))
    .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label)),
  0.95,
  3.1,
);
const tagsSingle = tagIndex.tags.length - tagCloud.length;
const orgCloud = scale(
  sortedOrgs.slice(0, 48).map((o) => ({ key: o.id, label: o.name, n: orgCount(o.id), to: { path: base + "/catalog", query: { org: o.id } } })),
  0.85,
  2.9,
).sort((a, b) => a.label.localeCompare(b.label));
const cloud = computed(() => (cloudMode.value === "tags" ? tagCloud : orgCloud));
const cloudRange = computed(() => [Math.min(...cloud.value.map((c) => c.n)), Math.max(...cloud.value.map((c) => c.n))]);

/* ---------- organizations page ---------- */
const orgQuery = computed(() => String(route.query.q || ""));
const orgType = computed(() => String(route.query.type || ""));
const orgTypeCounts = Object.fromEntries(Object.keys(orgTypes).map((k) => [k, organizations.filter((o) => o.type === k).length]));
const orgsShown = computed(() =>
  sortedOrgs.filter(
    (o) =>
      (!orgType.value || o.type === orgType.value) &&
      (!orgQuery.value || o.aliases.join(" ").toLocaleLowerCase("ru").includes(orgQuery.value.toLocaleLowerCase("ru"))),
  ),
);
const maxOrg = orgCount(sortedOrgs[0].id);
function setOrgFilter(key, value, push = false) {
  const q = { ...route.query, [key]: value };
  if (!value) delete q[key];
  router[push ? "push" : "replace"]({ path: base + "/organizations", query: q });
}

/* ---------- article ---------- */
const articleUrl = computed(() => (paper.value?.status === "reviewed" ? base + "/articles/" + paper.value.slug + ".json" : null));
// Тело разбора лежит отдельным JSON в public/. В SSR этот путь перехватывает эта
// же страница и отвечает 500 (проверено и с useRequestFetch), поэтому тянем тело
// с клиента: оттуда файл отдаёт CDN и разбор открывается по прямой ссылке.
// Список литературы грузится отдельным файлом на работу (262 файла по ~5 КБ):
// страница не тянет библиографию всего корпуса. Как и тело разбора — с клиента,
// потому что в SSR тот же путь перехватывает страница-обёртка и отвечает 500.
const refsUrl = computed(() => (paper.value ? base + "/refs/" + paper.value.slug + ".json" : null));
const { data: refsData } = useAsyncData(
  "recsys-refs-" + (id.value || "none"),
  () => (refsUrl.value ? $fetch(refsUrl.value).catch(() => null) : Promise.resolve(null)),
  { watch: [refsUrl], server: false },
);
const { data: article } = useAsyncData(
  "recsys-article-" + (id.value || "home"),
  () => (articleUrl.value ? $fetch(articleUrl.value) : Promise.resolve(null)),
  { watch: [articleUrl], server: false },
);
const related = computed(() =>
  paper.value?.tags
    ? reviewed
        .filter((p) => p.slug !== paper.value.slug)
        .map((p) => ({ p, n: p.tags.filter((t) => paper.value.tags.includes(t)).length }))
        .filter((x) => x.n)
        .sort((a, b) => b.n - a.n || a.p.title.localeCompare(b.p.title))
        .slice(0, 6)
        .map((x) => x.p)
    : [],
);
/* prev/next inside the primary theme, in catalog order */
const themeRun = computed(() => (paper.value ? papers.filter((p) => p.primaryTheme === paper.value.primaryTheme) : []));
const themePos = computed(() => themeRun.value.findIndex((p) => p.slug === paper.value?.slug));
const prevInTheme = computed(() => themeRun.value[themePos.value - 1] || null);
const nextInTheme = computed(() => themeRun.value[themePos.value + 1] || null);
const readPct = ref(0);
let readRaf = 0;
function measureReading() {
  readRaf = 0;
  const el = document.querySelector(".rs-prose");
  if (!el) return;
  const r = el.getBoundingClientRect();
  readPct.value = Math.round(Math.max(0, Math.min(1, (innerHeight * 0.35 - r.top) / Math.max(1, r.height - innerHeight * 0.4))) * 100);
}
const onReadScroll = () => (readRaf ||= requestAnimationFrame(measureReading));

/* catalog rows expand in place (click on the row or Enter on its number) */
const openRows = ref(new Set());
// «Что важно» и «граница вывода» — из карточки разбора; в проекции каталога их нет
// (иначе корпус целиком ехал бы в каждую загрузку), поэтому строка дотягивает их по клику.
const rowDetail = ref({});
function toggleRow(slug) {
  const s = new Set(openRows.value);
  s.has(slug) ? s.delete(slug) : s.add(slug);
  openRows.value = s;
  if (s.has(slug) && !rowDetail.value[slug])
    $fetch("/api/guide", { query: { mode: "papers", id: slug } }).then((b) => {
      const found = (b.papers || []).find((x) => x.slug === slug);
      if (found) rowDetail.value = { ...rowDetail.value, [slug]: { insight: found.insight, limitation: found.limitation } };
    });
}
// Один делегированный обработчик на весь список: раскрытие строки (клик по строке или по её
// номеру) и SPA-переход по внутренним ссылкам (внешние, ctrl/middle-click — браузеру).
function listClick(e) {
  if (e.defaultPrevented || e.button > 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const row = e.target.closest?.(".rs-paper-card");
  if (!row) return;
  const a = e.target.closest("a");
  if (a) {
    const h = a.getAttribute("href") || "";
    if (h.startsWith("/") && !a.target) {
      e.preventDefault();
      router.push(h);
    }
    return;
  }
  const slug = (row.querySelector("h2 a")?.getAttribute("href") || "").split("/").pop();
  if (!slug || window.getSelection?.().toString()) return;
  toggleRow(slug);
}
// mini-histogram above the table: works per theme within the current result
const maxTag = Math.max(...themes.map((t) => count(t.id)));
const hist = computed(() => Object.fromEntries(themes.map((t) => [t.id, filtered.value.filter((p) => p.tags.includes(t.id)).length])));

const backlinks = computed(() => themes.filter((t) => t.insights.some((i) => i.slugs.includes(paper.value?.slug))));
const orgNames = (p) => p.affiliations.map((a) => byOrg[a.organization]?.name).filter(Boolean);

/* ---------- reading: active section in the table of contents ---------- */
const activeSection = ref("");
let observer;
function observeSections() {
  observer?.disconnect();
  if (typeof IntersectionObserver === "undefined") return;
  observer = new IntersectionObserver(
    (entries) => {
      for (const e of entries) if (e.isIntersecting) activeSection.value = e.target.id;
    },
    { rootMargin: "-20% 0px -70% 0px" },
  );
  document.querySelectorAll(".rs-prose section[id]").forEach((s) => observer.observe(s));
}
let mastObserver;
onMounted(() => {
  document.documentElement.classList.add("rs-js");
  const t0 = document.documentElement.dataset.theme;
  themePref.value = THEMES.includes(t0) ? t0 : "auto";
  document.documentElement.dataset.theme = themePref.value;
  // nav scrolls horizontally on phones: bring the current item into view
  const navOn = document.querySelector(".rs-mast nav a.on");
  if (navOn) { const n = navOn.parentElement; n.scrollLeft = Math.max(0, navOn.offsetLeft - n.offsetLeft - 16); }
  // sticky layers below the masthead follow its real height (it wraps on narrow screens)
  const mast = document.querySelector(".rs-mast");
  if (mast && typeof ResizeObserver !== "undefined") {
    mastObserver = new ResizeObserver(() => document.querySelector(".rs")?.style.setProperty("--mast", Math.round(mast.getBoundingClientRect().height) + "px"));
    mastObserver.observe(mast);
  }
  observeSections();
  observeSteps();
  if (mode.value === "papers") {
    addEventListener("scroll", onReadScroll, { passive: true });
    addEventListener("resize", onReadScroll, { passive: true });
    measureReading();
  }
});
watch(article, () => nextTick(() => (observeSections(), measureReading())));
onBeforeUnmount(() => {
  observer?.disconnect();
  stepObserver?.disconnect();
  mastObserver?.disconnect();
  removeEventListener("scroll", onReadScroll);
  removeEventListener("resize", onReadScroll);
});
const pad = (n) => String(n).padStart(3, "0");
</script>

<template>
  <div class="rs">
    <a class="rs-skip" href="#main">К содержанию</a>
    <div v-if="mode === 'papers'" class="rs-progress" aria-hidden="true"></div>
    <header class="rs-mast">
      <NuxtLink to="/" class="rs-brand">Олег Нагорный</NuxtLink>
      <NuxtLink :to="base" class="rs-issue">RecSys<b>2026</b></NuxtLink>
      <nav aria-label="Раздел конференции">
        <NuxtLink :to="base" :class="{ on: mode === 'home' }">Обзор</NuxtLink>
        <NuxtLink :to="base + '#themes'">Темы</NuxtLink>
        <NuxtLink :to="base + '/catalog'" :class="{ on: mode === 'catalog' || mode === 'papers' }">Каталог <span>{{ stats.reviewed }}</span></NuxtLink>
        <NuxtLink :to="base + '/organizations'" :class="{ on: mode === 'organizations' }">Организации</NuxtLink>
        <NuxtLink :to="base + '/workshops'">Воркшопы <span>{{ wsMeta.positions }}</span></NuxtLink>
      </nav>
      <button type="button" class="rs-theme" :data-pref="themePref" :aria-label="'Тема: ' + THEME_LABEL[themePref] + '. Переключить'" :title="'Тема: ' + THEME_LABEL[themePref]" @click="cycleTheme">
        <svg v-if="themePref === 'light'" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
        <svg v-else-if="themePref === 'dark'" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17z" fill="currentColor" /></svg>
      </button>
    </header>
    <main id="main">
      <Transition :name="vtOn ? 'rs-none' : 'rs-view'" :css="!vtOn" mode="out-in">
        <div :key="viewKey" class="rs-view">
          <!-- ================= HOME ================= -->
          <template v-if="mode === 'home'">
            <section class="rs-hero rs-wrap">
              <div class="rs-hero-copy">
                <p class="rs-kicker"><span>ACM RecSys 2026</span><span>Миннеаполис · 27.09–02.10</span><span>обновлено {{ data.version }}</span></p>
                <h1>Путеводитель по&nbsp;<em>RecSys&nbsp;2026</em></h1>
                <p class="rs-lead">
                  Разборы {{ stats.reviewed }} работ конференции, прочитанных целиком: статьи, воркшоп-доклады, доклады симпозиума и tutorial. У каждой — что
                  предложено, какие числа получены и где вывод перестаёт работать.
                </p>
                <div class="rs-actions">
                  <NuxtLink class="rs-button" :to="base + '/catalog'">Открыть каталог</NuxtLink>
                  <NuxtLink class="rs-textlink" :to="base + '/organizations'">Организации</NuxtLink>
                  <NuxtLink class="rs-textlink" :to="base + '/workshops'">Воркшопы и туториалы · {{ wsMeta.positions }}</NuxtLink>
                  <a class="rs-textlink" href="#cloud">Облако тегов ↓</a>
                </div>
              </div>
              <figure class="rs-tmap" aria-labelledby="rs-tmap-cap">
                <figcaption id="rs-tmap-cap">
                  <b>Работы по основной теме: {{ stats.reviewed }}</b> · клетка — одна работа, клик открывает разбор · название темы — её каталог
                </figcaption>
                <ol class="rs-tmap-rows" :style="{ '--max': Math.max(...tmap.map((x) => x.n)) }" @mouseover="tmapPoint" @focusin="tmapPoint" @mouseleave="tip = null" @keydown="tmapKey">
                  <li v-for="a in tmap" :key="a.t.id" class="rs-tmap-line" :style="{ '--i': a.col, '--c': 'var(--t' + a.col + ')' }">
                    <NuxtLink
                      :to="{ path: base + '/catalog', query: { theme: a.t.id } }"
                      class="rs-tmap-row"
                      :aria-label="a.t.title + ': ' + a.n + ' как главная тема, ' + a.all + ' с тегом. Открыть каталог'"
                      ><span class="rs-tmap-label">{{ short(a.t.id) }}</span></NuxtLink
                    >
                    <span class="rs-tmap-cells" role="group" :aria-label="'Работы: ' + a.t.title"
                      ><NuxtLink
                        v-for="(p, k) in a.cells"
                        :key="p.slug"
                        :to="base + '/papers/' + p.slug"
                        class="rs-cell"
                        :data-row="a.col"
                        :data-k="k"
                        :tabindex="k === 0 ? 0 : -1"
                        :aria-label="p.title"
                        :style="{ '--k': k }"
                      ></NuxtLink
                    ></span>
                    <b class="rs-tmap-n" aria-hidden="true">{{ a.n }}</b>
                  </li>
                </ol>
                <p class="rs-tmap-tip" aria-live="polite" lang="en">
                  <template v-if="tip"><b>{{ short(tip.primaryTheme) }}</b> {{ tip.title }}</template>
                  <span v-else lang="ru">Наведите на клетку или пройдите стрелками — появится название работы.</span>
                </p>
              </figure>
            </section>
            <section class="rs-metrics rs-wrap" aria-label="Покрытие">
              <div><b>{{ themes.length }}</b><span>направлений</span></div>
              <div><b>{{ stats.themeInsights }}</b><span>{{ plural(stats.themeInsights, "тематический вывод", "тематических вывода", "тематических выводов") }}</span></div>
              <div><b>{{ organizations.length }}</b><span>организаций авторов</span></div>
              <div><b>{{ orgLinks }}</b><span>{{ plural(orgLinks, "связь", "связи", "связей") }} работа × организация</span></div>
              <div><b>{{ zotLinked }}<small>/{{ stats.records }}</small></b><span>записей в Zotero</span></div>
            </section>

            <section class="rs-story rs-wrap" aria-labelledby="rs-story-h">
              <header class="rs-section-head">
                <span class="rs-sec-no">00</span>
                <h2 id="rs-story-h">Одни и те же работы — три разреза.</h2>
                <p>Точка — одна работа конференции; меняется только признак, по которому её раскрасили. Разрез 1 — основная тема работы, разрез 2 — организации её авторов, разрез 3 — тип материала. Прокрутите страницу — рисунок перестроится.</p>
              </header>
              <div class="rs-story-grid">
                <figure class="rs-story-fig" :data-step="step" aria-hidden="true">
                  <div class="rs-story-layer">
                    <p class="rs-story-key"><b>{{ String(step + 1).padStart(2, "0") }}</b> / 03 · {{ steps[step].title }}</p>
                    <svg :viewBox="'0 0 ' + FIG.w + ' ' + FIG.h" class="rs-story-svg">
                      <g v-for="(a, si) in arrangements" :key="si" class="rs-story-labels" :class="{ on: si === step }">
                        <text v-for="l in a.labels" :key="l.key" :y="l.y" text-anchor="end" dominant-baseline="middle">
                          <tspan v-for="(line, li) in l.lines" :key="li" :x="FIG.x0 - 14" :dy="li === 0 ? (-(l.lines.length - 1) * 15) / 2 : 15"
                            >{{ line }}<tspan v-if="li === l.lines.length - 1" class="rs-story-n" dx="6">{{ l.n }}</tspan></tspan
                          >
                        </text>
                      </g>
                      <circle
                        v-for="d in dots"
                        :key="d.slug"
                        class="rs-dot"
                        r="3.2"
                        :style="{ transform: 'translate(' + px(d.pos[step][0]) + 'px,' + px(d.pos[step][1]) + 'px)', fill: d.fill[step], '--d': (d.i % 40) * 6 + 'ms' }"
                      />
                    </svg>
                  </div>
                </figure>
                <ol class="rs-steps">
                  <li v-for="(s, i) in steps" :key="i" class="rs-step" :data-step="i" :aria-current="step === i ? 'step' : undefined">
                    <span class="rs-step-no">{{ String(i + 1).padStart(2, "0") }}</span>
                    <h3>{{ s.title }}</h3>
                    <p>{{ s.text }}</p>
                  </li>
                </ol>
              </div>
            </section>

            <section id="themes" class="rs-wrap rs-section rs-reveal">
              <header class="rs-section-head">
                <span class="rs-sec-no">01</span>
                <h2>От задачи — к работам.</h2>
                <p>У каждой работы одна основная тема и до двух вторичных тегов. Основная тема задаёт место в списке, вторичные показывают, где направления пересекаются.</p>
              </header>
              <ol class="rs-routes">
                <li v-for="(t, i) in themes" :key="t.id" :style="{ '--w': (count(t.id) / Math.max(...themes.map((x) => count(x.id)))) * 100 + '%' }">
                  <NuxtLink :to="base + '/topics/' + t.id" class="rs-route">
                    <span class="rs-route-no">{{ String(i + 1).padStart(2, "0") }}</span>
                    <span class="rs-route-body"><b>{{ t.title }}</b><small>{{ t.dek }}</small></span>
                    <span class="rs-route-n">{{ count(t.id) }}</span>
                  </NuxtLink>
                  <NuxtLink :to="{ path: base + '/catalog', query: { theme: t.id } }" class="rs-route-filter">{{ count(t.id) }} в каталоге →</NuxtLink>
                </li>
              </ol>
            </section>

            <section id="cloud" class="rs-wrap rs-section rs-reveal">
              <header class="rs-section-head">
                <span class="rs-sec-no">02</span>
                <h2>Облако: чем больше слово, тем больше работ.</h2>
              </header>
              <div class="rs-cloud-bar">
                <fieldset class="rs-segment">
                  <legend>Что показать</legend>
                  <label><input v-model="cloudMode" type="radio" value="tags" name="cloud" /> Теги</label>
                  <label><input v-model="cloudMode" type="radio" value="orgs" name="cloud" /> Организации, топ-48</label>
                </fieldset>
                <p class="rs-cloud-legend">
                  <span style="font-size: 0.8rem">{{ cloudRange[0] }}</span> → <span style="font-size: 1.6rem">{{ cloudRange[1] }}</span>
                  <small
                    >работ; площадь слова растёт как √n. Клик открывает каталог с этим фильтром.<template v-if="cloudMode === 'tags'">
                      Теги из разборов, у которых 2 и больше работ: {{ tagCloud.length }} из {{ tagIndex.tags.length }}; остальные {{ tagsSingle }} — на страницах работ.</template
                    ></small
                  >
                </p>
              </div>
              <Transition name="rs-cloud" mode="out-in">
                <ul :key="cloudMode" class="rs-cloud" :class="'rs-cloud-' + cloudMode" :aria-label="cloudMode === 'tags' ? 'Облако тегов' : 'Облако организаций'">
                  <li v-for="(c, i) in cloud" :key="c.key" :style="{ '--i': i, '--c': c.color }">
                    <NuxtLink :to="c.to" :style="{ fontSize: c.size, '--fs': c.size }" :aria-label="c.label + ', ' + c.n + ' ' + plural(c.n, 'работа', 'работы', 'работ')" :title="c.n + ' ' + plural(c.n, 'работа', 'работы', 'работ')"
                      >{{ c.label }}<sup>{{ c.n }}</sup></NuxtLink
                    >
                  </li>
                </ul>
              </Transition>
            </section>

            <section id="analytics" class="rs-analytics rs-reveal">
              <div class="rs-wrap rs-section">
                <header class="rs-section-head">
                  <span class="rs-sec-no">03</span>
                  <h2>Темы редко живут поодиночке.</h2>
                  <p>Это карта нашей разметки, а не рейтинг научной значимости и не проекция эмбеддингов.</p>
                </header>
                <div class="rs-chart-grid">
                  <section class="rs-chart">
                    <h3>Распределение тем</h3>
                    <fieldset class="rs-segment">
                      <legend>Способ подсчёта</legend>
                      <label><input v-model="chartMode" type="radio" value="primary" /> Главная тема</label
                      ><label><input v-model="chartMode" type="radio" value="all" /> Все теги</label>
                    </fieldset>
                    <p class="rs-caption">
                      {{
                        chartMode === "primary"
                          ? "Каждый разбор учтён один раз; сумма равна " + stats.reviewed + "."
                          : "Один разбор может входить в несколько тем. Знаменатель — " + stats.reviewed + " разборов; сумма превышает его."
                      }}
                    </p>
                    <NuxtLink v-for="t in themes" :key="t.id" :to="{ path: base + '/catalog', query: { theme: t.id } }" class="rs-bar"
                      ><span>{{ t.title }}</span>
                      <div>
                        <i :style="{ width: (count(t.id, chartMode === 'primary') / maxCount) * 100 + '%' }"></i
                        ><b>{{ count(t.id, chartMode === "primary") }}</b>
                      </div></NuxtLink
                    >
                  </section>
                  <section class="rs-chart">
                    <h3>Матрица совместных тем</h3>
                    <p class="rs-caption">Ячейка — число разборов с обоими тегами. Диагональ — все материалы темы. Нажмите для списка.</p>
                    <div class="rs-matrix-scroll">
                      <table class="rs-matrix">
                        <caption>Пересечения тегов, число разборов</caption>
                        <thead>
                          <tr>
                            <th scope="col">Тема</th>
                            <th v-for="t in themes" :key="t.id" scope="col"><abbr :title="t.title">{{ t.id.toUpperCase() }}</abbr></th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr v-for="a in themes" :key="a.id">
                            <th scope="row"><abbr :title="a.title">{{ a.id.toUpperCase() }}</abbr></th>
                            <td v-for="b in themes" :key="b.id">
                              <button
                                :aria-label="a.title + ' + ' + b.title + ': ' + intersect(a.id, b.id)"
                                :aria-pressed="!!chosenPair && chosenPair[0] === a.id && chosenPair[1] === b.id"
                                :class="{ dark: 0.05 + (intersect(a.id, b.id) / reviewed.length) * 1.6 > 0.45 }"
                                :style="{ '--a': Math.min(1, 0.05 + (intersect(a.id, b.id) / reviewed.length) * 1.6) }"
                                @click="chosenPair = [a.id, b.id]"
                              >
                                {{ intersect(a.id, b.id) }}
                              </button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <Transition name="rs-fade" mode="out-in">
                      <div v-if="chosenPair" :key="chosenPair.join('-')" class="rs-pair" aria-live="polite">
                        <b>{{ byTheme[chosenPair[0]].title }} × {{ byTheme[chosenPair[1]].title }}</b>
                        <p>Найдено: {{ pairPapers.length }}</p>
                        <ul>
                          <li v-for="p in pairPapers.slice(0, 4)" :key="p.slug">
                            <NuxtLink :to="base + '/papers/' + p.slug">{{ p.title }}</NuxtLink>
                          </li>
                        </ul>
                        <NuxtLink :to="{ path: base + '/catalog', query: { theme: chosenPair[0], also: chosenPair[1] } }">Весь список →</NuxtLink>
                      </div>
                      <details v-else>
                        <summary>Расшифровка обозначений</summary>
                        <p v-for="t in themes" :key="t.id">{{ t.id.toUpperCase() }} — {{ t.title }}</p>
                      </details>
                    </Transition>
                  </section>
                </div>
              </div>
            </section>

            <section id="map" class="rs-wrap rs-section rs-reveal">
              <header class="rs-section-head">
                <span class="rs-sec-no">04</span>
                <h2>Близость: одна точка — один разбор.</h2>
                <p>
                  Два пространства. «Текст разбора» — проекция UMAP эмбеддингов (Qwen3-Embedding-0.6B: заголовок, суть, результат,
                  ограничение; темы и теги в текст не попадали). «Литература» — граф: ребро между работами, у которых есть общий источник,
                  вес ребра — число общих ссылок, раскладка графовая, сообщества — Leiden. Общие группы в тексте: кластеры эмбеддингов
                  и редакторские темы. Выберите группу — остальные точки уйдут в фон.
                </p>
              </header>
              <div class="rs-map-layout">
                <figure class="rs-map-fig" aria-labelledby="rs-map-cap">
                  <figcaption id="rs-map-cap" class="rs-caption">
                    <b>{{ mapMode === "refs" ? "Сообщества по литературе" : mapMode === "fulltext" ? "Полные тексты статей" : "По тексту разбора" }}</b> · {{ mapCaption }}. Нажмите на точку, чтобы открыть разбор.
                  </figcaption>
                  <fieldset class="rs-segment">
                    <legend>Группировка</legend>
                    <label><input v-model="mapMode" type="radio" value="refs" name="mapmode" /> Сообщества по литературе</label>
                    <label><input v-model="mapMode" type="radio" value="fulltext" name="mapmode" /> Кластеры по полным текстам</label>
                    <label><input v-model="mapMode" type="radio" value="clusters" name="mapmode" /> Кластеры эмбеддингов</label>
                    <label><input v-model="mapMode" type="radio" value="themes" name="mapmode" /> Редакторские темы</label>
                  </fieldset>
                  <svg :viewBox="'0 0 ' + MAP.w + ' ' + MAP.h" class="rs-map-svg" @mouseover="mapPick" @mouseleave="mapTip = null">
                    <circle
                      v-for="p in mapPoints"
                      :key="p.slug"
                      :cx="p.x"
                      :cy="p.y"
                      :r="mapMode === 'refs' ? 3.8 : 5.4"
                      class="rs-mdot"
                      :data-slug="p.slug"
                      :style="{ fill: mapFill(p), opacity: mapOpacity(p) }"
                      @click="router.push(base + '/papers/' + p.slug)"
                    >
                      <title>{{ bySlug[p.slug]?.title }}</title>
                    </circle>
                    <g v-if="mapEdges.length" class="rs-medges">
                      <line
                        v-for="e in mapEdges"
                        :key="e.key"
                        :x1="e.x1"
                        :y1="e.y1"
                        :x2="e.x2"
                        :y2="e.y2"
                        :style="{ strokeWidth: e.sw, opacity: e.op }"
                      />
                    </g>
                    <text
                      v-for="s in mapCenters"
                      :key="'l' + s.key"
                      :x="s.cx"
                      :y="s.cy"
                      class="rs-mlabel"
                      :class="{ on: mapSel === s.key }"
                      aria-hidden="true"
                    >
                      {{ s.no }}
                    </text>
                  </svg>
                  <p class="rs-map-tip" aria-live="polite">
                    <template v-if="mapTip">
                      <b>{{ short(mapTip.primaryTheme) }}</b> {{ mapTip.title }}
                    </template>
                    <span v-else>Наведите на точку — появится название работы.</span>
                  </p>
                </figure>
                <aside class="rs-map-side">
                  <button v-if="mapSel" type="button" class="rs-map-reset" @click="mapSel = ''">Показать все группы</button>
                  <ol class="rs-map-groups" :aria-label="mapMode === 'clusters' ? 'Кластеры' : 'Редакторские темы'">
                    <li v-for="g in mapGroups" :key="g.key">
                      <button
                        type="button"
                        :aria-pressed="mapSel === g.key"
                        :class="{ on: mapSel === g.key }"
                        @click="mapToggle(g.key)"
                      >
                        <span class="rs-map-no">{{ String(g.no).padStart(2, "0") }}</span>
                        <span class="rs-map-name">{{ g.label }}</span>
                        <b>{{ g.n }}</b>
                      </button>
                    </li>
                  </ol>
                  <div v-if="mapSelected" class="rs-map-list" aria-live="polite">
                    <b>{{ mapSelected.label }}</b>
                    <ul>
                      <li v-for="p in mapSelectedPapers.slice(0, 6)" :key="p.slug">
                        <NuxtLink :to="base + '/papers/' + p.slug">{{ p.title }}</NuxtLink>
                      </li>
                    </ul>
                    <p v-if="mapSelectedPapers.length > 6" class="rs-caption">и ещё {{ mapSelectedPapers.length - 6 }}</p>
                  </div>
                  <p v-else-if="mapMode === 'refs'" class="rs-caption">
                    Граф: ребро между двумя работами — общий источник в литературе, вес ребра — число общих источников (от двух).
                    Сообщества — Leiden на этом графе, раскладка графовая (не UMAP): {{ communitiesData.meta.edges }} связей,
                    modularity {{ communitiesData.meta.modularity }}, стабильность {{ communitiesData.meta.stabilityAri }} по сидам.
                    Совпадение с темами NMI {{ communitiesData.meta.nmiThemes }}, с текстовыми кластерами ARI
                    {{ communitiesData.meta.ariTextClusters }} — разрез про школу цитирования, а не про тему работы.
                  </p>
                  <p v-else-if="mapMode === 'fulltext'" class="rs-caption">
                    Кластеры по полным текстам статей (Qwen3-Embedding-0.6B, чанки усреднены по работе): силуэт в исходном
                    пространстве {{ fulltextData.meta.silhouetteCosine }}, стабильность {{ fulltextData.meta.stabilityAri }} по сидам.
                    Согласие с редакторскими темами ARI {{ fulltextData.meta.ariThemes }}, NMI {{ fulltextData.meta.nmiThemes }} —
                    темы остаются рамкой каталога, а не естественными классами.
                  </p>
                  <p v-else class="rs-caption">
                    Совпадение кластеров с редакторскими темами слабое: NMI {{ mapData.meta.nmiHdbscan }}, ARI
                    {{ mapData.meta.ariHdbscan }}. Темы отвечают на вопрос «о чём работа спорит», а кластеры собираются по постановке задачи —
                    поэтому одна тема распадается на несколько облаков, а соседние облака могут быть про разное.
                  </p>
                </aside>
              </div>
            </section>

            <section id="method" class="rs-wrap rs-section rs-method rs-reveal">
              <header class="rs-section-head"><span class="rs-sec-no">05</span><h2>Как читать эту карту</h2></header>
              <div class="rs-method-grid">
                <div class="rs-method-block">
                  <h3>Покрытие без двойного счёта</h3>
                  <p>
                    В опубликованном списке принятых работ конференции {{ stats.atlasRecords }} записей. После объединения дублей и вариантов названий остаётся
                    {{ stats.atlasUnique }} уникальных; ещё {{ stats.additional }} материалов нашлись за его пределами — среди воркшоп-докладов, tutorial и отдельных
                    публикаций. В каталоге {{ stats.records }} работ.
                  </p>
                  <p>
                    У {{ stats.reviewed }} работ есть разбор полного текста, {{ stats.awaiting }} ждут его и в графики не входят. У tutorial полным текстом
                    может быть короткая аннотация — тип материала указан на странице работы. Аннотация tutorial и его proceedings-версия — один материал, а не
                    два независимых доказательства.
                  </p>
                </div>
                <div class="rs-method-block">
                  <h3>Идентичность и темы</h3>
                  <p>
                    Работа опознаётся по DOI, затем по arXiv и подтверждённым вариантам названия; у каждой записи один адрес. Если разбор ссылается на
                    внешнюю статью, это не значит, что она попала в каталог конференции.
                  </p>
                  <p>
                    Темы — наша разметка разборов, и тем у одной работы может быть несколько. Числа разных датасетов, протоколов и A/B-тестов мы не складываем в
                    один процент улучшения: онлайн-эффект действует в условиях своей статьи. Это обзор того, что мы прочитали, а не обещание покрыть все
                    proceedings.
                  </p>
                </div>
                <div class="rs-method-block rs-zotero-status">
                  <h3>Zotero: {{ zotLinked }} из {{ stats.records }}</h3>
                  <p>
                    Ссылки ведут на конкретные записи библиотеки Zotero; запись считается привязанной, только если совпали DOI и название.
                    <template v-if="zotLinked < stats.records"
                      >Сейчас запись есть у {{ zotLinked }} материалов, у остальных её пока нет.</template
                    >
                  </p>
                  <NuxtLink :to="{ path: base + '/catalog', query: { zotero: '1' } }">Материалы с записью в Zotero →</NuxtLink>
                </div>
              </div>
            </section>
          </template>

          <!-- ================= ORGANIZATIONS ================= -->
          <section v-else-if="mode === 'organizations'" class="rs-wrap rs-section rs-orgs">
            <p class="rs-kicker"><span>RecSys 2026</span><span>Аффилиации</span></p>
            <h1>Где работают авторы</h1>
            <dl class="rs-org-figures">
              <div><dt>организаций</dt><dd>{{ organizations.length }}</dd></div>
              <div><dt>материалов с организацией</dt><dd>{{ stats.affiliationKnown }}<small>/{{ stats.records }}</small></dd></div>
              <div><dt>связей материал × организация</dt><dd>{{ orgLinks }}</dd></div>
            </dl>
            <div class="rs-org-tools">
              <label class="rs-search">Поиск организации<input type="search" :value="orgQuery" placeholder="Google, Tsinghua…" @input="setOrgFilter('q', $event.target.value)" /></label>
              <div class="rs-chips" role="group" aria-label="Тип организации">
                <button type="button" :aria-pressed="!orgType" @click="setOrgFilter('type', '', true)">Все <span>{{ organizations.length }}</span></button>
                <button v-for="(label, k) in orgTypesPlural" :key="k" type="button" :aria-pressed="orgType === k" @click="setOrgFilter('type', k, true)">
                  {{ label }} <span>{{ orgTypeCounts[k] }}</span>
                </button>
              </div>
            </div>
            <p class="rs-org-note">Аффилиации на момент публикации, не рейтинг. Подразделения не объединены: Google и Google YouTube — разные строки.</p>
            <p class="rs-resultline" aria-live="polite">
              <span><b>{{ orgsShown.length }}</b> из {{ organizations.length }}</span>
              <NuxtLink :to="{ path: base + '/catalog', query: { org: 'unknown' } }">Без подтверждённой организации: {{ stats.affiliationUnknown }} →</NuxtLink>
            </p>
            <TransitionGroup tag="ol" name="rs-row" class="rs-org-grid">
              <li v-for="o in orgsShown" :key="o.id" class="rs-org-row" :style="{ '--w': (orgCount(o.id) / maxOrg) * 100 + '%' }">
                <span class="rs-org-rank">{{ sortedOrgs.indexOf(o) + 1 }}</span>
                <h2><NuxtLink :to="{ path: base + '/catalog', query: { org: o.id } }">{{ o.name }}</NuxtLink></h2>
                <span class="rs-org-type">{{ orgTypes[o.type] }}</span>
                <span class="rs-org-bar" aria-hidden="true"><i></i></span>
                <span class="rs-org-n">{{ orgCount(o.id) }}<small>&nbsp;{{ orgCount(o.id) === 1 ? "работа" : orgCount(o.id) < 5 ? "работы" : "работ" }}</small></span>
                <details v-if="o.aliases.length > 1" class="rs-org-alias">
                  <summary>{{ o.aliases.length }} написания</summary>
                  <ul><li v-for="alias in o.aliases" :key="alias">{{ alias }}</li></ul>
                </details>
              </li>
            </TransitionGroup>
            <div v-if="!orgsShown.length" class="rs-empty">Ничего не найдено.</div>
            <details class="rs-org-method">
              <summary>Методика подсчёта</summary>
              <p>
                Организации на момент выхода статьи, подтверждённые в полном тексте. Не рейтинг влияния и не текущие места работы. Подтверждённая
                организация есть у {{ stats.affiliationKnown }} из {{ stats.records }} материалов. Обозначения Independent Researcher и Unaffiliated не считаются
                организациями.
              </p>
              <p>
                Материал учитывается один раз в каждой подтверждённой организации, поэтому сумма по организациям ({{ orgLinks }}) больше числа работ.
                Подразделения не объединены с материнскими компаниями: например, Amazon и Amazon Music показаны отдельно.
              </p>
              <p>Почему у {{ stats.affiliationUnknown }} материалов нет организации:</p>
              <ul>
                <li v-for="(label, code) in unknownReasonLabels" :key="code">{{ label }}: {{ stats.affiliationUnknownReasons[code] }}</li>
              </ul>
            </details>
          </section>

          <!-- ================= CATALOG ================= -->
          <section v-else-if="mode === 'catalog'" class="rs-wrap rs-section rs-catalog">
            <header class="rs-cat-head">
              <h1>Каталог</h1>
              <p aria-live="polite"><b>Найдено: {{ filtered.length }}</b> из {{ stats.records }} · теги в строках тоже фильтруют</p>
            </header>
            <div class="rs-cat-tools">
            <div class="rs-filters">
              <label class="rs-search"
                >Поиск<input type="search" :value="query" placeholder="SASRec, tokenization, причинность…" @input="setFilter('q', $event.target.value)" /></label
              ><label
                >Тема<select aria-label="Тема" :value="theme" @change="setFilter('theme', $event.target.value, true)">
                  <option value="" :selected="!theme">Все темы</option>
                  <option v-for="t in themes" :key="t.id" :value="t.id" :selected="theme === t.id">{{ t.title }}</option>
                </select></label
              ><label
                >Организация<select :value="org" @change="setFilter('org', $event.target.value, true)">
                  <option value="" :selected="!org">Все организации</option>
                  <option value="unknown" :selected="org === 'unknown'">Без подтверждённой организации</option>
                  <option v-for="o in sortedOrgs" :key="o.id" :value="o.id" :selected="org === o.id">{{ o.name }} ({{ orgCount(o.id) }})</option>
                </select></label
              ><label
                >Источник<select :value="status" @change="setFilter('status', $event.target.value, true)">
                  <option value="reviewed" :selected="status === 'reviewed'">Есть разбор</option>
                  <option value="awaiting_fulltext" :selected="status === 'awaiting_fulltext'">Ждём полный текст</option>
                  <option value="all" :selected="status === 'all'">Все материалы</option>
                </select></label
              ><NuxtLink
                  :to="{ path: base + '/catalog', query: catalogQuery({ zotero: inZotero ? '' : '1' }) }"
                  role="switch"
                  :aria-checked="inZotero ? 'true' : 'false'"
                  class="rs-ztoggle"
                  ><i aria-hidden="true"></i>Только в Zotero <span>{{ zotLinked }}</span></NuxtLink
                >
            </div>
            <figure class="rs-hist" aria-labelledby="rs-hist-cap">
              <figcaption id="rs-hist-cap">Темы в текущей выборке · полоса — работы с тегом из {{ filtered.length }} найденных, риска — весь корпус</figcaption>
              <div class="rs-hist-bars" role="group" aria-label="Быстрый фильтр по теме" :style="{ '--themes': themes.length }">
                <NuxtLink
                  v-for="(t, i) in themes"
                  :key="t.id"
                  :to="tagTo(t.id)"
                  :aria-current="theme === t.id ? 'true' : undefined"
                  class="rs-chip rs-hbar"
                  :title="t.title"
                  :data-theme="t.id"
                  :data-n="hist[t.id]"
                  :aria-label="t.title + ': ' + hist[t.id] + ' в выборке из ' + count(t.id)"
                  :style="{ '--c': 'var(--t' + i + ')', '--h': hist[t.id] / maxTag, '--all': count(t.id) / maxTag }"
                  ><span class="rs-hbar-track" aria-hidden="true"><i></i></span><span class="rs-hbar-label">{{ short(t.id) }}</span> <span class="rs-hbar-n">{{ hist[t.id] }}</span></NuxtLink
                >
              </div>
            </figure>
            </div>
            <div v-if="activeFilters.length" class="rs-resultline">
              <span v-for="f in activeFilters" :key="f.key" class="rs-active"
                >{{ f.label }}<button type="button" :aria-label="'Убрать фильтр ' + f.label" @click="setFilter(f.key, '', true)">×</button></span
              >
              <NuxtLink class="rs-reset" :to="base + '/catalog'">Сбросить фильтры</NuxtLink>
            </div>
            <div v-if="!filtered.length" class="rs-empty">Ничего не найдено. Попробуйте убрать тему или изменить запрос.</div>
            <div class="rs-table-head" aria-hidden="true"><span>№</span><span>Работа</span><span>Организации</span><span>Темы</span><span>Ссылки</span></div>
            <TransitionGroup tag="ol" name="rs-row" class="rs-list rs-list-dense" @click="listClick">
              <li v-for="p in filtered" :key="p.slug" class="rs-paper-card" :class="{ open: openRows.has(p.slug) }">
                <button
                  type="button"
                  class="rs-idx rs-expand"
                  :aria-expanded="openRows.has(p.slug) ? 'true' : 'false'"
                  :aria-controls="'rs-more-' + p.slug"
                  :aria-label="(openRows.has(p.slug) ? 'Свернуть ' : 'Раскрыть ') + '№ ' + pad(indexOf[p.slug])"
                >
                  {{ pad(indexOf[p.slug]) }}
                </button>
                <div class="rs-row-main">
                  <h2 lang="en"><a :href="base + '/papers/' + p.slug" v-bind="vtAttrs(p.slug)">{{ p.title }}</a></h2>
                  <p class="rs-row-sum">{{ p.summary || "Разбор не создан: выводы по одному названию или аннотации не публикуются." }}</p>
                  <div v-if="openRows.has(p.slug)" :id="'rs-more-' + p.slug" class="rs-row-more">
                    <template v-if="rowDetail[p.slug]">
                      <p><b>Что важно.</b> {{ rowDetail[p.slug].insight }}</p>
                      <p><b>Граница вывода.</b> {{ rowDetail[p.slug].limitation }}</p>
                    </template>
                    <p class="rs-row-more-links">
                      <NuxtLink :to="base + '/papers/' + p.slug">Читать разбор →</NuxtLink>
                      <a v-for="d in p.doi" :key="d" :href="'https://doi.org/' + d" target="_blank" rel="noopener noreferrer">doi:{{ d }}</a>
                    </p>
                  </div>
                </div>
                <p class="rs-row-orgs">
                  <template v-if="orgNames(p).length">{{ orgNames(p).slice(0, 2).join(", ") }}<small v-if="orgNames(p).length > 2"> +{{ orgNames(p).length - 2 }}</small></template>
                  <small v-else>—</small>
                </p>
                <div class="rs-tags">
                  <a
                    v-for="t in p.tags"
                    :key="t"
                    :href="linkHref(tagTo(t))"
                    :aria-current="theme === t ? 'true' : undefined"
                    :class="{ primary: t === p.primaryTheme }"
                    :title="byTheme[t].title"
                    :style="{ '--c': 'var(--t' + themeIdx[t] + ')' }"
                    >#{{ short(t) }}</a
                  >
                </div>
                <p class="rs-row-links">
                  <small>{{ p.status === "reviewed" ? kinds[p.kind] : "Ждём текст" }}</small>
                  <a v-if="zotBySlug[p.slug]" class="rs-z" :href="zotBySlug[p.slug].url" target="_blank" rel="noopener noreferrer">Zotero ↗</a>
                </p>
              </li>
            </TransitionGroup>
          </section>

          <!-- ================= TOPIC ================= -->
          <section v-else-if="mode === 'topics' && topic" class="rs-wrap rs-section rs-topic">
            <NuxtLink :to="base + '#themes'" class="rs-back">← Все темы</NuxtLink>
            <p class="rs-kicker"><span>Направление</span><span>{{ topic.id.toUpperCase() }}</span></p>
            <h1>{{ topic.title }}</h1>
            <p class="rs-lead">{{ topic.dek }}</p>
            <p class="rs-topic-stat">
              <b>{{ topicPapers.length }}</b> материалов с этим тегом · <b>{{ count(topic.id, true) }}</b> с этой темой в качестве главной ·
              <NuxtLink :to="{ path: base + '/catalog', query: { theme: topic.id } }">в каталоге →</NuxtLink>
            </p>
            <ol class="rs-syntheses">
              <li v-for="(ins, i) in topic.insights" :key="ins.title" class="rs-reveal">
                <span class="rs-number">{{ String(i + 1).padStart(2, "0") }}</span>
                <h2>{{ ins.title }}</h2>
                <p>{{ ins.text }}</p>
                <ul class="rs-evidence">
                  <li v-for="s in ins.slugs" :key="s"><NuxtLink :to="base + '/papers/' + s">{{ bySlug[s].title }}</NuxtLink></li>
                </ul>
              </li>
            </ol>
            <h2 class="rs-subhead">Работы по теме</h2>
            <ol class="rs-list">
              <li v-for="p in topicPapers" :key="p.slug" class="rs-paper-card">
                <span class="rs-idx">{{ pad(indexOf[p.slug]) }}</span>
                <div class="rs-row-main">
                  <h3><NuxtLink :to="base + '/papers/' + p.slug">{{ p.title }}</NuxtLink></h3>
                  <p class="rs-row-sum">{{ p.summary }}</p>
                  <div class="rs-tags">
                    <NuxtLink v-for="t in p.tags" :key="t" :to="{ path: base + '/catalog', query: { theme: t } }" :class="{ primary: t === p.primaryTheme }">#{{ byTheme[t].title }}</NuxtLink>
                  </div>
                </div>
              </li>
            </ol>
          </section>

          <!-- ================= PAPER ================= -->
          <section v-else-if="paper" class="rs-wrap rs-section rs-paper">
            <NuxtLink :to="backToCatalog" class="rs-back">← Каталог</NuxtLink>
            <div class="rs-paper-head">
              <div class="rs-paper-main">
                <p class="rs-kicker">
                  <span>№ {{ pad(indexOf[paper.slug]) }}</span><span>{{ kinds[paper.kind] || "Материал конференции" }}</span
                  ><span>{{ paper.status === "reviewed" ? "Разбор" : "Ожидание источника" }}</span>
                </p>
                <h1 class="rs-paper-title" lang="en" :style="{ viewTransitionName: 'rs-title' }">{{ paper.title }}</h1>
                <p class="rs-lead">{{ paper.summary || "Полный текст пока недоступен. Метод и результаты не пересказываются по аннотации." }}</p>
              </div>
              <aside class="rs-paper-meta" aria-label="О работе">
                <div class="rs-rail-block">
                  <h2>Темы</h2>
                  <div class="rs-tags" aria-label="Темы">
                    <NuxtLink
                      v-for="t in paper.tags"
                      :key="t"
                      :to="{ path: base + '/catalog', query: { theme: t } }"
                      :class="{ primary: t === paper.primaryTheme }"
                      :style="{ '--c': 'var(--t' + themeIdx[t] + ')' }"
                      >#{{ byTheme[t].title }}</NuxtLink
                    >
                  </div>
                </div>
                <div v-if="tagsOf(paper.slug).length" class="rs-rail-block rs-review-tags">
                  <h2>Теги</h2>
                  <div class="rs-tags" aria-label="Теги разбора">
                    <NuxtLink v-for="t in tagsOf(paper.slug)" :key="t" :to="reviewTagTo(t)" :title="(byTag[t]?.count || 0) + ' в каталоге'">{{ tagLabel(t) }}</NuxtLink>
                  </div>
                </div>
                <div class="rs-rail-block rs-sources">
                  <h2>Источники</h2>
                  <a v-for="d in paper.doi" :key="d" class="rs-doi" :href="'https://doi.org/' + d" target="_blank" rel="noopener noreferrer">DOI {{ d }}</a>
                  <span v-if="!paper.doi.length" class="rs-z-missing">DOI нет</span>
                  <a v-if="paper.source" :href="paper.source" target="_blank" rel="noopener noreferrer">Первоисточник ↗</a>
                  <a v-if="zotBySlug[paper.slug]" class="rs-z" :href="zotBySlug[paper.slug].url" target="_blank" rel="noopener noreferrer">Открыть в Zotero ↗</a>
                  <span v-else class="rs-z-missing">В Zotero пока нет</span>
                </div>
                <nav class="rs-rail-block rs-theme-nav" :aria-label="'Соседние работы по теме ' + byTheme[paper.primaryTheme].title">
                  <h2>{{ short(paper.primaryTheme) }} · {{ themePos + 1 }} из {{ themeRun.length }}</h2>
                  <NuxtLink v-if="prevInTheme" class="rs-prev" rel="prev" :to="base + '/papers/' + prevInTheme.slug"><small>← Предыдущая</small><span lang="en">{{ prevInTheme.title }}</span></NuxtLink>
                  <NuxtLink v-if="nextInTheme" class="rs-next" rel="next" :to="base + '/papers/' + nextInTheme.slug"><small>Следующая →</small><span lang="en">{{ nextInTheme.title }}</span></NuxtLink>
                </nav>
                <section class="rs-rail-block rs-affiliations" aria-label="Аффилиации авторов">
                  <h2>Организации авторов</h2>
                  <ul v-if="paper.affiliations.length">
                    <li v-for="a in paper.affiliations" :key="a.organization">
                      <NuxtLink :to="{ path: base + '/catalog', query: { org: a.organization } }">{{ byOrg[a.organization].name }}</NuxtLink>
                      <small>{{ orgTypes[byOrg[a.organization].type] }}</small>
                      <details>
                        <summary>Подтверждение в источнике</summary>
                        <p>«{{ a.quote }}»</p>
                        <a :href="a.source" target="_blank" rel="noopener noreferrer">{{ a.locator }} ↗</a>
                      </details>
                    </li>
                  </ul>
                  <p v-else>Организация не указана. Причина: {{ unknownReasonLabels[paper.affiliationUnknownReason] }}.</p>
                  <details v-if="paper.nonInstitutionalAffiliations?.length">
                    <summary>Авторы без организационной аффилиации</summary>
                    <p v-for="a in paper.nonInstitutionalAffiliations" :key="a.quote">
                      «{{ a.quote }}» — <a :href="a.source" target="_blank" rel="noopener noreferrer">{{ a.locator }} ↗</a>
                    </p>
                  </details>
                  <p class="rs-caption">
                    На момент публикации; список может быть неполным.
                    <NuxtLink :to="base + '/organizations'">Все организации →</NuxtLink>
                  </p>
                </section>
              </aside>
            </div>
            <div v-if="article" class="rs-reading">
              <aside class="rs-toc">
                <nav aria-label="Оглавление">
                  <div class="rs-read" role="progressbar" aria-label="Прочитано" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="readPct" :style="{ '--p': readPct / 100 }">
                    <b>В этом разборе</b><span>{{ readPct }}%</span><i aria-hidden="true"></i>
                  </div>
                  <a v-for="s in article.sections" :key="s.id" :href="'#' + s.id" :aria-current="activeSection === s.id ? 'true' : undefined">{{ s.title }}</a>
                </nav>
                <p class="rs-caption">Публичная редакция исходного разбора. Внутренние примечания исключены. Числа относятся только к протоколу статьи.</p>
              </aside>
              <div class="rs-prose">
                <div class="rs-takeaway">
                  <div><b>Что важно</b><p>{{ paper.insight }}</p></div>
                  <div><b>Граница вывода</b><p>{{ paper.limitation }}</p></div>
                </div>
                <section v-for="s in article.sections" :id="s.id" :key="s.id">
                  <h2>{{ s.title }}</h2>
                  <div v-html="render(s.markdown)"></div>
                </section>
                <section v-if="refsData?.items?.length" id="refs">
                  <h2>Литература</h2>
                  <p class="rs-caption">
                    {{ refsData.items.length }} ссылок из Crossref для этой публикации. Где есть DOI, ссылка ведёт на него; нумерация — как в источнике.
                  </p>
                  <ol class="rs-refs">
                    <li v-for="(r, ri) in refsData.items" :key="ri">
                      <template v-if="r.authors?.length">{{ r.authors.join(", ") }}. </template>
                      <a v-if="r.doi" :href="'https://doi.org/' + r.doi" target="_blank" rel="noopener noreferrer">{{ r.title || r.doi }}</a>
                      <span v-else>{{ r.title }}</span>
                      <template v-if="r.venue"> — {{ r.venue }}</template>
                      <template v-if="r.year">, {{ r.year }}</template>.
                    </li>
                  </ol>
                </section>
                <section v-if="backlinks.length">
                  <h2>В тематических выводах</h2>
                  <ul>
                    <li v-for="t in backlinks" :key="t.id"><NuxtLink :to="base + '/topics/' + t.id">{{ t.title }}</NuxtLink></li>
                  </ul>
                </section>
                <section>
                  <h2>Рядом по тематике</h2>
                  <p class="rs-caption">Связи по общим тегам, не рейтинг качества и не список цитирований.</p>
                  <ul>
                    <li v-for="p in related" :key="p.slug"><NuxtLink :to="base + '/papers/' + p.slug">{{ p.title }}</NuxtLink></li>
                  </ul>
                </section>
              </div>
            </div>
          </section>
        </div>
      </Transition>
    </main>
    <!-- Обсуждение страницы (vpvd). Разметка — по контракту встраивания: data-url — адрес именно
         этой страницы (ветку заводит кадр по нему), data-theme нарочно не задаём: загрузчик берёт
         тему с <html data-theme>, поэтому переключатель выше меняет и кадр, без перезагрузки.
         data-lang=ru — язык раздела (страница объявлена как lang="ru"). Токены --vpvd-* — «наряд
         хозяина»: кадр надевает наш шрифт, кегль, акцент и радиус (список у vpvd закрытый и
         проверяемый). Внутри контейнера — запасная ссылка: она остаётся, если загрузчик не поднялся
         (выключенный JS, наша недоступность) и ведёт на ту же ветку. Сам загрузчик ставит
         компонент при монтировании (см. ensureVpvdLoader выше), а не разметка сниппета. -->
    <section class="rs-embed rs-wrap" id="discussion">
      <h2>Обсуждение</h2>
      <p class="rs-caption">Ветка живёт на vpvd и привязана к адресу этой страницы: читать можно без входа, писать — после входа.</p>
      <div data-vpvd-thread :data-url="embedUrl" data-lang="ru" data-theme="auto" class="rs-embed-box">
        <a :href="'https://vpvd.io/embed/ru?url=' + encodeURIComponent(embedUrl)" target="_blank" rel="noopener noreferrer">Обсуждение на vpvd</a>
      </div>
    </section>
    <footer class="rs-footer rs-wrap">
      <NuxtLink :to="base">RecSys<b>2026</b></NuxtLink>
      <p>Разборы работ RecSys 2026 · обновлено {{ data.version }}.</p>
    </footer>
  </div>
</template>
