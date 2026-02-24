#!/usr/bin/env python3
"""
Generate complete inventory of ALL files in legal case folder
Includes file counts, sizes, types, and detailed listings
"""
import sys
from pathlib import Path
from collections import defaultdict
import csv
from datetime import datetime

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

def get_file_size_human(size_bytes):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_file_extension(filepath):
    """Get file extension - only the last extension."""
    path = Path(filepath)
    
    # Get only the last extension
    ext = path.suffix.lower()
    
    return ext if ext else '(no extension)'

def scan_directory(source, all_files, by_folder, by_extension, total_size, source_label=""):
    """Scan a directory and add files to the collections."""
    for filepath in source.rglob('*'):
        if filepath.is_file():
            try:
                stat = filepath.stat()
                size = stat.st_size
                total_size += size
                
                rel_path = filepath.relative_to(source)
                folder = str(rel_path.parent) if rel_path.parent != Path('.') else 'Root'
                
                # Add source label if this is from extracted archives
                if source_label:
                    folder = f"{source_label}/{folder}"
                
                ext = get_file_extension(filepath)
                
                file_info = {
                    'name': filepath.name,
                    'folder': folder,
                    'path': str(rel_path),
                    'extension': ext,
                    'size': size,
                    'size_human': get_file_size_human(size),
                    'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                }
                
                all_files.append(file_info)
                by_folder[folder].append(file_info)
                by_extension[ext].append(file_info)
                
            except Exception as e:
                print(f"Error processing {filepath.name}: {e}")
    
    return total_size

def generate_inventory(source_dir, output_dir, archive_dir=None):
    """Generate complete file inventory including extracted archives."""
    
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    
    print(f"Scanning {source}...")
    if archive_dir:
        print(f"Also scanning extracted archives: {archive_dir}")
    print("This may take a moment...\n")
    
    # Collect all files
    all_files = []
    by_folder = defaultdict(list)
    by_extension = defaultdict(list)
    
    total_size = 0
    
    # Scan main source directory
    total_size = scan_directory(source, all_files, by_folder, by_extension, total_size)
    
    # Scan extracted archives if available
    if archive_dir:
        archive_path = Path(archive_dir)
        zipped_dir = archive_path / "zipped"
        if zipped_dir.exists():
            print(f"Scanning extracted archives...")
            total_size = scan_directory(zipped_dir, all_files, by_folder, by_extension, total_size, "zipped")
    
    print(f"Found {len(all_files)} files")
    print(f"Total size: {get_file_size_human(total_size)}\n")
    
    # Generate reports
    generate_summary_report(all_files, by_folder, by_extension, total_size, output)
    generate_detailed_csv(all_files, output)
    generate_folder_report(by_folder, output)
    generate_extension_report(by_extension, output)
    
    print("\n" + "=" * 70)
    print("✅ Complete inventory generated!")
    print("=" * 70)

def generate_summary_report(all_files, by_folder, by_extension, total_size, output_dir):
    """Generate summary markdown report."""
    
    output_file = output_dir / "complete_inventory_summary.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Complete Legal Case File Inventory\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Total Files:** {len(all_files):,}\n\n")
        f.write("---\n\n")
        
        # Sort extensions by file count
        sorted_exts = sorted(by_extension.items(), key=lambda x: len(x[1]), reverse=True)
        
        for ext, files in sorted_exts:
            # Header for this extension type
            f.write(f"## {ext}\n\n")
            
            # Folder-by-folder breakdown
            sorted_folders = sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)
            
            for folder, folder_files in sorted_folders:
                # Count files of this extension type in this folder
                folder_count = sum(1 for f in folder_files if f['extension'] == ext)
                if folder_count > 0:
                    f.write(f"- {folder}: {folder_count}\n")
            
            # Total
            f.write(f"\n**Total: {len(files)} files**\n\n")
            f.write("---\n\n")
    
    print(f"\n✓ Summary report: {output_file}")

def generate_detailed_csv(all_files, output_dir):
    """Generate detailed CSV with all files."""
    
    output_file = output_dir / "complete_inventory_detailed.csv"
    
    # Sort by folder then name
    sorted_files = sorted(all_files, key=lambda x: (x['folder'], x['name']))
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Folder', 'Filename', 'Extension', 'Size', 'Size (Bytes)', 'Modified', 'Path'])
        
        for file_info in sorted_files:
            writer.writerow([
                file_info['folder'],
                file_info['name'],
                file_info['extension'],
                file_info['size_human'],
                file_info['size'],
                file_info['modified'],
                file_info['path']
            ])
    
    print(f"✓ Detailed CSV: {output_file}")

def generate_folder_report(by_folder, output_dir):
    """Generate folder-by-folder breakdown."""
    
    output_file = output_dir / "inventory_by_folder.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# File Inventory by Folder\n\n")
        
        sorted_folders = sorted(by_folder.items(), key=lambda x: len(x[1]), reverse=True)
        
        for folder, files in sorted_folders:
            folder_size = sum(f['size'] for f in files)
            
            f.write(f"## 📂 {folder}\n\n")
            f.write(f"**Files:** {len(files)} | **Size:** {get_file_size_human(folder_size)}\n\n")
            
            # Count by extension in this folder
            ext_counts = defaultdict(int)
            for file_info in files:
                ext_counts[file_info['extension']] += 1
            
            f.write("**File types:** ")
            f.write(", ".join(f"{count} {ext}" for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)))
            f.write("\n\n")
            
            # List files (sorted by size)
            sorted_files = sorted(files, key=lambda x: x['size'], reverse=True)
            for file_info in sorted_files[:10]:  # Top 10 in each folder
                f.write(f"- {file_info['name']} ({file_info['size_human']})\n")
            
            if len(files) > 10:
                f.write(f"- ... and {len(files) - 10} more files\n")
            
            f.write("\n---\n\n")
    
    print(f"✓ Folder report: {output_file}")

def generate_extension_report(by_extension, output_dir):
    """Generate report organized by file extension."""
    
    output_file = output_dir / "inventory_by_extension.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# File Inventory by Extension\n\n")
        
        sorted_ext = sorted(by_extension.items(), key=lambda x: len(x[1]), reverse=True)
        
        for ext, files in sorted_ext:
            ext_size = sum(f['size'] for f in files)
            
            f.write(f"## {ext}\n\n")
            f.write(f"**Count:** {len(files)} files | **Total Size:** {get_file_size_human(ext_size)}\n\n")
            
            # Count by folder
            folder_counts = defaultdict(int)
            for file_info in files:
                folder_counts[file_info['folder']] += 1
            
            f.write("**Distribution:** ")
            f.write(", ".join(f"{folder} ({count})" for folder, count in sorted(folder_counts.items(), key=lambda x: x[1], reverse=True)[:5]))
            f.write("\n\n")
            
            # Sample files
            if len(files) <= 20:
                for file_info in sorted(files, key=lambda x: x['name']):
                    f.write(f"- {file_info['folder']}/{file_info['name']}\n")
            else:
                for file_info in sorted(files, key=lambda x: x['name'])[:10]:
                    f.write(f"- {file_info['folder']}/{file_info['name']}\n")
                f.write(f"- ... and {len(files) - 10} more files\n")
            
            f.write("\n---\n\n")
    
    print(f"✓ Extension report: {output_file}")

if __name__ == "__main__":
    import os
    
    source_dir = config.SOURCE_DIR
    output_dir = Path(config.OUTPUT_DIR) / "inventory"
    
    # Check for extracted archives directory from environment
    archive_dir = os.environ.get('LEGAL_CONVERTER_ARCHIVE_DIR')
    
    generate_inventory(source_dir, output_dir, archive_dir)
    
    print(f"\nAll reports saved to: {output_dir}")
