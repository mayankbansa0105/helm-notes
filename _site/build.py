#!/usr/bin/env python3
"""Bundle the Helm notes (../*.md) into one HTML page: _site/helm-notes.html"""
import json, pathlib, re

here = pathlib.Path(__file__).resolve().parent
src = here.parent
docs = []
for p in sorted(src.glob("*.md")):
    text = p.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+)$", text, re.M)
    title = m.group(1).strip() if m else p.stem
    title = re.sub(r"^\d+\s+[—-]\s+", "", title)
    key = "home" if p.name.lower() == "readme.md" else "n" + p.name[:2]
    docs.append({"key": key, "file": p.name, "num": "" if key == "home" else p.name[:2], "title": title, "md": text})
docs.sort(key=lambda d: (d["key"] != "home", d["file"]))
payload = json.dumps(docs, ensure_ascii=False).replace("</", "<\\/")
tpl = (here / "template.html").read_text(encoding="utf-8")
page = tpl.replace("__DOCS__", payload)
(here / "helm-notes.html").write_text(page, encoding="utf-8")
# Standalone copy for GitHub Pages, which serves the file as-is: add the document skeleton.
head = '<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
(here / "index.html").write_text(head + page, encoding="utf-8")
print("wrote", here / "helm-notes.html", "and", here / "index.html", len(docs), "docs")
