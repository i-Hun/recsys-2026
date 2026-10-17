<script setup>
// Страница-обёртка путеводителя: спрашивает у слоя проекцию данных для своего маршрута,
// держит её в payload и отдаёт представлению (components/rs/GuideView.vue). Сам датасет
// (~600 КБ) в клиентский бандл не попадает — раньше он уезжал туда статическим импортом.
definePageMeta({ layout: false });
const base = "/stories/recsys-2026";
const route = useRoute();
const parts = computed(() => {
  const v = route.params.path;
  return Array.isArray(v) ? v : (v || "").split("/").filter(Boolean);
});
const mode = computed(() => parts.value[0] || "home");
const id = computed(() => parts.value[1]);
const viewKey = computed(() => mode.value + "/" + (id.value || ""));
const KNOWN = ["home", "catalog", "organizations", "topics", "papers", "workshops"];
const malformed =
  !KNOWN.includes(mode.value) ||
  parts.value.length > 2 ||
  (["catalog", "organizations"].includes(mode.value) && parts.value.length !== 1) ||
  (["topics", "papers"].includes(mode.value) && parts.value.length !== 2);
if (malformed) throw createError({ statusCode: 404, statusMessage: "Материал не найден" });

const { data: bundle } = await useAsyncData(
  () => "rs-guide-" + viewKey.value,
  () => $fetch("/api/guide", { query: { mode: mode.value, id: id.value }, ignoreResponseError: true }),
  { watch: [viewKey] },
);
// Эндпоинт отвечает 404 на неизвестный разбор/тему; тело с error повторяем как страницу 404.
if (!bundle.value || bundle.value.error) throw createError({ statusCode: 404, statusMessage: "Материал не найден" });

const pageTitle = computed(() => bundle.value?.pageTitle || "Путеводитель по RecSys 2026");
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
</script>

<template>
  <!-- :key — представление пересоздаётся на каждый разбор/тему/раздел, а внутри раздела
       (например, при смене фильтров каталога) остаётся живым: состояние фильтров и раскрытых
       строк не зависит от загрузки данных. -->
  <RsGuideView :key="viewKey" :bundle="bundle" />
</template>