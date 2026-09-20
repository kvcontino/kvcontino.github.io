#!/usr/bin/env python3
"""
Put the site's structure back on the standalone pages.

These pages use `layout: null`, so they never receive the sidebar. That is why
they read cleanly and also why they were dead ends: a reader who landed on one
had no route to the rest of the site. Four destinations, set in the same tracked
caps the pages already use for apparatus, wrapping on their own at phone width
so desktop and mobile run identical markup with no JS and no menu state.

The CSS deliberately uses `color: inherit` and opacity rather than any custom
property: these pages do not share a token vocabulary (mcaid is #0d1117, the
NNY/VT maps are light paper, the rest are black), and a nav that names a
variable one page does not define renders invisible there.
"""
import re, sys
from pathlib import Path

ROOT = Path("/home/contino/2_projects/kvcontino.github.io/_resources")
CSS = """  .sitenav{display:flex;flex-wrap:wrap;gap:0.15rem 1.15rem;font-size:0.72rem;
    letter-spacing:0.14em;text-transform:uppercase;padding:0.5rem 0 0.7rem;line-height:1.5}
  .sitenav a{color:inherit;opacity:0.62;text-decoration:none;
    border-bottom:1px solid transparent;padding-bottom:1px}
  .sitenav a:hover{opacity:1;border-bottom-color:currentColor}
"""
NAV = """<nav class="sitenav" aria-label="Site"><a href="/index.html">About</a><a href="/posts/">Posts</a><a href="/_pages/presentations.html">Projects</a><a href="/feed.xml">Feed</a></nav>"""

# (path, what to replace, what to put there). Each page keeps its own brand
# line; only the destination list is made consistent.
JOBS = [
    ("nny-population-map.html",
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a> &middot; <a href="/_pages/presentations.html">Projects</a></nav>',
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a></nav>\n  ' + NAV),
    ("nny-toponyms.html",
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a> &middot; <a href="/_pages/presentations.html">Projects</a></nav>',
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a></nav>\n  ' + NAV),
    ("vermont-population-map.html",
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a> &middot; <a href="/_pages/presentations.html">Projects</a></nav>',
     '<nav class="sitelink"><a href="/">Kevin V. Contino</a></nav>\n  ' + NAV),
    ("metro-relocation/index.html",
     '<nav><a href="/index.html">About</a><a href="/_pages/presentations.html">Projects</a></nav>',
     NAV),
    ("mcaid/index.html",
     '  <header class="site-header">',
     '  ' + NAV + '\n  <header class="site-header">'),
    ("nova-walksheds/map/index.html",
     '  <p id="sel"></p>\n</div>',
     '  <p id="sel"></p>\n  ' + NAV + '\n</div>'),
]

def main():
    changed = 0
    for rel, old, new in JOBS:
        p = ROOT / rel
        h = p.read_text()
        if 'class="sitenav"' in h:
            print(f"  skip {rel}: already has the nav"); continue
        if old not in h:
            sys.exit(f"REFUSING {rel}: anchor not found -- {old[:60]!r}")
        h = h.replace(old, new, 1)
        if ".sitenav{" not in h:
            m = re.search(r"\n\s*</style>", h)
            if m:
                h = h[:m.start()] + "\n" + CSS + h[m.start():]
            else:
                # mcaid keeps its CSS in a separate styles.css; append there
                sheet = p.parent / "styles.css"
                if not sheet.exists():
                    sys.exit(f"REFUSING {rel}: no <style> block and no styles.css")
                if ".sitenav{" not in sheet.read_text():
                    sheet.write_text(sheet.read_text().rstrip() + "\n\n"
                                     + "/* Site navigation on a standalone page. */\n"
                                     + CSS.replace("  ", "", 1))
                    print(f"  + nav rules appended to {sheet.name}")
        p.write_text(h); changed += 1
        print(f"  navved {rel}")
    print(f"{changed} pages updated")

if __name__ == "__main__":
    main()
