// Nuxt layer: the RecSys 2026 guide (https://nagornyy.me/stories/recsys-2026).
// The site (a private repo) mounts this repository as a git submodule and `extends` it;
// on its own the layer also runs as a standalone app (`npm run dev`) for contributors.
export default defineNuxtConfig({
  compatibilityDate: '2025-01-03',
  routeRules: {
    // Dynamic SSR only: filters live in the query (?theme=, ?org=, ?tag=, ?zotero=, ?type=),
    // and a prerendered index.html would ignore them and serve the unfiltered list.
    '/stories/recsys-2026': { prerender: false },
    '/stories/recsys-2026/**': { prerender: false },
  },
})
