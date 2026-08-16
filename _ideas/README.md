# _ideas

Project seeds and scratch material. **Not** Jekyll content.

These files lived in `_drafts/` until 2026-08-03. That was a mistake: `_drafts/`
is a Jekyll collection, so every file in it is parsed as a post, and files
without YAML front matter — `.py`, `.jsx`, `.m3u`, raw `.html` — broke
`jekyll build --drafts` outright. Moving them here fixes that, because Jekyll
ignores directories whose names start with `_` unless they are listed under
`include:` in `_config.yml`. This one deliberately is not.

Nothing in here is published. `_drafts/` now holds only real drafts.

| Path | What it is |
|---|---|
| `medicaid-fraud-monitor/` | Redshift-based fraud-detection pipeline for Medicaid managed care: 7 SQL rules, composite provider risk scoring, Excel/Tableau export. `README.md` is its own documentation. |
| `architecture-diagrams/` | Three React components rendering interactive layer diagrams. Two are Medicaid claims-flow architectures (one generic, one California Medi-Cal); the third is a server dashboard mockup. Uploaded 2026-04-05. |
| `wu-wei/` | The "Grain and Pivot" essay — outline plus a standalone HTML draft. |
| `radio_kevin.m3u` | Playlist. |
| `post-template.md` | Skeleton front matter and component reminders for a new post. Its `date: YYYY-MM-DD` is an intentional placeholder — harmless here, but it is what broke the draft build while this file sat in `_drafts/`. |

## To do

*(The post index and the visible subscribe link that used to head this list are
both done: `posts.html` iterates `site.posts` and honours `draft: true`, and as
of 2026-08-16 the feed is advertised from the nav on every page, from a
`.subscribe` block on the index, and from one line on `/posts/`.)*

**Rewrite `_posts/2018-04-05-populationhealth.markdown` as a critique of
population health as an idea.** Not a copy-edit of the 2018 post: a reversal of
it. Held back from the feed and from `/posts/` with `draft: true`, so there is
no hurry and nothing is advertising it in the meantime. The missing
`description:` is not worth writing until the argument is settled, since the
blurb should describe the critique rather than the original.
