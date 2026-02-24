#!/usr/bin/env python3
"""
Master script to run all conversion steps in sequence
Orchestrates archive extraction and passes temp directory to all scripts
"""
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

# Import the extraction script directly
import importlib.util
scripts_dir = Path(__file__).parent
spec = importlib.util.spec_from_file_location("extract_archives", scripts_dir / "0_extract_archives.py")
extract_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract_module)

def main():
    """Run all conversion steps with orchestrated temp directory."""
    
    print("=" * 70)
    print("LEGAL EMAIL CONVERTER")
    print("=" * 70)
    print(f"\nSource: {config.SOURCE_DIR}")
    print(f"Output: {config.OUTPUT_DIR}\n")
    
    # Create base temporary directory for this run
    base_temp_dir = tempfile.mkdtemp(prefix="legal_converter_")
    print(f"Working directory: {base_temp_dir}\n")

    try:
        # Step 0: Extract all archives
        print("\n" + "=" * 70)
        print("Step 0: Extract archived files")
        print("=" * 70 + "\n")

        archive_temp_dir = extract_module.extract_all_archives(
            config.SOURCE_DIR,
            base_temp_dir
        )

        # Ask user if they want to filter emails
        print("\n" + "=" * 70)
        print("Optional: Filter Emails")
        print("=" * 70)
        print("Would you like to filter emails by sender and recipient?")
        filter_choice = input("Enter 'y' to filter, or press Enter to skip: ").strip().lower()

        # Define processing steps with temp directory
        steps = [
            ("Step 1: Create Apple Mail .mbox from emails", "1_create_mbox.py"),
            ("Step 2: Create Apple Mail .mbox from PDFs (OCR)", "2_create_pdf_mbox.py"),
            ("Step 3: Generate email inventory reports", "3_generate_reports.py"),
        ]

        if filter_choice == 'y':
            steps.append(("Step 4: Filter emails by sender/recipient", "4_filter_emails.py"))

        steps.append(("Step 5: Generate complete file inventory", "generate_complete_inventory.py"))
        
        scripts_dir = Path(__file__).parent
        
        # Pass temp directory to each script via environment variable
        import os
        env = os.environ.copy()
        env['LEGAL_CONVERTER_TEMP_DIR'] = base_temp_dir
        env['LEGAL_CONVERTER_ARCHIVE_DIR'] = archive_temp_dir
        
        for description, script in steps:
            print("\n" + "=" * 70)
            print(f"{description}")
            print("=" * 70 + "\n")
            
            script_path = scripts_dir / script
            
            # Run script as subprocess with temp dir in environment
            result = subprocess.run(
                [sys.executable, str(script_path)],
                env=env
            )
            
            if result.returncode != 0:
                print(f"\n❌ Error in {script}")
                print("Stopping execution.")
                sys.exit(1)
        
        print("\n" + "=" * 70)
        print("✅ ALL STEPS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nOutput files:")
        print(f"  - mbox: {config.MBOX_OUTPUT}")
        if filter_choice == 'y':
            # Check if filtered mbox was actually created
            from pathlib import Path
            if Path(config.FILTERED_MBOX_OUTPUT).exists():
                print(f"  - filtered mbox: {config.FILTERED_MBOX_OUTPUT}")
        print(f"  - Markdown: {config.MARKDOWN_REPORT}")
        print(f"  - CSV: {config.CSV_REPORT}")
        
    finally:
        # Clean up temporary directory
        print(f"\n\nCleaning up temporary directory: {base_temp_dir}")
        shutil.rmtree(base_temp_dir, ignore_errors=True)
        print("✓ Cleanup complete")

if __name__ == "__main__":
    main()
