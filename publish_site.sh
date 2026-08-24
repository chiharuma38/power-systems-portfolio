#!/usr/bin/env bash
# Publishes the portfolio site.
#
# Keeps the live June design and adds: five project write-ups, the four result
# figures, and a downloadable CV. Your local branch and GitHub had diverged —
# five commits from 24 June, made through the GitHub web UI, only ever touched
# index.html and never reached this Mac. index.html on disk is that live design
# with everything wired in, so this replays your work on top of GitHub's.
#
#   bash ~/power-systems-portfolio/publish_site.sh
set -euo pipefail

ROOT=~/power-systems-portfolio
SITE="$ROOT/chiharuma38.github.io"

# ---------------------------------------------------------------- stale locks
# Earlier git commands were run through a sandboxed shell that is not permitted
# to delete files, so git could create its lock files but never clean them up.
# Nothing is actually running; these are orphans. Close any editor mid-commit
# before running this, then they are safe to remove.
clean_locks () {
  local repo="$1" label="$2" found=0
  for f in index.lock HEAD.lock objects/maintenance.lock; do
    if [ -e "$repo/.git/$f" ]; then rm -f "$repo/.git/$f"; echo "    removed  $label/.git/$f"; found=1; fi
  done
  local n
  n=$(find "$repo/.git/objects" -name 'tmp_obj_*' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -gt 0 ]; then
    find "$repo/.git/objects" -name 'tmp_obj_*' -delete
    echo "    removed  $n orphaned temp objects in $label"
    found=1
  fi
  [ "$found" -eq 0 ] && echo "    $label: clean"
  return 0
}

echo "==> Clearing stale git locks"
clean_locks "$SITE" "site repo"
clean_locks "$ROOT" "portfolio repo"

cd "$SITE"

echo
echo "==> Fetching what GitHub has"
git fetch origin

echo
echo "==> Checking the five write-ups"
for f in n1_contingency offshore_wind fault_detection storage_optimizer contingency_toolkit; do
  [ -s "projects/$f.html" ] && echo "    ok   projects/$f.html" || { echo "    MISSING projects/$f.html"; exit 1; }
done

echo
echo "==> Checking the result figures"
for n in 02 03 04 05; do
  [ -s "images/p${n}_results.png" ] && echo "    ok   images/p${n}_results.png" || { echo "    MISSING images/p${n}_results.png"; exit 1; }
done

echo
echo "==> Checking the CV"
[ -s "assets/Chiharu_Mamiya_CV.pdf" ] \
  && echo "    ok   assets/Chiharu_Mamiya_CV.pdf ($(wc -c < assets/Chiharu_Mamiya_CV.pdf | tr -d ' ') bytes)" \
  || { echo "    MISSING assets/Chiharu_Mamiya_CV.pdf"; exit 1; }
[ "$(grep -c 'assets/Chiharu_Mamiya_CV.pdf' index.html)" -ge 2 ] \
  && echo "    ok   linked from the hero card and the contact section" \
  || { echo "    index.html does not link the CV twice"; exit 1; }

echo
echo "==> Checking index.html is the live design, fully wired"
grep -q 'class="exp-panel' index.html || { echo "    not the June design"; exit 1; }
for f in offshore_wind fault_detection storage_optimizer contingency_toolkit; do
  grep -q "data-href=\"projects/$f.html\"" index.html || { echo "    panel for $f not wired"; exit 1; }
done
echo "    ok   all five panels point at write-ups"

echo
echo "==> Replaying your work on top of GitHub's history"
echo "    (your previous local commit stays recoverable via: git reflog)"
git reset --soft origin/main
git add -A

echo
echo "==> What is about to be published"
git status --short

echo
git commit -q -m "Publish project write-ups and add a downloadable CV

Keeps the live site design. The five project panels now open full write-ups
instead of pointing at the repository root, and the CV is downloadable from
both the hero card and the contact section.

  02  HVAC export cable    AC feasible to 160 km, 109 Mvar charging at 100 km
  03  Fault detection      0.962 clean, chance level at 0.5 percent noise
  04  Storage optimizer    duality verified, zero revenue below a 1.181 ratio
  05  Contingency toolkit  2.85x on 4 cores, results verified identical

Each page states the question, the method, the measured results and an
explicit limitations section, matching the existing project 01 page.

Also:
- CV added at assets/Chiharu_Mamiya_CV.pdf under a stable filename, so the
  link survives future updates
- result figures added to images/, click to enlarge
- panel 05 retitled from PSS/E Automation to Parallel N-1 Toolkit, and its
  subtitle corrected to that project's own result
- GE Vernova dates corrected to Oct 2025 to May 2026
- hero, background and contact copy moved to present tense
- fixed mobile horizontal overflow on wide tables, long DOIs and code lines
- added .gitignore for .DS_Store"

echo "==> Pushing the site"
git push

# ---------------------------------------------------- the other repo, if dirty
echo
cd "$ROOT"
if [ -n "$(git status --porcelain)" ]; then
  echo "==> Portfolio repo has changes too, committing those"
  git add -A
  git status --short
  git commit -q -m "Point sync_progress.py at the new Academy path

The Energy Systems Academy moved into ~/Desktop/Energy-Systems-HQ/1-Academy
during the folder reorganisation, so the default path in sync_progress.py
no longer resolved."
  git push
else
  echo "==> Portfolio repo already clean, nothing to push"
fi

echo
echo "Done. GitHub Pages usually redeploys within a minute."
echo "  Site   https://chiharuma38.github.io/"
echo "  CV     https://chiharuma38.github.io/assets/Chiharu_Mamiya_CV.pdf"
