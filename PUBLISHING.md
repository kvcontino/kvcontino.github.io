# Publishing this site

Quick reference for `kvcontino.github.io`. Not published — excluded in
`_config.yml`. Companion to `~/cheatsheet.md` (general CLI) and the memory notes
`project-kvcontino-site`, `feedback-typography-conventions`.

---

## Preview

Opening a file from the file manager shows **nothing** — no layout, no styling.
Two reasons, both fundamental: a source file's front matter is unprocessed until
Jekyll builds it, and `/_stylesheets/lite.css` is a root-absolute path that
`file://` resolves against the top of your disk. A static site needs a server.

```fish
cd ~/2_projects/kvcontino.github.io
bundle exec jekyll serve --host 127.0.0.1 --port 4000 --livereload
```

Then <http://127.0.0.1:4000>. Leave it running while you write; it rebuilds and
refreshes the browser on every save.

- `jekyll build` writes `_site/` and exits. `jekyll serve` builds, serves, watches.
- A rebuild **wipes anything hand-copied into `_site/`**. The typography specimen
  lives in `_ideas/`, which Jekyll ignores, so previewing it needs
  `cp _ideas/typography-specimen.html _site/` after each build.

---

## Writing a post

```fish
script/new-post.fish "Post Title"
```

Creates `_posts/YYYY-MM-DD-slug.markdown` with front matter and opens it in
Obsidian. It keeps the **filename date and the `date:` field in step** — they
must agree, because Jekyll takes the URL date from the filename, and fixing a
published URL is expensive.

### Front matter

```yaml
---
title:  "Gems from the Vault"
date:   2026-08-03 09:00:00 -0400
layout: default
categories: notes          # sets the URL: /notes/YYYY/MM/DD/slug.html
description: "One line."   # blurb on /posts/, and what RSS + search show
---
```

- **Always set `description:`.** It is the only summary readers see before clicking.
- **`draft: true`** publishes the page at its URL but keeps it out of `/feed.xml`
  *and* `/posts/`. Good for something to link privately before announcing.
  Only safe on a post with an explicit `categories:` — it also flips Jekyll's own
  draft handling, which would otherwise change the permalink.

#### Keeping a post out of search

`draft: true` is not enough on its own. Hiding a post is three separate asks,
each with its own switch, because each is enforced by a different thing:

| ask | switch | enforced by |
|---|---|---|
| **unlinked** — not in `/posts/` or `/feed.xml` | `draft: true` | `jekyll-feed` + `posts.html` |
| **unlisted** — not in `sitemap.xml` | `sitemap: false` | `jekyll-sitemap` |
| **unindexed** — Google won't index it even if it finds the URL | `noindex: true` | `_layouts/default.html` |

A sitemap is a *suggestion* about what to crawl, not a fence. Leave off
`noindex:` and the post is still indexable the moment anyone follows a link to
it — which is exactly what you do when you "link it privately." Set all three,
and remove all three to publish for real. `_posts/2018-04-05-populationhealth.markdown`
is the worked example.

`noindex:` works on any page using this layout, not just posts.

### Write directly, no help needed

Prose, headings, **bold**, *italic*, links, lists, blockquotes, and markdown
tables. Tables are styled automatically — `.tablewrap table` matches alongside
`table.data`, so a plain markdown table gets small-caps column heads, rules and
lining figures with no extra markup.

### Ask Claude for

Figures with captions, `.note` asides, small caps on proper names, anything
using raw HTML. **If you hand-write HTML in a post, have the tag balance checked
before publishing** — an unclosed `<div>` silently swallows the rest of the page,
and Obsidian's preview does not show it.

```fish
# the check itself
python3 -c "
s=open('_posts/FILE.markdown').read()
for t in ('div','p','figure'):
    print(t, s.count('<'+t), s.count('</'+t+'>'))"
```

### House style

| device | markup | rule |
|---|---|---|
| proper name, first mention | `<span class="sc">Name</span>` | debut only; plain thereafter |
| term of art | `<span class="term">word</span>` | italic every time |
| its first appearance | `<span class="term debut">word</span>` | italic **and** red, once |
| inline capitals | `<span class="caps">text</span>` | tracked |
| aside | `<div class="note">…</div>` | red rule at the left |
| wide table or figure | wrap in `<div class="tablewrap">` | see the warning below about `markdown="1"` |
| link out to a project | `<a class="mark">` + inline SVG inside `<div class="marks">` | four-up grid, two-up under 600px |
| subscribe block | `<p class="subscribe">` | one per page at most; the nav already carries **Feed** |

Never letterspace lowercase. Full rationale is in `_stylesheets/lite.css`.

> **Inline SVG inherits the page's CSS, including the parts you did not want.**
> The career figure on `index.html` is hand-written SVG so that it picks up
> Sorts Mill Goudy and resolves `var(--ink)` — but it also inherited
> `.content`'s `word-spacing: 0.12em`, which font metrics cannot see, and the
> longest label overran the viewBox and was clipped mid-letter. Any SVG text
> sized from font metrics needs `word-spacing: normal`.
>
> Note also that `check-site.sh` strips `<svg>` blocks before its glyph scan,
> so **text inside inline SVG is not covered by it**. The font has no arrows and
> no geometric shapes; keep SVG text to letters, digits and the middot, and draw
> any mark as a path.

> **`markdown="1"` only works inside a Markdown document.** It is a kramdown
> feature, and kramdown never runs on a `.html` file — so a markdown table
> inside a `<div markdown="1">` on an HTML page renders as literal `|` pipes.
> Posts (`.markdown`) are fine. On an HTML project page, write real
> `<table>` markup, or better, ask whether the thing is a table at all: an
> ordered process is an `<ol class="stages">`, and a handful of headline
> numbers is a `.statrow`.

---

## Publish

```fish
git add _posts/2026-08-03-my-post.markdown
git commit -m "Publish \"My Post\""
git push origin master          # master deploys; there is no staging
```

> **"The deploy looks broken" is usually a stale stylesheet, not a bad build.**
> Pages serves `lite.css` with `cache-control: max-age=600`, so for up to ten
> minutes a browser or a CDN edge can pair **new HTML with the old CSS**. Inline
> SVG degrades violently under that mismatch rather than merely looking
> unstyled: on 2026-08-16 the front page's marks rendered at 1024×648 instead of
> 160×101, and the career timeline's bars fell back to `fill: black` on a black
> page and vanished, leaving a blank gap under a heading.
>
> `_layouts/default.html` now appends `?v={{ site.time | date: '%s' }}` to the
> stylesheet URL, which changes every build, so this cannot recur. **Before
> assuming a build is bad, diff the live files against local** — that is what
> settles it in one step:
>
> ```fish
> diff (curl -s https://kvcontino.github.io/_stylesheets/lite.css | psub) _stylesheets/lite.css
> curl -sI https://kvcontino.github.io/_stylesheets/lite.css | grep -i cache-control
> ```
>
> To reproduce what a reader with a stale cache sees, serve the previous
> stylesheet against the live HTML with Playwright's `context.route()`.

**A green `git push` does not mean the site updated.** Publishing is two stages:
`build` (Jekyll → artifact) and `deploy` (artifact → CDN). Deploy can fail on
its own, and when it does the *previous* version keeps serving — so the site
looks healthy and simply shows stale content.

```fish
gh run list --limit 3                                   # is the latest run red?
gh run view <id> --json jobs --jq '.jobs[]|{name,conclusion}'   # which job
gh run view <id> --log-failed | tail -20                # the actual error
```

Normal end-to-end is **under a minute**. If `deploy` sits in `deployment_queued`
and dies at ~10 minutes, that is GitHub not allocating a runner — it does not
show on githubstatus.com, re-running does not help, and neither does a new
commit. Wait and retry later.

---

## Who is reading this

Two separate things, answering two different questions.

**Google Search Console** — *are people finding it?* Impressions, clicks, and
the queries people actually searched, which no on-page script can see because
it happens before the visit. Ownership is the `webmaster_verifications:` key in
`_config.yml`, emitted into every page by `jekyll-seo-tag`.

DNS verification is impossible here and always will be: `github.io` is GitHub's
zone, so there is no DNS record you can add. If Search Console offers a *Domain
property*, it is the wrong kind — you need a **URL prefix** property verified by
HTML tag.

**GoatCounter** — *what happened after the click?* Dashboard at
<https://kvcontino.goatcounter.com>. No cookies and no personal data, so no
consent banner is owed. `count.js` skips localhost, so `jekyll serve` previews
are not counted. Anyone blocking scripts is not counted either; treat the
numbers as a floor, not a census.

### The snippet lives in three places, and that is the thing to remember

| pages | how they get it |
|---|---|
| anything using `_layouts/default.html` | free, nothing to do |
| standalone project pages in `_resources/` | **their own copy**, before `</body>` |
| `metro-age-structure/interactive_map.html` | injected by `src/site.py` upstream |

The middle row is the trap. A new project page in `_resources/` written as a
full standalone document inherits nothing, and there is no error — it just
quietly never appears in the stats. **If you add one, paste the snippet in
before `</body>`.** The five existing ones each carry a copy.

The third row is its own case because the file is generated: `src/site.py`
inserts the snippet before `</body>` as it copies, and refuses to publish if
the file's shape changes or if it already carries one. Do not hand-edit the
published copy — fix it in the pipeline, then re-run `make site`.

> That page was a bare *fragment* until 2026-08-15 — a `<style>` block, markup
> and a `<script>` with no `<html>`/`<head>`/`<body>` at all, served directly
> and left to the browser to wrap. It now emits a real document with a
> `<title>` and a description, which is what makes it a usable search result
> rather than a URL.

```fish
# which published pages are NOT counted? (want: none)
bundle exec jekyll build --quiet
grep -rL goatcounter _site --include=*.html
```

---

## Structure

| path | what |
|---|---|
| `index.html` | About |
| `posts.html` | `/posts/` index — honours `draft: true` |
| `_posts/` | blog posts; **filename date is load-bearing** |
| `_pages/presentations.html` | Projects list — hand-maintained |
| `_resources/<slug>/` | standalone project pages |
| `_ideas/` | scratch, to-do list, typography specimen — **Jekyll ignores this** |
| `_drafts/` | a real Jekyll collection: every file is parsed as a post. Put scratch in `_ideas/`, never here |
| `_stylesheets/lite.css` | the whole theme, with rationale in comments |
| `assets/fonts/` | self-hosted Sorts Mill Goudy — **do not replace with Google Fonts**, their subset drops small caps |

**Posts vs Projects.** A post is short — a thought, a chart, a note. A project is
larger, ongoing, curated, and lives in `_resources/`.

**`_resources/metro-age-structure/` is mixed**, per file, and the old blanket
"this directory is generated" rule was wrong:

| file | authored where |
|---|---|
| `report.md`, `manifest.md`, `figures/`, `interactive_map.html` | **generated** by `src/site.py` in `~/2_projects/metro_age_structure/` — edits here are overwritten |
| `index.html` | **hand-written here.** `site.py` never writes it |

Regenerate the report alone with `.venv/bin/python -m src.report` then
`src.site.publish_report()`. **Not `make site`** unless you mean it: that
re-renders all eight figures and dirties every SVG with a fresh timestamp and
new random clip-path ids even when nothing changed.

The GoatCounter injection guard belongs to `interactive_map.html` specifically —
`site.py` inserts the snippet as it copies and refuses to publish if the file's
shape changes or if it already carries one.

**`_resources/onecare/` is mixed**, and the line matters:

| part | authored where |
|---|---|
| `figures/*.svg` | **generated** by `_resources/onecare/build_figures.py`, off `data/results_manifest.json` (built upstream by `analysis/build_results.py` in `~/2_projects/onecare_retrospective/`) |
| `index.html`, `methodology.html` | **hand-written here.** Prose, `<figcaption>`, and `alt=` are all editable in place |

So a narrative pass runs no pipeline and touches one file. Two things do cross
the line: text *inside* a plot is glyph-pathed into the SVG (not greppable, not
editable as text — it needs a rebuild), and every number in the prose is
answerable to `data/results_manifest.json`.

```fish
# read a section as plain text, or count words section by section
script/prose.py _resources/onecare/index.html
script/prose.py _resources/onecare/index.html "four cents"
```

Read prose diffs by word, not by line — rewrapping a paragraph makes a line
diff useless:

```fish
git diff --word-diff=color -- _resources/onecare/index.html
```

**`assets/css/style.scss` is deliberately empty.** It overrides the
github-pages gem's injected default theme, which otherwise publishes 136 KB of
unused CSS. Do not delete it.

---

## Gotchas

- **Obsidian autosaves continuously.** If Claude edits a file you have open, one
  of you loses. Close it, or say which file you are in.
- **`.obsidian/` is gitignored** — vault config, not site content.
- After changing `lite.css`, look at `_ideas/typography-specimen.html` first.
  Every device the stylesheet offers appears there exactly once.
- `grep -c` counts matching **lines**, not occurrences. Use `grep -o … | wc -l`
  when the number is the point.
