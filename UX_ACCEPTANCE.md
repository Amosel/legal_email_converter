# UX Acceptance Checklist

This checklist defines release gates for a delightful PDF ingest experience.
Every `P0` item must pass before claiming UX readiness.

Status legend: `[ ]` pending, `[x]` passed.

## P0 Core Experience (Required)

- [x] Single default happy-path command exists:
  - `legal-email-converter pdf-ingest --input <path>`
  - Defaults to `balanced` profile with sensible tuning.
- [x] Mandatory preflight runs before processing:
  - validates input/output access,
  - validates required tools,
  - prints actionable remediation on failure.
- [x] Structured live progress exists:
  - shows done/total,
  - current file,
  - current mode (`text-layer`/`ocr`),
  - ETA.
- [x] End-of-run summary includes status counts:
  - `good`, `low_text`, `likely_bad_ocr`, `failed`.
- [x] Per-file quality artifact is generated:
  - `quality_report.csv` with worst-first ordering.
- [x] User can recover quickly:
  - `pdf-retry` command reprocesses only targeted failed/low-quality files.
- [x] User can resume interrupted runs:
  - `--resume <run_id>` skips already completed files.

## P1 Clarity and Trust (Strongly Recommended)

- [x] CLI help text explains profile tradeoffs:
  - expected speed vs coverage for `quick`, `balanced`, `thorough`.
- [x] Output copy consistently answers:
  - what happened,
  - what it means,
  - what to do next.
- [x] Timeouts provide explicit guidance:
  - includes file name,
  - includes suggested `--ocr-timeout` adjustment.
- [x] Missing dependency errors include exact install commands.
- [x] Final summary points to exact artifact paths.

## P1 Perceived Performance

- [x] Fast startup:
  - first useful console output within 2 seconds.
- [x] Progress cadence:
  - update every N files and on stage transitions,
  - avoid noisy per-file spam by default.
- [x] Balanced profile demonstrates selective OCR fallback:
  - avoids OCR on high-text files.

## P2 Delight and Polish

- [x] Optional rich progress mode (compact table or spinner + counters).
- [x] Suggested next command shown automatically:
  - e.g. retry failed files.
- [x] Run manifests include concise audit trail metadata.
- [x] Command examples are documented for top 3 user journeys.

## Test Gates

- [x] Integration test: quick profile on mixed corpus.
- [x] Integration test: balanced profile routes low-text files to OCR.
- [x] Integration test: thorough profile OCRs all files.
- [x] Integration test: retry only failed/likely_bad_ocr.
- [x] Integration test: resume skips completed files.
- [x] Snapshot test: end-of-run summary copy format.

## Exit Criteria

- [x] All P0 items passed.
- [x] At least 80% of P1 items passed.
- [x] No critical UX regressions in test suite.

## Large/Hard PDF Companion

- Use `LARGE_PDF_UX_ACCEPTANCE.md` for first-25/50/150-page sampling flows,
  escalation rules, and benchmark matrix on very large or difficult PDFs.
