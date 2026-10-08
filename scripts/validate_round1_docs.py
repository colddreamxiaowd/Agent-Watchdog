"""Static source and link check for the round1 to round3 markdown tutorials.

No network; checks repository relative links and visible markdown structure.
Not a correctness proof of the explanations.
"""
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / f"从零开发 Agent Watchdog（{i}）.md" for i in range(21, 33)]
PAGES += [ROOT / "README.md", ROOT / "examples/v04/CHAPTERS_21-24.md", ROOT / "examples/v04/CHAPTERS_25-28.md", ROOT / "examples/v04/CHAPTERS_29-32.md"]
PAGES += list((ROOT / "docs").glob("*.md"))
errors = []
for page in PAGES:
    if not page.is_file():
        errors.append(f"missing file: {page}")
        continue
    data = page.read_text(encoding="utf-8")
    if page.name.startswith("从零开发"):
        if len(data) < 4000:
            errors.append(f"tutorial too short: {page}")
        if len(re.findall(r"^# ", data, re.M)) != 1:
            errors.append(f"invalid H1 count: {page}")
        if "\u00a7" * 3 in data:
            errors.append(f"unconverted placeholder: {page}")
        if len(re.findall(r"^```", data, re.M)) % 2:
            errors.append(f"unbalanced markdown fences: {page}")
    for url in re.findall(r"\[[^\]]+\]\(([^)]+)\)", data):
        if url.startswith(("https:", "http:", "mailto:", "#")):
            continue
        dest = (page.parent / unquote(url.split("#", 1)[0])).resolve()
        if not dest.is_file():
            errors.append(f"broken link: {page.relative_to(ROOT)} -> {url}")
print(f"checked {len(PAGES)} markdown files; errors={len(errors)}")
for error in errors:
    print(error, file=sys.stderr)
if errors:
    raise SystemExit(1)
