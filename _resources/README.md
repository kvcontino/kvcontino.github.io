# `_resources/`

This directory is two things at once: the URL path for published analysis
work (`_resources/onecare/`, `_resources/metro-relocation/`, the NNY maps,
`nny-toponyms`), and the place scripts and data end up because that's where
the pages citing them already live.

**Policy: a file belongs here only if some published page links to it or
names it.** If nothing on the site points at a script or a data file, it
isn't documentation for a reader — it's a working file that drifted into a
public directory, and it belongs in a scratch or tools location outside this
repo instead.

This exists because the question "does this unlinked script belong here?"
kept getting re-asked case by case (`build-nny-population.py`,
`build-vermont-population.py` were the recurring examples) with no written
answer to point to. If a new orphaned file shows up, check whether a page
actually cites it before leaving it in place.
