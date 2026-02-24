# PDF Ingest UX Spec

## Command Surface

- `legal-email-converter pdf-ingest --input <dir_or_file> --profile <quick|balanced|thorough>`
- `legal-email-converter pdf-retry --from quality_report.csv --status <statuses> --profile <profile>`

## Profiles

- `quick`
  - Uses direct text extraction only (`pdftotext`).
  - No OCR fallback.
  - Fastest turnaround, lowest coverage on scanned PDFs.
- `balanced` (default)
  - Runs direct text extraction first.
  - Routes low-text files to OCR.
  - Best default tradeoff for speed and coverage.
- `thorough`
  - OCR all PDFs.
  - Slowest, highest likely text coverage.

## Preflight

- Validate input path exists and is readable.
- Validate output path writable.
- Validate dependencies:
  - `pdftotext` always required.
  - OCR dependencies required for `balanced`/`thorough`.
- On missing OCR dependency:
  - Print actionable install command.
  - Offer fallback to `quick`.

## File-Level Routing Logic

- Initial pass extracts direct text.
- Compute quality metrics per file:
  - `pages`
  - `chars_extracted`
  - `chars_per_page`
- If in `balanced` profile:
  - Route file to OCR when below threshold.

## Status Model

- `good`
- `low_text`
- `likely_bad_ocr`
- `failed`

## Initial Quality Thresholds

- `low_text`: `chars_per_page < 40`
- `likely_bad_ocr`: OCR used and `chars_per_page < 15`
- `failed`: extraction/processing exception or timeout

## Progress UX

- Show aggregate progress (not noisy per-line spam):
  - files done / total
  - current mode (text-layer or OCR)
  - current file
  - ETA
- Update every N files and on stage transitions.

## End-of-Run Summary UX

- Print counts by status:
  - `good`, `low_text`, `likely_bad_ocr`, `failed`
- Print where reports were written.
- Print recommended next action:
  - review flagged files,
  - run retry command for failed/low-quality files.

## Artifacts

- `manifest.json`
  - includes per-file mode and quality fields.
- `quality_report.csv`
  - columns:
    - `file_path`
    - `pages`
    - `mode_used`
    - `chars_extracted`
    - `chars_per_page`
    - `status`
    - `warning`
    - `retry_suggested`
- `failed_files.json`
  - machine-readable retry set.

## Retry Flow

- `pdf-retry` accepts prior report and status filters.
- Reprocess only selected files.
- Merge results back into updated manifest/report.

## Interrupt and Resume

- Persist per-file run state to `.run_state/<run_id>.jsonl`.
- Resume command:
  - `legal-email-converter pdf-ingest --resume <run_id>`
- Completed files are skipped unless forced.

## Timeout UX

- On timeout:
  - mark file as `failed`
  - include timeout in warning text
  - suggest higher `--ocr-timeout` for large scanned files

## Default Tuning Guidance

- Single very large PDF:
  - `workers=1`
  - `ocr_jobs=2`
- Many large PDFs:
  - `workers=2`
  - `ocr_jobs=2`

## Example UX Copy

- Preflight:
  - `Preflight: checking dependencies and filesystem access...`
- Route decision:
  - `scan_224.pdf -> low text; queued for OCR`
- Progress:
  - `Progress: 37/250 files | mode=ocr | current=scan_224.pdf | ETA=18m`
- Completion:
  - `Completed: 250 files | good=221 low_text=18 likely_bad_ocr=7 failed=4`

