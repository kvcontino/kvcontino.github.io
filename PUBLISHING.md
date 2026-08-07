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
| wide table or figure | wrap in `<div class="tablewrap" markdown="1">` | `markdown="1"` is required or the markdown inside is not parsed |

Never letterspace lowercase. Full rationale is in `_stylesheets/lite.css`.

---

## Publish

```fish
git add _posts/2026-08-03-my-post.markdown
git commit -m "Publish \"My Post\""
git push origin master          # master deploys; there is no staging
```

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

**Do not hand-edit** `_resources/onecare/` or `_resources/metro-age-structure/`.
They are generated by `make site` upstream; edits here are overwritten. Fix them
in their pipeline.

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
