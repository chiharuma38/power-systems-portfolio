#!/usr/bin/env python3
"""
sync_progress.py, one file in, three places out.

progress.json is the single source of truth. Edit it, run this, and:

  1. chiharuma38.github.io/progress.json          <- the live site reads this
  2. chiharuma38.github.io/index.html             <- FALLBACK block refreshed
  3. Energy Systems Academy/01 Dashboard/         <- private dashboard reads this
       portfolio-progress.js

Usage
-----
    python3 sync_progress.py                # sync everything it can find
    python3 sync_progress.py --check        # validate only, write nothing
    python3 sync_progress.py --academy PATH # point at the Academy folder explicitly

Why a script rather than a shared fetch: the Academy dashboard is opened as a
local file (file://), and browsers block cross-origin fetch from file:// URLs.
A generated .js file loaded via <script src> works everywhere.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "progress.json"
SITE = HERE / "chiharuma38.github.io"
DEFAULT_ACADEMY = Path.home() / "Desktop" / "Energy-Systems-HQ" / "1-Academy"

VALID_STATUS = {"complete", "active", "planned"}

GREEN, YELLOW, RED, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


# ----------------------------------------------------------------- validate
def load_and_validate(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"{RED}✗{OFF} {path} not found")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"{RED}✗ progress.json is not valid JSON{OFF}\n  line {e.lineno}: {e.msg}")

    problems: list[str] = []

    if "projects" not in data:
        problems.append("missing top-level 'projects'")

    seen = set()
    for i, p in enumerate(data.get("projects", [])):
        tag = p.get("id", f"#{i}")
        if not p.get("id"):
            problems.append(f"project {i}: missing 'id'")
        if p.get("id") in seen:
            problems.append(f"duplicate id '{tag}'")
        seen.add(p.get("id"))

        if p.get("status") not in VALID_STATUS:
            problems.append(f"{tag}: status '{p.get('status')}' not in {sorted(VALID_STATUS)}")

        ms = p.get("milestones") or []
        if ms:
            pct = round(sum(bool(m.get("done")) for m in ms) / len(ms) * 100)
            if abs(pct - p.get("percent", pct)) > 12:
                problems.append(
                    f"{tag}: percent={p.get('percent')} but milestones imply {pct}% "
                    f"- milestones win, consider updating percent"
                )
            p["percent"] = pct  # milestones are authoritative
        elif not isinstance(p.get("percent"), (int, float)):
            problems.append(f"{tag}: no milestones and no numeric 'percent'")

        # honesty guard
        if p.get("status") == "complete" and p.get("percent", 0) < 100:
            problems.append(f"{tag}: marked complete but only {p['percent']}%")
        if p.get("percent") == 100 and p.get("status") != "complete":
            problems.append(f"{tag}: at 100% but status is '{p.get('status')}'")

    if problems:
        print(f"{RED}✗ progress.json has problems:{OFF}")
        for x in problems:
            print(f"    · {x}")
        sys.exit(1)

    # keep the timestamp honest
    data["updated"] = data.get("updated") or date.today().isoformat()
    return data


# ------------------------------------------------------------------- writers
def write_site_json(data: dict) -> bool:
    if not SITE.exists():
        print(f"{YELLOW}!{OFF} site folder not found at {SITE}, skipped")
        return False
    slim = {
        "updated": data["updated"],
        "projects": [
            {k: p[k] for k in ("id", "num", "name", "status", "percent",
                               "headline", "milestones", "repo", "page") if k in p}
            for p in data["projects"]
        ],
    }
    (SITE / "progress.json").write_text(
        json.dumps(slim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{GREEN}✓{OFF} chiharuma38.github.io/progress.json")
    return True


def write_site_fallback(data: dict) -> bool:
    index = SITE / "index.html"
    if not index.exists():
        print(f"{YELLOW}!{OFF} index.html not found, fallback not refreshed")
        return False

    rows = ",\n".join(
        '      {{ id: "{id}", status: "{status}", percent: {percent} }}'.format(
            id=p["id"], status=p["status"], percent=p["percent"])
        for p in data["projects"]
    )
    block = (
        '  var FALLBACK = {\n'
        f'    updated: "{data["updated"]}",\n'
        '    projects: [\n'
        f'{rows}\n'
        '    ]\n'
        '  };'
    )

    html = index.read_text(encoding="utf-8")
    pattern = re.compile(r"  var FALLBACK = \{.*?\n  \};", re.DOTALL)
    if not pattern.search(html):
        print(f"{YELLOW}!{OFF} FALLBACK block not found in index.html, left untouched")
        return False

    index.write_text(pattern.sub(lambda _: block, html, count=1), encoding="utf-8")
    print(f"{GREEN}✓{OFF} chiharuma38.github.io/index.html  (fallback refreshed)")
    return True


def write_academy(data: dict, academy: Path) -> bool:
    dash = academy / "01 Dashboard"
    if not dash.exists():
        print(f"{YELLOW}!{OFF} Academy not found at {academy}, skipped")
        print(f"{DIM}    pass --academy PATH if it lives somewhere else{OFF}")
        return False

    (dash / "portfolio-progress.js").write_text(
        "/* generated by sync_progress.py, do not edit by hand */\n"
        "window.PORTFOLIO_PROGRESS = "
        + json.dumps(data, indent=2, ensure_ascii=False)
        + ";\n",
        encoding="utf-8")
    print(f"{GREEN}✓{OFF} Energy Systems Academy/01 Dashboard/portfolio-progress.js")
    return True


# ---------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    ap.add_argument("--academy", type=Path, default=DEFAULT_ACADEMY,
                    help=f"path to the Energy Systems Academy folder (default: {DEFAULT_ACADEMY})")
    args = ap.parse_args()

    data = load_and_validate(SOURCE)

    total = len(data["projects"])
    done = sum(p["status"] == "complete" for p in data["projects"])
    overall = round(sum(p["percent"] for p in data["projects"]) / total)

    print()
    print(f"  {DIM}portfolio{OFF}  {done}/{total} shipped · {overall}% overall")
    for p in data["projects"]:
        bar = "█" * round(p["percent"] / 5) + "░" * (20 - round(p["percent"] / 5))
        mark = {"complete": GREEN + "●", "active": YELLOW + "◐", "planned": DIM + "○"}[p["status"]]
        print(f"    {mark}{OFF} {p['num']} {bar} {p['percent']:3d}%  {p['name'][:46]}")

    lw = data.get("learning", {})
    if lw:
        print()
        print(f"  {DIM}learning{OFF}   week {lw.get('current_week','?')}/{lw.get('total_weeks','?')}"
              f" · {lw.get('hours_studied',0)}/{lw.get('hours_target',0)} h"
              f" · {lw.get('papers_read',0)}/{lw.get('papers_target',0)} papers")
    print()

    if args.check:
        print(f"{GREEN}✓ valid{OFF}, nothing written (--check)\n")
        return

    write_site_json(data)
    write_site_fallback(data)
    write_academy(data, args.academy)

    print()
    print(f"{DIM}  next:{OFF}")
    print(f"{DIM}    cd chiharuma38.github.io && git add -A && git commit -m 'Update progress' && git push{OFF}")
    print(f"{DIM}    git add progress.json && git commit -m 'Update progress' && git push{OFF}")
    print()


if __name__ == "__main__":
    main()
