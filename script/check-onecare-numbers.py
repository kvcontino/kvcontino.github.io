#!/usr/bin/env python3
"""check-onecare-numbers.py — find numbers in the OneCare prose that no manifest blesses.

WHY THIS EXISTS
---------------
Every stale-number incident in this project has had the same shape: the essay
was updated, a supporting page was not. Four ACO-penetration figures stayed
keyed to a retired donor pool. The MDE "$394 actual gap" was really the
post-RMSPE. Two numbers in fig2's ALT TEXT went stale and were invisible to
every review, because nobody reads alt text.

The estimates all live in JSON manifests. The prose is written by hand. Nothing
connects them, so drift is silent and is only ever caught by a person
remembering a number.

WHAT IT CHECKS, and what it deliberately does not
-------------------------------------------------
It cannot know that a given sentence means a given manifest key -- prose has no
keys. So it asks the weaker question that still catches the whole failure class:

    does this number appear ANYWHERE in the manifests?

A number in the prose that matches no manifest value is either stale, or one of
the many numbers that legitimately are not model output (years, counts of
tables, footnote markers). The second group is filtered by shape, not by
guessing at meaning:

  * years 1900-2100, and 4-digit numbers generally
  * bare integers under 100 -- section numbers, counts, footnote markers
  * anything inside <code>, <script>, <style>, or an href/src

What survives is the interesting set: dollar amounts, percentages, p-values,
and decimals -- exactly the shapes a model produces.

Numbers sitting next to a SOURCE CITATION (CDC, VSRR, NORC, Census, "per
100,000", "national rate") are counted but not failed on. Those are somebody
else's statistics; they will never be in a manifest, and failing on them is how
a check earns a reputation for crying wolf and stops being read.

A hit is a QUESTION, not a verdict. A number can be correctly derived from two
manifest values (a difference, a sum) and legitimately appear nowhere. Read the
list; do not gate a build on it blindly.

ALT TEXT IS CHECKED, and reported separately, because that is where the last
two incidents hid.

USAGE
  script/check-onecare-numbers.py
  script/check-onecare-numbers.py --show-blessed   # what the manifests carry
Exit 0 = every prose number is accounted for, 1 = findings.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "_resources" / "onecare"
PAGES = [RES / "index.html", RES / "methodology.html", RES / "data" / "index.html"]
MANIFEST_DIR = RES / "data"

# Shapes a model produces. A number matching none of these is page furniture.
INTERESTING = re.compile(r"""
    (?:\$\s?-?\d[\d,]*(?:\.\d+)?)         # $1,234  $394  $-801.18
  | (?:-?\d[\d,]*\.\d+)                   # any decimal
  | (?:-?\d[\d,]*\s?%)                    # 45.5%   12 %
  | (?:\bp\s?[=<>]\s?\.?\d+(?:\.\d+)?)    # p=0.10  p<.05
""", re.X)

STRIP_TAGS = re.compile(r"(?is)<(script|style|code|pre)\b.*?</\1>")
ALT_ATTR = re.compile(r'\balt\s*=\s*"([^"]*)"', re.I)
TAG = re.compile(r"<[^>]+>")


# A number sitting next to a source citation is somebody else's statistic, not
# this model's output, and it will never be in a manifest. Flagging those as
# suspect is how a check earns a reputation for crying wolf.
CITED_NEAR = re.compile(
    r"(?i)\b(VSRR|CDC|NORC|Census|BLS|KFF|GMCB|CMS|NCHS|OECD|per 100,000|"
    r"national rate|United States|peers?|regional|Hampshire|Maine|source)\b")


def numbers_in(text: str):
    """-> {normalised: (original token, context, looks_externally_cited)}."""
    out = {}
    for m in INTERESTING.finditer(text):
        tok = m.group(0)
        n = normalise(tok)
        if n is None:
            continue
        lo, hi = max(0, m.start() - 90), min(len(text), m.end() + 90)
        ctx = re.sub(r"\s+", " ", text[lo:hi]).strip()
        # Keep the FIRST occurrence; later ones are usually restatements.
        if n not in out:
            out[n] = (tok, ctx, bool(CITED_NEAR.search(ctx)))
    return out


def normalise(tok: str):
    """'$1,234.50' / '45.5%' / 'p=0.10' -> a comparable float string, or None."""
    s = tok.replace(",", "").replace("$", "").replace("%", "").strip()
    s = re.sub(r"(?i)^p\s*[=<>]\s*", "", s).strip()
    if s.startswith("."):
        s = "0" + s
    try:
        v = float(s)
    except ValueError:
        return None
    # Years and small bare integers are page furniture, not estimates.
    if v == int(v):
        iv = int(abs(v))
        if 1900 <= iv <= 2100 or iv < 100:
            return None
    return f"{v:.6g}"


def walk_json(o):
    """Every scalar number anywhere in a nested structure."""
    if isinstance(o, dict):
        for v in o.values():
            yield from walk_json(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk_json(v)
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)):
        yield float(o)
    elif isinstance(o, str):
        # Manifests carry numbers inside prose fields too (notes, labels).
        for m in INTERESTING.finditer(o):
            n = normalise(m.group(0))
            if n is not None:
                yield float(n)


def _bless(vals: set, v: float) -> None:
    """Add every reading of one manifest value that prose might legitimately use."""
    vals.add(f"{v:.6g}")
    # A share may be stored as 0.456 and written as 45.6%, or the reverse.
    vals.add(f"{v * 100:.6g}")
    vals.add(f"{v / 100:.6g}")
    # Display rounding is not drift.
    for nd in (0, 1, 2):
        vals.add(f"{round(v, nd):.6g}")
        vals.add(f"{round(v * 100, nd):.6g}")


def blessed_values() -> tuple[set, int]:
    vals, files = set(), 0
    for p in sorted(MANIFEST_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception as e:
            print(f"  could not parse {p.name}: {e}", file=sys.stderr)
            continue
        files += 1
        for v in walk_json(d):
            # Bless the ABSOLUTE value too. The prose writes a negative as
            # "&minus;$482": the sign is an HTML entity OUTSIDE the numeric
            # token, so the scanner reads 482 while the manifest holds -482,
            # and every negative estimate in the robustness tables came back a
            # false positive. Sign drift is not what this hunts; a magnitude
            # that exists nowhere any more is.
            _bless(vals, v)
            _bless(vals, abs(v))
    return vals, files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show-blessed", action="store_true")
    a = ap.parse_args()

    if not RES.exists():
        print(f"no {RES} — nothing to check")
        return 0

    vals, nfiles = blessed_values()
    print(f"\n=== manifests ===")
    print(f"  {nfiles} file(s), {len(vals):,} blessed values "
          f"(including rounded and percent/share readings)")
    if a.show_blessed:
        for v in sorted(vals, key=lambda x: abs(float(x)))[:60]:
            print(f"    {v}")
        return 0

    bad = 0
    for page in PAGES:
        if not page.exists():
            continue
        raw = page.read_text(encoding="utf-8", errors="replace")
        alts = " ".join(ALT_ATTR.findall(raw))
        body = STRIP_TAGS.sub(" ", raw)
        # Drop attributes wholesale EXCEPT alt, which we harvested above --
        # hrefs and inline styles are full of numbers that mean nothing here.
        body = TAG.sub(" ", body)

        rel = page.relative_to(ROOT)
        print(f"\n=== {rel} ===")
        for label, text in (("prose", body), ("ALT TEXT", alts)):
            found = numbers_in(text)
            orphans = [n for n in found if n not in vals]
            external = [n for n in orphans if found[n][2]]
            unattributed = sorted((n for n in orphans if not found[n][2]),
                                  key=lambda x: -abs(float(x)))
            print(f"  {label:<9} {len(found):>4} numeric claim(s); "
                  f"{len(orphans)} not in a manifest "
                  f"({len(external)} next to a source citation, "
                  f"{len(unattributed)} unattributed)")
            for n in unattributed[:20]:
                tok, ctx, _ = found[n]
                print(f"      {tok:>12}   ...{ctx[:88]}...")
            if len(unattributed) > 20:
                print(f"      ...and {len(unattributed) - 20} more unattributed")
            # Only the UNATTRIBUTED ones are worth failing on. A number quoted
            # from CDC or NORC is correctly absent from this model's manifests,
            # and treating it as a finding is how the check gets ignored.
            if unattributed:
                bad = 1

    print("\n=== verdict ===")
    if bad:
        print("  numbers above appear in the prose but in no manifest.")
        print("  Each is a QUESTION: stale value, or legitimately derived")
        print("  (a difference or sum of two manifest values)? Check, do not assume.")
        return 1
    print("  every manifest-shaped number in the prose is carried by a manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
