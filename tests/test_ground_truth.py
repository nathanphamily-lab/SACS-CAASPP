"""The pipeline vs hand-verified ground truth (data/ground_truth/expected.csv), per district.

Ground truth comes from each district's board-approved Unaudited Actuals (Form 01, Form A) and
the CAASPP results site, not from the pipeline's own files. Build it with
`python src/ground_truth.py`. Phase 1: LAUSD, 3 years. Phase 2: 3 more districts, 2024-25.

    .venv/bin/pytest -q
"""
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import caaspp_parser  # noqa: E402
import join  # noqa: E402
import sacs_parser  # noqa: E402
from cds_lookup import CDS, directory_record  # noqa: E402

LAUSD = CDS.parse("19647330000000")
YEARS = ["2022-23", "2023-24", "2024-25"]
# Which filed years each verified district must have ground truth for.
VERIFIED = {
    "19647330000000": YEARS,        # Los Angeles Unified (Phase 1)
    "19753410000000": ["2024-25"],  # Redondo Beach Unified: mid-size unified
    "19646260000000": ["2024-25"],  # Hughes-Elizabeth Lakes Union Elementary: small elementary
    "19651280000000": ["2024-25"],  # Whittier Union High: high school district
}
EXPECTED = pd.read_csv(ROOT / "data" / "ground_truth" / "expected.csv", keep_default_na=False, dtype={"cds": str})
SCORE_TOL = 0.011  # CAASPP site sums rounded Met + Exceeded; research file computes from counts
SPEND_TOL = Decimal("0.01")

KNOWN = pd.read_csv(ROOT / "data" / "ground_truth" / "known_differences.csv", dtype={"cds": str})
spend_rows = EXPECTED[EXPECTED.measure == "gf_expenditure"]
score_rows = EXPECTED[EXPECTED.measure.str.endswith("pct_met_or_exceeded")]
ada_rows = EXPECTED[EXPECTED.measure.isin(["k12_ada", "fund01_charter_ada"])]


@pytest.mark.parametrize("cds", VERIFIED)
def test_fixture_covers_every_verified_year(cds):
    """Each verified district must have filing-based ground truth for every year it's verified for."""
    for rows, what in [(spend_rows, "Form 01"), (ada_rows, "Form A")]:
        missing = sorted(set(VERIFIED[cds]) - set(rows[rows.cds == cds].year))
        assert not missing, f"no {what} for {cds} in data/raw/filings/{cds}/ for {missing}"
    scored = set(score_rows[score_rows.cds == cds].year)
    assert set(YEARS) <= scored, f"CAASPP site values missing for {cds}"


@pytest.mark.parametrize("row", spend_rows.to_dict("records"),
                         ids=lambda r: f"{r['cds']}-{r['year']}-{r['function']}")
def test_spending_matches_filing(row):
    fiscal, _ = join.year_codes(row["year"])
    ours = sacs_parser.form01_function_totals(CDS.parse(row["cds"]), fiscal).get(row["function"], Decimal(0))
    # Differences between CDE's statewide file and the district's filing must be explained
    # line by line in known_differences.csv; anything else fails.
    known = KNOWN[(KNOWN.cds == row["cds"]) & (KNOWN.year == row["year"]) & (KNOWN.function == row["function"])]
    allowed = Decimal(str(known.ours_minus_filing.sum())) if len(known) else Decimal(0)
    assert abs(ours - Decimal(str(row["expected"])) - allowed) <= SPEND_TOL, row["source"]


@pytest.mark.parametrize("row", score_rows.to_dict("records"),
                         ids=lambda r: f"{r['cds']}-{r['year']}-{r['measure']}")
def test_scores_match_caaspp_site(row):
    _, test_year = join.year_codes(row["year"])
    ours = caaspp_parser.proficiency(CDS.parse(row["cds"]), test_year)[row["measure"]]
    assert ours == pytest.approx(float(row["expected"]), abs=SCORE_TOL)


@pytest.mark.parametrize("row", ada_rows.to_dict("records"),
                         ids=lambda r: f"{r['cds']}-{r['year']}-{r['measure']}")
def test_ada_matches_form_a(row):
    fiscal, _ = join.year_codes(row["year"])
    assert sacs_parser.lea(CDS.parse(row["cds"]), fiscal)[row["measure"]] == pytest.approx(float(row["expected"]), abs=0.01)


def test_join_output_all_years_present_and_flagged_both():
    table = join.build(LAUSD, YEARS)
    assert sorted(table.year.unique()) == YEARS
    assert (table.data_status == "both").all()
    assert table.district_name.unique().tolist() == [directory_record(LAUSD)["District"]]
    # spend_per_pupil is exactly spend_total / ada, and ada = district + Fund 01 charter ADA
    assert np.allclose(table.spend_per_pupil, (table.spend_total / table.ada).round(2))
    assert np.allclose(table.ada, table.k12_ada + table.fund01_charter_ada)


def test_identifiers_agree_across_sources():
    rec = directory_record(LAUSD)
    assert rec["CD Code"] == LAUSD.county + LAUSD.district == "1964733"
    for y in YEARS:
        fiscal, _ = join.year_codes(y)
        assert sacs_parser.lea(LAUSD, fiscal)["district_name"] == rec["District"]


def test_combine_flags_years_missing_from_one_source():
    spend = pd.DataFrame({"function": ["1000 Instruction"], "spend_total": [100.0], "ada": [10.0],
                          "k12_ada": [8.0], "fund01_charter_ada": [2.0]})
    scores = {"ela_pct_met_or_exceeded": 40.0, "math_pct_met_or_exceeded": 30.0}
    out = join.combine("Test Unified",
                       spend={"2022-23": spend, "2023-24": spend, "2024-25": None},
                       scores={"2022-23": scores, "2023-24": None, "2024-25": scores})
    status = out.groupby("year")["data_status"].first().to_dict()
    assert status == {"2022-23": "both", "2023-24": "missing_caaspp", "2024-25": "missing_sacs"}
    assert len(out) == 3  # nothing dropped
    assert out.loc[out.year == "2022-23", "spend_per_pupil"].item() == 10.0
