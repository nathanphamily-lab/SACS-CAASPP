"""Build the Task 1 ground-truth fixture from sources that are independent of the pipeline's
own parsing of the SACS .mdb:

  * LAUSD's board-approved Unaudited Actuals, SACS Form 01 (General Fund), as published on
    CDE's SACS Data Viewer (viewer.sacs-cde.org). PDFs in data/raw/lausd_filings/.
    The "Expenditures by Function" page gives total-fund (col. C) amounts for objects
    1000-7999 (excluding 7600-7699 transfers out), by function group.
  * CAASPP % met or exceeded, as read from the CAASPP results site (caaspp-elpac.ets.org)
    by hand. Entered below, not parsed from the research files.

    python src/ground_truth.py     # writes data/ground_truth/lausd_expected.csv
"""
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
FILINGS = ROOT / "data" / "raw" / "lausd_filings"
OUT = ROOT / "data" / "ground_truth" / "lausd_expected.csv"

# Form 01 line, matched by its function-code range: the labels don't extract reliably
# from older PDFs (2022-23 and 2023-24 come out as "Serv ices", with doubled spaces).
FUNCTION_LINES = {
    "1000-1999": "1000 Instruction",
    "2000-2999": "2000 Instruction-Related Services",
    "3000-3999": "3000 Pupil Services",
    "4000-4999": "4000 Ancillary Services",
    "5000-5999": "5000 Community Services",
    "6000-6999": "6000 Enterprise",
    "7000-7999": "7000 General Administration",
    "8000-8999": "8000 Plant Services",
    "9000-9999": "9000 Other Outgo",
    "TOTAL, EXPENDITURES": "TOTAL",
}
NUM = r"\(?-?[\d,]+\.\d{2}\)?"

# Read from caaspp-elpac.ets.org "Test Results at a Glance", LAUSD, all students, all grades.
CAASPP_SITE = {
    "2022-23": {"ela": 41.17, "math": 30.50},
    "2023-24": {"ela": 43.06, "math": 32.83},
    "2024-25": {"ela": 46.46, "math": 36.76},
}


def _num(s: str) -> float:
    neg = s.startswith("(")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


def filing_year(text: str) -> str:
    """Fiscal year of the Unaudited Actuals column, e.g. '2024-25'."""
    m = re.search(r"(\d{4}-\d{2}) Unaudited Actuals", text)
    if not m:
        raise ValueError("not an Unaudited Actuals filing")
    return m.group(1)


def function_page(reader: PdfReader) -> tuple[int, str]:
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if "Expenditures by Function" in t and "B. EXPENDITURES (Objects 1000-7999)" in t:
            return i + 1, t
    raise ValueError("no Expenditures by Function page")


def parse_filing(path: Path) -> pd.DataFrame:
    reader = PdfReader(path)
    first = reader.pages[0].extract_text()
    if "Los Angeles Unified" not in first or "Form 01" not in first:
        raise ValueError(f"{path.name} is not LAUSD's Form 01")
    year = filing_year(first)
    page_no, text = function_page(reader)
    body = text[text.find("B. EXPENDITURES (Objects 1000-7999)"):]
    body = " ".join(body.split())  # re-join labels split across lines

    rows = []
    for label, function in FUNCTION_LINES.items():
        # columns: unrestricted (A), restricted (B), total fund (C), then budget columns
        # (text can run on after the code, e.g. "9000-9999 Except 7600-7699")
        m = re.search(re.escape(label) + r".{0,40}?(" + NUM + r") (" + NUM + r") (" + NUM + r")", body)
        if not m:
            raise ValueError(f"{path.name}: line {label!r} not found")
        rows.append({"year": year, "measure": "gf_expenditure", "function": function,
                     "expected": _num(m.group(3)),
                     "source": f"LAUSD Unaudited Actuals {year}, Form 01 Expenditures by Function "
                               f"(p. {page_no}, col. C Total Fund); {path.name}"})
    return pd.DataFrame(rows)


# Form A (average daily attendance) lines; columns are P-2, Annual, Funded, then budget.
# The Annual column is what SACS LEAs.K12ADA and Charters.K12ADA carry.
FORM_A_LINES = {
    "k12_ada": r"4\. Total, District Regular ADA \(Sum of Lines A1 through A3\)",
    "fund01_charter_ada": r"4\. TOTAL CHARTER SCHOOL ADA \(Sum of Lines C1, C2d, and C3f\)",
}


def parse_form_a(path: Path) -> pd.DataFrame:
    reader = PdfReader(path)
    text = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
    if "Los Angeles Unified" not in text or "Form A" not in text:
        raise ValueError(f"{path.name} is not LAUSD's Form A")
    year = filing_year(text)
    rows = []
    for measure, label in FORM_A_LINES.items():
        m = re.search(label + r" (" + NUM + r") (" + NUM + r")", text)
        if not m:
            raise ValueError(f"{path.name}: Form A line for {measure} not found")
        rows.append({"year": year, "measure": measure, "function": "", "expected": _num(m.group(2)),
                     "source": f"LAUSD Unaudited Actuals {year}, Form A, Annual ADA column; {path.name}"})
    return pd.DataFrame(rows)


def filing_paths() -> list[Path]:
    """Loose PDFs saved from the viewer, plus Form 01 from unzipped 'Download all' folders
    (lausd_filings/<year>/, filled by `python src/sacs_viewer.py ingest`)."""
    return sorted(FILINGS.glob("*.pdf")) + sorted(FILINGS.glob("*/*_Fund-A_01.pdf"))


def build() -> pd.DataFrame:
    parts = [parse_filing(p) for p in filing_paths()]
    spend = pd.concat(parts, ignore_index=True)
    # The same year can arrive twice (a loose PDF and a Download-all copy). Keep one, but
    # only if the two copies agree line for line.
    per_year = spend.groupby(["year", "function"])["expected"].nunique()
    if (per_year > 1).any():
        raise ValueError(f"filings disagree for {sorted(per_year[per_year > 1].index.get_level_values(0).unique())}")
    spend = spend.drop_duplicates(["year", "function"])
    ada = pd.concat([parse_form_a(p) for p in sorted(FILINGS.glob("*/*_A.pdf"))], ignore_index=True)
    scores = pd.DataFrame([
        {"year": y, "measure": f"{subj}_pct_met_or_exceeded", "function": "", "expected": v,
         "source": "caaspp-elpac.ets.org Test Results at a Glance, LAUSD, all students, all grades"}
        for y, d in CAASPP_SITE.items() for subj, v in d.items()])
    return pd.concat([spend, ada, scores], ignore_index=True).sort_values(["year", "measure", "function"])


if __name__ == "__main__":
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(df.to_string(index=False, max_colwidth=50))
    print(f"\nWrote {OUT}; filing years: {sorted(df[df.measure == 'gf_expenditure'].year.unique())}")
