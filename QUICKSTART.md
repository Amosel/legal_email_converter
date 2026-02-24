# Quick Start Guide

## TL;DR - Get Started in 3 Steps

### 1. Edit Configuration
```bash
nano config/config.py
```

Change the source directory to your case folder:
```python
SOURCE_DIR = Path.home() / "Library/CloudStorage/ShareFile-ShareFile/Folders/YOUR-CASE-FOLDER"
# OUTPUT_DIR is automatically set to the project's output/ folder
```

### 2. Install Dependencies
```bash
pip3 install extract-msg
```

### 3. Run Conversion
```bash
cd ~/dev/scripts/legal_email_converter
python3 scripts/run_all.py
```

That's it! ✅

## What You'll Get

1. **legal_emails.mbox** - Double-click to open in Apple Mail
2. **email_inventory_with_senders.csv** - Open in Excel/Sheets
3. **email_inventory_with_senders.md** - Human-readable report

## Output Location

All generated files are saved to the project's `output/` directory:
- legal_emails.mbox
- email_inventory_with_senders.csv
- email_inventory_with_senders.md

## Need to Convert Again?

Just run:
```bash
python3 scripts/run_all.py
```

## Individual Steps

Run only what you need:
```bash
# Just create mbox
python3 scripts/1_create_mbox.py

# Just generate reports
python3 scripts/3_generate_reports.py
```

## Troubleshooting

**"extract_msg not found"**
```bash
pip3 install extract-msg
```

**"Permission denied"**
```bash
chmod +x scripts/*.py
```

**Need help?**
See full README.md for details.
