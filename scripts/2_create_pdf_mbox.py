#!/usr/bin/env python3
"""
Step 2: OCR PDFs and create mbox-style container
Extracts text from PDFs (with OCR if needed) and creates an mbox for searching/browsing
"""
import sys
from pathlib import Path
from datetime import datetime
import plistlib
import tempfile
import shutil
import subprocess
import os
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

def check_dependencies(skip_ocr=False):
    """Check if required OCR tools are installed."""
    dependencies = {'pdftotext': 'poppler (install via: brew install poppler)'}
    if not skip_ocr:
        dependencies['ocrmypdf'] = 'ocrmypdf (install via: pip install ocrmypdf)'
    
    missing = []
    for cmd, install_info in dependencies.items():
        if shutil.which(cmd) is None:
            missing.append(f"  - {cmd}: {install_info}")
    
    return missing

def extract_pdf_text(pdf_path, temp_dir, skip_ocr=False, ocr_jobs=1):
    """
    Extract text from PDF, using OCR if needed.
    
    Args:
        pdf_path: Path to PDF file
        temp_dir: Temporary directory for OCR processing
    
    Returns:
        Extracted text or None if extraction failed
    """
    pdf_path = Path(pdf_path)
    
    # First, try direct text extraction with pdftotext
    try:
        result = subprocess.run(
            ['pdftotext', str(pdf_path), '-'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            # Check if we got meaningful text (not just whitespace/junk)
            if len(text) > 50:  # At least 50 chars
                return text
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    if skip_ocr:
        return None

    # If pdftotext didn't work, try OCR with ocrmypdf
    try:
        source_hash = hashlib.sha1(str(pdf_path).encode('utf-8', errors='ignore')).hexdigest()[:10]
        ocr_output = temp_dir / f"ocr_{source_hash}_{pdf_path.name}"
        
        result = subprocess.run(
            ['ocrmypdf', '--force-ocr', '--jobs', str(ocr_jobs), str(pdf_path), str(ocr_output)],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0 and ocr_output.exists():
            # Now extract text from the OCR'd PDF
            result = subprocess.run(
                ['pdftotext', str(ocr_output), '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return None


def process_pdf_file(pdf_file, temp_dir, skip_ocr=False, ocr_jobs=1):
    """Process one PDF and return structured result for writer stage."""
    try:
        stat = pdf_file.stat()
        modified_date = datetime.fromtimestamp(stat.st_mtime)
        text = extract_pdf_text(pdf_file, temp_dir, skip_ocr=skip_ocr, ocr_jobs=ocr_jobs)
        if not text:
            return {"status": "skipped", "pdf_file": pdf_file}
        return {
            "status": "ok",
            "pdf_file": pdf_file,
            "stat": stat,
            "modified_date": modified_date,
            "text": text,
        }
    except Exception as e:
        return {"status": "failed", "pdf_file": pdf_file, "error": str(e)}


def create_pdf_mbox(workers=None, ocr_jobs=1, skip_ocr=False):
    """Create an mbox-style container from all PDFs."""
    
    # Check dependencies first
    missing_deps = check_dependencies(skip_ocr=skip_ocr)
    if missing_deps:
        print("Error: Missing required dependencies:")
        print("\n".join(missing_deps))
        print("\nPlease install them and try again.")
        sys.exit(1)
    
    source_dir = Path(config.SOURCE_DIR)
    output_dir = Path(config.OUTPUT_DIR)
    mbox_path = output_dir / "legal_pdfs.mbox"
    
    # Check for extracted archives directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')
    
    # Create temporary directory for OCR processing
    temp_dir = Path(tempfile.mkdtemp(prefix="legal_pdf_ocr_"))
    
    print(f"Using temporary directory: {temp_dir}")
    print(f"Scanning source: {source_dir}")
    
    try:
        # Find all PDF files in source
        pdf_files = list(source_dir.rglob('*.pdf'))
        
        # Also scan extracted archives if available
        if archive_dir:
            archive_path = Path(archive_dir)
            zipped_dir = archive_path / "zipped"
            if zipped_dir.exists():
                print(f"Also scanning extracted archives: {zipped_dir}")
                archive_pdf_files = list(zipped_dir.rglob('*.pdf'))
                pdf_files.extend(archive_pdf_files)
                print(f"Found {len(archive_pdf_files)} PDF files in archives")
        
        pdf_files = sorted(pdf_files)
        total = len(pdf_files)
        
        print(f"Found {total} PDF files")
        print(f"Creating mbox at: {mbox_path}\n")
        
        # Create .mbox directory
        mbox_path.mkdir(parents=True, exist_ok=True)
        mbox_file = mbox_path / "mbox"
        
        successful = 0
        failed = 0
        skipped = 0
        
        resolved_workers = workers if workers and workers > 0 else 1
        print(f"Using workers={resolved_workers}, ocr_jobs={ocr_jobs}, skip_ocr={skip_ocr}")

        with open(mbox_file, 'w', encoding='utf-8') as mbox:
            if resolved_workers == 1:
                results_iter = (
                    process_pdf_file(pdf_file, temp_dir, skip_ocr=skip_ocr, ocr_jobs=ocr_jobs)
                    for pdf_file in pdf_files
                )
            else:
                with ThreadPoolExecutor(max_workers=resolved_workers) as executor:
                    results_iter = executor.map(
                        lambda p: process_pdf_file(p, temp_dir, skip_ocr=skip_ocr, ocr_jobs=ocr_jobs),
                        pdf_files
                    )

            for i, result in enumerate(results_iter, 1):
                pdf_file = result["pdf_file"]
                print(f"Processing {i}/{total}: {pdf_file.name}...", end=' ')
                if result["status"] == "failed":
                    failed += 1
                    print(f"✗ Error: {result.get('error', 'Unknown error')}")
                    continue

                if result["status"] == "skipped":
                    skipped += 1
                    print("✗ (no text extracted)")
                    continue

                stat = result["stat"]
                modified_date = result["modified_date"]
                text = result["text"]

                # Format as mbox entry
                date_str = modified_date.strftime('%a %b %d %H:%M:%S %Y')

                # Write mbox entry
                mbox.write(f"From legal_docs@local {date_str}\n")
                mbox.write(f"From: Legal Documents <legal_docs@local>\n")
                mbox.write(f"To: Archive <archive@local>\n")
                mbox.write(f"Subject: {pdf_file.name}\n")
                mbox.write(f"Date: {date_str}\n")
                mbox.write(f"X-PDF-Path: {pdf_file}\n")
                mbox.write(f"X-PDF-Size: {stat.st_size}\n")
                mbox.write("Content-Type: text/plain; charset=UTF-8\n")
                mbox.write("\n")

                # Write extracted text (escape "From " at start of lines)
                for line in text.split('\n'):
                    if line.startswith('From '):
                        mbox.write('>')
                    mbox.write(line + '\n')

                # Add blank line between messages
                mbox.write("\n")

                successful += 1
                print("✓")
        
        # Create table_of_contents (Apple Mail metadata)
        toc_data = {
            'MessageCount': successful,
            'Version': 5
        }
        
        toc_file = mbox_path / "table_of_contents"
        with open(toc_file, 'wb') as f:
            plistlib.dump(toc_data, f)
        
        print(f"\n{'=' * 60}")
        print(f"PDF OCR and mbox creation complete!")
        print(f"{'=' * 60}")
        print(f"Successfully processed: {successful}")
        print(f"No text extracted: {skipped}")
        print(f"Failed: {failed}")
        print(f"\nCreated PDF mbox at: {mbox_path}")
        print(f"You can open this in Apple Mail for full-text search.")
    
    finally:
        # Clean up temporary directory
        print(f"\nCleaning up temporary files...")
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"✓ Temporary directory removed")

def parse_args():
    parser = argparse.ArgumentParser(
        description="OCR PDFs and create mbox-style container."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="Number of PDFs to process in parallel.",
    )
    parser.add_argument(
        "--ocr-jobs",
        type=int,
        default=1,
        help="Per-file OCR threads passed to ocrmypdf --jobs.",
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Skip OCR fallback; only use direct text extraction.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    create_pdf_mbox(workers=args.workers, ocr_jobs=args.ocr_jobs, skip_ocr=args.skip_ocr)
