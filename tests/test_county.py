"""Phase 2: the LA County run (79 districts, 2022-23 -> 2024-25).

Needs the outputs of `python src/la_county.py` and `python src/run_county.py`.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import caaspp_parser  # noqa: E402
import join  # noqa: E402
import la_county  # noqa: E402

YEARS = ["2022-23", "2023-24", "2024-25"]
DISTRICTS = pd.read_csv(la_county.OUT, dtype=str)
TABLE = pd.read_csv(ROOT / "data" / "processed" / "la_county_2223-2425.csv", dtype={"cds": str})
LOG = pd.read_csv(ROOT / "data" / "processed" / "run_log.csv", dtype={"cds": str})


def test_district_list_is_79_and_matches_sacs_every_year():
    assert len(DISTRICTS) == 79
    assert DISTRICTS.district_type.value_counts().to_dict() == {"Unified": 48, "Elementary": 26, "High School": 5}
    assert la_county.cross_check(DISTRICTS) == []


def test_every_district_year_is_present_none_dropped():
    got = set(map(tuple, TABLE[["cds", "year"]].drop_duplicates().values))
    want = {(c, y) for c in DISTRICTS.cds for y in YEARS}
    assert got == want


def test_run_log_covers_every_step():
    assert len(LOG) == 79 * 3 * 2
    assert LOG.ok.all(), LOG[~LOG.ok].to_string()


def test_per_pupil_is_spend_over_ada_and_never_zero_for_missing():
    ok = TABLE[TABLE.ada > 0]
    assert np.allclose(ok.spend_per_pupil, (ok.spend_total / ok.ada).round(2))
    assert TABLE.loc[~(TABLE.ada > 0), "spend_per_pupil"].isna().all()


def test_lausd_rows_equal_phase1_output():
    p1 = pd.read_csv(ROOT / "data" / "processed" / "19647330000000_2223-2425.csv")
    p2 = TABLE[TABLE.cds == "19647330000000"]
    cols = ["year", "function", "spend_per_pupil", "ela_pct_met_or_exceeded", "math_pct_met_or_exceeded", "ada"]
    pd.testing.assert_frame_equal(p1[cols].reset_index(drop=True), p2[cols].reset_index(drop=True))


def test_scores_null_not_zero_when_unavailable():
    for col in ("ela_pct_met_or_exceeded", "math_pct_met_or_exceeded"):
        assert not (TABLE[col] == 0).any()


def test_suppressed_score_is_null_and_flagged(monkeypatch):
    """No LA County district had a suppressed district-level score in 2023-2025, so this
    exercises the path with a synthetic '*' row."""
    real = caaspp_parser._district_rows

    def fake(test_year):
        df = real(test_year).copy()
        hit = (df["County Code"] == "19") & (df["District Code"] == "64626") & (df["School Code"] == "0000000") \
            & (df["Test ID"] == "1")
        df.loc[hit, caaspp_parser.PCT_COL] = "*"
        return df

    monkeypatch.setattr(caaspp_parser, "_district_rows", fake)
    one = DISTRICTS[DISTRICTS.cds == "19646260000000"]
    table, _ = join.build_many(one, ["2024-25"])
    assert table.ela_pct_met_or_exceeded.isna().all()
    assert table.math_pct_met_or_exceeded.notna().all()
    assert (table.data_quality_flag == "ela_suppressed").all()


def test_combine_keeps_and_flags_a_year_missing_from_one_source():
    spend = pd.DataFrame({"function": ["1000 Instruction"], "spend_total": [100.0], "ada": [10.0],
                          "k12_ada": [10.0], "fund01_charter_ada": [0.0], "sacs_name": ["X"]})
    out = join.combine("X", {"2024-25": spend, "2025-26": None},
                       {"2024-25": {"ela_pct_met_or_exceeded": 40.0, "math_pct_met_or_exceeded": 30.0},
                        "2025-26": {"ela_pct_met_or_exceeded": 41.0, "math_pct_met_or_exceeded": 31.0}})
    assert out.groupby("year").data_status.first().to_dict() == {"2024-25": "both", "2025-26": "missing_sacs"}


@pytest.mark.parametrize("a,b", [("Lennox", "Lennox Elementary"), ("Whittier City", "Whittier City Elementary")])
def test_name_check_ignores_type_suffix(a, b):
    assert join._norm(a) == join._norm(b)


def test_name_check_still_catches_a_different_district():
    assert join._norm("Lennox") != join._norm("Lawndale Elementary")
