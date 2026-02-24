#!/usr/bin/env python3
"""
Step 4: Filter emails by sender and recipient
Creates a separate filtered mbox file based on user-specified sender and recipient
"""
import sys
import os
import argparse
import plistlib
from pathlib import Path
from datetime import datetime

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

try:
    import extract_msg
except ImportError:
    print("Error: extract_msg library not found.")
    print("Please install it: pip install extract-msg")
    sys.exit(1)

def extract_email_address(email_str):
    """Parse email address from various formats.

    Handles formats like:
    - "Name <email@example.com>"
    - "email@example.com"
    - "Name email@example.com"

    Returns normalized lowercase email or None if invalid.
    """
    if not email_str:
        return None

    email_str = email_str.strip()

    # Handle angle bracket format: "Name <email@example.com>"
    if '<' in email_str and '>' in email_str:
        email = email_str.split('<')[1].split('>')[0].strip().lower()
        return email if '@' in email else None

    # Handle space-separated format (find part with @)
    if ' ' in email_str:
        for part in reversed(email_str.split()):
            part = part.strip()
            if '@' in part:
                return part.lower()

    # Plain email format
    if '@' in email_str:
        return email_str.lower()

    return None

def parse_recipient_list(recipient_str):
    """Parse comma/semicolon-separated recipient list.

    Returns a set of normalized lowercase email addresses.
    """
    if not recipient_str:
        return set()

    # Normalize separators (replace semicolons with commas)
    recipient_str = recipient_str.replace(';', ',')

    emails = set()
    for part in recipient_str.split(','):
        email = extract_email_address(part)
        if email:
            emails.add(email)

    return emails

def scan_all_emails(source_dir, archive_dir):
    """Scan all .msg files and extract unique senders and recipients.

    Returns (senders_set, recipients_set) - both deduplicated and sorted.
    """
    source_path = Path(source_dir)
    msg_files = list(source_path.rglob('*.msg'))

    # Also scan archive directory if available
    if archive_dir:
        archive_path = Path(archive_dir) / "zipped"
        if archive_path.exists():
            archive_msg_files = list(archive_path.rglob('*.msg'))
            msg_files.extend(archive_msg_files)

    total = len(msg_files)
    print(f"Scanning {total} .msg files for unique email addresses...")

    senders = set()
    recipients = set()

    for i, msg_file in enumerate(msg_files, 1):
        try:
            msg = extract_msg.Message(str(msg_file))

            # Extract sender
            if msg.sender:
                sender_email = extract_email_address(str(msg.sender))
                if sender_email:
                    senders.add(sender_email)

            # Extract recipients from To field
            if msg.to:
                to_emails = parse_recipient_list(str(msg.to))
                recipients.update(to_emails)

            # Extract recipients from CC field
            if msg.cc:
                cc_emails = parse_recipient_list(str(msg.cc))
                recipients.update(cc_emails)

            if i % 50 == 0:
                print(f"  Processed {i}/{total}...")

        except Exception:
            # Silent failure - continue processing
            pass

    print(f"\n✓ Found {len(senders)} unique senders")
    print(f"✓ Found {len(recipients)} unique recipients\n")

    return sorted(senders), sorted(recipients)

def interactive_select_email(email_list, title):
    """Display numbered email list and let user select one.

    Returns selected email or None if user quits.
    """
    print(f"\n{title}")
    print("=" * 70)

    for i, email in enumerate(email_list, 1):
        print(f"{i:4d}. {email}")

    print("\nEnter 'q' to quit")

    while True:
        try:
            choice = input(f"\nSelect email (1-{len(email_list)}): ").strip().lower()

            if choice == 'q':
                return None

            idx = int(choice) - 1
            if 0 <= idx < len(email_list):
                return email_list[idx]
            else:
                print(f"Please enter a number between 1 and {len(email_list)}")

        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\n\nOperation cancelled.")
            return None

def interactive_mode():
    """Run interactive email selection flow.

    Returns (sender_email, recipient_email) or (None, None) if cancelled.
    """
    print("\n" + "=" * 70)
    print("INTERACTIVE EMAIL FILTER")
    print("=" * 70)
    print("\nScanning emails to build selection lists...\n")

    # Get archive directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')

    # Scan all emails
    senders, recipients = scan_all_emails(config.SOURCE_DIR, archive_dir)

    if not senders:
        print("❌ No senders found in .msg files")
        return None, None

    if not recipients:
        print("❌ No recipients found in .msg files")
        return None, None

    # Select sender
    sender = interactive_select_email(senders, "SELECT SENDER")
    if not sender:
        print("\nOperation cancelled.")
        return None, None

    print(f"\n✓ Selected sender: {sender}")

    # Select recipient
    recipient = interactive_select_email(recipients, "SELECT RECIPIENT")
    if not recipient:
        print("\nOperation cancelled.")
        return None, None

    print(f"✓ Selected recipient: {recipient}")

    # Confirm
    print("\n" + "=" * 70)
    print("CONFIRMATION")
    print("=" * 70)
    print(f"Sender:    {sender}")
    print(f"Recipient: {recipient}")
    confirm = input("\nProceed with filtering? (y/N): ").strip().lower()

    if confirm != 'y':
        print("\nOperation cancelled.")
        return None, None

    return sender, recipient

def filter_and_create_mbox(sender_filter, recipient_filter):
    """Filter emails and create filtered mbox file.

    Filters by:
    - Exact sender match (case-insensitive)
    - Recipient in To OR CC fields (case-insensitive)

    Creates filtered mbox at FILTERED_MBOX_OUTPUT.
    """
    source_dir = Path(config.SOURCE_DIR)
    mbox_path = Path(config.FILTERED_MBOX_OUTPUT)

    # Get archive directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')

    print(f"Scanning source: {source_dir}")

    # Find all .msg files
    msg_files = list(source_dir.rglob('*.msg'))

    # Also scan extracted archives if available
    if archive_dir:
        archive_path = Path(archive_dir) / "zipped"
        if archive_path.exists():
            print(f"Also scanning extracted archives: {archive_path}")
            archive_msg_files = list(archive_path.rglob('*.msg'))
            msg_files.extend(archive_msg_files)
            print(f"Found {len(archive_msg_files)} .msg files in archives")

    total = len(msg_files)
    print(f"\nFiltering {total} .msg files...")
    print(f"  Sender filter: {sender_filter}")
    print(f"  Recipient filter: {recipient_filter}\n")

    # Create .mbox directory
    mbox_path.mkdir(parents=True, exist_ok=True)
    mbox_file = mbox_path / "mbox"

    successful = 0
    failed = 0

    # Single pass: filter + write, avoids second parse and temp-file copies
    with open(mbox_file, 'w', encoding='utf-8') as mbox:
        for i, msg_file in enumerate(msg_files, 1):
            try:
                msg = extract_msg.Message(str(msg_file))

                # Check sender
                sender_email = extract_email_address(str(msg.sender)) if msg.sender else None
                if sender_email != sender_filter:
                    continue

                # Check recipient in To or CC
                recipient_match = False

                if msg.to:
                    to_emails = parse_recipient_list(str(msg.to))
                    if recipient_filter in to_emails:
                        recipient_match = True

                if not recipient_match and msg.cc:
                    cc_emails = parse_recipient_list(str(msg.cc))
                    if recipient_filter in cc_emails:
                        recipient_match = True

                if not recipient_match:
                    continue

                print(f"Processing match {successful + 1}: {msg_file.name}...", end=' ')

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
                sender_email_for_mbox = sender
                if '<' in sender and '>' in sender:
                    sender_email_for_mbox = sender.split('<')[1].split('>')[0]
                elif ' ' in sender:
                    sender_email_for_mbox = sender.split()[-1]

                # Write mbox entry with proper "From " separator
                mbox.write(f"From {sender_email_for_mbox} {date_str}\n")

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

                if i % 50 == 0:
                    print(f"  Scanned {i}/{total}...")

            except Exception as e:
                failed += 1
                print(f"✗ Error: {e}")

    if successful == 0:
        print("\n" + "=" * 70)
        print("❌ NO MATCHING EMAILS FOUND")
        print("=" * 70)
        print(f"\nNo emails found matching:")
        print(f"  Sender: {sender_filter}")
        print(f"  Recipient: {recipient_filter}")
        return

    # Create table_of_contents (Apple Mail metadata)
    toc_data = {
        'MessageCount': successful,
        'Version': 5
    }

    toc_file = mbox_path / "table_of_contents"
    with open(toc_file, 'wb') as f:
        plistlib.dump(toc_data, f)

    print(f"\n{'=' * 70}")
    print(f"FILTERING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Successfully converted: {successful}")
    print(f"Failed: {failed}")
    print(f"\nCreated filtered .mbox at: {mbox_path}")
    print(f"You can now open this in Apple Mail by double-clicking it.")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Filter emails by sender and recipient',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  %(prog)s

  # CLI mode
  %(prog)s --sender bob@company.com --recipient sarah@client.com

  # List all unique emails
  %(prog)s --list-emails
        """
    )

    parser.add_argument(
        '--sender',
        help='Filter by sender email address'
    )

    parser.add_argument(
        '--recipient',
        help='Filter by recipient email address (matches To or CC)'
    )

    parser.add_argument(
        '--list-emails',
        action='store_true',
        help='List all unique sender and recipient email addresses'
    )

    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_arguments()

    # Get archive directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')

    # List emails mode
    if args.list_emails:
        print("\n" + "=" * 70)
        print("LISTING ALL UNIQUE EMAIL ADDRESSES")
        print("=" * 70 + "\n")

        senders, recipients = scan_all_emails(config.SOURCE_DIR, archive_dir)

        print("\nUNIQUE SENDERS:")
        print("-" * 70)
        for email in senders:
            print(f"  {email}")

        print(f"\nUNIQUE RECIPIENTS:")
        print("-" * 70)
        for email in recipients:
            print(f"  {email}")

        return

    # CLI mode
    if args.sender and args.recipient:
        sender_filter = args.sender.lower()
        recipient_filter = args.recipient.lower()

        print("\n" + "=" * 70)
        print("CLI EMAIL FILTER")
        print("=" * 70)
        print(f"Sender:    {sender_filter}")
        print(f"Recipient: {recipient_filter}")

        filter_and_create_mbox(sender_filter, recipient_filter)
        return

    # CLI mode with missing arguments
    if args.sender or args.recipient:
        print("Error: Both --sender and --recipient are required for CLI mode")
        print("Use --help for usage information")
        sys.exit(1)

    # Interactive mode (default)
    sender, recipient = interactive_mode()

    if sender and recipient:
        filter_and_create_mbox(sender, recipient)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
