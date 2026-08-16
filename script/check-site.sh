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

# ------------------------------------------------------------- anchors resolve
# A deep link to a heading that has no id fails silently: the browser just stays
# put at the top of the page and the reader never learns the link was wrong.
# Added when the methodology note grew section ids and the essay started aiming
# at them.
section "in-site anchors resolve"
if python3 - <<'PY'
import re, os, glob, sys
ids = {}
for f in glob.glob("_site/**/*.html", recursive=True):
    html = open(f, encoding="utf-8", errors="replace").read()
    ids["/" + os.path.relpath(f, "_site")] = set(re.findall(r'\bid="([^"]+)"', html))
bad = []
for f in glob.glob("_site/**/*.html", recursive=True):
    src = "/" + os.path.relpath(f, "_site")
    for href in re.findall(r'href="([^"]*#[^"]+)"', open(f, encoding="utf-8", errors="replace").read()):
        page, frag = href.split("#", 1)
        if page.startswith(("http://", "https://", "mailto:")):
            continue
        target = src if not page else (
            page if page.startswith("/") else
            os.path.normpath(os.path.join(os.path.dirname(src), page)))
        if target.endswith("/"):
            target += "index.html"
        if target not in ids or frag not in ids[target]:
            bad.append(f"{href}  <- {src.lstrip('/')}")
for b in sorted(set(bad)):
    print("  BROKEN ANCHOR: " + b)
sys.exit(1 if bad else 0)
PY
then note "ok"; else fail=1; fi

# ------------------------------------------------------------- glyph coverage
# Sorts Mill Goudy carries 392 glyphs and no arrows, no math relations, no Greek.
# A character it lacks does not error: it silently falls back to whatever
# fontconfig picks, in a different face, at a different weight. That shipped
# twice before this check existed (U+21A9 in a footnote back-link, U+2248 in a
# figure caption). Scoped to pages that actually load lite.css.
section "glyph coverage"
if python3 - <<'PY'
import re, os, glob, sys, unicodedata
try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("  (fontTools not installed - skipped)"); sys.exit(0)
cmaps = []
for face in ("Regular", "Italic"):
    p = f"assets/fonts/SortsMillGoudy-{face}.woff2"
    if os.path.exists(p):
        cmaps.append(set(TTFont(p).getBestCmap()))
if not cmaps:
    print("  (font not found - skipped)"); sys.exit(0)
covered = set().union(*cmaps)
bad = {}
for f in glob.glob("_site/**/*.html", recursive=True):
    html = open(f, encoding="utf-8", errors="replace").read()
    if "lite.css" not in html:
        continue                      # standalone pages ship their own fonts
    # code/pre/samp/kbd carry a monospace stack in lite.css, so Goudy's coverage
    # does not apply to them; .program and .rw are the inline monospace spans.
    body = re.sub(r"<(script|style|svg|pre|code|samp|kbd)\b.*?</\1>", " ", html, flags=re.S | re.I)
    body = re.sub(r'<span class="(?:program|rw)"[^>]*>.*?</span>', " ", body, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    for ch in set(body):
        if ord(ch) < 0x20 or ch.isspace() or ord(ch) in covered:
            continue
        bad.setdefault(ch, set()).add(os.path.relpath(f, "_site"))
for ch, pages in sorted(bad.items()):
    name = unicodedata.name(ch, "?")
    where = ", ".join(sorted(pages)[:3]) + ("..." if len(pages) > 3 else "")
    print(f"  MISSING GLYPH U+{ord(ch):04X} {ch!r} ({name}) - {where}")
sys.exit(1 if bad else 0)
PY
then note "ok"; else fail=1; fi

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
