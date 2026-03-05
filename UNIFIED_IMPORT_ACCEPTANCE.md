# Unified Import Acceptance (Lean)

## First-principle contract

Unified import must be deterministic and path-safe:
- same input tree always yields same document order and count
- one bad file never aborts the whole import
- output location defaults are predictable and explicit

## Acceptance criteria

1. Discovery
- Given a folder, only `.msg` and `.pdf` files are discovered.
- Discovery traverses nested folders.
- Order is deterministic (sorted by normalized path).

2. Input handling
- `unified-export` accepts either a folder or a single file input.
- If `--input` is missing, CLI prompts for it.
- Prompted/supplied input path is validated before processing.

3. Output handling
- If `--out` is omitted, output defaults to same folder as input context:
  - folder input -> `<folder>/unified_case_export.txt`
  - file input -> `<file_parent>/unified_case_export.txt`
- Manifest file is always written next to output text file.

4. Import resilience
- For each discovered file, extraction is attempted independently.
- Failures are recorded in manifest `failed_files` and processing continues.

5. Consistency checks
- `manifest.summary.total == discovered_count`
- `manifest.summary.msg == discovered_msg_count`
- `manifest.summary.pdf == discovered_pdf_count`
- number of `=== DOCUMENT START ===` blocks equals discovered count.
- document `Path:` fields are relative to input root.
- `manifest.files[*].relative_path` are relative (no absolute source paths).

## Minimal combination matrix (one-file-per-type)

1. `pdf_root_only`: root has one `.pdf`
2. `msg_root_only`: root has one `.msg`
3. `mixed_root`: root has one `.pdf` + one `.msg`
4. `mixed_nested`: nested folders contain one `.pdf` + one `.msg`
5. `single_pdf_input_file`: input path is one `.pdf`
6. `single_msg_input_file`: input path is one `.msg`

Run matrix with both PDF modes where applicable:
- `--skip-ocr`
- default mode (OCR fallback allowed)

## Lean fixture structure suggestion

```
tests/fixtures_local/unified_import/
  pdf_root_only/
    one.pdf
  msg_root_only/
    one.msg
  mixed_root/
    one.msg
    one.pdf
  mixed_nested/
    level1/
      one.pdf
      level2/
        one.msg
```

Note: fixtures can be generated at runtime in tests to keep repository lean; `tests/fixtures_local/` stays gitignored.
