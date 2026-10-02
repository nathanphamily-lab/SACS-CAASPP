"""CDS code handling: the canonical join key between SACS and CAASPP.

A CDS code is 14 digits: county (2) + district (5) + school (7).
District-level records use school code 0000000.

Verified for 2022-23, 2023-24 and 2024-25 (notes/task2_identifiers.md):
  CDE directory  pubdistricts.txt 'CD Code'         -> '1964733'
  SACS           LEAs.Ccode/Dcode                   -> '19' / '64733'
  CAASPP         County Code/District Code/School Code -> '19' / '64733' / '0000000'
All three use native CDS components, so no crosswalk table is needed.
Re-verify this for every new year added.
"""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
DISTRICT_SCHOOL_CODE = "0000000"


@dataclass(frozen=True)
class CDS:
    county: str
    district: str
    school: str = DISTRICT_SCHOOL_CODE

    @classmethod
    def parse(cls, code: str) -> "CDS":
        code = code.strip()
        if len(code) != 14 or not code.isdigit():
            raise ValueError(f"CDS code must be 14 digits, got {code!r}")
        return cls(code[:2], code[2:7], code[7:])

    @property
    def code(self) -> str:
        return self.county + self.district + self.school

    @property
    def is_district(self) -> bool:
        return self.school == DISTRICT_SCHOOL_CODE


def directory_record(cds: CDS) -> dict:
    """CDE public districts directory (cde.ca.gov/ds/si/ds/pubschls.asp, "Public Districts"
    TXT). Districts are keyed by the 7-digit 'CD Code' = county (2) + district (5)."""
    path = RAW / "cde" / "pubdistricts.txt"
    d = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, encoding="utf-8")
    hit = d[d["CD Code"] == cds.county + cds.district]
    if len(hit) != 1:
        raise LookupError(f"Expected 1 directory record for {cds.county}{cds.district}, found {len(hit)}")
    return hit.iloc[0].to_dict()


def caaspp_entity(cds: CDS, year: str = "2025") -> dict:
    """Return the CAASPP entities-file record for one CDS code (names, type)."""
    path = RAW / "caaspp" / f"sb_ca{year}entities_csv.txt"
    ent = pd.read_csv(path, sep="^", dtype=str, keep_default_na=False, encoding="latin-1")
    hit = ent[
        (ent["County Code"] == cds.county)
        & (ent["District Code"] == cds.district)
        & (ent["School Code"] == cds.school)
    ]
    if len(hit) != 1:
        raise LookupError(f"Expected 1 CAASPP entity for {cds.code}, found {len(hit)}")
    return hit.iloc[0].to_dict()
