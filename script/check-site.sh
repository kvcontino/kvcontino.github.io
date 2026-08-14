#!/usr/bin/env bash
# check-site.sh — integrity checks over the BUILT site (_site/).
#
# Written 2026-08-14, after the same ad-hoc greps were hand-rolled in three
# separate sessions and two defects shipped anyway that these would have caught:
#   * _pages/media.html shipped TWO nested <html> documents;
#   * an unclosed <div class="tablewrap"> in the metadata-archaeology post,
#     which would have swallowed the rest of the page;
#   * a markdown table that rendered as literal | pipes, because kramdown never
#     runs on a .html file no matter what `markdown="1"` claims.
# The link crawler separately found two dead links that had been live for months.
#
# USAGE
#   script/check-site.sh              # builds, then checks
#   script/check-site.sh --no-build   # check an existing _site/
#   script/check-site.sh --drafts     # ALSO build with --drafts and check that
#
# Exit 0 = clean, 1 = findings. Intended for CI as well as by hand.
#
# KNOWN BLIND SPOT, do not re-derive it: the crawler reads href= and src=
# attributes only. A page that loads something via an ES-module `import` or a
# `fetch()` call will look like an ORPHAN even though it is used. The five
# standalone dashboards are the live example. Check the orphan list by eye
# before deleting anything.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 2
BUILD=1; DRAFTS=0
for a in "$@"; do
  case "$a" in
    --no-build) BUILD=0 ;;
    --drafts)   DRAFTS=1 ;;
    *) echo "unknown flag: $a" >&2; exit 64 ;;
  esac
done

fail=0
note() { printf '  %s\n' "$1"; }
section() { printf '\n=== %s ===\n' "$1"; }

if [ "$BUILD" = 1 ]; then
  section "jekyll build"
  bundle exec jekyll build --quiet || { echo "BUILD FAILED"; exit 1; }
  note "ok"
fi
[ -d _site ] || { echo "no _site/ — run without --no-build"; exit 2; }

# Every .html file Jekyll produced. -print0/read -d '' so paths with spaces
# survive; an unquoted for-loop over find output has bitten this setup before.
mapfile -d '' PAGES < <(find _site -name '*.html' -print0)
section "scope"
note "${#PAGES[@]} built pages"

# ---------------------------------------------------------------- tag balance
# Not a parser — a counter. It catches the failure that actually happens (a
# forgotten closing tag on a structural element), not malformed HTML in general.
section "structural tag balance"
for f in "${PAGES[@]}"; do
  for tag in div html body main article section; do
    o=$(grep -o "<$tag[ >]" "$f" | wc -l)
    c=$(grep -o "</$tag>" "$f" | wc -l)
    if [ "$o" -ne "$c" ]; then
      note "UNBALANCED <$tag>: $o open / $c close — ${f#_site/}"; fail=1
    fi
  done
done
[ "$fail" = 0 ] && note "ok"

# --------------------------------------------------------- one document only
section "single document per page"
for f in "${PAGES[@]}"; do
  n=$(grep -c '<html' "$f")
  if [ "$n" -gt 1 ]; then
    note "NESTED DOCUMENTS: $n <html> tags — ${f#_site/}"; fail=1
  fi
done

# ------------------------------------------------------------- unrendered md
# kramdown does not run on .html source files. `markdown="1"` is silently
# ignored there, and the tell is a literal pipe table surviving into output.
section "unrendered markdown"
for f in "${PAGES[@]}"; do
  if grep -qE '^\s*\|.*\|\s*$' "$f"; then
    note "LITERAL PIPE TABLE — ${f#_site/}"; fail=1
  fi
  if grep -q 'markdown="1"' "$f"; then
    note "markdown=\"1\" survived into output (inert in .html) — ${f#_site/}"; fail=1
  fi
done

# ------------------------------------------------------------------ img alt
section "img alt text"
for f in "${PAGES[@]}"; do
  # every <img ...> that has no alt= before its closing bracket
  n=$(grep -o '<img[^>]*>' "$f" | grep -cv 'alt=')
  if [ "$n" -gt 0 ]; then
    note "$n <img> without alt — ${f#_site/}"; fail=1
  fi
done

# ------------------------------------------------------------ internal links
section "internal links resolve"
dead=0
for f in "${PAGES[@]}"; do
  dir=$(dirname "$f")
  grep -oE '(href|src)="[^"#?]+"' "$f" | sed -E 's/^(href|src)="//; s/"$//' |
  while read -r u; do
    case "$u" in
      http*|//*|mailto:*|data:*|tel:*|"") continue ;;
    esac
    if [ "${u:0:1}" = "/" ]; then t="_site$u"; else t="$dir/$u"; fi
    # a bare directory link resolves to its index.html
    [ -d "$t" ] && t="$t/index.html"
    [ -e "$t" ] || echo "DEAD: $u  <- ${f#_site/}"
  done
done | sort -u | while read -r l; do note "$l"; dead=1; done
# the subshell above cannot set `fail`; recompute from a second pass
if [ -n "$(
  for f in "${PAGES[@]}"; do
    dir=$(dirname "$f")
    grep -oE '(href|src)="[^"#?]+"' "$f" | sed -E 's/^(href|src)="//; s/"$//' |
    while read -r u; do
      case "$u" in http*|//*|mailto:*|data:*|tel:*|"") continue ;; esac
      if [ "${u:0:1}" = "/" ]; then t="_site$u"; else t="$dir/$u"; fi
      [ -d "$t" ] && t="$t/index.html"
      [ -e "$t" ] || echo x
    done
  done)" ]; then fail=1; else note "ok"; fi

# ---------------------------------------------------------------- drafts build
if [ "$DRAFTS" = 1 ]; then
  section "jekyll build --drafts"
  # This build was broken for MONTHS purely because nothing ever ran it.
  if bundle exec jekyll build --drafts --quiet --destination _site_drafts; then
    note "ok"; rm -rf _site_drafts
  else
    note "DRAFTS BUILD FAILED"; fail=1
  fi
fi

section "verdict"
if [ "$fail" = 0 ]; then note "clean"; else note "findings above"; fi
exit "$fail"
