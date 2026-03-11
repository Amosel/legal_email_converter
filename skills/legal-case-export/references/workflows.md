# Workflows

Use this file for workflow selection, mailbox export patterns, shared summary language, and unsupported-input narrowing.

## Intent Map

- Raw `.mbox` mailbox to review package: `export-mbox`
- PDF extraction with OCR fallback: `pdf-ingest`
- Retry failed or weak OCR files from a report: `pdf-retry`
- Mixed `.msg` and `.pdf` corpus to one text export: `unified-export`
- Unsupported evidence mix: narrow to `.mbox`, `.msg`, `.pdf` or reject

## Export Mbox

Use for mailbox packaging and review/LLM-ready export requests.

Command pattern:

```bash
legal-email-converter export-mbox \
  --mbox "/path/to/mailbox.mbox/mbox"
```

Useful options:

```bash
legal-email-converter export-mbox \
  --mbox "/path/to/mailbox.mbox/mbox" \
  --out-dir "/path/to/output" \
  --name mailbox_review_package
```

Only mention these when relevant:
- `--keep-attachments`
- `--keep-artifacts`
- `--force`
- `--skip-ocr`

Explain these artifacts when summarizing:
- `review.md`
- `llm_corpus.jsonl`
- `manifest.json`

Rules:
- Validate the mailbox path first.
- Default behavior should be described as non-destructive unless `--force` is requested.
- Raw attachments are optional, not default.

Do not claim:
- mailbox deduplication
- multi-mbox merge support
- attachment redaction

## PDF Retry

Use when the user already has a prior `quality_report.csv` and wants targeted recovery.

Command pattern:

```bash
legal-email-converter pdf-retry \
  --from-csv "/path/to/output/pdf_ingest/quality_report.csv" \
  --status failed,likely_bad_ocr \
  --profile thorough
```

Rules:
- Validate the report path first.
- Keep the framing targeted, not full reprocessing.
- Preserve already-good files as untouched.

Do not claim:
- automatic merge across unrelated reports
- semantic prioritization beyond explicit statuses

## Unsupported Inputs

If the request includes unsupported evidence types:
- state the V1 support boundary clearly
- narrow the task to supported evidence if possible
- otherwise reject cleanly

Example narrowing language:
- "I can handle the `.pdf` and `.msg` inputs in this folder, but not the `.docx`, image, or audio files in V1."

## Shared Response Pattern

For all workflows, structure summaries like this:

1. What happened
2. What it means
3. What to do next

Good summary traits:
- mention the selected workflow
- mention the main output artifact paths
- mention the next command when recovery is relevant
- stay category-level when remediation is weak
