// Theme-map contract of the public export: the ninth theme «Реклама и рекомендации».
// Runs on the exported data only; no network, no browser. Imported by test-recsys.mjs.
import assert from "node:assert/strict";
import fs from "node:fs";

export const THEME_IDS = ["gen", "seq", "llm", "graph", "eval", "human", "prod", "domain", "ads"];
// approved labels (directive: theme labels are short, self-explanatory, never truncated titles)
export const APPROVED = {
  gen: "Генеративные рекомендации",
  seq: "Последовательные рекомендации",
  llm: "Языковые модели и агенты",
  graph: "Коллаборативные модели",
  eval: "Оценка и причинность",
  human: "Объяснения и контроль",
  prod: "Промышленные системы",
  domain: "Кросс-домен и мультимодальность",
  ads: "Реклама и рекомендации",
};
export const ADS_PRIMARY = 13;
export const ADS_TAGGED = 18;

const data = JSON.parse(
  fs.readFileSync(new URL("../data/recsys-2026.json", import.meta.url)),
);
const papers = data.papers;
const themes = data.themes;
const reviewed = papers.filter((p) => p.status === "reviewed");

assert.equal(papers.length, 269, "corpus size");
assert.equal(reviewed.length, data.stats.reviewed, "reviewed == stats.reviewed");

// exactly nine themes, in the published order, ids and labels unique
assert.deepEqual(
  themes.map((t) => t.id),
  THEME_IDS,
  "theme ids and order",
);
assert.equal(new Set(themes.map((t) => t.id)).size, themes.length);
for (const t of themes) {
  assert.equal(t.short, APPROVED[t.id], "approved short label: " + t.id);
  assert.ok(t.title && t.dek && t.dek.length > 40, "title/dek: " + t.id);
  assert.ok(Array.isArray(t.insights) && t.insights.length >= 2, "insights: " + t.id);
  for (const ins of t.insights) {
    assert.ok(ins.title && ins.text, "insight fields: " + t.id);
    assert.ok(ins.slugs.length, "insight without works: " + t.id);
  }
}
// the new label must fit the field it renders in, and stay a sentence, not a sentence fragment
assert.ok(APPROVED.ads.length <= 30, "ads short label length: " + APPROVED.ads.length);

// every work carries exactly one primary theme, which is also one of its tags
const ids = new Set(themes.map((t) => t.id));
let primarySum = 0;
for (const p of papers) {
  assert.ok(ids.has(p.primaryTheme), "unknown primary theme: " + p.slug);
  assert.ok(p.tags.includes(p.primaryTheme), "primary not in tags: " + p.slug);
  assert.equal(new Set(p.tags).size, p.tags.length, "duplicate tag: " + p.slug);
  for (const tag of p.tags) assert.ok(ids.has(tag), "unknown tag " + tag + ": " + p.slug);
  assert.ok(p.tags.length <= 4, "tag count: " + p.slug);
  primarySum++;
}
assert.equal(primarySum, 269, "one primary theme per work");
const byPrimary = Object.fromEntries(
  THEME_IDS.map((id) => [id, reviewed.filter((p) => p.primaryTheme === id).length]),
);
assert.equal(
  Object.values(byPrimary).reduce((n, v) => n + v, 0),
  269,
  "sum of primary counts",
);
assert.equal(byPrimary.ads, ADS_PRIMARY, "works with ads as the primary theme");

// the ninth theme and its digest stay wired to real reviews
const ads = themes.find((t) => t.id === "ads");
assert.equal(ads.title, "Реклама и рекомендации");
assert.ok(ads.dek.includes("одной выдаче"), "ads dek wording");
const tagged = papers.filter((p) => p.tags.includes("ads"));
assert.equal(tagged.length, ADS_TAGGED, "works tagged ads");
const slugs = new Set(reviewed.map((p) => p.slug));
const cited = new Set(ads.insights.flatMap((i) => i.slugs));
for (const slug of cited) {
  assert.ok(slugs.has(slug), "ads insight cites a non-reviewed work: " + slug);
  assert.ok(
    papers.find((p) => p.slug === slug).tags.includes("ads"),
    "ads insight cites an untagged work: " + slug,
  );
}
assert.ok(cited.size >= 8, "ads insights must span the theme: " + cited.size);

// corpus invariants this edit must not touch
assert.equal(new Set(papers.map((p) => p.slug)).size, papers.length, "slug uniqueness");
assert.equal(data.stats.affiliationKnown + data.stats.affiliationUnknown, papers.length);
assert.equal(data.organizations.length, 264, "organizations after the Sber AI Lab merge");
assert.equal(
  sum(papers.map((p) => p.affiliations.length)),
  462,
  "affiliation links",
);

function sum(xs) {
  return xs.reduce((a, b) => a + b, 0);
}

console.log(
  JSON.stringify({
    status: "PASS",
    themes: themes.length,
    primary: byPrimary,
    ads: { primary: byPrimary.ads, tagged: tagged.length, insights: ads.insights.length, cited: cited.size },
  }),
);