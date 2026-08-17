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

**Publish the NoVA walksheds map as a project.** A barrier-aware WMATA
walk-time Leaflet map, built 2026-07-21, living at
`~/2_projects/relocation/deep_dives/` — `NoVA Walksheds Version A` is finished,
`nova_walksheds_version_b` is scaffolded. The repository is local-only, so
nothing is published yet. This is the shortest path from existing work to a new
Projects entry: it is finished, it is visual, and it is geographic. It would
reuse the `catchment` mark, or earn one of its own if the isochrone form is
different enough on the page.

**Write up the RSS reconstruction as a post.** `~/2_projects/rss/` — three
phases done: topic-first categories, paywall triage, crawler-only-on-create,
quality tiers applied 2026-08-04. Rebuilding an information diet deliberately
is a subject almost nobody writes about concretely, and it is the natural
companion piece to the Personal Media Audit, whose blurb is now "Staving off
infobesity."

**Write up the browser audit as a *method* post, not a data post.**
`~/2_projects/browser_audit/` holds full Firefox browsing history, is mode
`700`, and is deliberately not git-backed — none of it gets published. What is
publishable is the method plus the structural finding that the dwell data
expires around four months, which is why the `data/history/` archives are the
real record rather than the live database. The interesting claim survives
without exposing anything.
