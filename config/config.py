"""
Configuration file for Legal Email Converter
Edit the paths below to match your environment
"""
from pathlib import Path

# Get project root directory (where this config file is located)
PROJECT_ROOT = Path(__file__).parent.parent

# SOURCE PATHS
# Path to the legal case folder containing .msg files
# Update this to point to your specific case folder
SOURCE_DIR = Path.home() / "Library/CloudStorage/ShareFile-ShareFile/Folders/71443-0001.15872"

# OUTPUT PATHS (relative to project root)
OUTPUT_DIR = PROJECT_ROOT / "output"
MBOX_OUTPUT = OUTPUT_DIR / "legal_emails.mbox"
FILTERED_MBOX_OUTPUT = OUTPUT_DIR / "legal_emails_filtered.mbox"
MARKDOWN_REPORT = OUTPUT_DIR / "email_inventory_with_senders.md"
CSV_REPORT = OUTPUT_DIR / "email_inventory_with_senders.csv"

# Convert Path objects to strings for compatibility
SOURCE_DIR = str(SOURCE_DIR)
OUTPUT_DIR = str(OUTPUT_DIR)
MBOX_OUTPUT = str(MBOX_OUTPUT)
FILTERED_MBOX_OUTPUT = str(FILTERED_MBOX_OUTPUT)
MARKDOWN_REPORT = str(MARKDOWN_REPORT)
CSV_REPORT = str(CSV_REPORT)
