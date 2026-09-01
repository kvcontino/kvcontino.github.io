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
#   script/check-site.sh --selftest   # prove the checks can FAIL, then exit
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
BUILD=1; DRAFTS=0; SELFTEST=0; LIVE=0
for a in "$@"; do
  case "$a" in
    --no-build) BUILD=0 ;;
    --drafts)   DRAFTS=1 ;;
    --selftest) SELFTEST=1 ;;
    --live)     LIVE=1; BUILD=0 ;;
    *) echo "unknown flag: $a" >&2; exit 64 ;;
  esac
done


fail=0
note() { printf '  %s\n' "$1"; }
section() { printf '\n=== %s ===\n' "$1"; }

# ---------------------------------------------------------------------- live
# Everything else in this file reads _site/, which answers "did Jekyll produce
# the right thing". It cannot answer "can a reader reach it" -- a green build
# still does not guarantee a publish (memory reference-pages-deploy-vs-build),
# and the two failures look identical from here.
#
# --live HEADs the deployed URLs instead. It implies --no-build: rebuilding
# locally is irrelevant to what the server is serving, and doing it anyway would
# make a stale deploy look fresh.
if [ "$LIVE" = 1 ]; then
  ORIGIN=https://kvcontino.github.io
  section "live site — $ORIGIN"
  live_fail=0
  # Pages the site must always serve, plus every share card referenced by the
  # projects data. A card that 404s is the specific failure that made the
  # Federal Medicaid Data Catalog's og:image dead on arrival for two hours on
  # 2026-08-31, and nothing in the built-tree checks could see it.
  urls=(/ /posts/ /feed.xml /_pages/presentations.html)
  while IFS= read -r c; do urls+=("/assets/og/$c"); done     < <(ls assets/og/*.png 2>/dev/null | xargs -r -n1 basename)
  for u in "${urls[@]}"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 -I "$ORIGIN$u")
    if [ "$code" = "200" ]; then
      note "ok    $u"
    else
      note "FAIL  $u -> HTTP $code"; live_fail=$((live_fail+1)); fail=1
    fi
  done
  printf '\n=== live verdict ===\n'
  if [ "$live_fail" = 0 ]; then
    note "all ${#urls[@]} URLs serve 200"
  else
    note "$live_fail of ${#urls[@]} URLs are not being served"
  fi
  exit $fail
fi

if [ "$BUILD" = 1 ]; then
  section "jekyll build"
  bundle exec jekyll build --quiet || { echo "BUILD FAILED"; exit 1; }
  note "ok"
fi
[ -d _site ] || { echo "no _site/ — run without --no-build"; exit 2; }

# ------------------------------------------------------------------- selftest
# WHY THIS EXISTS. The glyph check was scoped by the bare substring "lite.css",
# and a first attempt at tightening that scope MATCHED ZERO PAGES WHILE STILL
# REPORTING "ok" -- a check that cannot fail is indistinguishable from a check
# that passes, and it was caught only by injecting a U+2192 by hand. So the
# hand-injection became the flag.
#
# EACH PROBE PICKS ITS OWN PAGE, and that is the whole lesson repeating itself.
# The first version of this flag poisoned one page for all four probes and
# reported that the glyph and orphan-footnote checks "cannot fail" -- because
# the page it happened to pick (_resources/mcaid/) references no lite.css and
# carries no footnotes, so both checks correctly skipped it. A probe run
# somewhere the check does not apply proves nothing, and says so in exactly the
# words that mean a real defect. So: select a page that satisfies the check's
# own precondition, and if none exists, say NO PROBE PAGE rather than "not
# detected". The two are not the same finding.
#
# Reverting is in a trap, not at the end of the loop, so an interrupted
# selftest cannot leave a poisoned page behind. Only _site/ is ever written to,
# never a source file.
if [ "$SELFTEST" = 1 ]; then
  [ -d _site ] || { echo "no _site/ — build first"; exit 2; }
  st_fail=0
  probe_page=""; backup=""
  restore() { [ -n "$backup" ] && [ -n "$probe_page" ] && cp "$backup" "$probe_page"; rm -f "$backup"; }
  trap restore EXIT INT TERM

  # $1 label, $2 mode, $3 grep pattern the page must contain
  probe() {
    printf '\n--- selftest: %s\n' "$1"
    probe_page=$(grep -rl "$3" _site --include='*.html' 2>/dev/null | head -1)
    if [ -z "$probe_page" ]; then
      printf '    NO PROBE PAGE matches %s — cannot exercise this check\n' "$3"
      st_fail=1; return
    fi
    printf '    poisoning %s\n' "${probe_page#_site/}"
    backup=$(mktemp); cp "$probe_page" "$backup"
    python3 - "$probe_page" "$2" <<'PY'
import sys
f, mode = sys.argv[1], sys.argv[2]
h = open(f, encoding="utf-8").read()
if mode == "glyph":      h = h.replace("</p>", " →</p>", 1)
elif mode == "tag":      h = h.replace("</div>", "", 1)
elif mode == "orphanfn": h = h.replace('<span class="fn-note"', '<span class="fn-NOTE"', 1)
elif mode == "ogdup":
    h = h.replace('<meta property="og:image"',
                  '<meta property="og:image" content="x"><meta property="og:image"', 1)
open(f, "w", encoding="utf-8").write(h)
PY
    if bash "$0" --no-build >/dev/null 2>&1; then
      printf '    NOT DETECTED — this check cannot fail\n'; st_fail=1
    else
      printf '    detected (suite exited non-zero)\n'
    fi
    cp "$backup" "$probe_page"; rm -f "$backup"; backup=""; probe_page=""
  }

  probe "missing glyph (U+2192 into prose)" glyph    'lite\.css'
  probe "unbalanced tag (drop one </div>)"  tag      '</div>'
  probe "orphan footnote marker"            orphanfn 'class="fn-note"'
  probe "duplicate og:image tag"            ogdup    'property="og:image"'

  # NO stale-share-card probe, deliberately. That check was demoted to
  # report-only on 2026-08-30 (see the "feed and share cards" section for the
  # two wrong implementations that preceded the decision), so it can no longer
  # fail and there is nothing to prove. A probe kept here would report NOT
  # DETECTED forever and train you to ignore the selftest verdict, which is
  # the one output in this file that has to stay trustworthy.

  trap - EXIT INT TERM
  printf '\n=== selftest verdict ===\n'
  if [ "$st_fail" = 0 ]; then
    note "every probe was detected — the checks can fail"; exit 0
  else
    note "a probe went UNDETECTED or had no page — see above"; exit 1
  fi
fi

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
# Figure text is glyph-pathed into the SVG, so the HTML scan above cannot see
# it -- and matplotlib now sets the figures in the same face as the page. A
# character the font lacks becomes a .notdef box baked into the image, which no
# amount of HTML checking will catch. Read the strings straight out of the
# figure builders instead.
section "figure text glyph coverage"
if python3 - <<'PY'
import re, os, glob, sys, unicodedata
try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("  (fontTools not installed - skipped)"); sys.exit(0)
cov = set()
for face in ("Regular", "Italic"):
    p = f"assets/fonts/SortsMillGoudy-{face}.woff2"
    if os.path.exists(p):
        cov |= set(TTFont(p).getBestCmap())
if not cov:
    print("  (font not found - skipped)"); sys.exit(0)
bad = []
for src in glob.glob("_resources/**/build_figures.py", recursive=True):
    for n, line in enumerate(open(src, encoding="utf-8"), 1):
        if line.lstrip().startswith("#"):
            continue
        for lit in re.findall(r'"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'', line):
            for ch in (lit[0] or lit[1]):
                if ord(ch) < 0x20 or ch.isspace() or ord(ch) in cov:
                    continue
                bad.append(f"U+{ord(ch):04X} {ch!r} ({unicodedata.name(ch,'?')}) - {src}:{n}")
for b in sorted(set(bad)):
    print("  TOFU IN FIGURE TEXT: " + b)
sys.exit(1 if bad else 0)
PY
then note "ok"; else fail=1; fi

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
    # Scope by an actual stylesheet REFERENCE, not a bare substring: a page
    # that merely mentions lite.css in prose or in a CSS comment was being
    # scoped into this check and flagged for glyphs its own fonts cover.
    # (Caught 2026-08-16 on the metro-relocation dashboard, which ships
    # Cormorant/Spectral and names the shared stylesheet in a comment.)
    if not re.search(r'(?:href\s*=\s*|@import\s+)["\'][^"\']*lite\.css', html):
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

# ------------------------------------------------------------------- em-dashes
# REPORTS, never fails. The standing preference is em-dashes out of authored
# prose and kept inside verbatim quotes, so <blockquote> is excluded -- but the
# methodology page carries 72 the user has explicitly declined to convert, and
# a check that fails on a decided exception just teaches you to ignore it.
# Enforcement was a manual `grep -c` roughly six times in one editing session;
# this makes the number visible without making it a gate.
section "em-dashes outside blockquote (report only)"
python3 - "${PAGES[@]}" <<'PY'
import re, sys, os
rows = []
for f in sys.argv[1:]:
    html = open(f, encoding="utf-8", errors="replace").read()
    body = re.sub(r"<(script|style|blockquote)\b.*?</\1>", " ", html, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    n = body.count("—")
    if n:
        rows.append((n, os.path.relpath(f, "_site")))
for n, f in sorted(rows, reverse=True)[:12]:
    print(f"  {n:>4}  {f}")
print(f"  ({sum(n for n, _ in rows)} total across {len(rows)} page(s); reported, not enforced)")
PY

# ------------------------------------------------------------- footnote integrity
# Two hazards, one check. An orphan `<span class="fn">` with no `.fn-note`
# inside it renders a bare superscript number pointing at nothing. And the
# user's editor strips superscripts when prose is pasted out to edit, so a
# footnote that vanishes between commits is ambiguous between a deliberate cut
# and a paste artifact -- the throwaway version of this found 5 apparent losses,
# 4 of which were rewrites and 1 carried more fully elsewhere. Orphans FAIL;
# a drop in count against HEAD is reported for a human to read.
section "footnote integrity"
if python3 - "${PAGES[@]}" <<'PY'
import re, sys, os, subprocess
bad = 0
per_page = {}
for f in sys.argv[1:]:
    html = open(f, encoding="utf-8", errors="replace").read()
    marks = re.findall(r'<span class="fn"[^>]*>(.*?)</span>\s*</span>', html, flags=re.S)
    total = len(re.findall(r'<span class="fn"[^>]*>', html))
    notes = len(re.findall(r'<span class="fn-note"[^>]*>', html))
    rel = os.path.relpath(f, "_site")
    if total:
        per_page[rel] = total
    if total != notes:
        print(f"  ORPHAN MARKER {rel}: {total} fn marker(s) but {notes} fn-note(s)")
        bad = 1
if per_page:
    for k, v in sorted(per_page.items()):
        print(f"  {v:>4} footnote(s)  {k}")
# Compare against the previous commit's built count where the source is tracked.
try:
    prev = subprocess.run(["git", "show", "HEAD:_resources/onecare/index.html"],
                          capture_output=True, text=True, timeout=20)
    if prev.returncode == 0:
        was = len(re.findall(r'<span class="fn"[^>]*>', prev.stdout))
        now_src = open("_resources/onecare/index.html", encoding="utf-8").read()
        now = len(re.findall(r'<span class="fn"[^>]*>', now_src))
        if now < was:
            print(f"  NOTE: onecare/index.html footnotes {was} -> {now}. A drop is not")
            print( "        automatically wrong, but the editor strips superscripts on paste,")
            print( "        so confirm each loss was meant. (reported, not a failure)")
except Exception:
    pass
sys.exit(bad)
PY
then note "ok"; else fail=1; fi

# ------------------------------------------------------------------ feed + cards
section "feed and share cards"
if python3 - <<'PY'
import os, re, struct, sys, xml.etree.ElementTree as ET
bad = 0

# (1) feed.xml is hand-maintained and nothing validates it.
try:
    tree = ET.parse("_site/feed.xml")
    entries = tree.getroot().findall("{http://www.w3.org/2005/Atom}entry")
    ids = [e.find("{http://www.w3.org/2005/Atom}id").text for e in entries]
    print(f"  feed.xml parses, {len(entries)} entries")
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"  DUPLICATE FEED ID(S): {sorted(dupes)}")
        bad = 1
    if not entries:
        print("  feed.xml has NO entries"); bad = 1
except Exception as e:
    print(f"  feed.xml FAILED to parse: {e}"); bad = 1

def png_size(path):
    """Width/height from the IHDR header -- no image library needed."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])

# (2) exactly one og:image per page, the file exists, and the declared
#     dimensions match the PNG header. The duplicate-tag and wrong-card bugs
#     were both found only by a throwaway loop.
for root, _, files in os.walk("_site"):
    for fn in files:
        if not fn.endswith(".html"):
            continue
        f = os.path.join(root, fn)
        html = open(f, encoding="utf-8", errors="replace").read()
        imgs = re.findall(r'<meta property="og:image" content="([^"]+)"', html)
        rel = os.path.relpath(f, "_site")
        if len(imgs) > 1:
            print(f"  {rel}: {len(imgs)} og:image tags, expected 1"); bad = 1
        if not imgs:
            continue
        local = imgs[0].split("kvcontino.github.io", 1)[-1].lstrip("/")
        path = os.path.join("_site", local)
        if not os.path.exists(path):
            print(f"  {rel}: og:image missing on disk -> {local}"); bad = 1
            continue
        size = png_size(path)
        w = re.search(r'<meta property="og:image:width" content="(\d+)"', html)
        h = re.search(r'<meta property="og:image:height" content="(\d+)"', html)
        if size and w and h and (int(w.group(1)), int(h.group(1))) != size:
            print(f"  {rel}: og declares {w.group(1)}x{h.group(1)} but the PNG is "
                  f"{size[0]}x{size[1]}"); bad = 1

# (3) share-card freshness. REPORTED, never fails -- and the reason is worth
#     keeping, because two different implementations of this check were both
#     wrong before the third was right.
#
#     v1 compared MTIMES. Git does not preserve them, so every file gets its
#     checkout time and one clone made all 11 cards look stale.
#
#     v2 compared GIT COMMIT TIMES. Better -- it survives a clone -- but still
#     wrong, because it asks "was this card committed after projects.yml last
#     changed?" when the question is "would regenerating change it?". Adding a
#     NEW project edits projects.yml without altering any existing card, so v2
#     reported the 10 older cards as stale on 2026-08-30 when they were fine.
#
#     What settled it: build-og-cards.py is DETERMINISTIC. Regenerating all 11
#     on 2026-08-30 produced 11 byte-identical files (sha256, all unchanged).
#     So the only sound staleness test IS regeneration, and regeneration is
#     also the fix -- which makes a failing gate here pure noise. `git status`
#     after a rebuild is the real check, and it cannot be wrong.
#
#     So: report what exists, name the command, and never fail the suite on it.
#     A check that fires on ten provably-identical files is one you learn to
#     ignore, which is the same argument the em-dash section makes above.
cards = [c for c in sorted(os.listdir("assets/og")) if c.endswith(".png")]
print(f"  {len(cards)} share card(s) present (freshness is not asserted here)")
print("  -> bundle exec jekyll build && uv run script/build-og-cards.py && git status")
sys.exit(bad)
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
