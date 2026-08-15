#!/usr/bin/env python3
"""Read an HTML page on this site as prose.

    script/prose.py PAGE                 per-section word counts
    script/prose.py PAGE PATTERN         one section, as plain text
    script/prose.py PAGE --all           the whole page, as plain text

PATTERN is a case-insensitive substring of an <h2>; "four cents" finds
"Four cents on the dollar".

Why this exists: the project pages in _resources/ are hand-written HTML with
prose hard-wrapped inside the tags, so the file is hard to read as writing and
`wc -w` counts markup as words. This strips the markup and keeps the shape.

Figures and tables are not narrative, so word counts exclude them.  When
printing a section they appear as [FIGURE] with the caption (captions ARE
editable prose) and [TABLE] as a placeholder.
"""

import html
import re
import sys
import textwrap

# Tags that end a block of prose.  Substituting a blank line here is what
# preserves paragraph breaks once the tags themselves are gone.
BLOCK_END = re.compile(r"</(p|h3|h4|li|figcaption|blockquote)>", re.I)

# Non-narrative blocks.  re.S ("dotall") lets `.` match newlines, which it does
# not by default — without it these patterns stop at the first line break.
FIGURE = re.compile(r"<figure.*?</figure>", re.S | re.I)
TABLE = re.compile(r"<table.*?</table>", re.S | re.I)
CAPTION = re.compile(r"<figcaption>(.*?)</figcaption>", re.S | re.I)


def detag(s):
    """Markup out, HTML entities in (&middot; -> ·, &amp; -> &)."""
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def wordcount(s):
    return len(detag(FIGURE.sub(" ", TABLE.sub(" ", s))).split())


def split_front_matter(src):
    """Jekyll front matter is a --- fenced YAML block at the very top."""
    m = re.match(r"\A---\n.*?\n---\n", src, re.S)
    return src[m.end():] if m else src


def sections(src):
    """[(level, heading, html), ...].  Level 0 is the text before the first heading.

    Splits on h2 and h3 both, so a subsection gets its own line in the counts
    and can be matched by name.  \\1 is a backreference — it forces the closing
    tag to be the same one that opened, so </h3> cannot close an <h2>.
    """
    # Capturing groups in a split pattern keep what they matched in the result,
    # so the list runs [before, tag, head, body, tag, head, body, ...]
    parts = re.split(r"<(h[23])[^>]*>(.*?)</\1>", src, flags=re.S)
    out = [(0, None, parts[0])]
    out += [(int(parts[i][1]), detag(parts[i + 1]).strip(), parts[i + 2])
            for i in range(1, len(parts), 3)]
    return out


def flatten(chunk):
    """Section HTML -> wrapped plain text."""

    def as_caption(m):
        cap = CAPTION.search(m.group(0))
        body = detag(cap.group(1)).strip() if cap else "(no caption)"
        return "\n\n[FIGURE] " + body + "\n\n"

    chunk = FIGURE.sub(as_caption, chunk)
    chunk = TABLE.sub("\n\n[TABLE]\n\n", chunk)
    chunk = BLOCK_END.sub("\n\n", chunk)
    chunk = detag(chunk)

    out = []
    for para in re.split(r"\n\s*\n", chunk):
        para = " ".join(para.split())          # collapse the hard wrapping
        # detag() leaves a space where each tag was, which is right between
        # words but wrong before punctuation ("at its peak ." from a link).
        para = re.sub(r"\s+([,.;:!?%)\]])", r"\1", para)
        para = re.sub(r"([(\[])\s+", r"\1", para)
        if para:
            out.append(textwrap.fill(para, width=84))
    return "\n\n".join(out)


def main(argv):
    if not argv:
        sys.exit(__doc__)

    path, pattern = argv[0], (argv[1] if len(argv) > 1 else None)
    with open(path) as fh:
        src = split_front_matter(fh.read())
    found = sections(src)

    if pattern is None:                                   # counting mode
        total = 0
        for level, head, body in found:
            n = wordcount(body)
            total += n
            indent = "    " if level == 3 else ""
            print(f"{n:>6}  {indent}{head or '(opening)'}")
        print(f"{total:>6}  TOTAL  ({path}, figures and tables excluded)")
        return

    if pattern == "--all":
        hits = found
    else:
        needle = pattern.lower()
        hits = [(l, h, b) for l, h, b in found if h and needle in h.lower()]
        if not hits:
            sys.exit(f"no heading matching {pattern!r} in {path}")

    for level, head, body in hits:
        if head:
            rule = "-" if level == 2 else "·"
            print(f"\n{'#' * level} {head}\n" + rule * (len(head) + level + 1))
        text = flatten(body)
        if text:
            print(text)


if __name__ == "__main__":
    main(sys.argv[1:])
