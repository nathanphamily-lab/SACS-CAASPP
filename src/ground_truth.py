"""Build the ground-truth fixture from sources independent of the pipeline's own parsing of
the SACS .mdb, for every district that has filings on disk:

  * Each district's board-approved Unaudited Actuals from CDE's SACS Data Viewer, filed by
    `python src/sacs_viewer.py ingest <cds>` into data/raw/filings/<cds>/<year>/:
      - Form 01 (General Fund), "Expenditures by Function" page, total-fund column (C):
        objects 1000-7999 excluding 7600-7699 transfers out, by function group.
      - Form A (ADA), Annual ADA column: district regular ADA (line A4) and charter ADA
        reported in the district's Fund 01 (line C4).
  * CAASPP % met or exceeded as read from the CAASPP results site (caaspp-elpac.ets.org),
    recorded in data/ground_truth/caaspp_site.csv, not parsed from the research files.

    python src/ground_truth.py     # writes data/ground_truth/expected.csv
"""
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
FILINGS = ROOT / "data" / "raw" / "filings"
SITE_SCORES = ROOT / "data" / "ground_truth" / "caaspp_site.csv"
OUT = ROOT / "data" / "ground_truth" / "expected.csv"

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
# Form A lines; columns are P-2, Annual, Funded, then budget. The Annual column is what SACS
# LEAs.K12ADA and Charters.K12ADA carry.
FORM_A_LINES = {
    "k12_ada": r"4\. Total, District Regular ADA \(Sum of Lines A1 through A3\)",
    "fund01_charter_ada": r"4\. TOTAL CHARTER SCHOOL ADA \(Sum of Lines C1, C2d, and C3f\)",
}
NUM = r"\(?-?[\d,]+\.\d{2}\)?"


def _num(s: str) -> float:
    neg = s.startswith("(")
    v = float(s.strip("()").replace(",", ""))
    return -v if neg else v


def _cds_on_form(cds: str) -> str:
    """How SACS forms print a CDS code in their header: '19 64733 0000000'."""
    return f"{cds[:2]} {cds[2:7]} {cds[7:]}"


def filing_year(text: str) -> str:
    """Fiscal year of the Unaudited Actuals column, e.g. '2024-25'."""
    m = re.search(r"(\d{4}-\d{2}) Unaudited Actuals", text)
    if not m:
        raise ValueError("not an Unaudited Actuals filing")
    return m.group(1)


def _check_form(text: str, cds: str, form: str, path: Path) -> None:
    if _cds_on_form(cds) not in text or form not in text:
        raise ValueError(f"{path.name} is not {form} for CDS {cds}")


def function_page(reader: PdfReader) -> tuple[int, str]:
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if "Expenditures by Function" in t and "B. EXPENDITURES (Objects 1000-7999)" in t:
            return i + 1, t
    raise ValueError("no Expenditures by Function page")


def parse_form01(path: Path, cds: str) -> pd.DataFrame:
    reader = PdfReader(path)
    first = reader.pages[0].extract_text()
    _check_form(first, cds, "Form 01", path)
    year = filing_year(first)
    page_no, text = function_page(reader)
    body = " ".join(text[text.find("B. EXPENDITURES (Objects 1000-7999)"):].split())
    rows = []
    for label, function in FUNCTION_LINES.items():
        # columns: unrestricted (A), restricted (B), total fund (C), then budget columns.
        # Text can run on after the code, e.g. "9000-9999 Except 7600-7699".
        m = re.search(re.escape(label) + r".{0,40}?(" + NUM + r") (" + NUM + r") (" + NUM + r")", body)
        if not m:
            raise ValueError(f"{path.name}: line {label!r} not found")
        rows.append({"cds": cds, "year": year, "measure": "gf_expenditure", "function": function,
                     "expected": _num(m.group(3)),
                     "source": f"Unaudited Actuals {year}, Form 01 Expenditures by Function "
                               f"(p. {page_no}, col. C Total Fund); {path.name}"})
    return pd.DataFrame(rows)


def parse_form_a(path: Path, cds: str) -> pd.DataFrame:
    reader = PdfReader(path)
    text = " ".join(" ".join(p.extract_text() for p in reader.pages).split())
    _check_form(text, cds, "Form A", path)
    year = filing_year(text)
    rows = []
    for measure, label in FORM_A_LINES.items():
        m = re.search(label + r" (" + NUM + r") (" + NUM + r")", text)
        if m:
            value, note = _num(m.group(2)), "Annual ADA column"
        elif re.search(label, text):
            value, note = 0.0, "line present with no amounts (blank = 0)"
        else:
            raise ValueError(f"{path.name}: Form A line for {measure} not found")
        rows.append({"cds": cds, "year": year, "measure": measure, "function": "", "expected": value,
                     "source": f"Unaudited Actuals {year}, Form A, {note}; {path.name}"})
    return pd.DataFrame(rows)


def site_scores() -> pd.DataFrame:
    s = pd.read_csv(SITE_SCORES, dtype={"cds": str})
    rows = [{"cds": r.cds, "year": r.year, "measure": f"{subj}_pct_met_or_exceeded", "function": "",
             "expected": getattr(r, subj), "source": f"{r.source} (checked {r.checked})"}
            for r in s.itertuples() for subj in ("ela", "math")]
    return pd.DataFrame(rows)


def build() -> pd.DataFrame:
    parts = []
    for district in sorted(p for p in FILINGS.iterdir() if p.is_dir()):
        cds = district.name
        parts += [parse_form01(p, cds) for p in sorted(district.glob("*/*_Fund-A_01.pdf"))]
        parts += [parse_form_a(p, cds) for p in sorted(district.glob("*/*_A.pdf"))]
    filed = pd.concat(parts, ignore_index=True)
    if filed.duplicated(["cds", "year", "measure", "function"]).any():
        raise ValueError("two filings for the same district and year")
    out = pd.concat([filed, site_scores()], ignore_index=True)
    return out.sort_values(["cds", "year", "measure", "function"]).reset_index(drop=True)


if __name__ == "__main__":
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT}: {len(df)} rows")
    print(df[df.measure == "gf_expenditure"].groupby("cds").year.unique().to_string())
