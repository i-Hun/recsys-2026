// Проекция данных путеводителя для одного маршрута: ?mode=home|catalog|organizations|topics|papers|workshops&id=<slug|topicId>.
// Страницы слоя ходят сюда вместо статического импорта data/*.json, поэтому датасет
// (~600 КБ) остаётся на сервере, а клиенту достаётся только то, что маршрут рендерит.
// Ответ кладётся в payload страницы (useAsyncData), так что SSR и гидрация видят один объект.
export default defineEventHandler((event) => {
  const { mode, id } = getQuery(event);
  const name = String(mode || "home");
  const bundle = guideBundle(name, id ? String(id) : undefined);
  if (!bundle) {
    setResponseStatus(event, 404);
    return { error: "not found" };
  }
  // Данные меняются вместе с деплоем: браузеру час, CDN — сутки.
  setHeader(event, "cache-control", "public, max-age=3600, s-maxage=86400");
  return bundle;
});