# Large/Hard PDF UX Acceptance

This checklist is for very large PDFs and hard-to-read scans.
Use it alongside `UX_ACCEPTANCE.md`.

## Goals

- Keep first-pass feedback fast and actionable.
- Minimize wasted OCR time when quality is already unacceptable.
- Provide deterministic next-step commands for escalation and retry.

## User Flows

### Flow A: Triage sample (first 25 pages)

Command:

```bash
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile quick --max-pages 25 --quiet --no-color
```

Accept if:

- Summary is printed with `Run health`, artifacts, and next step.
- `quality_report.csv` is generated.
- If `Run health` is `WARN` or `FAIL`, retry/escalation command is explicit.

### Flow B: Mid-depth sample (first 50 or 150 pages)

Command examples:

```bash
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile balanced --max-pages 50 --quiet --no-color
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile balanced --max-pages 150 --quiet --no-color
```

Accept if:

- `balanced` only OCRs low-text files/pages.
- Timeout copy includes file name and `--ocr-timeout` guidance.
- Artifacts exist and next-step command is actionable.

### Flow C: Full quality pass

Command:

```bash
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile thorough --ocr-timeout 3600 --quiet --no-color
```

Accept if:

- Any failure produces retry guidance (`pdf-retry` command).
- `manifest.json` and `quality_report.csv` are consistent with summary counts.

### Flow D: Targeted recovery

Command:

```bash
legal-email-converter pdf-retry --from-csv "/path/to/out/quality_report.csv" --status failed,likely_bad_ocr --profile thorough --ocr-timeout 3600 --quiet --no-color
```

Accept if:

- Only targeted statuses are retried.
- Already-good items are left untouched.

## Benchmark Matrix (Recommended)

Run these in order and compare elapsed time + summary outcomes:

1. `quick --max-pages 25`
2. `quick --max-pages 50`
3. `balanced --max-pages 50`
4. `balanced --max-pages 150`
5. `thorough` full pass

Promote to next step when:

- `PASS`: proceed downstream.
- `WARN`: promote profile/depth (`quick -> balanced`, `50 -> 150`, then full).
- `FAIL`: run targeted retry and increase timeout.
