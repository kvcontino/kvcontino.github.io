"""Build the authoritative, publication-facing OneCare results manifest.

The heavy CMS input and original optimizer live in the companion
``onecare_retrospective`` project. Set ONECARE_SOURCE to that checkout when it is
not at the default sibling location. This script deliberately computes every
placebo statistic from the same intercept-shifted specification; the previous
publication accidentally mixed diagnostics from an older level-matched model.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get(
    "ONECARE_SOURCE",
    HERE.parents[2] / "onecare_retrospective",
))
sys.path.insert(0, str(SOURCE / "analysis"))
import synth_medicare as sm  # noqa: E402

PRE = [2014, 2015, 2016, 2017]
POST = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
sm.DATA = str(SOURCE / "data" / "geo_variation_2014_2024.csv")


def rmspe(series, years):
    return float(np.sqrt(np.mean(np.square(series.loc[years]))))


def fit(panel, outcome, treated, donors, pre=None, post=None):
    old_pre, old_post = sm.PRE_YEARS, sm.POST_YEARS
    sm.PRE_YEARS = pre or PRE
    sm.POST_YEARS = post or POST
    try:
        actual, synthetic, weights = sm.synth_gaps(
            panel, outcome, treated, donors, demean=True
        )
    finally:
        sm.PRE_YEARS, sm.POST_YEARS = old_pre, old_post
    return actual, synthetic, weights


def rank(values, target):
    return 1 + sum(value >= target for value in values.values())


def main():
    panel = sm.load_panel()
    donors = [
        state for state in sorted(panel.state.unique())
        if state not in sm.EXCLUDE
    ]
    outcomes = {}
    placebo_rows = []

    for key, label in sm.OUTCOMES.items():
        actual, synthetic, weights = fit(panel, key, "VT", donors)
        gap = actual - synthetic
        vt_post = rmspe(gap, POST)
        vt_pre = rmspe(gap, PRE)
        placebo_post, placebo_ratio = {}, {}

        for state in donors:
            p_actual, p_synthetic, _ = fit(
                panel, key, state, [d for d in donors if d != state]
            )
            p_gap = p_actual - p_synthetic
            p_pre, p_post = rmspe(p_gap, PRE), rmspe(p_gap, POST)
            placebo_post[state] = p_post
            placebo_ratio[state] = p_post / p_pre if p_pre else float("inf")
            placebo_rows.append({
                "outcome": key,
                "state": state,
                "post_rmspe": round(p_post, 6),
                "post_pre_ratio": round(placebo_ratio[state], 6),
            })

        post_rank = rank(placebo_post, vt_post)
        ratio_rank = rank(placebo_ratio, vt_post / vt_pre)

        cv = {}
        for held_out in PRE:
            train = [year for year in PRE if year != held_out]
            cv_actual, cv_synthetic, _ = fit(
                panel, key, "VT", donors, pre=train, post=[held_out] + POST
            )
            cv[str(held_out)] = round(
                float(cv_actual.loc[held_out] - cv_synthetic.loc[held_out]), 3
            )
        cv_rmse = float(np.sqrt(np.mean(np.square(list(cv.values())))))

        loo_2024 = {}
        for state, weight in weights[weights > .01].items():
            l_actual, l_synthetic, _ = fit(
                panel, key, "VT", [d for d in donors if d != state]
            )
            loo_2024[state] = round(
                float(l_actual.loc[2024] - l_synthetic.loc[2024]), 2
            )

        outcomes[key] = {
            "label": label,
            "estimand": (
                "Vermont minus an intercept-shifted synthetic comparison; "
                "incremental 2018 regime change over an already ACO-exposed baseline"
            ),
            "actual": {str(k): round(float(v), 2) for k, v in actual.items()},
            "synthetic": {
                str(k): round(float(v), 2) for k, v in synthetic.items()
            },
            "gap": {str(k): round(float(v), 2) for k, v in gap.items()},
            "weights": {
                k: round(float(v), 4)
                for k, v in weights[weights > .005]
                .sort_values(ascending=False).items()
            },
            "mean_post_gap": round(float(gap.loc[POST].mean()), 2),
            "mean_post_gap_pct": round(
                float(gap.loc[POST].mean() / synthetic.loc[POST].mean() * 100), 2
            ),
            "pre_rmspe": round(vt_pre, 3),
            "post_rmspe": round(vt_post, 3),
            "post_pre_ratio": round(vt_post / vt_pre, 3),
            "placebo": {
                "n": len(donors),
                "post_rmspe": {
                    "rank": post_rank,
                    "p": round(post_rank / (len(donors) + 1), 3),
                },
                "post_pre_ratio": {
                    "rank": ratio_rank,
                    "p": round(ratio_rank / (len(donors) + 1), 3),
                },
                "interpretation": (
                    "Exact ranks under two defensible discrepancy statistics; "
                    "neither is treated as a binary significance verdict."
                ),
            },
            "preperiod_cross_validation": {
                "leave_one_year_out_gap": cv,
                "rmse": round(cv_rmse, 3),
                "interpretation": (
                    "Four temporal holdouts are an overfit diagnostic, not a "
                    "sampling-based uncertainty interval."
                ),
            },
            "leave_one_contributing_donor_out": {
                "gap_2024_by_omitted_donor": loo_2024,
                "range": [
                    min(loo_2024.values()),
                    max(loo_2024.values()),
                ],
                "threshold": "baseline donor weight greater than 0.01",
            },
        }

    for outcome in outcomes.values():
        for statistic in ("post_rmspe", "post_pre_ratio"):
            raw = outcome["placebo"][statistic]["p"]
            outcome["placebo"][statistic]["bonferroni_three_outcomes"] = round(
                min(1, 3 * raw), 3
            )

    manifest = {
        "schema_version": 1,
        "generated": str(date.today()),
        "model": {
            "name": "intercept-shifted synthetic control",
            "treatment_year": 2018,
            "pre_period": PRE,
            "post_period": POST,
            "treated_unit": "VT",
            "excluded_donors": ["MD"],
            "primary_reporting_rule": (
                "Report both post-RMSPE and post/pre-RMSPE placebo ranks. "
                "Do not classify either as a definitive hypothesis test."
            ),
            "multiplicity": (
                "Three co-primary Medicare outcomes; interpret the most extreme "
                "rank in the family and avoid outcome-wise threshold claims."
            ),
        },
        "outcomes": outcomes,
        "limitations": [
            "Four pre-treatment years and one treated state.",
            "Treatment date is a regime change after substantial prior ACO exposure.",
            "Most post-treatment years overlap COVID-era disruption.",
            "Fee-for-service composition changes as Medicare Advantage grows.",
            "Statewide Medicare results do not identify Medicaid effects.",
        ],
    }
    (HERE / "data" / "results_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    import csv
    with (HERE / "data" / "scm_placebo_statistics.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=placebo_rows[0].keys())
        writer.writeheader()
        writer.writerows(placebo_rows)

    print("wrote data/results_manifest.json")
    print("wrote data/scm_placebo_statistics.csv")
    for key, value in outcomes.items():
        p = value["placebo"]
        print(
            key,
            "post rank", p["post_rmspe"]["rank"],
            "ratio rank", p["post_pre_ratio"]["rank"],
            "CV RMSE", value["preperiod_cross_validation"]["rmse"],
        )


if __name__ == "__main__":
    main()
