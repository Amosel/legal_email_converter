#!/usr/bin/env python3
"""
Step 1: Convert .msg files to Apple Mail compatible .mbox format
Copies files to temporary directory and cleans up after completion
"""
import sys
from pathlib import Path
from datetime import datetime
import plistlib

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

try:
    import extract_msg
except ImportError:
    print("Error: extract_msg library not found.")
    print("Please install it: pip install extract-msg")
    sys.exit(1)

def create_apple_mbox():
    """Create an Apple Mail compatible .mbox directory."""
    import os
    
    source_dir = Path(config.SOURCE_DIR)
    mbox_path = Path(config.MBOX_OUTPUT)
    
    # Check for extracted archives directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')
    
    print(f"Scanning source: {source_dir}")
    
    # Find all .msg files in source
    msg_files = list(source_dir.rglob('*.msg'))
    
    # Also scan extracted archives if available
    if archive_dir:
        archive_path = Path(archive_dir)
        zipped_dir = archive_path / "zipped"
        if zipped_dir.exists():
            print(f"Also scanning extracted archives: {zipped_dir}")
            archive_msg_files = list(zipped_dir.rglob('*.msg'))
            msg_files.extend(archive_msg_files)
            print(f"Found {len(archive_msg_files)} .msg files in archives")
    
    msg_files = sorted(msg_files)
    total = len(msg_files)
    
    print(f"Found {total} .msg files")
    print(f"Creating mbox at: {mbox_path}\n")
    
    # Create .mbox directory
    mbox_path.mkdir(parents=True, exist_ok=True)
    mbox_file = mbox_path / "mbox"

    successful = 0
    failed = 0
    
    with open(mbox_file, 'w', encoding='utf-8') as mbox:
        for i, msg_file in enumerate(msg_files, 1):
            try:
                print(f"Processing {i}/{total}: {msg_file.name}...", end=' ')
            
                # Extract the .msg file directly from source path
                msg = extract_msg.Message(str(msg_file))

                # Get email metadata
                sender = str(msg.sender) if msg.sender else 'unknown@unknown.com'
                to = str(msg.to) if msg.to else ''
                cc = str(msg.cc) if msg.cc else ''
                subject = str(msg.subject) if msg.subject else '(No Subject)'
                body = str(msg.body) if msg.body else ''

                # Parse date
                if msg.date:
                    if isinstance(msg.date, str):
                        date_str = msg.date
                    else:
                        date_str = msg.date.strftime('%a %b %d %H:%M:%S %Y')
                else:
                    date_str = datetime.now().strftime('%a %b %d %H:%M:%S %Y')

                # Extract email address from sender
                sender_email = sender
                if '<' in sender and '>' in sender:
                    sender_email = sender.split('<')[1].split('>')[0]
                elif ' ' in sender:
                    sender_email = sender.split()[-1]

                # Write mbox entry with proper "From " separator
                mbox.write(f"From {sender_email} {date_str}\n")

                # Write headers
                mbox.write(f"From: {sender}\n")
                if to:
                    mbox.write(f"To: {to}\n")
                if cc:
                    mbox.write(f"Cc: {cc}\n")
                mbox.write(f"Subject: {subject}\n")
                mbox.write(f"Date: {date_str}\n")
                mbox.write("Content-Type: text/plain; charset=UTF-8\n")
                mbox.write("\n")

                # Write body (escape "From " at start of lines)
                for line in body.split('\n'):
                    if line.startswith('From '):
                        mbox.write('>')
                    mbox.write(line + '\n')

                # Add blank line between messages
                mbox.write("\n")
                    
                successful += 1
                print("✓")
                
            except Exception as e:
                failed += 1
                print(f"✗ Error: {e}")
    
    # Create table_of_contents (Apple Mail metadata)
    toc_data = {
        'MessageCount': successful,
        'Version': 5
    }
    
    toc_file = mbox_path / "table_of_contents"
    with open(toc_file, 'wb') as f:
        plistlib.dump(toc_data, f)
    
    print(f"\n{'=' * 60}")
    print(f"Conversion complete!")
    print(f"{'=' * 60}")
    print(f"Successfully converted: {successful}")
    print(f"Failed: {failed}")
    print(f"\nCreated Apple Mail .mbox at: {mbox_path}")
    print(f"You can now open this in Apple Mail by double-clicking it.")

if __name__ == "__main__":
    create_apple_mbox()
