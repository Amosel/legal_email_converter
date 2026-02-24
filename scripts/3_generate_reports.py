#!/usr/bin/env python3
"""
Step 3: Generate inventory reports (Markdown and CSV) with sender information
"""
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import csv

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

try:
    import extract_msg
except ImportError:
    print("Error: extract_msg library not found.")
    print("Please install it: pip install extract-msg")
    sys.exit(1)

def extract_email_info(base_dir):
    """Extract sender, subject, and date from all .msg files organized by folder."""
    
    msg_files = sorted(Path(base_dir).rglob('*.msg'))
    
    # Group by directory
    by_folder = defaultdict(list)
    
    total = len(msg_files)
    print(f"Processing {total} .msg files...\n")
    
    for i, msg_file in enumerate(msg_files, 1):
        try:
            # Get relative path and folder
            rel_path = msg_file.relative_to(base_dir)
            folder = rel_path.parent if rel_path.parent != Path('.') else 'Root'
            
            # Extract message
            msg = extract_msg.Message(str(msg_file))
            
            # Parse date for sorting and display
            date_obj = None
            date_display = '(No Date)'
            if msg.date:
                try:
                    if isinstance(msg.date, datetime):
                        date_obj = msg.date
                        date_display = msg.date.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        date_display = str(msg.date)
                except:
                    date_display = str(msg.date)
            
            email_info = {
                'filename': msg_file.name,
                'sender': str(msg.sender) if msg.sender else '(Unknown)',
                'subject': str(msg.subject) if msg.subject else '(No Subject)',
                'date': str(msg.date) if msg.date else '(No Date)',
                'date_obj': date_obj,
                'date_display': date_display,
                'to': str(msg.to) if msg.to else '(No recipient)'
            }
            
            by_folder[str(folder)].append(email_info)
            
            if i % 10 == 0:
                print(f"Processed {i}/{total}...")
            
        except Exception as e:
            print(f"Error processing {msg_file.name}: {e}")
    
    return by_folder

def generate_report(by_folder, output_file):
    """Generate formatted Markdown report."""
    
    total_count = sum(len(emails) for emails in by_folder.values())
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Email Files (.msg) Inventory Report with Senders\n\n")
        f.write(f"**Total: {total_count} .msg files**\n\n")
        f.write("---\n\n")
        
        # Sort folders by email count (descending)
        sorted_folders = sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)
        
        for folder, emails in sorted_folders:
            count = len(emails)
            percentage = (count / total_count * 100) if total_count > 0 else 0
            
            f.write(f"## 📂 **{folder}** ({count} files - {percentage:.0f}%)\n\n")
            
            # Sort emails chronologically by date
            emails.sort(key=lambda x: x['date_obj'] if x.get('date_obj') else '')
            
            for email in emails:
                f.write(f"### {email['filename']}\n")
                f.write(f"- **Date Sent:** {email['date_display']}\n")
                f.write(f"- **From:** {email['sender']}\n")
                f.write(f"- **To:** {email['to']}\n")
                f.write(f"- **Subject:** {email['subject']}\n")
                f.write("\n")
            
            f.write("---\n\n")
    
    print(f"\n✓ Markdown report saved to: {output_file}")

def generate_csv_report(by_folder, output_file):
    """Generate CSV version for spreadsheet analysis."""
    
    # Flatten all emails with folder info
    all_emails = []
    for folder, emails in by_folder.items():
        for email in emails:
            all_emails.append({
                'folder': folder,
                'filename': email['filename'],
                'sender': email['sender'],
                'to': email['to'],
                'subject': email['subject'],
                'date': email['date_display'],
                'date_obj': email.get('date_obj', '')
            })
    
    # Sort chronologically
    all_emails.sort(key=lambda x: x['date_obj'] if x['date_obj'] else '')
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date Sent', 'From', 'To', 'Subject', 'Folder', 'Filename'])
        
        for email in all_emails:
            writer.writerow([
                email['date'],
                email['sender'],
                email['to'],
                email['subject'],
                email['folder'],
                email['filename']
            ])
    
    print(f"✓ CSV report saved to: {output_file}")

if __name__ == "__main__":
    import os
    
    source_dir = config.SOURCE_DIR
    md_output = config.MARKDOWN_REPORT
    csv_output = config.CSV_REPORT
    
    # Check for extracted archives directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')
    
    print("Extracting email information...\n")
    
    # Extract from source directory
    by_folder = extract_email_info(source_dir)
    
    # Also extract from archives if available
    if archive_dir:
        archive_path = Path(archive_dir)
        zipped_dir = archive_path / "zipped"
        if zipped_dir.exists():
            print(f"\nExtracting from archived files: {zipped_dir}")
            archive_by_folder = extract_email_info(zipped_dir)
            
            # Merge with main folder data, prefixing folder names
            for folder, emails in archive_by_folder.items():
                prefixed_folder = f"zipped/{folder}"
                if prefixed_folder in by_folder:
                    by_folder[prefixed_folder].extend(emails)
                else:
                    by_folder[prefixed_folder] = emails
    
    print("\nGenerating reports...\n")
    generate_report(by_folder, md_output)
    generate_csv_report(by_folder, csv_output)
    
    print("\n" + "=" * 60)
    print("Complete!")
    print("=" * 60)
    print(f"\nMarkdown report: {md_output}")
    print(f"CSV report: {csv_output}")
