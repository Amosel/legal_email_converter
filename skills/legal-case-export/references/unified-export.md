# Unified Export

Use this file only for `unified-export`.

## Supported Inputs

Supported in V1:
- `.msg`
- `.pdf`

Not supported in V1:
- `.docx`
- `.xlsx`
- images
- audio

## Default Command

```bash
legal-email-converter unified-export --input "/path/to/case-folder"
```

Useful options:

```bash
legal-email-converter unified-export \
  --input "/path/to/case-folder" \
  --out "/path/to/out.txt" \
  --skip-ocr
```

## Output Defaults

If `--out` is omitted:
- folder input -> `<folder>/unified_case_export.txt`
- file input -> `<file_parent>/unified_case_export.txt`

Manifest behavior:
- manifest is written next to the output text file
- manifest includes `failed_files`
- manifest includes per-file rows and `date_query` diagnostics when relevant

## Sort Modes

Use public CLI names in skill guidance:
- `path`
- `date-signal`
- `date-query`

Examples:

```bash
legal-email-converter unified-export \
  --input "/path/to/case-folder" \
  --sort-mode date-signal
```

```bash
legal-email-converter unified-export \
  --input "/path/to/case-folder" \
  --sort-mode date-query \
  --date-query-provider ollama \
  --ollama-model llama3.2:3b
```

Strict mode:

```bash
legal-email-converter unified-export \
  --input "/path/to/case-folder" \
  --sort-mode date-query \
  --date-query-provider ollama \
  --date-query-strict
```

## Deterministic Contract

Strong claims for V1:
- only `.msg` and `.pdf` files are discovered
- discovery is recursive and deterministic
- one bad file does not abort the whole run
- failed files are recorded in the manifest

## Failure Taxonomy

Use these categories only:

1. Input-level blockers
   Examples:
   - missing input path
   - no supported `.msg` or `.pdf` files found

2. Per-file extraction failures
   Behavior:
   - run continues
   - failed file appears in `failed_files`
   - manifest row contains the raw error string

3. Date-query provider failures
   Behavior:
   - diagnostics recorded in `manifest.date_query`
   - non-strict mode falls back
   - strict mode can fail the run

Do not invent finer per-file remediation categories.

## Date-Query Resilience

Non-strict mode:
- fall back to heuristic/local date-signal behavior if Ollama preflight or query fails

Strict mode:
- fail fast on Ollama preflight or query errors

Do not claim:
- quality guarantees for model-derived date ranking
- richer provider support than the current CLI exposes

## Summary Guidance

Good summary elements:
- selected sort mode
- counts for total, msg, pdf, and failed files
- output and manifest paths
- whether fallback occurred in date-query mode

Good next steps:
- inspect `failed_files` and per-file error strings
- retry with `path` or `date-signal` if date-query issues persist
- use strict mode only when fail-fast behavior is desired

Do not promise:
- tailored per-file remediation
- automatic repair of failed files
