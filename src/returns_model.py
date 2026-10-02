"""Which kinds of dollars go with below-par, par, and above-par results across one
district's schools (LAUSD 2024-25), for score LEVELS or score GROWTH.

    python src/returns_model.py --outcome both      # default; also: level, growth

ASSOCIATIONAL, NOT CAUSAL. Money is not assigned to schools at random: Title I and other
federal dollars follow poverty by design, and special-ed dollars follow students with
disabilities. The controls absorb some of that, not all of it. The results show where
spending and results look out of line and are worth a closer look. They don't prove
that a dollar caused a result.

Outcome switch (one tidy table; a dashboard toggle filters the `outcome` column):
  level   y = 2025 % met or above.             Controls = demographics.
  growth  y = 2025 minus 2024 % met or above.  Controls = demographics + 2024 score
          (low scorers tend to rise, high scorers to slip; the prior score absorbs that).
  Demographics = % FRPM, % EL, % SWD, grade span, log enrollment.

ROI scale: Method A per $1,000/pupil (a realistic step: federal SD across schools ~$1,100);
per-school ratios (B, C) per $10,000/pupil, so a typical school reads ~1 point, not ~0.1.
  Method A (district par ROI): model coefficient on each kind of dollar, in points per
           $1,000/pupil, with 95% CIs. "par_roi" on total dollars comes from the same
           model using total $/pupil.
  Method B (school vs par): par = what demographics, prior score (growth), and the
           district par ROI x the school's spending predict. vs_par = actual - par.
           roi_per_10k = actual / ($/pupil / 10,000); par_roi_per_10k = par / same.
           Band: vs_par beyond +/- 0.5 SD. Because the two ratios share a denominator,
           roi_per_10k > par_roi_per_10k exactly when vs_par > 0.
  Method C (peer cross-check, no regression): peer group = elementary/secondary x FRPM
           tercile (x prior-score tercile for growth). Peer par = group median of
           roi_per_10k; band = within-group deviation beyond +/- 0.5 SD.
           Groups under 15 schools are flagged.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import school_data
from cds_lookup import CDS

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
X_DOLLARS = 1000           # Method A: marginal step (federal SD across schools ~$1,100)
SCHOOL_X_DOLLARS = 10_000  # Methods B/C: per-school ratios (~1 point per $10k at the median)
DEMOGRAPHICS = "pct_frpm + pct_el + pct_swd + C(span, Treatment('elementary')) + np.log(enrollment)"
SUBJECTS = ("ela", "math")
OUTCOMES = ("level", "growth")
BAND_SD = 0.5
MIN_PEERS = 15
KINDS = {"fed_k": "Federal", "sl_k": "State & local", "total_k": "All dollars"}
PRIOR = school_data.PRIOR_YEAR


def fit(df: pd.DataFrame, formula: str):
    return smf.ols(formula, data=df).fit(cov_type="HC3")


def band(z: pd.Series) -> pd.Series:
    return pd.Series(np.select([z < -BAND_SD, z > BAND_SD], ["below par", "above par"], "par"),
                     index=z.index)


def spec(outcome: str, subj: str) -> tuple[str, str]:
    """(dependent variable, controls) for one outcome/subject."""
    if outcome == "level":
        return f"{subj}_pct_met", DEMOGRAPHICS
    return f"{subj}_growth", f"{DEMOGRAPHICS} + {subj}_pct_met_{PRIOR}"


def growth_sample(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ok = pd.Series(True, index=df.index)
    for subj in SUBJECTS:
        ok &= (df[f"{subj}_tested_{PRIOR}"] >= school_data.MIN_TESTED) & df[f"{subj}_growth"].notna()
    dropped = df[~ok].assign(school_type=df["school_type"],
                             reason=f"no {PRIOR} score or fewer than {school_data.MIN_TESTED} tested in {PRIOR}")
    return df[ok].reset_index(drop=True), dropped[["cds", "school_name", "school_type", "reason"]]


def peer_groups(df: pd.DataFrame, outcome: str, subj: str) -> pd.Series:
    level = np.where(df["span"] == "elementary", "elem", "secondary")
    frpm = pd.qcut(df["pct_frpm"], 3, labels=["lowFRPM", "midFRPM", "highFRPM"]).astype(str)
    g = pd.Series(level, index=df.index) + "|" + frpm
    if outcome == "growth":
        prior = pd.qcut(df[f"{subj}_pct_met_{PRIOR}"], 3, labels=["lowPrior", "midPrior", "highPrior"]).astype(str)
        g = g + "|" + prior
    return g


def run(cds: CDS, outcome: str):
    """One outcome ('level' or 'growth'). Returns tidy (schools, coefs, fit_stats, excluded)."""
    df, excluded = school_data.build(cds)
    if outcome == "growth":
        df, extra = growth_sample(df)
        excluded = pd.concat([excluded, extra], ignore_index=True)
    df = df.assign(fed_k=df["fed_ppe"] / X_DOLLARS, sl_k=df["sl_ppe"] / X_DOLLARS,
                   total_k=df["total_ppe"] / X_DOLLARS)

    rows, coefs, stats = [], [], []
    for subj in SUBJECTS:
        y, controls = spec(outcome, subj)
        demo = fit(df, f"{y} ~ {controls}")
        by_kind = fit(df, f"{y} ~ {controls} + fed_k + sl_k")
        total = fit(df, f"{y} ~ {controls} + total_k")

        # Method A
        for term, label in KINDS.items():
            m = total if term == "total_k" else by_kind
            lo, hi = m.conf_int().loc[term]
            coefs.append({"outcome": outcome, "subject": subj, "kind_of_dollar": label,
                          "par_roi_per_1000": m.params[term], "ci_low": lo, "ci_high": hi,
                          "p_value": m.pvalues[term]})
        stats.append({"outcome": outcome, "subject": subj, "n": int(demo.nobs),
                      "r2_controls_only": demo.rsquared, "r2_with_spending": by_kind.rsquared,
                      "residual_sd_pts": total.resid.std()})

        # Method B
        s = df[["cds", "school_name", "span", "enrollment", "pct_frpm", "pct_el", "pct_swd",
                "fed_ppe", "sl_ppe", "total_ppe"]].copy()
        s.insert(0, "subject", subj)
        s.insert(0, "outcome", outcome)
        s["prior_pct_met"] = df[f"{subj}_pct_met_{PRIOR}"] if f"{subj}_pct_met_{PRIOR}" in df else np.nan
        s["actual"] = df[y]
        s["expected_demographics"] = demo.fittedvalues
        s["par"] = total.fittedvalues
        s["vs_par"] = total.resid
        s["z"] = total.resid / total.resid.std()
        s["band"] = band(s["z"])
        s["roi_per_10k"] = s["actual"] / (df["total_ppe"] / SCHOOL_X_DOLLARS)
        s["par_roi_per_10k"] = s["par"] / (df["total_ppe"] / SCHOOL_X_DOLLARS)

        # Method C
        s["peer_group"] = peer_groups(df, outcome, subj)
        g = s.groupby("peer_group")["roi_per_10k"]
        s["peer_n"] = g.transform("size")
        s["peer_par_roi_per_10k"] = g.transform("median")
        dev = s["roi_per_10k"] - s["peer_par_roi_per_10k"]
        s["peer_band"] = band(dev / dev.std())
        s["peer_group_small"] = s["peer_n"] < MIN_PEERS
        rows.append(s)

    return (pd.concat(rows, ignore_index=True), pd.DataFrame(coefs),
            pd.DataFrame(stats), excluded.assign(outcome=outcome))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outcome", choices=[*OUTCOMES, "both"], default="both")
    args = ap.parse_args()
    outcomes = OUTCOMES if args.outcome == "both" else (args.outcome,)

    cds = CDS.parse("19647330000000")
    parts = [run(cds, o) for o in outcomes]
    schools, coefs, stats, excluded = (pd.concat(p, ignore_index=True) for p in zip(*parts))

    PROCESSED.mkdir(parents=True, exist_ok=True)
    stem = f"{cds.county}{cds.district}_2425"
    schools.round(4).to_csv(PROCESSED / f"school_returns_{stem}.csv", index=False)
    coefs.round(4).to_csv(PROCESSED / f"returns_by_kind_{stem}.csv", index=False)
    stats.round(4).to_csv(PROCESSED / f"model_fit_{stem}.csv", index=False)
    excluded.to_csv(PROCESSED / f"excluded_schools_{stem}.csv", index=False)

    pd.set_option("display.width", 200)
    print("ASSOCIATIONAL, NOT CAUSAL: see module docstring.\n")
    print(stats.round(3).to_string(index=False))
    print(f"\nMethod A: par ROI, points per ${X_DOLLARS:,}/pupil (95% CI):")
    print(coefs.round(3).to_string(index=False))
    agree = schools.assign(same=schools["band"] == schools["peer_band"]).groupby(["outcome", "subject"])["same"].mean()
    print("\nMethod B vs C band agreement:\n", (agree * 100).round(1).astype(str).add("%").to_string())
    print("\nBands (Method B):\n", schools.groupby(["outcome", "subject"])["band"].value_counts().unstack().to_string())
    print(f"\nOutputs in {PROCESSED}")


if __name__ == "__main__":
    main()
