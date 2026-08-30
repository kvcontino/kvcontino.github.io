#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.55.0"]
# ///
"""render-check.py — ask a real browser what a page actually looks like.

WHY THIS EXISTS
---------------
The headless recipe in `reference-playwright-headless` was hand-rebuilt THREE
times in one session: once to screenshot a page, once to probe computed CSS on
a hover state, once to measure a sidenote's clearance across five viewport
widths. Each time it was the same forty lines — launch with an explicit
executable_path, set a viewport, go, wait, evaluate — and each time the two
gotchas below had to be remembered from scratch. That is the argument
`mark-sheet.py` won, and it is the class of instruction that gets skipped on
the fifth use.

It also closes a real gap. Publishing returns a URL and says nothing about the
rendered result: a `::before`-is-a-grid-item bug shipped in TWO published
artifacts and was caught by a person, not by review. "The file was written" and
"it renders correctly" are different claims, and only the first was ever
checked.

THE TWO GOTCHAS, so they never have to be rediscovered
------------------------------------------------------
1. The pip `playwright` package pins a browser REVISION (1.53 -> 1179, 1.56 ->
   1194). This laptop's cache holds revision 1223, which no pip version maps
   to, so a plain `p.chromium.launch()` dies with "Executable doesn't exist".
   Passing `executable_path` bypasses the revision lookup entirely.
2. The binary is at `chrome-headless-shell-linux64/chrome-headless-shell`, NOT
   the `chrome-linux/headless_shell` path the error message suggests.

USAGE
  script/render-check.py URL --shot out.png
  script/render-check.py URL --width 1440 --hover .fn --css color,font-style
  script/render-check.py URL --widths 480,768,1024,1440 --measure .sidenote
  script/render-check.py URL --js "document.querySelectorAll('img').length"
  script/render-check.py URL --expect "Population Health"     # exit 1 if absent

A file path works as well as a URL; it is turned into file:// for you. Note
that a page fetching JSON will NOT work over file:// — serve it instead.

Exit 0 = every requested assertion held, 1 = something failed, 2 = could not run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SHELL = Path(
    "~/.cache/ms-playwright/chromium_headless_shell-1223"
    "/chrome-headless-shell-linux64/chrome-headless-shell"
).expanduser()


def as_url(target: str) -> str:
    if "://" in target:
        return target
    p = Path(target).expanduser().resolve()
    if not p.exists():
        sys.exit(f"no such file, and not a URL: {target}")
    return p.as_uri()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="URL, or a path to a local HTML file")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--widths", help="comma-separated widths to repeat the run at")
    ap.add_argument("--shot", help="write a full-page PNG here")
    ap.add_argument("--hover", help="CSS selector to hover before measuring")
    ap.add_argument("--css", help="comma-separated computed properties to report")
    ap.add_argument("--measure", help="CSS selector: report its box at each width")
    ap.add_argument("--js", help="JS expression to evaluate; its value is printed")
    ap.add_argument("--expect", action="append", default=[],
                    help="text that must appear in the rendered page (repeatable)")
    ap.add_argument("--wait", type=int, default=400,
                    help="ms to settle after load, for webfonts and late layout")
    a = ap.parse_args()

    if not SHELL.exists():
        print(f"headless shell not found at {SHELL}", file=sys.stderr)
        print("the cached revision may have changed; check ~/.cache/ms-playwright/",
              file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not importable — run this file directly so uv can "
              "resolve its inline deps", file=sys.stderr)
        return 2

    url = as_url(a.target)
    widths = [int(w) for w in a.widths.split(",")] if a.widths else [a.width]
    props = [p.strip() for p in a.css.split(",")] if a.css else []
    failures = []

    print(f"# {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=str(SHELL))
        try:
            for w in widths:
                page = browser.new_page(viewport={"width": w, "height": a.height})
                # Console errors are the single most useful thing a headless
                # run can report and the easiest to forget to collect.
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                        if m.type == "error" else None)
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(a.wait)

                print(f"\n=== {w}px ===")
                print(f"  title       {page.title()!r}")

                if a.hover:
                    el = page.query_selector(a.hover)
                    if not el:
                        failures.append(f"{w}px: --hover {a.hover} matched nothing")
                        print(f"  hover       {a.hover} MATCHED NOTHING")
                    else:
                        # elementFromPoint and computed styles both return
                        # nothing useful for content outside the viewport.
                        el.scroll_into_view_if_needed()
                        el.hover()
                        page.wait_for_timeout(150)
                        print(f"  hover       {a.hover}")

                if props:
                    sel = a.hover or a.measure
                    if not sel:
                        failures.append("--css needs --hover or --measure to say WHAT")
                    else:
                        vals = page.eval_on_selector(sel, """(el, ps) => {
                            const cs = getComputedStyle(el);
                            return Object.fromEntries(ps.map(p => [p, cs.getPropertyValue(p)]));
                        }""", props)
                        for k, v in vals.items():
                            print(f"  css         {k}: {v.strip()}")

                if a.measure:
                    boxes = page.eval_on_selector_all(a.measure, """els => els.map(el => {
                        const r = el.getBoundingClientRect();
                        return {x: Math.round(r.x), y: Math.round(r.y),
                                w: Math.round(r.width), h: Math.round(r.height),
                                text: (el.textContent || '').trim().slice(0, 40)};
                    })""")
                    if not boxes:
                        failures.append(f"{w}px: --measure {a.measure} matched nothing")
                        print(f"  measure     {a.measure} MATCHED NOTHING")
                    for i, b in enumerate(boxes[:8]):
                        print(f"  measure[{i}]  x={b['x']:>5} y={b['y']:>5} "
                              f"w={b['w']:>4} h={b['h']:>4}  {b['text']!r}")
                    if len(boxes) > 8:
                        print(f"  measure     ...and {len(boxes)-8} more")

                if a.js:
                    print(f"  js          {json.dumps(page.evaluate(a.js), default=str)}")

                if a.expect:
                    body = page.inner_text("body")
                    for want in a.expect:
                        ok = want in body
                        print(f"  expect      {'ok  ' if ok else 'MISS'} {want!r}")
                        if not ok:
                            failures.append(f"{w}px: expected text not rendered: {want!r}")

                if errors:
                    print(f"  ERRORS      {len(errors)}")
                    for e in errors[:5]:
                        print(f"    {e[:140]}")
                    failures.append(f"{w}px: {len(errors)} page/console error(s)")

                if a.shot:
                    out = Path(a.shot)
                    if len(widths) > 1:
                        out = out.with_name(f"{out.stem}-{w}{out.suffix}")
                    page.screenshot(path=str(out), full_page=True)
                    print(f"  shot        {out}")
                page.close()
        finally:
            browser.close()

    print()
    if failures:
        for f in failures:
            print(f"  FAIL  {f}")
        return 1
    print("  all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
