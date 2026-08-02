"""Medicare Advantage robustness, refit on the published intercept-shifted model.

Two specifications, both aimed at the same worry: the outcome series are Medicare
fee-for-service only, so differential MA growth changes the denominator's composition
rather than anyone's behaviour.

  A. yearly MA penetration as time-varying predictors, replacing the single
     pre-period mean the published fit uses.
  B. donor pool restricted to states within +/-10 points of Vermont's pre-period
     mean MA rate, so the comparison is built from states on a similar trajectory.

Both were previously computed on the superseded level-matched model. Neither result
transfers, because the donor pool and the fit both change. This recomputes them under
the model actually published, with placebo ranks recomputed inside each specification
rather than borrowed from the baseline.

Writes data/ma_robustness.json.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get(
    "ONECARE_SOURCE", HERE.parents[2] / "onecare_retrospective",
))
sys.path.insert(0, str(SOURCE / "analysis"))
import synth_medicare as sm  # noqa: E402

sm.DATA = str(SOURCE / "data" / "geo_variation_2014_2024.csv")
PRE = [2014, 2015, 2016, 2017]
POST = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
OUTCOMES = ["TOT_MDCR_STDZD_PYMT_PC", "ER_VISITS_PER_1000_BENES"]
RESTRICT_PP = 0.10

_original_predictor_matrix = sm.predictor_matrix


def yearly_ma_predictor_matrix(panel, outcome, states, demean=False):
    """Baseline predictors, but MA enters once per pre-period year, not as a mean.

    A single pre-period mean cannot express a trajectory. If Vermont's MA share was
    flat while a donor's was climbing to the same average, the mean calls them
    identical; year-by-year columns do not.
    """
    X = _original_predictor_matrix(panel, outcome, states, demean=demean)
    X = X.drop(columns=["MA_PRTCPTN_RATE"])
    wide = panel.pivot_table(index="state", columns="year", values="MA_PRTCPTN_RATE")
    for year in PRE:
        X[f"MA_{year}"] = wide.loc[states, year]
    return X


def rmspe(series, years):
    return float(np.sqrt(np.mean(np.square(series.loc[years]))))


def fit_one(panel, outcome, treated, donors):
    actual, synthetic, weights = sm.synth_gaps(
        panel, outcome, treated, donors, demean=True
    )
    gap = actual - synthetic
    return gap, weights


def run(panel, outcome, donors, label):
    """Fit Vermont and every placebo inside this specification."""
    gap, weights = fit_one(panel, outcome, "VT", donors)
    vt_post, vt_pre = rmspe(gap, POST), rmspe(gap, PRE)
    placebo = {}
    for state in donors:
        p_gap, _ = fit_one(panel, outcome, state, [d for d in donors if d != state])
        placebo[state] = rmspe(p_gap, POST)
    rank = 1 + sum(v >= vt_post for v in placebo.values())
    units = len(donors) + 1
    return {
        "specification": label,
        "n_donors": len(donors),
        "mean_post_gap": round(float(gap.loc[POST].mean()), 2),
        "gap_2024": round(float(gap.loc[2024]), 2),
        "pre_rmspe": round(vt_pre, 3),
        "post_rmspe": round(vt_post, 3),
        "post_rmspe_rank": rank,
        "units": units,
        "p": round(rank / units, 3),
        "finest_achievable_p": round(1 / units, 3),
        "weights": {
            k: round(float(v), 4)
            for k, v in weights[weights > .005].sort_values(ascending=False).items()
        },
    }


def main():
    panel = sm.load_panel()
    donors = [s for s in sorted(panel.state.unique()) if s not in sm.EXCLUDE]

    pre = panel[panel.year.isin(PRE)]
    ma_mean = pre.groupby("state")["MA_PRTCPTN_RATE"].mean()
    vt_ma = float(ma_mean.loc["VT"])
    restricted = [d for d in donors if abs(ma_mean.loc[d] - vt_ma) <= RESTRICT_PP]

    out = {
        "generated": str(date.today()),
        "model": "intercept-shifted synthetic control (the published specification)",
        "vt_pre_period_mean_ma": round(vt_ma, 4),
        "restrict_pp": RESTRICT_PP,
        "restricted_pool": restricted,
        "outcomes": {},
    }

    for outcome in OUTCOMES:
        baseline = run(panel, outcome, donors, "baseline (published)")

        sm.predictor_matrix = yearly_ma_predictor_matrix
        try:
            yearly = run(panel, outcome, donors, "yearly MA predictors")
        finally:
            sm.predictor_matrix = _original_predictor_matrix

        pool = run(panel, outcome, restricted, "restricted donor pool")

        for spec in (yearly, pool):
            spec["delta_mean_post_gap"] = round(
                spec["mean_post_gap"] - baseline["mean_post_gap"], 2
            )
            spec["pct_change_mean_post_gap"] = round(
                100 * (spec["mean_post_gap"] - baseline["mean_post_gap"])
                / abs(baseline["mean_post_gap"]), 1
            )
        out["outcomes"][outcome] = {
            "baseline": baseline, "yearly_ma": yearly, "restricted_pool": pool
        }

    path = HERE / "data" / "ma_robustness.json"
    path.write_text(json.dumps(out, indent=1))
    print("wrote", path.name)
    for outcome, res in out["outcomes"].items():
        print(f"\n{outcome}")
        for key in ("baseline", "yearly_ma", "restricted_pool"):
            r = res[key]
            d = f"  ({r.get('pct_change_mean_post_gap', 0):+.1f}%)" if key != "baseline" else ""
            print(f"  {r['specification']:24s} gap {r['mean_post_gap']:>9.1f}{d:>10s}"
                  f"  rank {r['post_rmspe_rank']:2d}/{r['units']:2d}  p={r['p']}")


if __name__ == "__main__":
    main()
