# Legal Email Converter - Project Summary

## 📦 What This Project Does

Converts Microsoft Outlook .msg email files from legal cases into:
1. **Apple Mail .mbox format** - For easy browsing in Mail app
2. **CSV spreadsheet** - For analysis in Excel/Sheets
3. **Markdown report** - Human-readable documentation

## 📁 Project Structure

```
legal_email_converter/
├── README.md              # Full documentation
├── QUICKSTART.md          # Quick start guide
├── requirements.txt       # Python dependencies
├── .gitignore            # Git ignore rules
├── config/
│   └── config.py         # ⚙️ EDIT THIS - Set your paths here
├── scripts/
│   ├── 1_copy_msg_files.py      # Copy .msg files from source
│   ├── 2_create_mbox.py         # Convert to Apple Mail format
│   ├── 3_generate_reports.py   # Generate CSV & Markdown
│   └── run_all.py               # Run all steps at once
└── output/
    ├── legal_emails.mbox/                # Apple Mail format
    ├── email_inventory_with_senders.csv  # 20KB spreadsheet
    └── email_inventory_with_senders.md   # 24KB report
```

## ✅ Current Status

**Fully configured and ready to use!**

- ✅ Source path set to legal case folder
- ✅ Output path configured to project directory
- ✅ All 103 emails already converted
- ✅ Reports generated (chronologically sorted)
- ✅ Scripts ready to run again if needed

## 🎯 Key Features

### 1. Easy Path Configuration
All paths are in one file: `config/config.py`
```python
SOURCE_DIR = "/path/to/legal/case"  # Change this
OUTPUT_DIR = "/path/to/output"      # Change this
```

### 2. Modular Scripts
Run all steps or individual steps:
- Step 1: Copy files from read-only source
- Step 2: Convert to .mbox
- Step 3: Generate reports

### 3. Chronological Sorting
All emails sorted by date sent (earliest to latest)

### 4. Complete Metadata
Preserves:
- Sender (From)
- Recipient (To)
- CC
- Subject
- Date & time
- Full email body

## 📊 Output Files

### legal_emails.mbox/
- **Size:** 368KB (103 emails)
- **Format:** Apple Mail compatible
- **Usage:** Double-click to open in Mail app
- **Structure:**
  - `mbox` - Email data file
  - `table_of_contents` - Apple Mail metadata

### email_inventory_with_senders.csv
- **Size:** 20KB
- **Format:** CSV spreadsheet
- **Columns:** Date Sent, From, To, Subject, Folder, Filename
- **Sorting:** Chronological (all emails)
- **Usage:** Open in Excel, Numbers, Google Sheets

### email_inventory_with_senders.md
- **Size:** 24KB
- **Format:** Markdown
- **Organization:** By folder (Correspondence, Client Docs, etc.)
- **Sorting:** Chronological within each folder
- **Usage:** Read in any text editor or Markdown viewer

## 🚀 How to Use

### First Time Setup
```bash
# Install dependency
pip3 install extract-msg

# Run conversion (if needed)
cd ~/Desktop/legal_email_converter
python3 scripts/run_all.py
```

### Modify Paths for New Case
1. Edit `config/config.py`
2. Change `SOURCE_DIR` to new case folder
3. Run `python3 scripts/run_all.py`

### Re-run Individual Steps
```bash
python3 scripts/1_copy_msg_files.py    # Just copy
python3 scripts/2_create_mbox.py       # Just convert
python3 scripts/3_generate_reports.py  # Just reports
```

## 📧 Email Inventory Overview

**Total:** 103 emails

**By Folder:**
- Correspondence: 79 files (77%)
- Client Documents: 10 files (10%)
- Depositions: 5 files (5%)
- Discovery: 3 files (3%)
- Miscellaneous: 2 files (2%)
- Financial, Research, Settlement, Trial: 1 file each (1% each)

**Date Range:** April 2025 - October 2025

**Key Participants:**
- Craig D. Specht (attorney)
- Rachel A. Abbott (attorney)
- Tracy J. Lee (paralegal)
- Joyce Crawford (opposing counsel)
- James Gross (AFC)

## 🔧 Technical Details

**Dependencies:**
- Python 3.7+
- extract-msg library (for .msg file parsing)

**Platform:**
- macOS (for .mbox compatibility)
- Can be adapted for Windows/Linux

**Data Handling:**
- All encoding issues handled automatically
- UTF-8 encoding throughout
- Original files never modified

## 📝 Notes

- This project is self-contained and portable
- All paths configurable in one location
- Safe to share (excluding output/ folder)
- Already includes .gitignore for sensitive data
- Can be version controlled (scripts only)

## 🎉 Ready to Use!

Your project is complete and functional. All existing artifacts are in the `output/` folder, and you can re-run conversions anytime by executing:

```bash
python3 scripts/run_all.py
```

For quick reference, see `QUICKSTART.md`.
For detailed documentation, see `README.md`.
