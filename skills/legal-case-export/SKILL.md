---
name: legal-case-export
description: Use when Codex needs to process legal evidence files such as .mbox, .msg, and .pdf into review-ready exports, OCR quality reports, retry flows, or unified case text outputs; especially when the task requires workflow selection, safe execution, deterministic artifacts, or recovery guidance.
---

# Legal Case Export

Route the request to the right CLI workflow first. Keep execution safe, explain the outcome clearly, and load only the reference file that matches the chosen workflow.

## Workflow Routing

Use this table before proposing commands:

| User intent | Workflow |
| --- | --- |
| Export a raw mailbox for review or LLM ingestion | `export-mbox` |
| Process PDFs with OCR fallback and quality reporting | `pdf-ingest` |
| Retry only failed or weak OCR files from a prior report | `pdf-retry` |
| Combine `.msg` and `.pdf` evidence into one deterministic text export | `unified-export` |
| Mixed or unsupported evidence request | narrow to supported types or reject cleanly |

Supported V1 evidence types:
- `.mbox`
- `.msg`
- `.pdf`

Unsupported in V1:
- `.docx`
- `.xlsx`
- images
- audio

## Shared Rules

Before running anything:
- Validate the input path exists.
- Prefer predictable default output locations unless the user asked for a specific destination.
- Do not imply hidden destructive behavior.
- Do not claim support for unsupported evidence types.

When reporting results:
- Explain what happened.
- Explain what it means.
- Explain what to do next.

When a run partially fails:
- Preserve partial success in the explanation.
- Point to the manifest or quality report.
- Give category-level next steps only.
- Do not invent rich per-file remediation if the runtime does not support it.

## Workflow Conventions

`export-mbox`
- Validate the `.mbox` path.
- Explain the main review artifacts and overwrite behavior.
- Keep raw attachments optional unless explicitly requested.

`pdf-ingest`
- Default to `balanced` unless the user has a clear reason to use `quick` or `thorough`.
- Treat preflight, artifacts, resume, retry, and summary behavior as hard expectations.
- Do not imply real parallel worker execution.
- Describe OCR quality as expectation-based, not guaranteed.

`pdf-retry`
- Require a prior `quality_report.csv`.
- Frame retry as targeted reuse of status signals, not full reprocessing.

`unified-export`
- Keep the supported input boundary to `.msg` and `.pdf`.
- Use public sort mode names in guidance: `path`, `date-signal`, `date-query`.
- In non-strict `date-query` mode, describe fallback behavior if Ollama fails.
- In strict mode, describe fail-fast behavior.

## Reference Loading

Load only what you need:

- Read `references/workflows.md` for workflow selection, mailbox export patterns, shared summary language, and unsupported-input narrowing.
- Read `references/pdf-ingest.md` when the workflow is `pdf-ingest` or `pdf-retry`.
- Read `references/unified-export.md` when the workflow is `unified-export`.

Do not load all references by default.

## V1 Boundaries

- This skill is CLI-backed.
- Omit MCP execution guidance from V1 responses.
- Do not introduce new scripts unless actual authoring reveals a repeated fragile manual task.
