// Ссылки путеводителя не нуждаются в router-link-active/router-link-exact-active:
// ни один стиль сайта и слоя их не использует (проверено grep'ом по css/scss/vue),
// а NuxtLink вешает обе на каждую ссылку, чей путь совпадает с текущим. В каталоге это
// 626 фрагментов класса — около 27 КБ разметки на страницу. Пустая строка отключает класс:
// NuxtLink берёт значение через «??», а не через «||» (nuxt/dist/app/components/nuxt-link.js).
export default {
  linkActiveClass: "",
  linkExactActiveClass: "",
};