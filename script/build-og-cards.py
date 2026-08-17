# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright", "pyyaml"]
# ///
"""Build the site's Open Graph share cards into assets/og/.

WHAT THESE ARE FOR
------------------
Paste a URL into Slack, Signal, iMessage, Discord, LinkedIn or Mastodon and the
app fetches the page and looks for <meta property="og:image"> to build a preview
card. With no such tag it renders a bare blue link. Every share of this site was
doing exactly that.

Two constraints drive the design:

  * The image must be a RASTER file at an ABSOLUTE url. Essentially no scraper
    renders SVG, and most reject relative paths outright. So the marks, which
    are SVG everywhere else on this site, have to be baked into PNG here.
  * 1200x630 (1.91:1) is the size the large-card layouts are cut for. We render
    at 2x for retina and declare the real pixel size in the meta tags.

WHY GENERATE RATHER THAN DRAW
-----------------------------
The card art is the project's own mark and its own blurb, both read from the
same sources the site reads: `_data/projects.yml`, and the marks lifted out of
the BUILT projects page. Nothing is transcribed, so a card cannot drift from the
page it advertises. Re-run this after changing a mark, a title or a blurb.

USAGE
-----
    bundle exec jekyll build          # cards are cut from the built site
    uv run script/build-og-cards.py
"""

import base64
import html
import pathlib
import re
import shutil
import sys

import yaml
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
OUT = ROOT / "assets" / "og"
FONT = ROOT / "assets" / "fonts" / "SortsMillGoudy-Regular.woff2"

W, H, SCALE = 1200, 630, 2

# The palette, copied from _stylesheets/lite.css. Kept as literals on purpose:
# these are baked into a PNG, so they cannot be custom properties, and a card
# built from a stale colour should be visibly wrong rather than quietly close.
VOID, INK, INK_2, INK_FAINT, BLEED = "#000000", "#e8e8e8", "#cbb8a9", "#4a4038", "#b81419"
TRACK = "0.14em"


def slug(url: str) -> str:
    """A filename for a project's card, derived from its URL."""
    s = url.rstrip("/").split("/")[-1]
    return re.sub(r"[^a-z0-9-]+", "-", s.replace(".html", "").lower()).strip("-")


def marks_from(page_path: pathlib.Path, viewbox: str) -> list[str]:
    """Lift the inline marks straight out of a built page, in document order."""
    text = page_path.read_text()
    found = re.findall(rf'<svg viewBox="{viewbox}".*?</svg>', text, re.S)
    if not found:
        sys.exit(f"no marks matching viewBox {viewbox!r} in {page_path} — build the site first")
    return found


def shell(body: str, extra_css: str = "") -> str:
    font64 = base64.b64encode(FONT.read_bytes()).decode()
    return f"""<!DOCTYPE html><meta charset="utf-8"><style>
@font-face {{ font-family:'Sorts Mill Goudy';
  src:url(data:font/woff2;base64,{font64}) format('woff2'); font-display:block; }}
/* The marks are lifted verbatim from the built site, and they paint their
   STRUCTURE -- street grids, chart baselines, the faint parcel of a choropleth
   -- with `stroke="var(--ink-faint)"`. Those custom properties have to exist
   here or every one of those strokes silently resolves to nothing and the mark
   loses half its drawing: the first run of this script produced a Metro
   Relocation card with a bare cross and no streets under it. Redeclaring the
   palette as properties is not duplication, it is the contract the lifted
   markup is written against. */
:root {{ --ink:{INK}; --ink-2:{INK_2}; --ink-faint:{INK_FAINT}; --bleed:{BLEED}; }}
*,*::before,*::after {{ box-sizing:border-box; }}
html,body {{ margin:0; padding:0; }}
body {{ width:{W}px; height:{H}px; background:{VOID}; color:{INK};
  font-family:'Sorts Mill Goudy',Georgia,serif; overflow:hidden;
  display:flex; flex-direction:column; padding:64px 72px 52px 72px; }}
/* The footer is the same device on every card, so a reader who has seen one
   recognises the next: a hairline, the name in tracked capitals, and one date
   or dek opposite it. The name is the single red element -- the same budget the
   site keeps, where red marks identity and nothing else. */
.foot {{ margin-top:auto; border-top:1px solid {INK_FAINT}; padding-top:26px;
  display:flex; justify-content:space-between; align-items:baseline; }}
.byname {{ font-size:25px; letter-spacing:{TRACK}; text-transform:uppercase; color:{BLEED}; }}
.bymeta {{ font-size:21px; letter-spacing:{TRACK}; text-transform:uppercase;
  color:{INK_2}; opacity:.55; }}
{extra_css}
</style>{body}"""


def project_card(mark_svg: str, title: str, blurb: str, date: str) -> str:
    # width/height are stripped off the lifted SVG so the CSS below can size it;
    # the viewBox carries the geometry, so nothing is distorted.
    mark = re.sub(r'\s(width|height)="[^"]*"', "", mark_svg, count=2)
    return shell(
        f"""<div class="row">
  <div class="markwrap">{mark}</div>
  <div class="text">
    <div class="title">{html.escape(title)}</div>
    <div class="blurb">{html.escape(blurb)}</div>
  </div>
</div>
<div class="foot"><span class="byname">Kevin V. Contino</span>
<span class="bymeta">{date}</span></div>""",
        f""".row {{ display:flex; gap:56px; align-items:center; flex:1 1 auto; min-height:0; }}
/* The mark is drawn at 40px on the projects index and at 240px here. It scales
   cleanly BECAUSE it is vector and stroke-light; the home page's denser figure
   marks would not survive the same jump. */
.markwrap {{ flex:0 0 240px; color:{INK_2}; }}
.markwrap svg {{ display:block; width:240px; height:240px; }}
.text {{ flex:1 1 auto; min-width:0; }}
.title {{ font-size:62px; line-height:1.12; color:{INK}; }}
.blurb {{ margin-top:22px; font-size:28px; line-height:1.42; color:{INK_2}; }}""",
    )


def site_card(marks: list[str], dek: str) -> str:
    row = "".join(re.sub(r'\s(width|height)="[^"]*"', "", m, count=2) for m in marks)
    return shell(
        f"""<div class="hero">
  <div class="name">Kevin V. Contino</div>
  <div class="dek">{html.escape(dek)}</div>
</div>
<div class="strip">{row}</div>
<div class="foot"><span class="byname">kvcontino.github.io</span>
<span class="bymeta">Maps &middot; Models &middot; Data</span></div>""",
        f""".hero {{ flex:0 0 auto; }}
/* The name IS the title here, so it takes the red the h1 takes on the site
   itself. On a project card the title is white and the byline is red instead --
   one red element either way. */
.name {{ font-size:96px; letter-spacing:{TRACK}; text-transform:uppercase;
  color:{BLEED}; line-height:1.05; }}
.dek {{ margin-top:26px; font-size:34px; color:{INK_2}; }}
.strip {{ margin-top:auto; margin-bottom:8px; display:flex; gap:44px; align-items:flex-end; }}
.strip svg {{ width:196px; height:124px; color:{INK_2}; opacity:.5; display:block; }}""",
    )


def main() -> None:
    if not SITE.exists():
        sys.exit("no _site/ — run `bundle exec jekyll build` first")

    projects = yaml.safe_load((ROOT / "_data" / "projects.yml").read_text())
    row_marks = marks_from(SITE / "_pages" / "presentations.html", "0 0 40 40")
    if len(row_marks) != len(projects):
        sys.exit(f"{len(row_marks)} marks vs {len(projects)} projects — rebuild the site")
    hero_marks = marks_from(SITE / "index.html", "0 0 120 76")

    dek = yaml.safe_load(
        re.search(r"^description:.*?(?=^\w)", (ROOT / "_config.yml").read_text(), re.S | re.M).group()
    )["description"].strip()

    jobs = [("site", site_card(hero_marks, dek))]
    for pr, mark in zip(projects, row_marks):
        if "://" in pr["url"]:
            print(f"  skip  {pr['title']} — lives in another repository")
            continue
        jobs.append((slug(pr["url"]),
                     project_card(mark, pr["title"], pr["blurb"].strip(), str(pr["date"]))))

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    tmp = OUT / "_card.html"

    with sync_playwright() as p:
        exe = next(iter(pathlib.Path("/home/contino/.cache/ms-playwright").glob(
            "chromium-*/chrome-linux64/chrome")), None)
        browser = p.chromium.launch(executable_path=str(exe) if exe else None)
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        for name, doc in jobs:
            tmp.write_text(doc)
            page.goto(tmp.as_uri())
            # The font is inlined as a data: URI, but layout still has to settle
            # before the screenshot or the type is measured against a fallback.
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(120)
            dest = OUT / f"{name}.png"
            page.screenshot(path=str(dest))
            print(f"  {dest.relative_to(ROOT)}  {dest.stat().st_size // 1024} KB")
        browser.close()

    tmp.unlink()
    print(f"\n{len(jobs)} cards at {W * SCALE}x{H * SCALE}. "
          f"Reference them with `image:` front matter (jekyll-seo-tag emits the tags).")


if __name__ == "__main__":
    main()
