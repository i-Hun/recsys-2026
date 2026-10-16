<script setup>
// Воркшопы, туториалы и кейноуты — отдельный разрез путеводителя (RecSys Challenge по решению владельца не выводится).
// Данные: data/recsys-2026-workshops-site.json — экспорт
// из проверенного разреза data/recsys-2026-workshops.json. Ничего не досчитывается на странице.
import cut from "../../../data/recsys-2026-workshops-site.json";
import main from "../../../data/recsys-2026.json";
import "../../../assets/styles/design-tokens.css";
import "../../../assets/styles/recsys-2026.css";
definePageMeta({ layout: false });
const base = "/stories/recsys-2026";
const { positions, counts, crossref, organizations: orgName, tutorialsInMainCorpus } = cut;
const mainStats = cut.mainCorpus;

const TYPES = [
  { id: "workshop", title: "Воркшопы", one: "воркшоп" },
  { id: "tutorial", title: "Туториалы", one: "туториал" },
  { id: "keynote", title: "Кейноуты", one: "кейноут" },
];
const groups = TYPES.map((t) => ({ ...t, items: positions.filter((p) => p.type === t.id) }));

const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const fmtDate = (iso) => {
  const [, m, d] = iso.split("-").map(Number);
  return d + "\u00a0" + MONTHS[m - 1];
};
const SLOTS = { morning: "утро", afternoon: "после обеда", "full-day": "весь день", "Opening Keynote": "открывающий кейноут", "Closing Keynote": "закрывающий кейноут" };
const STATUS = {
  confirmed: "",
  source_unavailable: "PDF работы не опубликован — организации не подтверждены",
  no_institution_declared: "В блоке авторов нет организации",
  anonymized_in_pdf: "PDF анонимизирован — авторы и организации скрыты",
};
const plural = (n, one, few, many) => (n % 10 === 1 && n % 100 !== 11 ? one : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? few : many);
const mainSlugs = new Set(main.papers.map((p) => p.slug));
const uniqOrgs = (affs) => [...new Map(affs.filter((a) => a.organization).map((a) => [a.organization, a])).values()];

const title = "Воркшопы, туториалы и кейноуты RecSys 2026";
useHead({
  title,
  htmlAttrs: { lang: "ru" },
  meta: [
    { name: "description", content: "Отдельный разрез путеводителя по RecSys 2026: 15 воркшопов, 6 туториалов и 2 кейноута с организаторами, датами и списками работ." },
    { property: "og:title", content: title },
    { property: "og:description", content: "Воркшопы, туториалы и кейноуты RecSys 2026 — организаторы, даты, работы и подтверждённые аффилиации." },
    { property: "og:image", content: "https://nagornyy.me/stories/recsys-2026/og.jpg" },
    { property: "og:image:width", content: "1200" },
    { property: "og:image:height", content: "630" },
    { property: "og:type", content: "article" },
    { name: "twitter:card", content: "summary_large_image" },
    { name: "twitter:image", content: "https://nagornyy.me/stories/recsys-2026/og.jpg" },
  ],
  script: [
    {
      key: "rs-theme",
      tagPosition: "head",
      innerHTML:
        "(function(){var r=document.documentElement,t;try{t=new URLSearchParams(location.search).get('scheme')||localStorage.getItem('rs-theme')}catch(e){}r.dataset.theme=t==='light'||t==='dark'?t:'auto'})()",
    },
  ],
});
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
onMounted(() => {
  document.documentElement.classList.add("rs-js");
  const t0 = document.documentElement.dataset.theme;
  themePref.value = THEMES.includes(t0) ? t0 : "auto";
  // nav scrolls horizontally on phones: bring the current item into view
  const navOn = document.querySelector(".rs-mast nav a.on");
  if (navOn) { const n = navOn.parentElement; n.scrollLeft = Math.max(0, navOn.offsetLeft - n.offsetLeft - 16); }
});
</script>

<template>
  <div class="rs">
    <a class="rs-skip" href="#main">К содержанию</a>
    <header class="rs-mast">
      <NuxtLink to="/" class="rs-brand">Олег Нагорный</NuxtLink>
      <NuxtLink :to="base" class="rs-issue">RecSys<b>2026</b></NuxtLink>
      <nav aria-label="Раздел конференции">
        <NuxtLink :to="base">Обзор</NuxtLink>
        <NuxtLink :to="base + '#themes'">Темы</NuxtLink>
        <NuxtLink :to="base + '/catalog'">Каталог <span>{{ main.stats.reviewed }}</span></NuxtLink>
        <NuxtLink :to="base + '/organizations'">Организации</NuxtLink>
        <NuxtLink :to="base + '/workshops'" class="on" aria-current="page">Воркшопы <span>{{ counts.positions }}</span></NuxtLink>
      </nav>
      <button type="button" class="rs-theme" :data-pref="themePref" :aria-label="'Тема: ' + THEME_LABEL[themePref] + '. Переключить'" :title="'Тема: ' + THEME_LABEL[themePref]" @click="cycleTheme">
        <svg v-if="themePref === 'light'" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
        <svg v-else-if="themePref === 'dark'" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" /></svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 3.5v17a8.5 8.5 0 0 0 0-17z" fill="currentColor" /></svg>
      </button>
    </header>
    <main id="main">
      <section class="rs-wrap rs-section rs-orgs rs-ws">
        <p class="rs-kicker"><span>RecSys 2026</span><span>Отдельный разрез</span><span>обновлено {{ cut.version }}</span></p>
        <h1>Воркшопы, туториалы и&nbsp;кейноуты</h1>
        <p class="rs-lead">
          Позиции конференции, которых нет в основном корпусе путеводителя: {{ counts.byType.workshop }} воркшопов,
          {{ counts.byType.tutorial }} туториалов и {{ counts.byType.keynote }} кейноута. У каждой позиции — организаторы, дата, официальная ссылка, а где
          воркшоп опубликовал список принятых работ — сами работы и организации их авторов.
        </p>
        <dl class="rs-org-figures">
          <div><dt>позиций в разрезе</dt><dd>{{ counts.positions }}</dd></div>
          <div><dt>работ воркшопов</dt><dd>{{ counts.papers }}</dd></div>
          <div><dt>с подтверждённой организацией</dt><dd>{{ counts.affiliationStatus.confirmed }}<small>/{{ counts.papers }}</small></dd></div>
        </dl>

        <aside class="rs-ws-boundary" aria-labelledby="rs-ws-boundary-h">
          <h2 id="rs-ws-boundary-h">Граница разреза</h2>
          <p>
            Это отдельный контур путеводителя. Работы воркшопов не входят в
            <NuxtLink :to="base + '/catalog'">каталог</NuxtLink>, в графики и в
            <NuxtLink :to="base + '/organizations'">список организаций</NuxtLink> и не меняют их чисел: в основном корпусе по-прежнему
            {{ mainStats.papers }} работ, {{ mainStats.papersWithOrganization }} из них с подтверждённой организацией, {{ mainStats.paperOrganizationLinks }} связей
            работа × организация.
          </p>
          <p>
            Сверка со сборником ACM «{{ crossref.containerTitle }}»: в нём {{ crossref.totalResults }} DOI —
            {{ crossref.inMainCorpus }} уже в основном корпусе, остальные {{ crossref.inThisCut }} — вводные статьи воркшопов, туториалов и RecSys
            Challenge. Здесь показаны {{ counts.inCrossrefShown }} из них: {{ counts.byType.workshop }} воркшопов и {{ counts.byType.tutorial }} туториалов;
            RecSys Challenge в раздел не входит. Кейноутов в сборнике нет, они взяты из программы конференции. Ещё
            {{ tutorialsInMainCorpus.length }} туториала уже есть в основном каталоге и здесь не повторяются:
            <template v-for="(t, i) in tutorialsInMainCorpus" :key="t.slug"
              ><NuxtLink :to="base + '/papers/' + t.slug" lang="en">{{ t.title }}</NuxtLink>{{ i < tutorialsInMainCorpus.length - 1 ? ", " : "." }}</template
            >
          </p>
          <p>
            Организации — на момент публикации, по блоку авторов в PDF или по метаданным сборника, не рейтинг. Подразделения не объединены с материнскими
            компаниями: Amazon и Amazon Music — разные строки. Где воркшоп не выложил PDF, организация не подтверждена и так и подписана.
          </p>
        </aside>

        <nav class="rs-chips rs-ws-jump" aria-label="Типы позиций">
          <a v-for="g in groups" :key="g.id" :href="'#' + g.id">{{ g.title }} <span>{{ g.items.length }}</span></a>
        </nav>

        <section v-for="g in groups" :id="g.id" :key="g.id" class="rs-ws-group" :aria-labelledby="'rs-ws-' + g.id">
          <h2 :id="'rs-ws-' + g.id">{{ g.title }} <span>{{ g.items.length }}</span></h2>
          <ol class="rs-ws-list">
            <li v-for="p in g.items" :id="p.id" :key="p.id" class="rs-ws-item">
              <p class="rs-ws-when">
                <b>{{ fmtDate(p.venue.date) }}</b> · {{ SLOTS[p.venue.slot] || p.venue.slot }}<template v-if="p.venue.room"> · {{ p.venue.room }}</template>
              </p>
              <h3 lang="en"><span v-if="p.acronym" class="rs-ws-acr">{{ p.acronym }}</span>{{ p.name }}</h3>
              <p class="rs-ws-place" lang="en">{{ p.venue.place }}</p>
              <p v-if="p.venue.slotConflict" class="rs-caption">{{ p.venue.slotConflict }}</p>
              <div class="rs-ws-org">
                <b>{{ g.id === "keynote" ? "Докладчик" : "Организаторы" }}</b>
                <ul>
                  <li v-for="o in p.organizers" :key="o.name">
                    <span lang="en">{{ o.name }}</span
                    ><template v-for="a in o.affiliations" :key="a.quote"
                      ><small v-if="a.organization" :title="a.quote">{{ orgName[a.organization] }}</small
                      ><small v-else :title="a.quote">{{ a.quote }}</small></template
                    >
                  </li>
                </ul>
              </div>
              <p class="rs-ws-links">
                <a v-for="l in p.links" :key="l.url" :href="l.url" target="_blank" rel="noopener noreferrer">{{ l.label }} ↗</a>
              </p>
              <details v-if="p.papers.length" class="rs-ws-papers">
                <summary>
                  {{ p.papers.length }} {{ plural(p.papers.length, "работа", "работы", "работ") }} · с организацией
                  {{ p.papers.filter((q) => q.status === "confirmed").length }}
                </summary>
                <p v-if="p.acceptedList.note" class="rs-caption">
                  Список: {{ p.acceptedList.note }}.
                  <a v-if="p.acceptedList.source" :href="p.acceptedList.source" target="_blank" rel="noopener noreferrer">Источник ↗</a>
                </p>
                <ol>
                  <li v-for="q in p.papers" :key="q.id">
                    <a v-if="q.url" :href="q.url" target="_blank" rel="noopener noreferrer" class="rs-ws-title" lang="en">{{ q.title }}</a>
                    <span v-else class="rs-ws-title" lang="en">{{ q.title }}</span>
                    <span class="rs-ws-authors" lang="en">{{ q.authors }}<template v-if="q.session"> · {{ q.session }}</template></span>
                    <span v-if="q.authorsNote" class="rs-caption">{{ q.authorsNote }}</span>
                    <span v-if="uniqOrgs(q.affiliations).length" class="rs-ws-affs">
                      <details v-for="a in uniqOrgs(q.affiliations)" :key="a.organization">
                        <summary>{{ orgName[a.organization] }}</summary>
                        <span>«{{ a.quote }}» — <a :href="a.source" target="_blank" rel="noopener noreferrer">{{ a.locator }} ↗</a></span>
                      </details>
                    </span>
                    <span v-if="q.nonInstitutional.length" class="rs-caption">Без организации: {{ [...new Set(q.nonInstitutional.map((a) => a.quote))].join("; ") }}</span>
                    <span v-if="STATUS[q.status]" class="rs-caption">{{ STATUS[q.status] }}<template v-if="q.note && q.status === 'confirmed'">. {{ q.note }}</template></span>
                    <span v-else-if="q.note" class="rs-caption">{{ q.note }}</span>
                    <span v-if="q.conflict" class="rs-caption">{{ q.conflict.note }}</span>
                    <NuxtLink v-if="q.mainCorpusSlug && mainSlugs.has(q.mainCorpusSlug)" :to="base + '/papers/' + q.mainCorpusSlug" class="rs-ws-main">Есть разбор в основном каталоге →</NuxtLink>
                  </li>
                </ol>
              </details>
              <p v-else class="rs-caption">{{ p.acceptedList.note }}</p>
            </li>
          </ol>
        </section>

        <details class="rs-org-method">
          <summary>Как собран разрез</summary>
          <p>
            Каждое название, имя, дата и организация взяты из источника и подтверждены цитатой: метаданные сборника ACM (Crossref), сайт воркшопа, его
            список принятых работ или первая страница PDF. Цитата и место в источнике открываются по клику на организацию работы, а у организаторов — во
            всплывающей подсказке.
          </p>
          <p>
            Работ в разрезе {{ counts.papers }} — все из опубликованных списков принятых работ воркшопов. Подтверждённая организация есть у {{ counts.affiliationStatus.confirmed }}; у {{ counts.affiliationStatus.source_unavailable }} воркшоп
            не опубликовал PDF, у {{ counts.affiliationStatus.no_institution_declared }} в блоке авторов нет организации,
            {{ counts.affiliationStatus.anonymized_in_pdf }} PDF анонимизирован. Работы, которые есть и здесь, и в основном каталоге, помечены ссылкой на разбор
            и учтены в статистике основного корпуса один раз — как работы каталога.
          </p>
        </details>
      </section>
    </main>
    <footer class="rs-footer rs-wrap">
      <NuxtLink :to="base">RecSys<b>2026</b></NuxtLink>
      <p>Воркшопы, туториалы и кейноуты RecSys 2026 · обновлено {{ cut.version }}.</p>
      <NuxtLink :to="base + '#method'">Методика основного корпуса ↑</NuxtLink>
    </footer>
  </div>
</template>
