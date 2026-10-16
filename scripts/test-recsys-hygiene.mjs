// Public hygiene check of the exported texts: no tracker ids, local paths,
// wiki-links or unresolved internal slugs. Runs in CI on every pull request.
// (The site additionally runs its own, private editorial filter before deploy.)
import assert from "node:assert/strict";
import fs from "node:fs";

const read = (p) => JSON.parse(fs.readFileSync(new URL(p, import.meta.url)));
const data = read("../data/recsys-2026.json");
// Hyphenated terms of 4+ parts that may appear in public text (method names, model ids,
// protocol terms). Anything else of that shape is treated as an unresolved internal slug:
// add a new term here in the same pull request that introduces it.
const allowed = new Set(read("./allowed-terms.json").terms.map((t) => t.toLowerCase()));

export function assertHygiene(text) {
  const prose = text.replace(/https?:\/\/[^\s)<>]+|\/stories\/recsys-2026\/[^\s)]+/g, "");
  assert(!/\bt_[0-9a-f]{8}\b|\[\[|\]\]|\/home\/|~\/\.|\.hermes\b|\bkanban\b|comparisons\//i.test(prose), "internal id, path or wiki-link");
  const bad = [...prose.matchAll(/\b[a-z][a-z0-9]*(?:-[a-z0-9]+){3,}\b/gi)]
    .map((m) => m[0])
    .filter((t) => !allowed.has(t.toLowerCase()));
  assert.deepEqual(bad, [], "unresolved slugs (add real terms to scripts/allowed-terms.json)");
}

let checked = 0;
const check = (where, text) => {
  try {
    assertHygiene(text);
    checked++;
  } catch (e) {
    throw Error(where + ": " + e.message);
  }
};
for (const p of data.papers) {
  for (const field of ["title", "summary", "insight", "limitation"]) if (p[field]) check(p.slug + "." + field, p[field]);
  if (p.status !== "reviewed") continue;
  const d = read("../public/stories/recsys-2026/articles/" + p.slug + ".json");
  d.sections.forEach((s, i) => check(p.slug + " §" + i, s.markdown));
}
for (const t of data.themes) {
  check("theme " + t.id, t.title + " " + t.dek);
  for (const i of t.insights) check("theme " + t.id + " insight", i.title + " " + i.text);
}
console.log("hygiene PASS " + checked);
