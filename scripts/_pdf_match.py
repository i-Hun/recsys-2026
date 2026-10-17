"""Сопоставление PDF из ~/papers с работами по DOI на первой странице."""
import json
import re
import subprocess
from pathlib import Path

D = json.loads(Path("/home/hun/repos/recsys-2026/data/recsys-2026.json").read_text(encoding="utf-8"))
papers = [p for p in D["papers"] if p["status"] == "reviewed"]
by_doi = {}
for p in papers:
    d = (p.get("doi") or [""])[0].lower()
    if d.startswith("10.1145/"):
        by_doi[d.split("10.1145/")[-1]] = p["slug"]

pdfs = sorted(Path("/home/hun/papers").rglob("*.pdf"))
found = {}
for f in pdfs:
    try:
        txt = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(f), "-"],
                             capture_output=True, text=True, timeout=30).stdout[:6000]
    except Exception:
        continue
    m = re.search(r"10\.1145/(3773078\.\d{7})", txt)
    if m and m.group(1) in by_doi:
        found[by_doi[m.group(1)]] = f.name

print(json.dumps({"pdfs": len(pdfs), "matchedByDoi": len(found), "papers": len(papers)}))
print(list(found.items())[:5])
Path("/home/hun/repos/recsys-2026/.pdf-match.json").write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
