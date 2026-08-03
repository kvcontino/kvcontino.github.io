"""Build the OneCare essay's figures as transparent, dark-theme SVGs that sit
directly on kvcontino.github.io's black page. Self-contained: reads ./data,
writes ./figures. Reproduces the analysis figures from the onecare_retrospective
project in the site's palette (VT = antique-brass accent #cd9575; comparators =
neutral grays separated by line style and weight, so identity never rests on
color alone).

Run:  python3 build_figures.py
"""

import json
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# Set ONECARE_PREVIEW=<dir> to render opaque PNGs on the site's black background
# for eyeballing (the shipped SVGs are transparent to sit on the live page).
PREVIEW = os.environ.get("ONECARE_PREVIEW")

# ---- site-matched dark palette ----
INK = "#ededed"; INK2 = "#c9c9c9"; MUTED = "#9a9a9a"
GRID = "#333333"; BASE = "#4d4d4d"; FAINT = "#3a3a3a"
VT = "#cd9575"                        # the site's accent — Vermont, everywhere
# Comparator series gray. NOT INK2/MUTED: against VT on a dark surface those score a
# normal-vision separation of only ~14.5 and ~8.6 (OKLab dE x100), both under the 15
# floor, so a reader with full colour vision can struggle to tell the pair apart.
# #7d7d7d clears it — 15.0 normal, 11.1 protan, 16.3 tritan. Measured, not eyeballed.
# INK2/MUTED remain the TEXT tokens (subtitles, tick labels, annotations, ref lines).
#
# ONE comparator step, deliberately. No third gray exists that clears 15 against BOTH
# the accent and #7d7d7d while keeping 3:1 contrast on black — lighter steps drift into
# the accent's lightness, darker ones fail the surface. Tested #c9c9c9/#b0b0b0/#a8a8a8/
# #5f5f5f/#565656; all fail. So every comparator series shares this one gray and is
# separated from its neighbours by dash pattern and a direct end label, never by colour.
# The trade is deliberate: it buys separation on the distinction that carries the
# argument (Vermont vs. not-Vermont) and spends it on one that does not (US vs. peers).
CMP = "#7d7d7d"

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10.5,
    "text.color": INK, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "none", "axes.facecolor": "none",
    "savefig.facecolor": "none", "savefig.transparent": True,
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
FIG_W = 12.5
# Title and standfirst sit flush with the figure's left edge, which the page
# puts flush with the prose. The axes inset (subplots_adjust left=) still
# varies per figure, because tick-label widths genuinely do.
TITLE_X = 0.0
TITLE_SIZE = 12.5


def style(ax, model_line=2017.5):
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    if model_line:
        ax.axvline(model_line, color=BASE, lw=0.8, ls=":", zorder=0)


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


def save(fig, name):
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

fig, axes = plt.subplots(1, 3, figsize=(FIG_W, 4.0))
fig.subplots_adjust(left=0.07, right=0.985, bottom=0.13, top=0.80, wspace=0.30)

ax = axes[0]
ax.plot(YEARS, synth.values, color=CMP, lw=1.8, ls=DASH)
ax.plot(YEARS, actual.values, color=VT, lw=2.6)
end(ax, 2024, actual[2024], "Vermont", VT, dy=-10, bold=True)
end(ax, 2024, synth[2024], "synthetic VT", INK2, dy=6)
dollars(ax); style(ax)
ax.set_xlim(2014, 2026.6)
# Headroom so the synthetic-VT end label clears the panel title.
ax.set_ylim(top=max(actual.max(), synth.max()) * 1.06)
ax.set_title("Standardized Medicare payment per capita", loc="left", fontsize=10.5, color=INK)
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
ax.set_title("Gap: Vermont − synthetic", loc="left", fontsize=10.5, color=INK)
covid_line(ax)

ax = axes[2]
for c in placebos.columns:
    ax.plot(placebos.index, placebos[c], color=FAINT, lw=0.7)
ax.plot(gap.index, gap.values, color=VT, lw=2.6)
ax.axhline(0, color=MUTED, lw=0.8)
dollars(ax); style(ax)
ax.set_xlim(2014, 2024.6)
ax.set_title("Vermont gap vs. 49 in-space placebos", loc="left", fontsize=10.5, color=INK)
end(ax, 2024, gap[2024], "VT", VT, dy=-4, bold=True)
covid_line(ax)

fig.suptitle("Vermont Medicare spending under the all-payer model, vs. a synthetic control",
             x=TITLE_X, y=0.965, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
# Every number in this caption is read from the fit, never typed in.
_post, _ratio = ranks(r)
fig.text(TITLE_X, 0.885,
         f"Post-2018 mean gap {signed_dollars(r['mean_post_gap'])} per beneficiary-year "
         f"({r['mean_post_gap_pct']:.1f}%), intercept-shifted specification; "
         f"pre-period gap is zero by construction.\n"
         f"Vermont ranks {_post} of 50 on post-period RMSPE and {_ratio} on the post/pre "
         f"ratio — the direction the federal evaluation found, not a settled causal estimate.",
         fontsize=9, color=INK2, parse_math=False, va="center", linespacing=1.5)
save(fig, "fig1_spending")

# ================= Figure 2: % gap by outcome, shared scale =================
order = ["TOT_MDCR_STDZD_PYMT_PC", "IP_CVRD_STAYS_PER_1000_BENES", "ER_VISITS_PER_1000_BENES"]
titles = ["Spending per capita", "Inpatient stays", "ED visits"]

fig, axes = plt.subplots(1, 3, figsize=(FIG_W, 4.1), sharey=True)
fig.subplots_adjust(left=0.06, right=0.985, bottom=0.12, top=0.73, wspace=0.12)
for i, (ax, key, title) in enumerate(zip(axes, order, titles)):
    rr = res[key]
    g = pd.Series({int(k): v for k, v in rr["gap"].items()})
    s = pd.Series({int(k): v for k, v in rr["synthetic"].items()})
    pct = g / s * 100
    ax.axhline(0, color=BASE, lw=1)
    ax.plot(YEARS, pct.values, color=VT, lw=2.6)
    style(ax)
    _p, _r = ranks(rr)
    ax.set_title(f"{title}   (rank {_p} / {_r} of 50)", loc="left",
                 fontsize=10.5, color=INK)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_xlim(2014, 2024.3)
    covid_line(ax, label=(i == 0))
fig.suptitle("Vermont vs. synthetic control — the gap as a share of the counterfactual",
             x=TITLE_X, y=0.95, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.875,
         "One scale across all three. Spending fell and ED visits rose against the "
         "counterfactual; inpatient stays never moved.\nRanks are Vermont's place among "
         "50 states on post-period RMSPE / the post-to-pre RMSPE ratio — both from the "
         "same fits, neither treated as a verdict.",
         fontsize=9, color=INK2, va="top", linespacing=1.5)
save(fig, "fig2_outcomes")

# ===== Figure 2b: what the inference rests on, both panels from the same fits =====
manifest = json.load(open("data/results_manifest.json"))
pstats = pd.read_csv("data/scm_placebo_statistics.csv")

fig, axes = plt.subplots(1, 2, figsize=(FIG_W, 4.82),
                         gridspec_kw={"width_ratios": [1.15, 1]})
fig.subplots_adjust(left=0.145, right=0.990, bottom=0.145, top=0.64, wspace=0.42)

# -- left: the rank moves with the discrepancy statistic --
ax = axes[0]
labels = ["Spending\nper capita", "Inpatient\nstays", "ED visits"]
post_ranks = [res[k]["placebo"]["post_rmspe"]["rank"] for k in order]
ratio_ranks = [res[k]["placebo"]["post_pre_ratio"]["rank"] for k in order]
ypos = range(3)
for y, a, b in zip(ypos, post_ranks, ratio_ranks):
    ax.plot([a, b], [y, y], color=BASE, lw=2, zorder=0, solid_capstyle="round")
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
ax.set_title("Rank moves with the statistic", loc="left", fontsize=10.5, color=INK)
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
ax.set_title("ED visits: pre-fit vs. post-fit, all 50", loc="left",
             fontsize=10.5, color=INK)

fig.suptitle("What the emergency-department inference rests on",
             x=TITLE_X, y=0.975, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.90,
         "Left: the same intercept-shifted fits ranked two defensible ways. Right: the ratio "
         "statistic divides the vertical\naxis by the horizontal one, so units at the left edge "
         "get large ratios from a small denominator — which is\nwhy both rankings are reported "
         "rather than one being called honest.",
         fontsize=9, color=INK2, va="top", linespacing=1.5)
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

fig, axes = plt.subplots(1, 3, figsize=(FIG_W, 4.0))
fig.subplots_adjust(left=0.06, right=0.987, bottom=0.13, top=0.75, wspace=0.32)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.fill_between(YA, od_ci["lo"].reindex(YA), od_ci["hi"].reindex(YA), color=VT, alpha=0.15, lw=0, zorder=0)
ax.plot(YA, us_idx.reindex(YA), color=CMP, lw=1.5)
ax.plot(YA, peer_idx.reindex(YA), color=CMP, lw=1.8, ls=DASH)
ax.plot(YA, vt_idx.reindex(YA), color=VT, lw=2.6)
end(ax, 2025, vt_idx[2025], "Vermont", VT, bold=True)
end(ax, 2025, us_idx[2025], "US", MUTED, dy=7)
end(ax, 2025, peer_idx[2025], "6 NE peers", INK2, dy=-7)
style(ax); ax.set_xlim(2015, 2027.6); ax.set_xticks(range(2015, 2026, 2))
ax.set_title("Overdose deaths, indexed (2015 = 100), with 95% CI", loc="left", fontsize=10.5, color=INK)

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
ax.annotate("WONDER (final) →\nMIOV (provisional)", (2019, ymax * 0.82), xytext=(4, 0),
            textcoords="offset points", color=MUTED, fontsize=7.3, va="top", linespacing=1.3)
end(ax, 2024, sui_vt[2024], "VT", VT, bold=True)
end(ax, 2024, sui_peer[2024], "6 NE peers", CMP)
style(ax); ax.set_ylim(0, ymax); ax.set_xlim(2004, 2027.6); ax.set_xticks([2005, 2010, 2015, 2020, 2024])
ax.set_title("Suicide, deaths per 100k, 2005–2024", loc="left", fontsize=10.5, color=INK)

ax = axes[2]
ax.plot(YB, odr_peer.reindex(YB), color=CMP, lw=1.8, ls=DASH)
ax.plot(YB, odr_vt.reindex(YB), color=VT, lw=2.6)
end(ax, 2024, odr_vt[2024], "VT", VT, bold=True)
end(ax, 2024, odr_peer[2024], "6 NE peers", CMP)
style(ax); ax.set_ylim(0, ymax); ax.set_xlim(2019, 2025.6); ax.set_xticks(range(2019, 2025))
ax.set_title("Overdose, deaths per 100k", loc="left", fontsize=10.5, color=INK)

fig.suptitle("The overdose climb is real; the suicide gap is a level, not a model-era trend",
             x=TITLE_X, y=0.955, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.855, "Overdose index carries a Poisson 95% band (small annual counts). Suicide is "
         "extended to 2005 (WONDER, age-adjusted); the pre-model\ngap (+5.2, 2014–17) and model-era "
         "gap (+5.5, 2018–20) are statistically indistinguishable — this predates the model.",
         fontsize=9, color=INK2, va="center", linespacing=1.5)
save(fig, "fig3_pophealth")

# ================= Figure 4: consolidation =================
FIPS = {"VT": 50, "NH": 33, "ME": 23}
df = pd.read_csv("data/cbp_6211_states.csv")
YRS = sorted(df.year.unique())
estab = df.pivot(index="year", columns="fipstate", values="estab")
emp = df.pivot(index="year", columns="fipstate", values="emp")
us_estab = df.groupby("year")["estab"].sum()
idx = lambda s: s / s.loc[2014] * 100

fig, axes = plt.subplots(1, 2, figsize=(FIG_W, 4.77))
fig.subplots_adjust(left=0.07, right=0.989, bottom=0.12, top=0.78, wspace=0.26)
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
ax.set_title("Physician-office establishments, indexed (2014 = 100)", loc="left", fontsize=10.5, color=INK)
ax = axes[1]
per_vt = emp[FIPS["VT"]] / estab[FIPS["VT"]]; per_nh = emp[FIPS["NH"]] / estab[FIPS["NH"]]
ax.plot(YRS, per_nh.reindex(YRS), color=CMP, lw=1.8, ls=DASH)
ax.plot(YRS, per_vt.reindex(YRS), color=VT, lw=2.8)
end(ax, 2023, per_vt[2023], "VT", VT, bold=True)
end(ax, 2023, per_nh[2023], "NH", CMP)
style(ax); ax.set_ylim(0, max(per_vt.max(), per_nh.max()) * 1.12)
ax.set_xlim(2014, 2025.2); ax.set_xticks(range(2014, 2024, 2))
ax.set_title("Employees per office (fewer offices, but larger)", loc="left", fontsize=10.5, color=INK)
fig.suptitle("Vermont's physician offices thinned faster than its neighbors' — but so did Maine's",
             x=TITLE_X, y=0.955, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.875, "NH is the clean no-model comparator; ME shows a like-sized decline with\n"
         "no all-payer model — the honesty guard on reading VT's drop as model-caused.",
         fontsize=9, color=INK2, va="center", linespacing=1.5)
save(fig, "fig4_consolidation")

# ================= Figure 5: consolidation, county grain =================
cty = pd.read_csv("data/cbp_6211_counties_vt_nh.csv")
UVMHN = ["Chittenden", "Washington", "Addison"]   # UVMMC / CVMC / Porter home counties
vt = cty[cty.state == "VT"].pivot(index="year", columns="county", values="estab")
vt = vt.drop(columns=["Grand Isle"])              # ≤2 offices, intermittently disclosed
nh_tot = cty[cty.state == "NH"].groupby("year")["estab"].sum()
grp = pd.DataFrame({"uvmhn": vt[UVMHN].sum(axis=1),
                    "rest": vt.drop(columns=UVMHN).sum(axis=1), "nh": nh_tot})
gidx = grp / grp.loc[2014] * 100

fig, axes = plt.subplots(1, 2, figsize=(FIG_W, 5.0), width_ratios=[1, 1.15])
fig.subplots_adjust(left=0.065, right=0.989, bottom=0.11, top=0.76, wspace=0.42)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.plot(gidx.index, gidx["nh"], color=CMP, lw=1.8, ls=DASH)
ax.plot(gidx.index, gidx["uvmhn"], color=VT, lw=1.8, ls=DOT)
ax.plot(gidx.index, gidx["rest"], color=VT, lw=2.8)
end(ax, 2023, gidx["nh"][2023], "NH  −3%", INK2, dy=4)
end(ax, 2023, gidx["uvmhn"][2023], "UVMHN counties  −18%", VT, dy=6)
end(ax, 2023, gidx["rest"][2023], "rest of VT  −35%", VT, dy=-6, bold=True)
style(ax); ax.set_xlim(2014, 2027.4); ax.set_xticks(range(2014, 2024, 2))
ax.set_title("Physician-office establishments, indexed (2014 = 100)", loc="left",
             fontsize=10.5, color=INK)

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
    ax.annotate(f"{vt.loc[2014, county]:.0f}→{vt.loc[2023, county]:.0f}",
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
ax.set_title("Change 2014 → 2023, by Vermont county (counts at right)", loc="left",
             fontsize=10.5, color=INK)

fig.suptitle("The thinning was steepest away from the network, not at its center",
             x=TITLE_X, y=0.955, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.855, "UVMHN home counties (Chittenden · Washington · Addison) lost 18% of "
         "physician offices; the rest of Vermont lost 35%.\nCounty counts are small — grouped "
         "series are the reliable read. Grand Isle (≤2 offices) excluded.",
         fontsize=9, color=INK2, va="center", linespacing=1.5, parse_math=False)
save(fig, "fig5_county")

# ================= Figure 6: commercial prices =================
rand = pd.read_csv("data/rand51_state_relative_prices.csv").set_index("State")
NORTHEAST = ["NY", "NJ", "PA", "VT", "CT", "ME", "NH", "RI", "MA"]
allsvc = (rand.loc[NORTHEAST, "Relative price"] * 100)
allsvc.loc["US"] = 254          # RAND 5.1 published national mean (all services)
allsvc = allsvc.sort_values()

fig, axes = plt.subplots(1, 2, figsize=(FIG_W, 5.11), width_ratios=[1.35, 1])
fig.subplots_adjust(left=0.095, right=0.987, bottom=0.12, top=0.76, wspace=0.35)
ax = axes[0]
for y, (st, v) in enumerate(allsvc.items()):
    if st == "VT":
        color, alpha = VT, 1.0
    elif st == "US":
        color, alpha = MUTED, 0.55
    else:
        color, alpha = BASE, 0.9
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
ax.set_title("Commercial price as % of Medicare, all services (2022)", loc="left",
             fontsize=10.5, color=INK)

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
    end(ax, 2022, b, f"{name}  {b}%", color, dy=(0, 6, -6)[i], bold=is_uvm)
    if is_uvm:  # start value only for the highlighted series; the others read off the axis
        ax.annotate(f"{a}%", (2020, a), xytext=(-8, -4), textcoords="offset points",
                    color=color, fontsize=8.5, ha="right", va="center", parse_math=False)
ax.set_xlim(2019.6, 2024.6); ax.set_xticks([2020, 2022])
ax.set_ylim(300, 375)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
style(ax, model_line=None)
ax.set_title("Hospital-system outpatient price, % of Medicare", loc="left",
             fontsize=10.5, color=INK)

fig.suptitle("Commercial prices: highest in the Northeast after New York — and still climbing",
             x=TITLE_X, y=0.955, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.855, "Vermont's commercial prices ran 283% of Medicare in 2022, above the US "
         "average. Every major Vermont hospital system's\noutpatient price rose through the "
         "model's mature years. Source: RAND Hospital Price Transparency 5.1.",
         fontsize=9, color=INK2, va="center", linespacing=1.5, parse_math=False)
save(fig, "fig6_prices")

# ============ Figure 7: pre-treatment ACO penetration — the attenuation ============
pen = pd.read_csv("data/aco_penetration_states.csv")
apen = json.load(open("data/aco_penetration.json"))
aback = json.load(open("data/aco_penetration_backcast.json"))

fig, axes = plt.subplots(1, 2, figsize=(FIG_W, 4.4),
                         gridspec_kw={"width_ratios": [1.15, 1]})
fig.subplots_adjust(left=0.065, right=0.989, bottom=0.13, top=0.72, wspace=0.22)

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
ax.scatter(rest.pen_lo, rest["rank"], s=13, color=FAINT, zorder=2,
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
    ax.annotate(f"{short}  {x:.0f}%", (x, y),
                xytext=(-11 if left else 11, -15 if is_vt else 0),
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
ax.set_title("Every state, 2017: share of Medicare FFS in an ACO", loc="left",
             fontsize=10.5, color=INK)

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
ax.set_title("The synthetic control's whole pre-period fit window", loc="left",
             fontsize=10.5, color=INK)

fig.suptitle("Vermont entered the model already among the most ACO-saturated states in the country",
             x=TITLE_X, y=0.965, ha="left", fontsize=TITLE_SIZE, fontweight="bold", color=INK)
fig.text(TITLE_X, 0.875,
         "In 2017, 51.6% of Vermont's Medicare fee-for-service beneficiaries were already in a Shared Savings Program ACO — second only to Delaware,\n"
         "and roughly twice its synthetic control. 2018 marks a change of ACO regime, not the arrival of one.",
         fontsize=9, color=INK2, va="center", linespacing=1.5, parse_math=False)
save(fig, "fig7_aco_penetration")

print("all figures written")
