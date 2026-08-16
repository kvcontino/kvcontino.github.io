"""Build the OneCare essay's figures as opaque, dark-theme SVGs that sit
directly on kvcontino.github.io's black page. Self-contained: reads ./data,
writes ./figures.

Three conventions, each of which the essay depends on:

  * ONE PANEL PER ROW. Panels stack vertically, so a figure is portrait and
    sits at the page's text measure, sharing both edges with the prose. Side
    by side, the panels made every figure wider than the column it explained.
  * RED SUBJECT, WHITE COMPARATORS. Vermont is the site's --ember red and every
    comparator is near-white, so the series separate by lightness rather than
    hue. See the palette note below for the measured colour-blindness numbers.
  * NO TITLE PROSE IN THE IMAGE beyond the title and the panel titles. The
    standfirst lives in the HTML <figcaption>, where it is selectable, reflows,
    and is set in the page's own type rather than baked into a picture.

Text is set in Sorts Mill Goudy, the site face, with lining figures frozen in;
that means the figures are subject to its glyph coverage, which is narrow.
script/check-site.sh reads the string literals in this file and fails on any
character the font lacks, because a missing glyph here becomes a .notdef box
baked into the image where no HTML check can see it.

Run:  python3 build_figures.py
      ONECARE_PREVIEW=<dir> python3 build_figures.py   # PNGs for eyeballing
"""

import json
import os
import tempfile
import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# Set ONECARE_PREVIEW=<dir> to render opaque PNGs on the site's black background
# for eyeballing (the shipped SVGs are transparent to sit on the live page).
PREVIEW = os.environ.get("ONECARE_PREVIEW")

# ---- site typeface ----------------------------------------------------------
# The page is set in Sorts Mill Goudy, so the figures are too. Two obstacles, both
# handled here rather than by hand:
#
#   1. The repo ships the font as .woff2, a web-only container. FreeType — and so
#      matplotlib — cannot read it. fontTools decompresses it to a plain TTF.
#   2. The font's DEFAULT figures are old-style: varying height, with descenders
#      on 3/4/5/7/9. That is correct in running prose and wrong on an axis, where
#      digits should align on one baseline at one height. A lining set exists, but
#      only behind the OpenType `lnum` feature, and matplotlib applies no OpenType
#      features at all. So freeze the feature: read lnum's substitution map out of
#      GSUB and repoint the cmap at the .lining glyphs, making lining figures this
#      build's default. lite.css does the same job on the page with
#      `font-variant-numeric: lining-nums` on tables and .num.
#
# If fontTools is missing the build still runs, in the previous sans-serif, and
# says so — a figure rebuild should never be blocked by a font dependency.
FONT_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "assets", "fonts", "SortsMillGoudy-Regular.woff2")
FONT_FAMILY = "sans-serif"


def _lining_ttf(src):
    """woff2 -> TTF with the `lnum` feature frozen in. Cached in the temp dir."""
    from fontTools.ttLib import TTFont

    out = os.path.join(tempfile.gettempdir(), "SortsMillGoudy-Lining.ttf")
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src):
        return out
    f = TTFont(src)
    f.flavor = None                      # drop woff2 compression
    sub = {}
    gsub = f["GSUB"].table
    for rec in gsub.FeatureList.FeatureRecord:
        if rec.FeatureTag == "lnum":
            for i in rec.Feature.LookupListIndex:
                for st in gsub.LookupList.Lookup[i].SubTable:
                    sub.update(getattr(st, "mapping", {}))
    for table in f["cmap"].tables:       # repoint every cmap subtable
        for cp, glyph in list(table.cmap.items()):
            if glyph in sub:
                table.cmap[cp] = sub[glyph]
    f.save(out)
    return out


try:
    _ttf = _lining_ttf(FONT_SRC)
    fm.fontManager.addfont(_ttf)
    FONT_FAMILY = fm.FontProperties(fname=_ttf).get_name()
except Exception as exc:                 # noqa: BLE001 - any failure falls back
    print(f"  (font: falling back to sans-serif — {type(exc).__name__}: {exc})")

# ---- site-matched dark palette ----
# Text and apparatus are warm, data is red-and-white, and no grey appears in
# either. That is not decoration: it is what makes the separation survive colour
# blindness.
#
# The subject series is the site's --ember red; every comparator is near-white.
# Separation by LIGHTNESS is the point. Measured OKLab dE x100 against the
# comparator, normal / protan / deutan / tritan:
#
#     ember  vs near-white   37.5 / 39.0 / 32.0 / 38.0   <- shipped
#     brass  vs mid-grey     15.0 / 12.0 / 15.4 / 13.4   <- the previous pairing
#
# The old brass-on-grey pair separated by HUE, which is exactly the channel
# protanopia and deuteranopia destroy; it scraped the floor at 12. Red on white
# separates by lightness, which no form of colour blindness touches, and clears
# it three times over. Dash pattern and a direct end label still carry identity
# as well, so colour is never the only channel.
INK  = "#f2e9e2"   # figure titles: warm white, brighter than the caption tier
INK2 = "#cbb8a9"   # panel titles and axis labels: the site's warm secondary
MUTED = "#cbb8a9"  # tick labels and annotations: same tier, deliberately
GRID = "#3a322c"   # warm rules, never text
BASE = "#5c5048"   # axis spines and reference lines
FAINT = "#4a4038"  # placebo spaghetti
VT = "#e04a42"     # the subject, everywhere: the site's --ember
CMP = "#ececec"    # every comparator series (lines and markers)
# Filled AREAS need their own tone. A near-white bar repeated nine times
# overwhelms the one red bar that matters, but the spine colour used before was
# 2.37:1 against black, under the 3:1 floor for a graphical object. This is warm
# (no grey re-enters the palette), 4.14:1, and sits clearly below the subject's
# 5.23:1 so the red still reads as the subject.
CMP_FILL = "#7d6b5e"
# Dimmest tone still legal for a DATA mark. The placebo cloud is context, but a
# reader has to see it to see that Vermont sits inside it, so it is a graphical
# object that conveys content and owes the same 3:1 as any other. FAINT/BASE are
# rules and spines at 2.08 and 2.70 and must never carry data.
CMP_DIM = "#6b5d54"   # 3.32:1

plt.rcParams.update({
    "font.family": FONT_FAMILY, "font.size": 10.5,
    "text.color": INK, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    # Painted black rather than transparent. A transparent SVG opened directly
    # in a browser tab renders on white, and light-on-light is unreadable; the
    # page it sits on is black either way, so nothing is lost on-page.
    "figure.facecolor": "#000000", "axes.facecolor": "#000000",
    "savefig.facecolor": "#000000", "savefig.transparent": False,
})
if PREVIEW:
    plt.rcParams.update({"figure.facecolor": "#000000", "axes.facecolor": "#000000",
                         "savefig.facecolor": "#000000", "savefig.transparent": False,
                         "savefig.dpi": 130})
DASH = (0, (5, 2)); DOT = (0, (1, 1.6))

# ---- Shared figure geometry -------------------------------------------------
# Every figure is authored at ONE width. The page displays them all at one
# column width (--measure-wide in lite.css), so the display scale is
# 1100/1200 = 0.917 for all eight; any spread in authored width would show up
# on the page as a spread in label size. Heights stay per-figure — only the
# width is shared, and each height below preserves that figure's own aspect.
FIG_W = 7.9
# Title and standfirst sit flush with the figure's left edge, which the page
# puts flush with the prose. The axes inset (subplots_adjust left=) still
# varies per figure, because tick-label widths genuinely do.
TITLE_X = 0.0
TITLE_SIZE = 13.5


def style(ax, model_line=2017.5):
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    # Years are integers. Without this the auto-locator is free to pick a 2.5-year
    # step when the tick font gets wider, and label them "2017.5", which is not a
    # year. A FixedLocator means the panel chose its own ticks with set_xticks();
    # leave those alone, whichever order the two calls happen to be in.
    if not isinstance(ax.xaxis.get_major_locator(), mticker.FixedLocator):
        ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins="auto"))
    if model_line:
        ax.axvline(model_line, color=BASE, lw=0.8, ls=":", zorder=0)


# ---- Vertical rhythm -------------------------------------------------------
# Spacing is specified in INCHES and converted per figure, not written as
# per-figure fractions of figure height. Fractions were how eight figures ended
# up with eight different gaps: the same 0.34 hspace is a different number of
# points on a 7.2in figure than on an 8.6in one, and `top=0.925` leaves a
# different gap under the title on each.
#
# The rule the old numbers broke is proximity: a panel title belongs to the
# chart BELOW it, so the space above a title must be clearly larger than the
# space under it. Otherwise the eye groups each title with the panel it follows.
# The governing rule: EVERY panel title gets the same clear air above it,
# whether it follows the figure title or another chart. When the first panel
# title sat 0.28in under the suptitle while later ones had 0.52in, the first
# read as a subtitle of the figure title and the rest read as panel titles, so
# one figure appeared to have two different kinds of heading. Hence TITLE_AIR,
# and hence TOP_PAD being derived from it rather than guessed.
TITLE_AIR_IN = 0.52    # clear space above ANY panel title
TITLE_BLOCK_IN = 0.30  # the panel title's own line, plus its pad to the axes
XLABEL_IN = 0.30       # room under a panel for its x tick labels
SUPTITLE_IN = 0.30     # figure top down to the figure title
SUPTITLE_H_IN = 0.20   # the figure title's own line

PANEL_H_IN = 2.30      # default plotting area of one panel
PANEL_GAP_IN = XLABEL_IN + TITLE_AIR_IN + TITLE_BLOCK_IN
TOP_PAD_IN = SUPTITLE_IN + SUPTITLE_H_IN + TITLE_AIR_IN + TITLE_BLOCK_IN
BOTTOM_IN = 0.60       # last panel's x-labels down to the figure bottom


def fig_height(n, panel_h=PANEL_H_IN, extra=0.0):
    """Total height for n stacked panels at the shared rhythm."""
    return TOP_PAD_IN + n * panel_h + (n - 1) * PANEL_GAP_IN + BOTTOM_IN + extra


def layout(fig, n, left, right=0.965, ratios=None):
    """Apply the rhythm to a stacked figure, in inches, whatever its height."""
    H = fig.get_figheight()
    top = 1 - TOP_PAD_IN / H
    bottom = BOTTOM_IN / H
    # n panels and n-1 gaps share the band; solve for the gap as a fraction of
    # the MEAN panel height, which is what hspace actually means.
    mean_h = ((top - bottom) * H - (n - 1) * PANEL_GAP_IN) / n
    fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top,
                        hspace=PANEL_GAP_IN / mean_h)


def suptitle(fig, text):
    fig.suptitle(text, x=TITLE_X, y=1 - SUPTITLE_IN / fig.get_figheight(),
                 ha="left", va="top", fontsize=TITLE_SIZE, fontweight="bold",
                 color=INK)


def panel_title(ax, text):
    """Panel title flush with the FIGURE's left edge, not the axes'.

    The suptitle sits at x=0 so it lines up with the prose column. A plain
    ax.set_title(loc="left") starts at the axes instead, which is inset by
    however much room the y-tick labels need, so the two titles land on
    different left edges and the whole block reads as misaligned against the
    text. Converting the figure-space offset into axes space puts every title
    on the one edge.
    """
    box = ax.get_position()
    x = (TITLE_X - box.x0) / box.width
    ax.set_title(text, loc="left", x=x, pad=7, fontsize=10.5, color=INK2)


def covid_line(ax, label=False):
    """2020 reference line — same visual language as the model-start line."""
    ax.axvline(2020, color=BASE, lw=0.8, ls=":", zorder=0)
    if label:
        ax.annotate("COVID onset", (2020, ax.get_ylim()[1]), xytext=(3, -10),
                    textcoords="offset points", color=MUTED, fontsize=8)


def dollars(ax):
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    for lbl in ax.get_yticklabels():
        lbl.set_parse_math(False)


def end(ax, x, y, text, color, dy=0, bold=False):
    ax.annotate(text, (x, y), xytext=(5, dy), textcoords="offset points",
                color=color, fontsize=9.5, va="center",
                fontweight="bold" if bold else "normal")


def _uncollide_corner(fig):
    """Left-align the leftmost x tick label on every axis.

    A tick label is centred on its tick, so the first one hangs half its width
    to the LEFT of the axes, straight into the column where the y tick labels
    live. At the corner the two overlap. Left-aligning only the first label
    pulls it inside the axes and leaves the rest centred, which is what makes
    the corner read cleanly without moving any data.
    """
    for ax in fig.axes:
        labels = ax.get_xticklabels()
        if not labels:
            continue
        xlim = ax.get_xlim()
        for lb in labels:
            if abs(lb.get_position()[0] - xlim[0]) < 1e-9:
                lb.set_horizontalalignment("left")


def save(fig, name):
    _uncollide_corner(fig)
    if PREVIEW:
        fig.savefig(f"{PREVIEW}/{name}.png")
    else:
        fig.savefig(f"figures/{name}.svg")
    plt.close(fig)
    print(("wrote " + (PREVIEW + "/" if PREVIEW else "figures/")) + name +
          (".png" if PREVIEW else ".svg"))


def ordinal(n):
    """1st, 2nd, 3rd, 11th, 21st. Ranks move on every refit, so the suffix is
    derived rather than written into the caption alongside the number."""
    n = int(n)
    suffix = ("th" if 10 <= n % 100 <= 20
              else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))
    return f"{n}{suffix}"


def ranks(outcome):
    """Both placebo rankings for one outcome, as ordinals out of 50."""
    p = outcome["placebo"]
    return ordinal(p["post_rmspe"]["rank"]), ordinal(p["post_pre_ratio"]["rank"])


def signed_dollars(v):
    return f"{'−' if v < 0 else '+'}${abs(v):,.0f}"


# One authority for every published number. Captions must read from here, not
# from the flatter per-outcome files, which sit on a different specification.
res = json.load(open("data/results_manifest.json"))["outcomes"]
placebos = pd.read_csv("data/placebo_gaps_spending.csv", index_col=0)
YEARS = list(range(2014, 2025))

# ================= Figure 1: spending — trajectory, gap, placebos =================
r = res["TOT_MDCR_STDZD_PYMT_PC"]
actual = pd.Series({int(k): v for k, v in r["actual"].items()})
synth = pd.Series({int(k): v for k, v in r["synthetic"].items()})
gap = pd.Series({int(k): v for k, v in r["gap"].items()})
pre_mean = gap.loc[2014:2017].mean()

fig, axes = plt.subplots(3, 1, figsize=(FIG_W, fig_height(3)))
layout(fig, 3, left=0.135)

ax = axes[0]
ax.plot(YEARS, synth.values, color=CMP, lw=1.8, ls=DASH)
ax.plot(YEARS, actual.values, color=VT, lw=2.6)
end(ax, 2024, actual[2024], "Vermont", VT, dy=-10, bold=True)
end(ax, 2024, synth[2024], "synthetic VT", INK2, dy=6)
dollars(ax); style(ax)
ax.set_xlim(2014, 2026.6)
# Headroom so the synthetic-VT end label clears the panel title.
ax.set_ylim(top=max(actual.max(), synth.max()) * 1.06)
panel_title(ax, "Standardized Medicare payment per capita")
covid_line(ax, label=True)

ax = axes[1]
ax.axhline(0, color=BASE, lw=1)
ax.axhline(pre_mean, color=MUTED, lw=0.8, ls=":")
ax.annotate(f"pre-period mean gap (${pre_mean:,.0f})", (2014.1, pre_mean),
            xytext=(0, 4), textcoords="offset points", color=MUTED, fontsize=8.5,
            parse_math=False)
ax.plot(YEARS, gap.values, color=VT, lw=2.6)
dollars(ax); style(ax)
ax.set_xlim(2014, 2024.3)
panel_title(ax, "Gap: Vermont − synthetic")
covid_line(ax)

ax = axes[2]
for c in placebos.columns:
    ax.plot(placebos.index, placebos[c], color=CMP_DIM, lw=0.7)
ax.plot(gap.index, gap.values, color=VT, lw=2.6)
ax.axhline(0, color=MUTED, lw=0.8)
dollars(ax); style(ax)
ax.set_xlim(2014, 2024.6)
panel_title(ax, "Vermont gap vs. 49 in-space placebos")
end(ax, 2024, gap[2024], "VT", VT, dy=-4, bold=True)
covid_line(ax)

suptitle(fig, "Vermont Medicare spending under the all-payer model, vs. a synthetic control")
# Every number in this caption is read from the fit, never typed in.
_post, _ratio = ranks(r)
save(fig, "fig1_spending")

# ================= Figure 2: % gap by outcome, shared scale =================
order = ["TOT_MDCR_STDZD_PYMT_PC", "IP_CVRD_STAYS_PER_1000_BENES", "ER_VISITS_PER_1000_BENES"]
titles = ["Spending per capita", "Inpatient stays", "ED visits"]

# sharey is load-bearing, not cosmetic: the essay's claim is "put all three
# outcomes on one scale and the ED series is the one that moved". Drop it and
# each panel autoscales to its own range, every series looks equally dramatic,
# and the figure quietly stops making the argument the sentence makes.
fig, axes = plt.subplots(3, 1, figsize=(FIG_W, fig_height(3, panel_h=2.05)),
                         sharex=True, sharey=True)
layout(fig, 3, left=0.135)
for i, (ax, key, title) in enumerate(zip(axes, order, titles)):
    rr = res[key]
    g = pd.Series({int(k): v for k, v in rr["gap"].items()})
    s = pd.Series({int(k): v for k, v in rr["synthetic"].items()})
    pct = g / s * 100
    ax.axhline(0, color=BASE, lw=1)
    ax.plot(YEARS, pct.values, color=VT, lw=2.6)
    style(ax)
    _p, _r = ranks(rr)
    panel_title(ax, f"{title}   (rank {_p} / {_r} of 50)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_xlim(2014, 2024.3)
    covid_line(ax, label=(i == 0))
suptitle(fig, "Vermont vs. synthetic control: the gap as a share of the counterfactual")
save(fig, "fig2_outcomes")

# ===== Figure 2b: what the inference rests on, both panels from the same fits =====
manifest = json.load(open("data/results_manifest.json"))
pstats = pd.read_csv("data/scm_placebo_statistics.csv")

fig, axes = plt.subplots(2, 1, figsize=(FIG_W, fig_height(2, panel_h=2.70)),
                         gridspec_kw={"height_ratios": [1.15, 1]})
layout(fig, 2, left=0.155)

# -- left: the rank moves with the discrepancy statistic --
ax = axes[0]
labels = ["Spending\nper capita", "Inpatient\nstays", "ED visits"]
post_ranks = [res[k]["placebo"]["post_rmspe"]["rank"] for k in order]
ratio_ranks = [res[k]["placebo"]["post_pre_ratio"]["rank"] for k in order]
ypos = range(3)
for y, a, b in zip(ypos, post_ranks, ratio_ranks):
    ax.plot([a, b], [y, y], color=CMP_FILL, lw=2, zorder=0, solid_capstyle="round")
    ax.annotate(str(a), (a, y), xytext=(0, 9), textcoords="offset points",
                ha="center", color=VT, fontsize=8.5, fontweight="bold")
    ax.annotate(str(b), (b, y), xytext=(0, 9), textcoords="offset points",
                ha="center", color=INK2, fontsize=8.5)
ax.scatter(post_ranks, list(ypos), color=VT, s=55, zorder=3, label="post-period RMSPE")
ax.scatter(ratio_ranks, list(ypos), facecolors="none", edgecolors=CMP, s=58,
           linewidths=1.6, zorder=3, label="post/pre RMSPE ratio")
ax.set_yticks(list(ypos), labels, fontsize=9.5)
ax.invert_yaxis()
ax.set_ylim(2.45, -0.55)   # headroom so the top row's rank labels clear the panel title
ax.set_xlim(0, 51)
ax.set_xticks([1, 10, 20, 30, 40, 50])
ax.set_xlabel("rank among 50 states (1 = most discrepant)", fontsize=9)
ax.grid(axis="y", visible=False); ax.tick_params(length=0)
panel_title(ax, "Rank moves with the statistic")
ax.legend(frameon=False, fontsize=8.5, loc="lower right", handletextpad=.4,
          borderpad=.2, labelcolor=INK2)

# -- right: pre-fit against post-fit, the joint distribution behind both statistics --
ax = axes[1]
ed = pstats[pstats.outcome == "ER_VISITS_PER_1000_BENES"]
vt = manifest["outcomes"]["ER_VISITS_PER_1000_BENES"]
ax.scatter(ed.pre_rmspe, ed.post_rmspe, s=15, color=CMP, alpha=.75, linewidths=0)
ax.scatter([vt["pre_rmspe"]], [vt["post_rmspe"]], s=70, color=VT, zorder=3)
ax.annotate("Vermont", (vt["pre_rmspe"], vt["post_rmspe"]), xytext=(9, -2),
            textcoords="offset points", color=VT, fontsize=9, fontweight="bold")
ax.set_xscale("log")
degenerate = ed[ed.pre_rmspe < 1e-4]
if len(degenerate):
    ax.annotate(f"{len(degenerate)} degenerate fits\n(ratio denominator ~0)",
                (degenerate.pre_rmspe.max(), degenerate.post_rmspe.max()),
                xytext=(6, 14), textcoords="offset points", color=MUTED,
                fontsize=8, linespacing=1.4)
ax.set_xlabel("pre-period RMSPE (log scale)", fontsize=9)
ax.set_ylabel("post-period RMSPE", fontsize=9)
ax.grid(axis="x", visible=True, color=GRID, lw=.6)
ax.tick_params(length=0)
panel_title(ax, "ED visits: pre-fit vs. post-fit, all 50")

suptitle(fig, "What the emergency-department inference rests on")
save(fig, "fig2b_specification")

# ================= Figure 3: population health =================
PEERS = ["NH", "ME", "MA", "NY", "CT", "RI"]
PN = {"New Hampshire": "NH", "Maine": "ME", "Massachusetts": "MA", "New York": "NY",
      "Connecticut": "CT", "Rhode Island": "RI", "Vermont": "VT"}

od = pd.read_csv("data/overdose_state_year.csv").pivot(index="year", columns="state", values="deaths")
od_ci = pd.read_csv("data/overdose_vt_index_ci.csv").set_index("year")   # Poisson 95% CI, VT index
YA = list(range(2015, 2026))
vt_idx = od["VT"] / od["VT"].loc[2015] * 100
us_idx = od["US"] / od["US"].loc[2015] * 100
peer_idx = pd.concat([od[p] / od[p].loc[2015] * 100 for p in PEERS], axis=1).mean(axis=1)

mi = pd.read_csv("data/miov_suicide_od_state.csv")
mi = mi[mi["period"].astype(str).str.isdigit()].copy()
mi["period"] = mi["period"].astype(int); mi["st"] = mi["name"].map(PN)
mi = mi.dropna(subset=["st"])
rate = lambda intent, st: mi[(mi.intent == intent) & (mi.st == st)].set_index("period")["rate"].sort_index()
peer_rate = lambda intent: pd.concat([rate(intent, p) for p in PEERS], axis=1).mean(axis=1)
YB = list(range(2019, 2025))
sui_vt, sui_peer = rate("All_Suicide", "VT"), peer_rate("All_Suicide")
odr_vt, odr_peer = rate("Drug_OD", "VT"), peer_rate("Drug_OD")

# Pre-2018 suicide baseline — CDC WONDER age-adjusted rates, 2005-2020 (data/suicide_vt_peer_gap.csv,
# computed by the onecare_retrospective analysis project; same peer set as the MIOV panel). Spliced
# with the MIOV series (2019-24, above): the VT overlap years disagree by 1.6/100k in 2019 (>1pt
# threshold), so the two sources are plotted as visually distinct segments (style + seam annotation),
# not blended into one continuous line.
wonder = pd.read_csv("data/suicide_vt_peer_gap.csv").set_index("year")
YW = [y for y in wonder.index if 2005 <= y <= 2020]
sui_wonder_vt = wonder.loc[YW, "vt_aa_rate"]
sui_wonder_peer = wonder.loc[YW, "peer6_mean_aa_rate"]

fig, axes = plt.subplots(3, 1, figsize=(FIG_W, fig_height(3)))
layout(fig, 3, left=0.135)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.fill_between(YA, od_ci["lo"].reindex(YA), od_ci["hi"].reindex(YA), color=VT, alpha=0.15, lw=0, zorder=0)
ax.plot(YA, us_idx.reindex(YA), color=CMP, lw=1.5)
ax.plot(YA, peer_idx.reindex(YA), color=CMP, lw=1.8, ls=DASH)
ax.plot(YA, vt_idx.reindex(YA), color=VT, lw=2.6)
# All three series converge by 2025, so the end labels need pulling apart
# vertically or "Vermont" and "US" print on top of each other.
end(ax, 2025, vt_idx[2025], "Vermont", VT, dy=10, bold=True)
end(ax, 2025, us_idx[2025], "US", CMP, dy=-2)
end(ax, 2025, peer_idx[2025], "6 NE peers", CMP, dy=-14)
style(ax); ax.set_xlim(2015, 2027.6); ax.set_xticks(range(2015, 2026, 2))
panel_title(ax, "Overdose deaths, indexed (2015 = 100), with 95% CI")

# Suicide panel (axes[1]): WONDER 2005-2020 (final, age-adjusted) spliced with MIOV 2019-24
# (provisional) at a visibly marked seam.
ax = axes[1]
sui_all_max = max(sui_wonder_vt.max(), sui_wonder_peer.max(), sui_vt.max(), sui_peer.max())
ymax = max(sui_all_max, odr_vt.max(), odr_peer.max()) * 1.10
ax.plot(YW, sui_wonder_peer.values, color=CMP, lw=1.8, ls=DASH)
ax.plot(YW, sui_wonder_vt.values, color=VT, lw=2.6)
ax.plot(YB, sui_peer.reindex(YB), color=CMP, lw=1.5, ls=DOT, marker="o", ms=3)
ax.plot(YB, sui_vt.reindex(YB), color=VT, lw=1.5, ls=DOT, marker="o", ms=3.5)
ax.axvline(2019, color=MUTED, lw=0.6, ls="-", alpha=0.4, zorder=0)
ax.annotate("WONDER (final), then\nMIOV (provisional)", (2019, ymax * 0.82), xytext=(4, 0),
            textcoords="offset points", color=MUTED, fontsize=7.3, va="top", linespacing=1.3)
end(ax, 2024, sui_vt[2024], "VT", VT, bold=True)
end(ax, 2024, sui_peer[2024], "6 NE peers", CMP)
style(ax); ax.set_ylim(0, ymax); ax.set_xlim(2004, 2027.6); ax.set_xticks([2005, 2010, 2015, 2020, 2024])
panel_title(ax, "Suicide, deaths per 100k, 2005–2024")

ax = axes[2]
ax.plot(YB, odr_peer.reindex(YB), color=CMP, lw=1.8, ls=DASH)
ax.plot(YB, odr_vt.reindex(YB), color=VT, lw=2.6)
end(ax, 2024, odr_vt[2024], "VT", VT, bold=True)
end(ax, 2024, odr_peer[2024], "6 NE peers", CMP)
style(ax); ax.set_ylim(0, ymax); ax.set_xlim(2019, 2025.6); ax.set_xticks(range(2019, 2025))
panel_title(ax, "Overdose, deaths per 100k")

suptitle(fig, "The overdose climb is real; the suicide gap is a level, not a model-era trend")
save(fig, "fig3_pophealth")

# ================= Figure 4: consolidation =================
FIPS = {"VT": 50, "NH": 33, "ME": 23}
df = pd.read_csv("data/cbp_6211_states.csv")
YRS = sorted(df.year.unique())
estab = df.pivot(index="year", columns="fipstate", values="estab")
emp = df.pivot(index="year", columns="fipstate", values="emp")
us_estab = df.groupby("year")["estab"].sum()
idx = lambda s: s / s.loc[2014] * 100

fig, axes = plt.subplots(2, 1, figsize=(FIG_W, fig_height(2, panel_h=2.55)))
layout(fig, 2, left=0.135)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.plot(YRS, idx(us_estab).reindex(YRS), color=CMP, lw=1.4)
ax.plot(YRS, idx(estab[FIPS["ME"]]).reindex(YRS), color=CMP, lw=1.6, ls=DOT)
ax.plot(YRS, idx(estab[FIPS["NH"]]).reindex(YRS), color=CMP, lw=1.8, ls=DASH)
ax.plot(YRS, idx(estab[FIPS["VT"]]).reindex(YRS), color=VT, lw=2.8)
end(ax, 2023, idx(us_estab)[2023], "US", MUTED, dy=7)
end(ax, 2023, idx(estab[FIPS["NH"]])[2023], "NH  −2%", INK2, dy=-2)
end(ax, 2023, idx(estab[FIPS["ME"]])[2023], "ME  −23%", MUTED, dy=6)
end(ax, 2023, idx(estab[FIPS["VT"]])[2023], "VT  −26%", VT, dy=-6, bold=True)
style(ax); ax.set_xlim(2014, 2025.6); ax.set_xticks(range(2014, 2024, 2))
panel_title(ax, "Physician-office establishments, indexed (2014 = 100)")
ax = axes[1]
per_vt = emp[FIPS["VT"]] / estab[FIPS["VT"]]; per_nh = emp[FIPS["NH"]] / estab[FIPS["NH"]]
ax.plot(YRS, per_nh.reindex(YRS), color=CMP, lw=1.8, ls=DASH)
ax.plot(YRS, per_vt.reindex(YRS), color=VT, lw=2.8)
end(ax, 2023, per_vt[2023], "VT", VT, bold=True)
end(ax, 2023, per_nh[2023], "NH", CMP)
style(ax); ax.set_ylim(0, max(per_vt.max(), per_nh.max()) * 1.12)
ax.set_xlim(2014, 2025.2); ax.set_xticks(range(2014, 2024, 2))
panel_title(ax, "Employees per office (fewer offices, but larger)")
suptitle(fig, "Vermont's physician offices thinned faster than its neighbors', but so did Maine's")
save(fig, "fig4_consolidation")

# ================= Figure 5: consolidation, county grain =================
cty = pd.read_csv("data/cbp_6211_counties_vt_nh.csv")
UVMHN = ["Chittenden", "Washington", "Addison"]   # UVMMC / CVMC / Porter home counties
vt = cty[cty.state == "VT"].pivot(index="year", columns="county", values="estab")
vt = vt.drop(columns=["Grand Isle"])              # 2 or fewer offices, intermittently disclosed
nh_tot = cty[cty.state == "NH"].groupby("year")["estab"].sum()
grp = pd.DataFrame({"uvmhn": vt[UVMHN].sum(axis=1),
                    "rest": vt.drop(columns=UVMHN).sum(axis=1), "nh": nh_tot})
gidx = grp / grp.loc[2014] * 100

fig, axes = plt.subplots(2, 1, figsize=(FIG_W, fig_height(2, panel_h=2.90)), height_ratios=[1, 1.15])
layout(fig, 2, left=0.155)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.plot(gidx.index, gidx["nh"], color=CMP, lw=1.8, ls=DASH)
ax.plot(gidx.index, gidx["uvmhn"], color=VT, lw=1.8, ls=DOT)
ax.plot(gidx.index, gidx["rest"], color=VT, lw=2.8)
end(ax, 2023, gidx["nh"][2023], "NH  −3%", INK2, dy=4)
end(ax, 2023, gidx["uvmhn"][2023], "UVMHN counties  −18%", VT, dy=6)
end(ax, 2023, gidx["rest"][2023], "rest of VT  −35%", VT, dy=-6, bold=True)
style(ax); ax.set_xlim(2014, 2027.4); ax.set_xticks(range(2014, 2024, 2))
panel_title(ax, "Physician-office establishments, indexed (2014 = 100)")

ax = axes[1]
chg = (vt.loc[2023] / vt.loc[2014] - 1) * 100
chg = chg.sort_values(ascending=True)
ypos = range(len(chg))
ax.axvline(0, color=BASE, lw=1)
ax.axvline(-26, color=VT, lw=0.8, ls=":", zorder=0)
ax.set_ylim(-0.7, len(chg) + 0.5)
ax.annotate("VT statewide −26%", (-26, len(chg) + 0.35), color=VT, fontsize=8,
            ha="center", va="top", parse_math=False)
for y, (county, v) in zip(ypos, chg.items()):
    color = VT if county in UVMHN else CMP
    ax.plot([0, v], [y, y], color=color, lw=1.1, alpha=0.6)
    ax.plot(v, y, "o", color=color, ms=6)
    ax.annotate(f"{vt.loc[2014, county]:.0f} to {vt.loc[2023, county]:.0f}",
                (v, y), xytext=(-6 if v < 0 else 6, 0), textcoords="offset points",
                color=CMP if county not in UVMHN else VT, fontsize=7.5,
                ha="right" if v < 0 else "left", va="center", parse_math=False)
ax.set_yticks(list(ypos))
ax.set_yticklabels(chg.index, fontsize=9,
                   color=INK2)
for lbl in ax.get_yticklabels():
    if lbl.get_text() in UVMHN:
        lbl.set_color(VT); lbl.set_fontweight("bold")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, lw=0.6)
ax.tick_params(length=0); ax.set_xlim(-62, 8)
panel_title(ax, "Change 2014 to 2023, by Vermont county (counts at right)")

suptitle(fig, "The thinning was steepest away from the network, not at its center")
save(fig, "fig5_county")

# ================= Figure 6: commercial prices =================
rand = pd.read_csv("data/rand51_state_relative_prices.csv").set_index("State")
NORTHEAST = ["NY", "NJ", "PA", "VT", "CT", "ME", "NH", "RI", "MA"]
allsvc = (rand.loc[NORTHEAST, "Relative price"] * 100)
allsvc.loc["US"] = 254          # RAND 5.1 published national mean (all services)
allsvc = allsvc.sort_values()

fig, axes = plt.subplots(2, 1, figsize=(FIG_W, fig_height(2, panel_h=2.95)), height_ratios=[1.35, 1])
layout(fig, 2, left=0.165)
ax = axes[0]
for y, (st, v) in enumerate(allsvc.items()):
    if st == "VT":
        color, alpha = VT, 1.0
    elif st == "US":
        # The US-average bar reads as a reference rather than a state, so it
        # sits a step lighter than the other comparators, but still BELOW the
        # subject's 5.23:1 - nothing on the chart may outrank Vermont.
        color, alpha = "#8a7669", 1.0
    else:
        color, alpha = CMP_FILL, 1.0
    ax.barh(y, v, color=color, alpha=alpha, height=0.62)
    ax.annotate(f"{v:.0f}%", (v, y), xytext=(5, 0), textcoords="offset points",
                color=VT if st == "VT" else INK2, fontsize=9, va="center",
                fontweight="bold" if st == "VT" else "normal", parse_math=False)
ax.set_yticks(range(len(allsvc)))
labels = {"US": "US average"}
ax.set_yticklabels([labels.get(s, s) for s in allsvc.index], fontsize=9.5, color=INK2)
for lbl in ax.get_yticklabels():
    if lbl.get_text() == "VT":
        lbl.set_color(VT); lbl.set_fontweight("bold")
ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, lw=0.6)
ax.tick_params(length=0); ax.set_xlim(0, 345)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
panel_title(ax, "Commercial price as % of Medicare, all services (2022)")

# Hospital-system outpatient trajectories, RAND 5.1 annex (hospital_finance_findings.md)
ax = axes[1]
systems = {"UVM Health Network": (329, 357), "Rutland Regional": (332, 351),
           "Southwestern VT": (321, 345)}
for i, (name, (a, b)) in enumerate(systems.items()):
    is_uvm = name.startswith("UVM")
    color = VT if is_uvm else INK2
    ax.plot([2020, 2022], [a, b], color=color, lw=2.6 if is_uvm else 1.6,
            ls="-" if is_uvm else (DASH if i == 1 else DOT),
            marker="o", ms=5 if is_uvm else 4)
    # Offsets must push AWAY from the neighbouring series, so they run
    # high-to-low like the values do; (0, 6, -6) nudged Rutland up into UVM.
    end(ax, 2022, b, f"{name}  {b}%", color, dy=(8, 0, -8)[i], bold=is_uvm)
    if is_uvm:  # start value only for the highlighted series; the others read off the axis
        ax.annotate(f"{a}%", (2020, a), xytext=(-8, -4), textcoords="offset points",
                    color=color, fontsize=8.5, ha="right", va="center", parse_math=False)
ax.set_xlim(2019.6, 2024.6); ax.set_xticks([2020, 2022])
ax.set_ylim(300, 375)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
style(ax, model_line=None)
panel_title(ax, "Hospital-system outpatient price, % of Medicare")

suptitle(fig, "Commercial prices: highest in the Northeast after New York, and still climbing")
save(fig, "fig6_prices")

# ============ Figure 7: pre-treatment ACO penetration — the attenuation ============
pen = pd.read_csv("data/aco_penetration_states.csv")
apen = json.load(open("data/aco_penetration.json"))
aback = json.load(open("data/aco_penetration_backcast.json"))

fig, axes = plt.subplots(2, 1, figsize=(FIG_W, fig_height(2, panel_h=2.70)),
                         gridspec_kw={"height_ratios": [1.15, 1]})
layout(fig, 2, left=0.145)

# ---- panel A: where Vermont sat in the 2017 national distribution ----
ax = axes[0]
d17 = (pen[pen.year == 2017][["state_name", "pen_lo"]]
       .sort_values("pen_lo", ascending=False).reset_index(drop=True))
d17["rank"] = d17.index + 1
LABEL = {"Vermont": VT, "Delaware": CMP, "Iowa": CMP, "Maine": CMP, "Alaska": CMP,
         "District of Columbia": CMP}
# Delaware is the only state above Vermont, so it is labelled to the LEFT of its dot;
# labelling both to the right would put Vermont's text straight through it.
LEFT_LABEL = {"Delaware"}

rest = d17[~d17.state_name.isin(LABEL)]
ax.scatter(rest.pen_lo, rest["rank"], s=13, color=CMP_FILL, zorder=2,
           edgecolors="none")
for name, color in LABEL.items():
    row = d17[d17.state_name == name]
    if row.empty:
        continue
    x, y = float(row.pen_lo.iloc[0]), int(row["rank"].iloc[0])
    is_vt = name == "Vermont"
    # 2px surface ring so a highlighted dot never merges with a neighbour
    ax.scatter([x], [y], s=95 if is_vt else 58, color=color, zorder=4,
               edgecolors="#000000", linewidths=1.6)
    short = {"District of Columbia": "DC"}.get(name, name)
    left = name in LEFT_LABEL
    # Vermont sits one rank under Delaware, so drop its label clear of Delaware's dot.
    # Delaware and Vermont are the top two dots and sit ~1.4 points apart on x,
    # so a label hung off either one lands on the other. Delaware lifts above its
    # row, Vermont drops below its own; the serif is wider than the sans this was
    # first tuned for, and at the old offsets the two collided.
    ax.annotate(f"{short}  {x:.0f}%", (x, y),
                xytext=(-11 if left else 11, 11 if left else (-15 if is_vt else 0)),
                textcoords="offset points",
                color=color, va="center", ha="right" if left else "left",
                fontsize=9.5 if is_vt else 9,
                fontweight="bold" if is_vt else "normal", parse_math=False)

synth17 = apen["headline_2017_gap"]["synthetic_2017_incl_next_gen"]
ax.axvline(synth17, color=BASE, lw=0.9, ls=DASH, zorder=1)
ax.annotate(f"synthetic\nVermont {synth17:.0f}%", (synth17, 43), xytext=(-8, 0),
            textcoords="offset points", color=MUTED, fontsize=8.5, ha="right",
            va="center", linespacing=1.4, parse_math=False)

ax.set_ylim(52.5, -1.8)
ax.set_xlim(0, 60)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax.set_ylabel("national rank", fontsize=9, color=MUTED)
ax.grid(axis="x", visible=True); ax.grid(axis="y", visible=False)
ax.tick_params(length=0)
panel_title(ax, "Share of Medicare FFS beneficiaries in an ACO, 2017")

# ---- panel B: the whole pre-period, Vermont vs its synthetic control ----
ax = axes[1]
yrs = [2014, 2015, 2016, 2017]
bk = {r["year"]: r for r in aback["backcast"]}
sm = {r["year"]: r for r in apen["summary"]}
vt_s = [bk[2014]["vt"], bk[2015]["vt"], sm[2016]["vt_lo"], sm[2017]["vt_lo"]]
sy_s = [bk[2014]["synthetic_mssp"], bk[2015]["synthetic_mssp"],
        sm[2016]["synthetic_lo"], sm[2017]["synthetic_lo"]]

# Estimated years (2014-15) are drawn dashed with open markers; measured years
# (2016-17, county-grain) solid and filled. Data quality is encoded, not asserted.
for series, color, lw, name, dy in ((vt_s, VT, 2.6, "Vermont", -13),
                                    (sy_s, CMP, 1.8, "synthetic VT", 11)):
    ax.plot(yrs[1:], series[1:], color=color, lw=lw)
    ax.plot(yrs[:2], series[:2], color=color, lw=lw, ls=DASH)
    ax.plot(yrs[2:], series[2:], color=color, lw=0, marker="o", ms=7,
            markerfacecolor=color, markeredgecolor="#000000", markeredgewidth=1.4)
    ax.plot(yrs[:2], series[:2], color=color, lw=0, marker="o", ms=7,
            markerfacecolor="none", markeredgecolor=color, markeredgewidth=1.6)
    end(ax, 2017, series[-1], name, color, dy=dy, bold=(name == "Vermont"))

ax.axvspan(2013.85, 2015.5, color="#ffffff", alpha=0.028, zorder=0, lw=0)
ax.annotate("estimated\n(open markers)", (2014.15, 8), color=MUTED, fontsize=8.5,
            va="center", linespacing=1.4, parse_math=False)
ax.annotate("measured", (2016.55, 8), color=MUTED, fontsize=8.5, va="center",
            parse_math=False)

ax.set_xlim(2013.85, 2018.5)
ax.set_xticks(yrs)
ax.set_ylim(0, 70)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
style(ax, model_line=None)
panel_title(ax, "Share of Vermont Medicare FFS beneficiaries in an ACO, 2014-2017")

suptitle(fig, "Vermont entered the model already among the most ACO-saturated states in the country")
save(fig, "fig7_aco_penetration")

print("all figures written")
