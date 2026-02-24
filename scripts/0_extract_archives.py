#!/usr/bin/env python3
"""
Step 0: Extract all zip files to temporary directory
Returns the temporary directory path for use by other scripts
"""
import sys
from pathlib import Path
import zipfile
import tempfile
import shutil

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config


def _is_within_directory(base_dir, target_path):
    """Return True if target_path resolves within base_dir."""
    base_resolved = base_dir.resolve()
    target_resolved = target_path.resolve()
    return base_resolved == target_resolved or base_resolved in target_resolved.parents


def safe_extract_zip(zip_ref, extract_dir):
    """Safely extract zip entries while preventing path traversal."""
    for member in zip_ref.infolist():
        member_path = Path(member.filename)
        target_path = extract_dir / member_path

        if not _is_within_directory(extract_dir, target_path):
            raise ValueError(f"Unsafe archive path detected: {member.filename}")

    zip_ref.extractall(extract_dir)

def extract_all_archives(source_dir, temp_base_dir=None):
    """
    Extract all zip files from source directory to a temporary location.
    
    Args:
        source_dir: Path to source directory to scan for zip files
        temp_base_dir: Optional base temp directory (if None, creates new temp dir)
    
    Returns:
        Path to temporary directory containing extracted files
    """
    source = Path(source_dir)
    
    # Create temporary directory for extractions
    if temp_base_dir:
        temp_dir = Path(temp_base_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="legal_archive_extract_"))
    
    print(f"Scanning for zip files in: {source}")
    print(f"Extraction directory: {temp_dir}\n")
    
    # Find all zip files
    zip_files = list(source.rglob('*.zip'))
    
    if not zip_files:
        print("No zip files found.")
        return str(temp_dir)
    
    print(f"Found {len(zip_files)} zip file(s)\n")
    
    extracted_count = 0
    failed_count = 0
    total_files_extracted = 0
    
    for zip_file in zip_files:
        try:
            # Get relative path from source to maintain structure
            rel_path = zip_file.relative_to(source)
            
            # Create extraction subdirectory (zip filename without .zip extension)
            extract_subdir = temp_dir / "zipped" / rel_path.parent / zip_file.stem
            extract_subdir.mkdir(parents=True, exist_ok=True)
            
            print(f"Extracting: {zip_file.name}")
            print(f"  → {extract_subdir}")
            
            # Extract the zip file
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                # Get list of files in zip
                zip_contents = zip_ref.namelist()
                print(f"  Files in archive: {len(zip_contents)}")
                
                # Extract all files
                safe_extract_zip(zip_ref, extract_subdir)
                
                total_files_extracted += len(zip_contents)
                extracted_count += 1
                print(f"  ✓ Extracted successfully\n")
                
        except zipfile.BadZipFile:
            print(f"  ✗ Error: Not a valid zip file\n")
            failed_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            failed_count += 1
    
    print("=" * 70)
    print("Extraction Summary")
    print("=" * 70)
    print(f"Total zip files found: {len(zip_files)}")
    print(f"Successfully extracted: {extracted_count}")
    print(f"Failed: {failed_count}")
    print(f"Total files extracted: {total_files_extracted}")
    print(f"\nExtraction directory: {temp_dir}")
    print("=" * 70)
    
    return str(temp_dir)

if __name__ == "__main__":
    source_dir = config.SOURCE_DIR
    temp_dir = extract_all_archives(source_dir)
    print(f"\nTemporary directory created: {temp_dir}")
    print("This directory will be passed to subsequent scripts.")
