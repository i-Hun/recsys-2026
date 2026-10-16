import { readFileSync, writeFileSync, mkdtempSync, rmSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { safetyCheck } from "./test-recsys.mjs";
const source = readFileSync(
  new URL("../utils/recsys-markdown.js", import.meta.url),
  "utf8",
);
const dir = mkdtempSync(new URL("./mutation-", import.meta.url));
try {
  if (!source.includes("html: false")) throw Error("mutation anchor missing");
  const file = dir + "/unsafe.mjs";
  writeFileSync(file, source.replace("html: false", "html: true"));
  const unsafe = await import(pathToFileURL(file));
  let killed = 0;
  for (const [name, render] of [
    ["enable_raw_html", unsafe.renderReview],
    ["strip_all_formatting", () => "plain text"],
  ]) {
    try {
      safetyCheck(render);
    } catch (e) {
      console.log(name + " killed: " + e.message);
      killed++;
      continue;
    }
    throw Error("SURVIVED " + name);
  }
  if (killed !== 2) throw Error("mutation count");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
