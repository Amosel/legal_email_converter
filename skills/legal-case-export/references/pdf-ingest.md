# PDF Ingest

Use this file only for `pdf-ingest` and `pdf-retry`.

## Default Route

Default command:

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder"
```

Default profile:
- `balanced`

Profile guidance:
- `quick`: text layer only, fastest, lowest coverage on scanned PDFs
- `balanced`: text layer first, OCR low-text files, best default
- `thorough`: OCR every file, slowest, highest coverage

## Verified Runtime Behaviors

These are strong claims for V1:
- dependency preflight runs before processing
- `quality_report.csv`, `failed_files.json`, and `manifest.json` are produced
- plain progress output is supported
- `rich` progress falls back to plain on non-interactive output
- `--quiet` gives summary-focused output
- resume support exists through `--resume <run_id>`
- retry support exists through `pdf-retry --from-csv ...`
- end-of-run summary includes counts, artifacts, and a next step

Do not claim:
- real parallel worker execution from `--workers`
- guaranteed OCR quality

## Command Patterns

Default ingest:

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder"
```

Richer terminal progress:

```bash
legal-email-converter pdf-ingest \
  --input "/path/to/pdf-or-folder" \
  --progress-style rich
```

Summary-only/log-friendly output:

```bash
legal-email-converter pdf-ingest \
  --input "/path/to/pdf-or-folder" \
  --quiet --no-color
```

Large PDF sampling:

```bash
legal-email-converter pdf-ingest \
  --input "/path/to/large.pdf" \
  --profile balanced \
  --max-pages 25
```

Retry targeted files:

```bash
legal-email-converter pdf-retry \
  --from-csv "/path/to/output/pdf_ingest/quality_report.csv" \
  --status failed,likely_bad_ocr \
  --profile thorough
```

## Large / Hard PDF Escalation

Use this progression:

1. Start with a light sample using `--max-pages`
2. If quality is still poor, increase the sample size
3. If needed, escalate to `thorough`
4. If OCR times out or quality remains weak, use targeted retry with a higher `--ocr-timeout`

Keep this as operator guidance. Do not describe it as automatic planning.

## Status Model

- `good`
- `low_text`
- `likely_bad_ocr`
- `failed`

Suggested interpretations:
- `good`: likely ready for downstream use
- `low_text`: inspect before downstream use
- `likely_bad_ocr`: likely needs retry or stronger OCR pass
- `failed`: processing did not complete for that file

## Preflight and Recovery

If preflight fails:
- surface the dependency or path issue clearly
- include the install hint when the runtime provides one

If OCR quality is weak:
- point to `quality_report.csv`
- recommend `pdf-retry`

If OCR times out:
- mention `--ocr-timeout`

If a run was interrupted:
- mention `--resume <run_id>`

## Summary Guidance

Good summary elements:
- selected profile
- status counts
- artifact locations
- next command when retry is warranted

Good phrasing:
- "What happened: starting extraction with automatic quality checks."
- "What it means: review low_text and likely_bad_ocr rows before downstream use."

Avoid phrasing that promises:
- perfect OCR
- guaranteed clean text
- parallel speedup
