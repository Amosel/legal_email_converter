# Legal Email Converter

Convert Microsoft Outlook .msg files to Apple Mail .mbox format and generate comprehensive email inventory reports.

## Features

- ✅ Convert .msg files to Apple Mail compatible .mbox format
- ✅ Filter emails by sender and recipient
- ✅ Generate chronologically sorted email inventory reports
- ✅ Export data to Markdown and CSV formats
- ✅ Preserve all email metadata (sender, recipient, subject, date)
- ✅ Easy configuration via single config file

## Project Structure

```
legal_email_converter/
├── README.md                   # This file
├── Makefile                    # Convenience commands
├── requirements.txt            # Python dependencies
├── config/
│   └── config.py              # Configuration file (EDIT THIS)
├── scripts/
│   ├── 0_extract_archives.py  # Step 0: Extract archives
│   ├── 1_create_mbox.py       # Step 1: Create .mbox from .msg
│   ├── 2_create_pdf_mbox.py   # Step 2: OCR PDFs into mbox
│   ├── 3_generate_reports.py  # Step 3: Generate reports
│   ├── 4_filter_emails.py     # Step 4: Filter by sender/recipient
│   ├── 5_export_mbox_for_llm.py # Step 5: Raw .mbox -> single review package
│   └── run_all.py             # Run all steps
└── output/
    ├── legal_emails.mbox/     # Apple Mail .mbox
    ├── email_inventory_with_senders.md
    └── email_inventory_with_senders.csv
```

## Setup

### 1. Install CLI

From repository root (`~/dev/projects/legal_email_converter`):
```bash
make install
```

Install behavior:
- Uses `pipx` when available (global command: `legal-email-converter`)
- Falls back to local `.venv` install when `pipx` is missing

Local-only/offline-friendly flow:
```bash
make install-cli
make cli-help
make cli-smoke
```

### 2. Configure Paths

Edit `config/config.py` and set your paths:
```python
SOURCE_DIR = "/path/to/your/legal/case/folder"
OUTPUT_DIR = "/path/to/output/folder"
```

## Usage

### Option 1: Run All Steps at Once

```bash
make run-all
```

This will:
1. Extract all archived files
2. Convert .msg files to Apple Mail .mbox format
3. Create PDF mbox (OCR)
4. Generate Markdown and CSV inventory reports
5. Optionally filter emails by sender/recipient (you'll be prompted)
6. Generate complete file inventory

### Option 2: Run Individual Steps

```bash
# Step 0: Extract archives
make extract-archives

# Step 1: Create Apple Mail .mbox from .msg
make create-mbox

# Step 2: Create PDF mbox (OCR)
make create-pdf-mbox

# Step 3: Generate inventory reports
make generate-reports

# Step 4: Filter emails (optional)
make filter-emails

# Step 5: Export raw .mbox to a single LLM review package
make export-mbox MBOX="/path/to/mailbox.mbox/mbox" OUT_DIR="/path/to/output"
```

## Testing

Run the test suite:

```bash
make test
```

Or directly:

```bash
python3 -m unittest tests/test_export_mbox_for_llm.py -v
```

Show all make commands:

```bash
make help
```

Integration matrix (real PDFs, expectation-driven):

```bash
make integration-init-yaml
# edit paths/expectations in tests/integration_pdf_matrix.local.yaml
make integration-matrix
```

Test scopes:

```bash
make test                       # exhaustive: unit + integration harness (+ real matrix if local config exists)
make test-unit                  # unit-focused
make test-integration           # integration-focused
make TEST_SCOPE=integration STRICT_INTEGRATION=1 test  # fail if local integration config is missing
```

### Make Quick Reference

```bash
# Full pipeline
make run-all

# Filter with explicit values
make filter-emails SENDER=bob@company.com RECIPIENT=sarah@client.com

# Export raw mbox -> single zip package
make export-mbox MBOX="/path/to/mailbox.mbox/mbox" SKIP_OCR=1 FORCE=1

# Unified export (.msg + .pdf) -> one text file (interactive)
make unified-export

# Download lean public hard-PDF fixture set (local, ignored)
make fixtures-hard-pdf-fetch

# Run unified-export E2E checker on a target folder
make unified-export-e2e INPUT="/path/to/folder-or-file" SKIP_OCR=1
```

Variables:
- `MBOX`: input raw mbox file
- `OUT_DIR`: output directory (default is next to `MBOX`)
- `NAME`: output zip base name (default `mailbox_review_package`)
- `SKIP_OCR=1`: skip OCR fallback for faster export
- `KEEP_ATTACHMENTS=1`: include raw attachments in final zip
- `KEEP_ARTIFACTS=1`: keep expanded artifact folder on disk
- `FORCE=1`: overwrite existing output zip

### Email Filtering

The filtering feature allows you to create a separate mbox file containing only emails matching specific sender and recipient criteria.

#### Interactive Mode (Default)

```bash
make filter-emails
```

The script will:
1. Scan all .msg files to build lists of unique senders and recipients
2. Display a numbered list of all senders for you to select from
3. Display a numbered list of all recipients for you to select from
4. Confirm your selection
5. Create a filtered mbox at `output/legal_emails_filtered.mbox`

#### CLI Mode

For automated workflows, you can specify sender and recipient directly:

```bash
make filter-emails SENDER=bob@company.com RECIPIENT=sarah@client.com
```

#### List All Emails

To see all unique email addresses in your collection:

```bash
make list-emails
```

This displays:
- All unique sender addresses
- All unique recipient addresses (from To and CC fields)

#### Filtering Behavior

- **Sender**: Exact match (case-insensitive)
- **Recipient**: Matches if found in To OR CC fields (case-insensitive)
- **Output**: Creates `output/legal_emails_filtered.mbox` (separate from main mbox)
- **No Matches**: If no emails match the criteria, no mbox file is created

### Raw Mbox Review Package

Use this when you already have a raw mbox file (for example from macOS Mail):

```bash
make export-mbox \
  MBOX="/path/to/mailbox.mbox/mbox" \
  OUT_DIR="/path/to/output" \
  NAME=mailbox_review_package
```

Output:
- A single zip file: `mailbox_review_package.zip`
- Contents: `review.md`, `llm_corpus.jsonl`, `manifest.json`
- Raw attachment files are included only with `KEEP_ATTACHMENTS=1`
- Use `SKIP_OCR=1` for faster runs when scanned PDF OCR is not required

Why `llm_corpus.jsonl`:
- JSONL is one JSON object per line, which works well for LLM/RAG ingestion and streaming.
- `review.md` is the human-friendly file to read in editors.
- If you omit `OUT_DIR`, the zip is written next to the input `.mbox` data file.

CLI equivalent:
```bash
legal-email-converter export-mbox \
  --mbox "/path/to/mailbox.mbox/mbox" \
  --out-dir "/path/to/output" \
  --name mailbox_review_package \
  --force
```

### Unified Text Export

Create one deterministic text file from mixed `.msg` and `.pdf` inputs:

```bash
legal-email-converter unified-export --input "/path/to/case-folder"
```

Behavior:
- If `--input` is omitted, CLI prompts and validates the path exists.
- If `--out` is omitted, default output is in the same folder as the input:
  - folder input: `/path/to/case-folder/unified_case_export.txt`
  - file input: `/path/to/file-parent/unified_case_export.txt`
- Paths are normalized consistently across commands (including unescaping `\ ` from quoted shell paths).

Optional:

```bash
legal-email-converter unified-export --input "/path/to/case-folder" --out "/path/to/out.txt" --skip-ocr
```

## PDF Ingest User Journeys

### 1) Fast first pass (triage)

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder"
```

Expected:
- Runs `balanced` by default.
- Produces `quality_report.csv`, `failed_files.json`, `manifest.json`.
- Prints a retry command automatically if any failures or bad OCR are detected.

Optional richer progress view:

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder" --progress-style rich
```

- Uses a compact spinner + counters in interactive terminals.
- Automatically falls back to plain progress lines when output is non-interactive.

Summary-only output (for logs/automation):

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder" --quiet --no-color
```

- Suppresses startup/progress noise and prints final summary, run health, artifacts, and next step.
- `Run health` values: `PASS` (no quality flags), `WARN` (low_text/likely_bad_ocr present), `FAIL` (any failed files).
- `kpi_runs.csv` is appended in the output directory for trend tracking across runs.

Large PDF sampling (first pages only):

```bash
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile balanced --max-pages 25
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile balanced --max-pages 50
legal-email-converter pdf-ingest --input "/path/to/large.pdf" --profile balanced --max-pages 150
```

- Useful for fast first-pass triage on very large/hard PDFs.
- Sampling applies to both text-layer extraction and OCR paths.
- See `LARGE_PDF_UX_ACCEPTANCE.md` for full benchmark and escalation flow.

### 2) Quality-first pass (max coverage)

```bash
legal-email-converter pdf-ingest --input "/path/to/pdf-or-folder" --profile thorough --ocr-jobs 2
```

Expected:
- OCR on every file.
- Slower but best coverage for scanned/legal packets.

### 3) Recover only failed/problem files

```bash
legal-email-converter pdf-retry \
  --from-csv "/path/to/output/pdf_ingest/quality_report.csv" \
  --status failed,likely_bad_ocr \
  --profile thorough
```

Expected:
- Reprocesses only selected statuses.
- Leaves already-good files untouched.

## Output Files

### 1. Apple Mail .mbox
- Location: `output/legal_emails.mbox/`
- Usage: Double-click to open in Apple Mail
- Contains all emails in standard mbox format

### 2. Filtered Apple Mail .mbox (Optional)
- Location: `output/legal_emails_filtered.mbox/`
- Usage: Double-click to open in Apple Mail
- Contains only emails matching sender/recipient filter criteria
- Created when using the email filtering feature

### 3. Markdown Report
- Location: `output/email_inventory_with_senders.md`
- Organized by folder
- Chronologically sorted within each folder
- Shows: Date, From, To, Subject

### 4. CSV Report
- Location: `output/email_inventory_with_senders.csv`
- All emails in one chronological list
- Can be opened in Excel, Google Sheets, etc.
- Columns: Date Sent, From, To, Subject, Folder, Filename

## Configuration

All paths are configured in `config/config.py`:

```python
# Source directory containing .msg files
SOURCE_DIR = "/path/to/legal/case"

# Output directory for all generated files
OUTPUT_DIR = "/path/to/output"

# Generated paths (automatically set):
# - MBOX_OUTPUT = OUTPUT_DIR + "/legal_emails.mbox"
# - FILTERED_MBOX_OUTPUT = OUTPUT_DIR + "/legal_emails_filtered.mbox"
# - MARKDOWN_REPORT = OUTPUT_DIR + "/email_inventory_with_senders.md"
# - CSV_REPORT = OUTPUT_DIR + "/email_inventory_with_senders.csv"
```

## Requirements

- Python 3.7+
- extract-msg library
- macOS (for Apple Mail .mbox compatibility)

## Troubleshooting

### "extract_msg not found"
Install the library:
```bash
pip install extract-msg
```

### Permission denied
Make scripts executable:
```bash
chmod +x scripts/*.py
```

### Path not found
Check that your SOURCE_DIR in config/config.py exists and is correct.

## Notes

- The .mbox format is compatible with Apple Mail on macOS
- All emails are sorted chronologically in reports
- Original .msg files are not modified
- Emails with encoding issues are automatically handled

## License

This is a utility script for personal use.
