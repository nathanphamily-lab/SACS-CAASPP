"""CDE SACS Data Viewer (viewer.sacs-cde.org): find a district's filed reports.

The viewer is an Angular app over a JSON API (endpoints read from its JS bundle):
  POST api/SubmissionArtifacts/Items    list a district's files for a year/period (no captcha)
  POST api/SubmissionArtifact            the "Download all" ZIP's metadata for one
                                        district/year (includeArtifactTypes ["All"]; no captcha)
  GET  api/SubmissionArtifact/{id}/Blob download one file
  POST api/Captcha/ValidateToken/{t}    Cloudflare Turnstile check the app runs before
                                        every download

Listing is automatic. Downloading is gated by the captcha, so this module never calls
the Blob endpoint itself. It writes a manifest of the files we want, including each
year's "Download all" ZIP; a person downloads those through the viewer (one captcha per
year); `ingest` then files and unzips them. See notes/sacs_viewer_api.md.

    python src/sacs_viewer.py list   19647330000000 2022-23 2023-24 2024-25
    python src/sacs_viewer.py ingest 19647330000000 [folder with *_ZipAll.zip, default ~/Downloads]
"""
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

from cds_lookup import CDS, RAW

API = "https://viewer.sacs-cde.org/api"
PERIODS = {"A": "Unaudited Actuals", "BS1": "Budget, July 1", "I1": "First Interim",
           "I2": "Second Interim", "I3": "End of Year Projection"}

# File-name suffix -> what it is. One of each per district/year/period.
WANTED = {
    "Fund-A_01.pdf": "Form 01 General Fund (PDF)",
    "_A.pdf": "Form A, average daily attendance (PDF)",
    "_CEA.pdf": "Form CEA, current expense of education (PDF)",
    "DataExtract.xlsx": "all forms' data (Excel)",
    "DatExport.dat": "SACS import file (DAT)",
}


def list_artifacts(cds: CDS, fiscal_year: str, period: str = "A") -> pd.DataFrame:
    """Every file the viewer lists for one district, fiscal year ('2024-25'), and period."""
    body = {
        "request": {
            "data": {"fullFiscalYear": fiscal_year, "reportingPeriod": period,
                     "cdsCode": cds.code, "excludeArtifactTypes": ["All"]},
            "first": 0, "rows": 5000, "sorts": [],
        },
        "runMode": None, "testRunId": None, "timeZoneId": "America/Los_Angeles",
    }
    r = requests.post(f"{API}/SubmissionArtifacts/Items", json=body, timeout=60,
                      headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") != "Success":
        raise RuntimeError(f"viewer error for {cds.code} {fiscal_year}: {payload.get('errors')}")
    res = payload["response"]
    df = pd.DataFrame(res["results"])
    if len(df) != res["totalCount"]:
        raise RuntimeError(f"got {len(df)} of {res['totalCount']} rows; raise 'rows'")
    return df


def wanted_files(artifacts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for suffix, what in WANTED.items():
        hit = artifacts[artifacts["fileName"].str.endswith(suffix)]
        if len(hit) != 1:
            raise LookupError(f"expected one '{suffix}', found {len(hit)}")
        rows.append({**hit.iloc[0][["id", "fileName", "fileFormat", "fullFiscalYear",
                                    "reportingPeriod", "submissionNumber"]].to_dict(),
                     "what": what})
    return pd.DataFrame(rows)


def download_all_artifact(cds: CDS, fiscal_year: str, period: str = "A") -> dict:
    """Metadata for the viewer's "Download all" ZIP (every file for one district/year)."""
    body = {
        "request": {"fullFiscalYear": fiscal_year, "reportingPeriod": period,
                    "cdsCode": cds.code, "includeArtifactTypes": ["All"]},
        "runMode": None, "testRunId": None, "timeZoneId": "America/Los_Angeles",
    }
    r = requests.post(f"{API}/SubmissionArtifact", json=body, timeout=60,
                      headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    res = r.json().get("response") or {}
    if not res.get("hasValue"):
        raise LookupError(f"no Download-all ZIP for {cds.code} {fiscal_year} {period}")
    return {k: res[k] for k in ("id", "fileName", "fileFormat", "fullFiscalYear",
                                "reportingPeriod", "submissionNumber")} | {"what": "all files (ZIP)"}


FILINGS = RAW / "filings"  # data/raw/filings/<cds>/<year>/ (one folder per district)


def manifest_path(cds: CDS, period: str = "A") -> Path:
    return FILINGS / cds.code / f"viewer_manifest_{cds.code}_{period}.csv"


def write_manifest(cds: CDS, years: list[str], period: str = "A") -> Path:
    out = manifest_path(cds, period)
    out.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for y in years:
        parts.append(wanted_files(list_artifacts(cds, y, period)))
        parts.append(pd.DataFrame([download_all_artifact(cds, y, period)]))
    pd.concat(parts, ignore_index=True).to_csv(out, index=False)
    return out


def ingest(cds: CDS, source: Path, period: str = "A") -> list[Path]:
    """Move each year's downloaded *_ZipAll.zip from `source` into filings/<cds>/<year>/ and
    unzip it. Only ZIPs whose exact file name is in the manifest are accepted, so a stale
    or wrong-district download can't slip in."""
    manifest = pd.read_csv(manifest_path(cds, period))
    zips = manifest[manifest["fileFormat"] == "ZIP"]
    done = []
    for _, row in zips.iterrows():
        src = source / row["fileName"]
        if not src.exists():
            print(f"  not yet downloaded: {row['fileName']}")
            continue
        dest = FILINGS / cds.code / row["fullFiscalYear"]
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / row["fileName"]
        src.replace(target)
        with zipfile.ZipFile(target) as z:
            z.extractall(dest)
        done.append(dest)
        print(f"  {row['fullFiscalYear']}: unzipped {row['fileName']} -> {dest}")
    return done


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    cds = CDS.parse(sys.argv[2] if len(sys.argv) > 2 else "19647330000000")
    if cmd == "list":
        years = sys.argv[3:] or ["2022-23", "2023-24", "2024-25"]
        path = write_manifest(cds, years)
        print(pd.read_csv(path)[["fullFiscalYear", "what", "fileName"]].to_string(index=False))
        print(f"\nManifest: {path}")
    elif cmd == "ingest":
        src = Path(sys.argv[3]).expanduser() if len(sys.argv) > 3 else Path.home() / "Downloads"
        ingest(cds, src)
    else:
        sys.exit(f"unknown command {cmd!r}; use list or ingest")
