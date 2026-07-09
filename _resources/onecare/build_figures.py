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


def style(ax, model_line=2017.5):
    ax.grid(axis="x", visible=False)
    ax.tick_params(length=0)
    if model_line:
        ax.axvline(model_line, color=BASE, lw=0.8, ls=":", zorder=0)


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


res = json.load(open("data/synth_results.json"))
placebos = pd.read_csv("data/placebo_gaps_spending.csv", index_col=0)
YEARS = list(range(2014, 2025))

# ================= Figure 1: spending — trajectory, gap, placebos =================
r = res["TOT_MDCR_STDZD_PYMT_PC"]
actual = pd.Series({int(k): v for k, v in r["actual"].items()})
synth = pd.Series({int(k): v for k, v in r["synthetic"].items()})
gap = pd.Series({int(k): v for k, v in r["gap"].items()})
pre_mean = gap.loc[2014:2017].mean()

fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
fig.subplots_adjust(left=0.07, right=0.985, bottom=0.13, top=0.80, wspace=0.30)

ax = axes[0]
ax.plot(YEARS, synth.values, color=INK2, lw=1.8, ls=DASH)
ax.plot(YEARS, actual.values, color=VT, lw=2.6)
end(ax, 2024, actual[2024], "Vermont", VT, dy=-10, bold=True)
end(ax, 2024, synth[2024], "synthetic VT", INK2, dy=6)
dollars(ax); style(ax)
ax.set_xlim(2014, 2026.6)
ax.set_title("Standardized Medicare payment per capita", loc="left", fontsize=10.5, color=INK)

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

ax = axes[2]
for c in placebos.columns:
    ax.plot(placebos.index, placebos[c], color=FAINT, lw=0.7)
ax.plot(gap.index, gap.values, color=VT, lw=2.6)
ax.axhline(0, color=MUTED, lw=0.8)
dollars(ax); style(ax)
ax.set_xlim(2014, 2024.6)
ax.set_title("Vermont gap vs. 49 in-space placebos", loc="left", fontsize=10.5, color=INK)
end(ax, 2024, gap[2024], "VT", VT, dy=-4, bold=True)

fig.suptitle("Vermont Medicare spending under the all-payer model, vs. a synthetic control",
             x=0.07, y=0.965, ha="left", fontsize=12.5, fontweight="bold", color=INK)
fig.text(0.07, 0.88,
         "Post-2018 mean gap −$759 per beneficiary-year; −$462 after netting the "
         "pre-period gap. Placebo p = 0.64 — the direction the federal evaluation found, "
         "not an individually significant estimate.",
         fontsize=9, color=INK2, parse_math=False)
save(fig, "fig1_spending")

# ================= Figure 2: % gap by outcome, shared scale =================
order = ["TOT_MDCR_STDZD_PYMT_PC", "IP_CVRD_STAYS_PER_1000_BENES", "ER_VISITS_PER_1000_BENES"]
titles = ["Spending per capita", "Inpatient stays", "ED visits"]

fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), sharey=True)
fig.subplots_adjust(left=0.06, right=0.985, bottom=0.13, top=0.78, wspace=0.12)
for ax, key, title in zip(axes, order, titles):
    rr = res[key]
    g = pd.Series({int(k): v for k, v in rr["gap"].items()})
    s = pd.Series({int(k): v for k, v in rr["synthetic"].items()})
    pct = g / s * 100
    ax.axhline(0, color=BASE, lw=1)
    ax.plot(YEARS, pct.values, color=VT, lw=2.6)
    style(ax)
    ax.set_title(f"{title}   (placebo p = {rr['placebo_p']:.2f})", loc="left",
                 fontsize=10.5, color=INK)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:+.0f}%"))
    ax.set_xlim(2014, 2024.3)
fig.suptitle("Vermont vs. synthetic control — the gap as a share of the counterfactual",
             x=0.06, y=0.95, ha="left", fontsize=12.5, fontweight="bold", color=INK)
fig.text(0.06, 0.85,
         "One scale across all three. Spending fell and ED visits rose against the "
         "counterfactual; inpatient stays never moved.", fontsize=9, color=INK2)
save(fig, "fig2_outcomes")

# ================= Figure 3: population health =================
PEERS = ["NH", "ME", "MA", "NY", "CT", "RI"]
PN = {"New Hampshire": "NH", "Maine": "ME", "Massachusetts": "MA", "New York": "NY",
      "Connecticut": "CT", "Rhode Island": "RI", "Vermont": "VT"}

od = pd.read_csv("data/overdose_state_year.csv").pivot(index="year", columns="state", values="deaths")
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

fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
fig.subplots_adjust(left=0.06, right=0.94, bottom=0.13, top=0.80, wspace=0.32)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.plot(YA, us_idx.reindex(YA), color=MUTED, lw=1.5)
ax.plot(YA, peer_idx.reindex(YA), color=INK2, lw=1.8, ls=DASH)
ax.plot(YA, vt_idx.reindex(YA), color=VT, lw=2.6)
end(ax, 2025, vt_idx[2025], "Vermont", VT, bold=True)
end(ax, 2025, us_idx[2025], "US", MUTED, dy=7)
end(ax, 2025, peer_idx[2025], "6 NE peers", INK2, dy=-7)
style(ax); ax.set_xlim(2015, 2027.6); ax.set_xticks(range(2015, 2026, 2))
ax.set_title("Overdose deaths, indexed (2015 = 100)", loc="left", fontsize=10.5, color=INK)
ymax = max(odr_vt.max(), odr_peer.max()) * 1.10
for ax, (v, p, t) in zip(axes[1:], [(sui_vt, sui_peer, "Suicide, deaths per 100k"),
                                    (odr_vt, odr_peer, "Overdose, deaths per 100k")]):
    ax.plot(YB, p.reindex(YB), color=INK2, lw=1.8, ls=DASH)
    ax.plot(YB, v.reindex(YB), color=VT, lw=2.6)
    end(ax, 2024, v[2024], "VT", VT, bold=True)
    end(ax, 2024, p[2024], "6 NE peers", INK2)
    style(ax); ax.set_ylim(0, ymax); ax.set_xlim(2019, 2025.6); ax.set_xticks(range(2019, 2025))
    ax.set_title(t, loc="left", fontsize=10.5, color=INK)
fig.suptitle("On both flagship model targets, Vermont deteriorated faster than its peers",
             x=0.06, y=0.965, ha="left", fontsize=12.5, fontweight="bold", color=INK)
fig.text(0.06, 0.87, "Overdose rates crossed from below the peer mean (2019) to above it "
         "(2022–24). Suicide, overdose rates share one scale.", fontsize=9, color=INK2)
save(fig, "fig3_pophealth")

# ================= Figure 4: consolidation =================
FIPS = {"VT": 50, "NH": 33, "ME": 23}
df = pd.read_csv("data/cbp_6211_states.csv")
YRS = sorted(df.year.unique())
estab = df.pivot(index="year", columns="fipstate", values="estab")
emp = df.pivot(index="year", columns="fipstate", values="emp")
us_estab = df.groupby("year")["estab"].sum()
idx = lambda s: s / s.loc[2014] * 100

fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
fig.subplots_adjust(left=0.07, right=0.90, bottom=0.12, top=0.78, wspace=0.26)
ax = axes[0]
ax.axhline(100, color=BASE, lw=0.8, ls=DASH, zorder=0)
ax.plot(YRS, idx(us_estab).reindex(YRS), color=MUTED, lw=1.4)
ax.plot(YRS, idx(estab[FIPS["ME"]]).reindex(YRS), color=MUTED, lw=1.6, ls=DOT)
ax.plot(YRS, idx(estab[FIPS["NH"]]).reindex(YRS), color=INK2, lw=1.8, ls=DASH)
ax.plot(YRS, idx(estab[FIPS["VT"]]).reindex(YRS), color=VT, lw=2.8)
end(ax, 2023, idx(us_estab)[2023], "US", MUTED, dy=7)
end(ax, 2023, idx(estab[FIPS["NH"]])[2023], "NH  −2%", INK2, dy=-2)
end(ax, 2023, idx(estab[FIPS["ME"]])[2023], "ME  −23%", MUTED, dy=6)
end(ax, 2023, idx(estab[FIPS["VT"]])[2023], "VT  −26%", VT, dy=-6, bold=True)
style(ax); ax.set_xlim(2014, 2025.6); ax.set_xticks(range(2014, 2024, 2))
ax.set_title("Physician-office establishments, indexed (2014 = 100)", loc="left", fontsize=10.5, color=INK)
ax = axes[1]
per_vt = emp[FIPS["VT"]] / estab[FIPS["VT"]]; per_nh = emp[FIPS["NH"]] / estab[FIPS["NH"]]
ax.plot(YRS, per_nh.reindex(YRS), color=INK2, lw=1.8, ls=DASH)
ax.plot(YRS, per_vt.reindex(YRS), color=VT, lw=2.8)
end(ax, 2023, per_vt[2023], "VT", VT, bold=True)
end(ax, 2023, per_nh[2023], "NH", INK2)
style(ax); ax.set_ylim(0, max(per_vt.max(), per_nh.max()) * 1.12)
ax.set_xlim(2014, 2025.2); ax.set_xticks(range(2014, 2024, 2))
ax.set_title("Employees per office (fewer offices, but larger)", loc="left", fontsize=10.5, color=INK)
fig.suptitle("Vermont's physician offices thinned faster than its neighbors' — but so did Maine's",
             x=0.07, y=0.955, ha="left", fontsize=12, fontweight="bold", color=INK)
fig.text(0.07, 0.855, "NH is the clean no-model comparator; ME shows a like-sized decline with "
         "no all-payer model — the honesty guard on reading VT's drop as model-caused.",
         fontsize=9, color=INK2)
save(fig, "fig4_consolidation")
print("all figures written")
