#!/bin/sh
# Show the differences between the pages generated in docs/web/ and the ones of the personal site
# (../rlinfati.github.io). Nothing is copied or changed; copy by hand after reviewing.
# Usage: scripts/web-diff.sh [page ...]      (default: every page in docs/web/, e.g. education.html)
cd "$(dirname "$0")/.." || exit 1
SITE=../rlinfati.github.io
if [ "$#" -gt 0 ]; then pages="$*"; else pages=$(cd docs/web && ls ./*.html 2>/dev/null | sed 's#^\./##'); fi
[ -n "$pages" ] || { echo "no pages in docs/web/ (run quarto render)"; exit 1; }
for page in $pages; do
  echo "=== $page"
  if [ ! -f "$SITE/$page" ]; then echo "(not in $SITE: new page)"; continue; fi
  diff -u "$SITE/$page" "docs/web/$page" > /dev/null && echo "identical" || diff -u --label "site/$page" --label "docs/web/$page" "$SITE/$page" "docs/web/$page"
done
exit 0
