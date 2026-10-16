# Путеводитель по RecSys 2026

Исходники раздела [nagornyy.me/stories/recsys-2026](https://nagornyy.me/stories/recsys-2026): 269 разборов
работ ACM RecSys 2026, девять тематических направлений, каталог с фильтрами, организации,
воркшопы и туториалы.

Нашли ошибку в разборе, неверное число или хотите что-то предложить — [откройте issue](../../issues/new/choose)
или пришлите pull request. Сайт пересобирается сам после каждого merge в `main`, обычно за несколько минут.

## Что где лежит

| Путь | Что это |
|---|---|
| `public/stories/recsys-2026/articles/<slug>.json` | текст разбора: `sections[].markdown` |
| `data/recsys-2026.json` | карточки работ (заголовок, кратко, вывод, ограничение, тема, теги, организации), темы, статистика |
| `scripts/recsys26-themes.json` | редакторские тексты тем: заголовок, подзаголовок, три вывода |
| `data/recsys-2026-tags.json` | индекс тегов |
| `data/recsys-2026-workshops*.json` | разрез воркшопов, туториалов и кейноутов |
| `data/recsys-2026-zotero.json` | ссылки на записи публичной библиотеки Zotero |
| `pages/stories/recsys-2026/` | страницы (Vue, Nuxt 3) |
| `assets/styles/` | стили раздела и дизайн-токены |
| `utils/recsys-markdown.js` | рендер markdown (сырой HTML выключен) |
| `scripts/test-*.mjs` | проверки, которые CI запускает на каждый pull request |

Адрес разбора на сайте — `/stories/recsys-2026/papers/<slug>`, файл — `public/stories/recsys-2026/articles/<slug>.json`.

## Запустить локально

Нужен Node.js 22.

```sh
npm ci
npm test        # проверки данных и рендера
npm run dev     # http://localhost:3000/stories/recsys-2026
```

Репозиторий — [слой Nuxt](https://nuxt.com/docs/getting-started/layers): сайт подключает его
git-сабмодулем и `extends`, а сам по себе он запускается как отдельное приложение только с этим разделом.

## Лицензия

Тексты и данные — [CC BY 4.0](LICENSE-CONTENT), код — MIT, шрифт Golos Text — SIL OFL 1.1.
Подробности в [LICENSE](LICENSE).
