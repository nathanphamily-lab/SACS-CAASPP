"""Assemble one row per school for a single district: ESSA per-pupil spending + FRPM
demographics + CAASPP scores, joined on the 14-digit CDS code.

Sources (2024-25, all in data/raw/):
  cde/essappe2425data.xlsx   ESSA school-level per-pupil expenditures (already $/pupil).
                             Federal vs state & local, each split into school-site and
                             central (district-office costs allocated per pupil).
  cde/frpm2425.xlsx          School type, grade span, K-12 enrollment, % eligible FRPM.
  caaspp/sb_ca2025_1_csv_v1.txt    All-students scores (% met or above).
  caaspp/sb_ca2025_all_csv_v1.txt  All student groups; used only for the share of tested
                                   students who are English learners / have disabilities.
  caaspp/sb_ca2024_1_csv_v1.txt    Prior-year all-students scores, for growth.

The school set is ESSA's list for the district: the schools whose spending the district
itself reports. Independently reporting charters file as their own LEAs and are not in it.
"""
import numpy as np
import pandas as pd

from caaspp_parser import ALL_GRADES, PCT_COL, to_pct
from cds_lookup import CDS, RAW

CACHE = RAW / "cache"
MIN_TESTED = 30
PRIOR_YEAR = "2024"  # growth = 2025 score minus this year's score

# CAASPP student group IDs (StudentGroups.txt)
ALL_STUDENTS, SWD, EL = "1", "128", "160"

# Non-traditional schools: spending and testing patterns aren't comparable to
# neighborhood schools, so they're excluded from the model and listed separately.
EXCLUDED_TYPES = {
    "Alternative Schools of Choice", "Continuation High Schools",
    "Special Education Schools (Public)", "District Community Day Schools",
    "Opportunity Schools",
}
SPAN = {
    "Elementary Schools (Public)": "elementary",
    "Intermediate/Middle Schools (Public)": "middle",
    "High Schools (Public)": "high",
    "K-12 Schools (Public)": "k12",
}


def _sheet_with_header(path, sheet, first_col) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet, header=None, dtype=str)
    h = raw.index[raw[0] == first_col][0]
    df = raw.iloc[h + 1:].copy()
    df.columns = [" ".join(str(c).split()) for c in raw.iloc[h]]
    return df


def essa(cds: CDS) -> pd.DataFrame:
    df = _sheet_with_header(RAW / "cde" / "essappe2425data.xlsx", "ESSA School Data", "County")
    df = df[df["LEA CDS Code"] == cds.county + cds.district + "0000000"]
    num = {
        "Student Membership": "membership",
        "School Expenditures–Federal ($)": "fed_school",
        "School Expenditures–State & Local ($)": "sl_school",
        "Central Expenditures–Federal ($)": "fed_central",
        "Central Expenditures–State & Local ($)": "sl_central",
    }
    out = df[["School CDS Code", "School Name"]].rename(
        columns={"School CDS Code": "cds", "School Name": "school_name"})
    for src, dst in num.items():
        out[dst] = pd.to_numeric(df[src], errors="coerce")
    out["fed_ppe"] = out["fed_school"] + out["fed_central"]
    out["sl_ppe"] = out["sl_school"] + out["sl_central"]
    out["total_ppe"] = out["fed_ppe"] + out["sl_ppe"]
    return out


def frpm(cds: CDS) -> pd.DataFrame:
    df = pd.read_excel(RAW / "cde" / "frpm2425.xlsx", "FRPM School-Level Data", header=1, dtype=str)
    df.columns = [" ".join(c.split()) for c in df.columns]
    df = df[(df["County Code"] == cds.county) & (df["District Code"] == cds.district)]
    return pd.DataFrame({
        "cds": df["County Code"] + df["District Code"] + df["School Code"],
        "school_type": df["School Type"],
        "charter": df["Charter School (Y/N)"].str.strip(),
        "enrollment": pd.to_numeric(df["Enrollment (K-12)"], errors="coerce"),
        "pct_frpm": pd.to_numeric(df["Percent (%) Eligible FRPM (K-12)"], errors="coerce") * 100,
    })


def _caaspp_groups(cds: CDS) -> pd.DataFrame:
    """School-level CAASPP rows for this district (all grades), cached from the 1GB file."""
    cache = CACHE / f"caaspp2025_groups_{cds.county}{cds.district}.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype=str, keep_default_na=False)
    cols = ["County Code", "District Code", "School Code", "Test ID", "Student Group ID",
            "Grade", "Total Students Tested with Scores", PCT_COL]
    parts = []
    for chunk in pd.read_csv(RAW / "caaspp" / "sb_ca2025_all_csv_v1.txt", sep="^", dtype=str,
                             keep_default_na=False, usecols=cols, chunksize=500_000,
                             encoding="latin-1"):
        parts.append(chunk[(chunk["County Code"] == cds.county)
                           & (chunk["District Code"] == cds.district)
                           & (chunk["School Code"] != "0000000")
                           & (chunk["Grade"] == ALL_GRADES)
                           & chunk["Student Group ID"].isin([ALL_STUDENTS, SWD, EL])])
    df = pd.concat(parts)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def caaspp(cds: CDS) -> pd.DataFrame:
    df = _caaspp_groups(cds)
    df = df.assign(cds=df["County Code"] + df["District Code"] + df["School Code"],
                   tested=pd.to_numeric(df["Total Students Tested with Scores"], errors="coerce"),
                   pct=df[PCT_COL].map(to_pct))
    wide = df.pivot_table(index="cds", columns=["Test ID", "Student Group ID"],
                          values=["tested", "pct"], aggfunc="first")
    g = lambda v, t, s: wide.get((v, t, s), pd.Series(np.nan, index=wide.index))
    out = pd.DataFrame({
        "ela_tested": g("tested", "1", ALL_STUDENTS),
        "math_tested": g("tested", "2", ALL_STUDENTS),
        "ela_pct_met": g("pct", "1", ALL_STUDENTS),
        "math_pct_met": g("pct", "2", ALL_STUDENTS),
    })
    # Share of ELA test-takers who are EL / SWD. CAASPP suppresses subgroups under 11
    # students; those are counted as 0, which slightly understates small shares.
    for name, grp in [("pct_el", EL), ("pct_swd", SWD)]:
        out[name] = (g("tested", "1", grp).fillna(0) / out["ela_tested"] * 100)
    return out.reset_index()


def prior_scores(cds: CDS, test_year: str = PRIOR_YEAR) -> pd.DataFrame:
    """All-students school scores from an earlier year's _1_ file, for growth."""
    df = pd.read_csv(RAW / "caaspp" / f"sb_ca{test_year}_1_csv_v1.txt", sep="^", dtype=str,
                     keep_default_na=False, encoding="latin-1")
    df = df[(df["County Code"] == cds.county) & (df["District Code"] == cds.district)
            & (df["School Code"] != "0000000") & (df["Student Group ID"] == ALL_STUDENTS)
            & (df["Grade"] == ALL_GRADES) & df["Test ID"].isin(["1", "2"])]
    df = df.assign(cds=df["County Code"] + df["District Code"] + df["School Code"],
                   tested=pd.to_numeric(df["Total Students Tested with Scores"], errors="coerce"),
                   pct=df[PCT_COL].map(to_pct))
    wide = df.pivot_table(index="cds", columns="Test ID", values=["tested", "pct"], aggfunc="first")
    return pd.DataFrame({
        f"ela_tested_{test_year}": wide[("tested", "1")],
        f"math_tested_{test_year}": wide[("tested", "2")],
        f"ela_pct_met_{test_year}": wide[("pct", "1")],
        f"math_pct_met_{test_year}": wide[("pct", "2")],
    }).reset_index()


def build(cds: CDS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (modelled schools, excluded schools with a reason).

    Prior-year columns and growth (2025 minus 2024, in points) are attached but may be NaN;
    returns_model applies the extra growth sample rule."""
    df = (essa(cds).merge(frpm(cds), on="cds", how="left")
          .merge(caaspp(cds), on="cds", how="left")
          .merge(prior_scores(cds), on="cds", how="left"))
    for subj in ("ela", "math"):
        df[f"{subj}_growth"] = df[f"{subj}_pct_met"] - df[f"{subj}_pct_met_{PRIOR_YEAR}"]
    df["span"] = df["school_type"].map(SPAN)

    reason = pd.Series("", index=df.index)
    reason[df["school_type"].isin(EXCLUDED_TYPES)] = "non-traditional school type"
    reason[(reason == "") & df["school_type"].isna()] = "not in FRPM file"
    reason[(reason == "") & df["span"].isna()] = "unmapped school type"
    reason[(reason == "") & ~(df["ela_tested"] >= MIN_TESTED)] = f"fewer than {MIN_TESTED} tested / no scores"
    reason[(reason == "") & (df["ela_pct_met"].isna() | df["math_pct_met"].isna())] = "suppressed score"
    reason[(reason == "") & df[["total_ppe", "pct_frpm"]].isna().any(axis=1)] = "missing spending or FRPM"

    excluded = df[reason != ""].assign(reason=reason[reason != ""])
    return df[reason == ""].reset_index(drop=True), excluded[["cds", "school_name", "school_type", "reason"]]


if __name__ == "__main__":
    kept, dropped = build(CDS.parse("19647330000000"))
    print(f"kept {len(kept)} schools; excluded {len(dropped)}")
    print(dropped["reason"].value_counts().to_string())
    print(kept.describe().T[["mean", "min", "max"]].round(1).to_string())
