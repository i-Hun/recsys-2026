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
console.log(
  JSON.stringify({
    status: "PASS",
    renderedSections: sections,
    xss: "raw HTML, javascript URLs and images blocked; safe formatting retained",
  }),
);
