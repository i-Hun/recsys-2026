// Nuxt layer: the RecSys 2026 guide (https://nagornyy.me/stories/recsys-2026).
// The site (a private repo) mounts this repository as a git submodule and `extends` it;
// on its own the layer also runs as a standalone app (`npm run dev`) for contributors.
export default defineNuxtConfig({
  compatibilityDate: '2026-10-17',
  // The guide's two page components import ~52 KB of hand-written CSS from <script setup>
  // (design-tokens.css + recsys-2026.css). Nuxt inlines that into the HTML of every guide
  // route — 49.9 KB of <style> per page, uncacheable — and the page chunk then fetches the
  // very same rules again as /_nuxt/recsys-2026.<hash>.css. Measured on the built site:
  // 52 749 B of inline <style> per document plus a 52 553 B duplicate stylesheet request.
  // With inlineStyles: false the CSS is delivered once, as a cacheable file shared by the
  // guide's three routes. The site's own pages lose 577 B of inline .vue styles and gain
  // three small stylesheet requests — those are cached after the first page.
  features: { inlineStyles: false },
  routeRules: {
    // Dynamic SSR only: filters live in the query (?theme=, ?org=, ?tag=, ?zotero=, ?type=),
    // and a prerendered index.html would ignore them and serve the unfiltered list.
    '/stories/recsys-2026': { prerender: false },
    '/stories/recsys-2026/**': { prerender: false },
  },
})
