import "./test-recsys-hygiene.mjs";
import "./test-recsys-themes.mjs";
import assert from "node:assert/strict";
import fs from "node:fs";
import { renderReview } from "../utils/recsys-markdown.js";
const payload =
  "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n[click](javascript:alert%281%29)\n![track](https://example.org/pixel.png)";
export function safetyCheck(render) {
  const output = render(payload);
  assert(
    !/<script|<img|href="javascript:/i.test(output),
    "unsafe HTML or external image",
  );
  assert(
    render("**Safe** [source](https://example.org)").includes(
      "<strong>Safe</strong>",
    ),
    "over-sanitization",
  );
}
safetyCheck(renderReview);
const data = JSON.parse(
  fs.readFileSync(new URL("../data/recsys-2026.json", import.meta.url)),
);
const slugSet = new Set(data.papers.map((p) => p.slug));
let sections = 0;
for (const p of data.papers.filter((p) => p.status === "reviewed")) {
  const d = JSON.parse(
    fs.readFileSync(
      new URL(
        "../public/stories/recsys-2026/articles/" + p.slug + ".json",
        import.meta.url,
      ),
    ),
  );
  assert.equal(d.slug, p.slug);
  for (const s of d.sections) {
    const html = renderReview(s.markdown);
    sections++;
    assert(
      !/<script|<iframe|<img|<object|<embed| onerror=/i.test(html),
      "unsafe markup " + p.slug,
    );
    for (const match of html.matchAll(/href="([^"]+)"/g)) {
      const url = match[1];
      assert(
        /^(https?:\/\/|\/stories\/recsys-2026\/papers\/|#)/.test(url),
        "unapproved link " + url + " " + p.slug,
      );
      if (url.startsWith("/stories/recsys-2026/papers/"))
        assert(
          slugSet.has(url.split("/").at(-1).split("#")[0]),
          "dead link " + url,
        );
    }
  }
}
// Карта близости: координаты, кластеры и связь с каталогом.
const map = JSON.parse(
  fs.readFileSync(new URL("../data/recsys-2026-map.json", import.meta.url)),
);
const reviewed = data.papers.filter((p) => p.status === "reviewed");
assert.equal(map.points.length, reviewed.length, "map: по точке на каждый разбор");
const mapSlugs = new Set();
for (const p of map.points) {
  assert(slugSet.has(p.slug), "map: неизвестный slug " + p.slug);
  assert(!mapSlugs.has(p.slug), "map: дубль slug " + p.slug);
  mapSlugs.add(p.slug);
  assert(p.x >= 0 && p.x <= 1000 && p.y >= 0 && p.y <= 1000, "map: координаты вне поля " + p.slug);
  assert(data.themes.some((t) => t.id === p.theme), "map: неизвестная тема " + p.theme);
}
const clusterIds = new Set(map.clusters.map((c) => c.id));
for (const c of map.clusters) {
  assert.equal(map.points.filter((p) => p.cluster === c.id).length, c.size, "map: размер кластера " + c.id);
  assert(c.name && c.name.length < 60, "map: нет названия кластера " + c.id);
}
for (const p of map.points) assert(p.cluster === -1 || clusterIds.has(p.cluster), "map: кластер вне списка " + p.slug);
assert.equal(
  map.clusters.reduce((n, c) => n + c.size, 0) + map.meta.noise,
  map.points.length,
  "map: шум и кластеры не покрывают корпус",
);

console.log(
  JSON.stringify({
    status: "PASS",
    renderedSections: sections,
    mapPoints: map.points.length,
    xss: "raw HTML, javascript URLs and images blocked; safe formatting retained",
  }),
);
