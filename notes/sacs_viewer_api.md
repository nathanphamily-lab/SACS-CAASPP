# Getting Unaudited Actuals from CDE's SACS Data Viewer

LAUSD's own finance sites (accounting.lausd.org, finance.lausd.org) are hard-blocked by Cloudflare. CDE's SACS Data Viewer (viewer.sacs-cde.org) hosts the same board-approved filings, for 2022-23 onward. These endpoints were read from the viewer's JS bundle (`main.b66bf5b74af942c6.js`) on 2026-09-30.

| Call | Body / path | What it returns | Captcha? |
|---|---|---|---|
| `POST /api/SubmissionArtifacts/Items` | `{"request":{"data":{fullFiscalYear, reportingPeriod, cdsCode, "excludeArtifactTypes":["All"]}, "first":0, "rows":5000, "sorts":[]}, "runMode":null, "testRunId":null, "timeZoneId":"America/Los_Angeles"}` | every file for one district/year/period (435–449 for LAUSD) | no |
| `POST /api/SubmissionArtifact` | `{"request":{fullFiscalYear, reportingPeriod, cdsCode, "includeArtifactTypes":["All"]}, ...}` (note: no `data` wrapper) | the "Download all" ZIP's metadata (`…_ZipAll.zip`) | no |
| `GET /api/Captcha/CaptchaData` | — | `{siteKey, disabled}`; `disabled` is `false` | — |
| `POST /api/Captcha/ValidateToken/{token}` | Cloudflare Turnstile token | `{success}` | this *is* the captcha check |
| `GET /api/SubmissionArtifact/{id}/Blob` | — | the file bytes | the app calls it only after `ValidateToken` succeeds |

Reporting periods: `A` Unaudited Actuals, `BS1` Budget, `I1` / `I2` First and Second Interim.

## What's automatic and what isn't
- **Automatic:** `python src/sacs_viewer.py list <cds> <years…>` finds each year's Form 01, Form A (ADA), Form CEA, the data extract, the DAT file and the "Download all" ZIP. It writes them to `data/raw/filings/<cds>/viewer_manifest_<cds>_A.csv`.
- **Needs a person, once per year:** the download itself. Cloudflare Turnstile protects the viewer's downloads, and the pipeline deliberately doesn't call `/Blob` without a token a person solved. Getting around it would mean defeating the site's bot check.
  - To download: open the viewer, pick the year, "Unaudited Actuals" and the district, then **Download all**, and solve the captcha. That's 3 captchas for 3 years, and each ZIP holds every form.
  - Then run `python src/sacs_viewer.py ingest <cds>`. It moves each `*_ZipAll.zip` whose name is in the manifest from `~/Downloads` into `data/raw/filings/<cds>/<year>/` and unzips it.
  - `python src/ground_truth.py` then picks up each year's `*_Fund-A_01.pdf`.
- **Routine runs need none of this.** The pipeline's numbers come from the SACS `.mdb` on `www3.cde.ca.gov`, which has no captcha. That file matches LAUSD's Form 01 to the cent (2024-25, every function and the total) and CDE's state totals to the cent for 2022-23, 2023-24 and 2024-25. The filings are only for independent verification.

## For fully hands-off downloads
The legitimate route is to ask CDE: Financial Accountability & Information Services, sacsinfo@cde.ca.gov. Ask for bulk or API access to SACS Data Viewer artifacts for research use, or for a captcha-exempt key. The user sends that request; it isn't automated.
